# -*- coding: utf-8 -*-
"""长 prompt 单发确认：20K prompt + 64 token，每变体重启 server，各 N 次。
用于短 prompt A/B 赢家的端到端验证（防"decode t/s 误导性指标"）。

用法：python confirm_ab.py nmax "--spec-draft-n-max 3|--spec-draft-n-max 5" 2
"""
import subprocess, time, urllib.request, json, statistics, sys, random, string
from pathlib import Path

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
MODEL = 'D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ = 'D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT = 8081
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500
BASE = ['-m', MODEL, '-ngl', '99', '--n-cpu-moe', '40', '-c', '98304', '-np', '1', '-fa', 'on',
        '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0', '-t', '8', '-b', '4096', '-ub', '2048', '-lm', 'none',
        '--mmproj', MMPROJ, '--mmproj-offload', '--moe-cache-mib', '1350', '--moe-cache-cpu-share', '1.0',
        '--port', str(PORT), '--host', '127.0.0.1', '--spec-type', 'draft-mtp',
        '--spec-draft-n-max', '5', '--spec-draft-p-min', '0.8', '--ctx-checkpoints', '2',
        '--cache-ram', '0', '--temp', '0.7', '--top-p', '0.95']


def log(m, LOG):
    s = f'{time.strftime("%H:%M:%S")} {m}'
    print(s, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(s+'\n')


def health():
    for _ in range(120):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=1).status==200: return True
        except Exception: pass
        time.sleep(1)
    return False


def apply(args, extra):
    toks = extra.split(); i=0
    while i < len(toks):
        t=toks[i]
        if t.startswith('!'):
            if t[1:] in args:
                j=args.index(t[1:]); del args[j:j+2]
            i+=1
        elif t.startswith('-') and i+1<len(toks):
            if t in args: args[args.index(t)+1]=toks[i+1]
            else: args.extend([t,toks[i+1]])
            i+=2
        else: i+=1
    return args


def run_variant(label, extra, runs, LOG):
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True); time.sleep(2)
    args=apply(list(BASE),extra)
    lf=open(f'D:/Brain/_cleanup_20261118/conf_{label}_srv.log','w')
    p=subprocess.Popen([EXE]+args,stdout=lf,stderr=subprocess.STDOUT)
    if not health():
        log(f'  {label}: START FAIL',LOG);p.kill();lf.close();return []
    tps=[];e2e=[];ttft=[]
    for k in range(runs):
        tag=''.join(random.choice(string.ascii_lowercase) for _ in range(48))
        b={'model':MODEL,'prompt':tag+' '+FILLER[:20000],'n_predict':64,'ignore_eos':True,
           'temperature':0.7,'stream':False,'cache_prompt':False}
        req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(b).encode(),
                                   headers={'Content-Type':'application/json'})
        t0=time.perf_counter()
        try:
            r=json.loads(urllib.request.urlopen(req,timeout=300).read())
            dt=time.perf_counter()-t0
            tm=r['timings']
            t=tm['predicted_per_second']
            tps.append(t);e2e.append(dt)
            log(f'  {label} r{k}: {t:.2f} t/s  e2e={dt:.1f}s  prefill={tm.get("prompt_per_second",0):.0f} t/s',LOG)
        except Exception as e:
            log(f'  {label} r{k} ERR {type(e).__name__}',LOG)
    p.terminate()
    try:p.wait(timeout=15)
    except:p.kill()
    lf.close();time.sleep(2)
    return tps,e2e


def main():
    label=sys.argv[1];variants=sys.argv[2].split('|')
    runs=int(sys.argv[3]) if len(sys.argv)>3 else 2
    LOG=f'D:/Brain/_cleanup_20261118/confirm_{label}.log'
    log(f'=== confirm {label} runs={runs} variants={variants} ===',LOG)
    res={}
    for v in variants:
        r=run_variant(f'{label}_{variants.index(v)}',v,runs,LOG)
        res[v]=r
    for v,r in res.items():
        if r and r[0]:
            log(f'RESULT {v[:55]}: tps_med={statistics.median(r[0]):.2f} e2e_med={statistics.median(r[1]):.1f}s n={len(r[0])}',LOG)
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True)
    log('=== DONE ===',LOG)


if __name__=='__main__':main()
