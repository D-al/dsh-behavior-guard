# -*- coding: utf-8 -*-
"""专家并行补丁 A/B：同一二进制，只靠 env GGML_MMID_EXPERT_PARALLEL 切换。
第一步：正确性验证（temperature=0 确定性输出对比）
第二步：速度 A/B（交叉顺序）
"""
import subprocess, time, urllib.request, json, statistics, os, sys
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/expert_parallel.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

EXE = 'D:/llama-gdn-src/build-gdn/bin/llama-server.exe'
PRESET = 'D:/Brain/_cleanup_20261118/preset_A_40_1350.ini'
PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500

def wait_health(seconds=240):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def post(body, timeout=1800):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def start_server(enable_parallel):
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True)
    time.sleep(3)
    MODEL_PATH='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
    MMPROJ='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
    args=[EXE,'-m',MODEL_PATH,'-ngl','99','--n-cpu-moe','40',
          '-c','98304','-np','1','-fa','on','--cache-type-k','q8_0','--cache-type-v','q4_0',
          '-t','8','-b','4096','-ub','2048','-lm','none',
          '--mmproj',MMPROJ,'--mmproj-offload',
          '--moe-cache-mib','1350','--moe-cache-cpu-share','1.0',
          '--port',str(PORT),'--host','127.0.0.1',
          '--spec-type','draft-mtp','--spec-draft-n-max','5','--spec-draft-p-min','0.8',
          '--ctx-checkpoints','2','--cache-ram','0',
          '--temp','0.7','--top-p','0.95']
    env=os.environ.copy()
    if enable_parallel: env['GGML_MMID_EXPERT_PARALLEL']='1'
    logf=open(f'D:/Brain/_cleanup_20261118/ep_{"on" if enable_parallel else "off"}_srv.log','w')
    p=subprocess.Popen(args,stdout=logf,stderr=subprocess.STDOUT,env=env)
    sec=wait_health()
    log(f'  health={sec}s' if sec else '  TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); return None
    # 加载
    try:
        post({'model':MODEL,'prompt':'你好','n_predict':8,'ignore_eos':True,'stream':False})
    except Exception as e:
        log(f'  LOAD ERR {e}'); p.terminate(); logf.close(); return None
    return p, logf

# ============ 第一步：正确性对比 ============
log('=== PHASE 1: CORRECTNESS (temp=0 deterministic) ===')
PROMPTS = [
    "请解释混合专家模型的工作原理，用中文回答。",
    "1+1等于几？只回答数字。",
    "把这句话翻译成英文：今天天气很好，我们去公园散步。",
    "列出三个常见的编程语言及其主要用途。",
]
outputs={}
for enable in (False, True):
    tag='PARALLEL_ON' if enable else 'PARALLEL_OFF'
    log(f'--- {tag} ---')
    r=start_server(enable)
    if not r: continue
    p,lf=r
    outs=[]
    for i,prompt in enumerate(PROMPTS):
        try:
            resp=post({'model':MODEL,'prompt':prompt,'n_predict':64,'temperature':0.0,
                       'ignore_eos':True,'stream':False,'cache_prompt':False})
            outs.append(resp['content'].strip())
            log(f'  q{i}: {outs[-1][:80]}')
        except Exception as e:
            log(f'  q{i} ERR {e}'); outs.append('ERR')
    outputs[tag]=outs
    p.terminate()
    try:p.wait(timeout=30)
    except:p.kill()
    lf.close(); time.sleep(3)

if len(outputs)==2:
    same=sum(1 for a,b in zip(outputs['PARALLEL_OFF'],outputs['PARALLEL_ON']) if a==b)
    log(f'CORRECTNESS: {same}/{len(PROMPTS)} identical')
    if same < len(PROMPTS):
        log('!! WARNING: outputs differ - investigate before speed test')
        for i,(a,b) in enumerate(zip(outputs['PARALLEL_OFF'],outputs['PARALLEL_ON'])):
            if a!=b: log(f'  q{i} OFF={a[:100]} | ON={b[:100]}')

# ============ 第二步：速度 A/B 交叉 ============
log('=== PHASE 2: SPEED A/B (crossover) ===')
def decode_runs(label, enable, runs=5, warm=2, n=128):
    r=start_server(enable)
    if not r: return []
    p,lf=r
    out=[]
    for k in range(-warm,runs):
        times=[];t0=time.perf_counter()
        body={'model':MODEL,'prompt':FILLER[:20000],'n_predict':n+32,
              'ignore_eos':True,'temperature':0.7,'stream':True,'cache_prompt':True}
        req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',
             data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=1800) as rsp:
                for raw in rsp:
                    s0=raw.decode('utf-8',errors='replace').strip()
                    if not s0.startswith('data:'):continue
                    pl=s0[5:].strip()
                    if pl=='[DONE]':break
                    try:
                        if json.loads(pl).get('content'):times.append(time.perf_counter()-t0)
                    except:pass
                    if len(times)>=n:break
        except Exception as e:
            log(f'  {label} ERR {type(e).__name__}');continue
        if len(times)<n:continue
        tps=(n-1)/(times[n-1]-times[0])
        tag='warm' if k<0 else f'r{k}'
        log(f'  {label:10} {tag:5} {tps:.2f} t/s')
        if k>=0:out.append(tps)
    if out:log(f'  {label:10} MEDIAN {statistics.median(out):.3f} mean {statistics.mean(out):.2f} sd {statistics.stdev(out):.3f}')
    p.terminate()
    try:p.wait(timeout=30)
    except:p.kill()
    lf.close();time.sleep(3)
    return out

# 第一轮：off -> on
log('--- Round 1: OFF then ON ---')
r1_off=decode_runs('r1_OFF',False)
r1_on=decode_runs('r1_ON',True)
# 第二轮：on -> off (交叉)
log('--- Round 2: ON then OFF ---')
r2_on=decode_runs('r2_ON',True)
r2_off=decode_runs('r2_OFF',False)

log('=== SUMMARY ===')
for name,vals in [('r1_off',r1_off),('r1_on',r1_on),('r2_on',r2_on),('r2_off',r2_off)]:
    if vals:log(f'  {name}: median={statistics.median(vals):.2f} mean={statistics.mean(vals):.2f}')
log('=== EXPERT PARALLEL DONE ===')
