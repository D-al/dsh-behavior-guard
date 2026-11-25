# -*- coding: utf-8 -*-
"""严格配对 A/B：为达到 95% 置信度。

设计：
- 每轮 A、B 各一次，ABBA 顺序抵消线性热漂移
- 每个请求都重启 server（消除变体间状态污染 + prefill 缓存差异）
- 同长 prompt（固定 seed 的随机前缀，等长）
- 记录 prefill t/s 作为协变量监控外部干扰
- n>=10 对，配对 t 检验 + 95% CI

用法：python paired_ab.py <label> "<A>|<B>" [pairs]
例：python paired_ab.py nmax_strict "--spec-draft-n-max 3|--spec-draft-n-max 5" 10
"""
import subprocess, time, urllib.request, json, statistics, math, sys, random
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
        '--spec-draft-n-max', '3', '--spec-draft-p-min', '0.8', '--ctx-checkpoints', '2',
        '--cache-ram', '0', '--temp', '0.7', '--top-p', '0.95']
# t 分布 95% 双尾临界值
T95 = {1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,9:2.262,
       10:2.228,11:2.201,12:2.179,13:2.160,14:2.145,15:2.131,16:2.120,17:2.110,
       18:2.101,19:2.093,20:2.086}


def log(m, LOG):
    s = f'{time.strftime("%H:%M:%S")} {m}'
    print(s, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(s+'\n')


def health(timeout=90):
    for _ in range(timeout):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=1).status==200:return True
        except Exception:pass
        time.sleep(1)
    return False


def apply(args, extra):
    toks=extra.split();i=0
    while i<len(toks):
        t=toks[i]
        if t.startswith('!'):
            if t[1:] in args:
                j=args.index(t[1:]);del args[j:j+2]
            i+=1
        elif t.startswith('-') and i+1<len(toks):
            if t in args:args[args.index(t)+1]=toks[i+1]
            else:args.extend([t,toks[i+1]])
            i+=2
        else:i+=1
    return args


def one_request(extra, prompt, idx, LOG):
    """每次请求都重启 server，保证独立同分布。"""
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(1)
    args=apply(list(BASE),extra)
    lf=open(f'D:/Brain/_cleanup_20261118/pa_{idx}_srv.log','w')
    p=subprocess.Popen([EXE]+args,stdout=lf,stderr=subprocess.STDOUT)
    if not health():
        log(f'  req{idx}: START FAIL',LOG);p.kill();lf.close();return None
    b={'model':MODEL,'prompt':prompt,'n_predict':96,'ignore_eos':True,
       'temperature':0.7,'seed':12345,'stream':False,'cache_prompt':False}
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(b).encode(),
                               headers={'Content-Type':'application/json'})
    t0=time.perf_counter()
    try:
        r=json.loads(urllib.request.urlopen(req,timeout=300).read())
        dt=time.perf_counter()-t0
        tm=r['timings']
        res={'e2e':dt,'tps':tm['predicted_per_second'],
             'prefill':tm.get('prompt_per_second',0),
             'acc':tm.get('draft_n_accepted',0),'draft':tm.get('draft_n',0)}
        log(f'  req{idx}: e2e={dt:.2f}s tps={res["tps"]:.2f} pf={res["prefill"]:.0f} acc={res["acc"]}/{res["draft"]}',LOG)
    except Exception as e:
        log(f'  req{idx}: ERR {type(e).__name__}',LOG);res=None
    p.terminate()
    try:p.wait(timeout=15)
    except:p.kill()
    lf.close();time.sleep(1)
    return res


def paired_stats(diffs, LOG):
    n=len(diffs);m=statistics.mean(diffs)
    sd=statistics.stdev(diffs) if n>1 else 0
    se=sd/math.sqrt(n) if n>0 else 0
    t=T95.get(n-1,1.96)
    lo,hi=m-t*se,m+t*se
    log(f'  DIFF (A-B): n={n} mean={m:.3f} sd={sd:.3f} se={se:.3f} t95={t}',LOG)
    log(f'  95%CI = [{lo:.3f}, {hi:.3f}]',LOG)
    if lo>0: log(f'  ==> A 显著大于 B (95%): YES',LOG)
    elif hi<0: log(f'  ==> B 显著大于 A (95%): YES',LOG)
    else: log(f'  ==> 差异不显著 (95%): CI 跨 0',LOG)
    return lo,hi


def main():
    label=sys.argv[1];A,B=sys.argv[2].split('|')
    pairs=int(sys.argv[3]) if len(sys.argv)>3 else 10
    LOG=f'D:/Brain/_cleanup_20261118/paired_{label}.log'
    log(f'=== PAIRED {label} pairs={pairs} ===',LOG)
    log(f'  A={A}',LOG);log(f'  B={B}',LOG)
    rnd=random.Random(42)  # 固定 seed，两变体用同一组 prompt
    prompts=[''.join(rnd.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(48))+' '+FILLER[:20000]
             for _ in range(pairs)]
    resA=[];resB=[]
    for i in range(pairs):
        # ABBA 顺序：偶数轮 A先B后，奇数轮 B先A后
        order=[(A,resA),(B,resB)] if i%2==0 else [(B,resB),(A,resA)]
        log(f'--- pair {i} ---',LOG)
        for extra,bucket in order:
            r=one_request(extra,prompts[i],f'{label}_{i}_{"A" if bucket is resA else "B"}',LOG)
            if r: bucket.append(r)
    log('=== STATS ===',LOG)
    for key in ['e2e','tps','prefill']:
        da=[x[key] for x in resA];db=[x[key] for x in resB]
        if len(da)==len(db) and da:
            log(f'-- {key}: A_med={statistics.median(da):.2f} B_med={statistics.median(db):.2f}',LOG)
            paired_stats([a-b for a,b in zip(da,db)],LOG)
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True)
    log('=== DONE ===',LOG)


if __name__=='__main__':main()
