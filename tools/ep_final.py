# -*- coding: utf-8 -*-
"""最终可靠测量：关闭 MTP，stream 每 chunk 恰一 token，自计时。
验证 ntok 严格固定；多轮交叉；只测纯 decode。
"""
import subprocess, time, urllib.request, json, statistics, os, math
from pathlib import Path
LOG=Path('D:/Brain/_cleanup_20261118/ep_final.log')
def log(m):
    line=f'{time.strftime("%H:%M:%S")} {m}'
    print(line,flush=True)
    with open(LOG,'a',encoding='utf-8') as f:f.write(line+'\n')

EXE='D:/llama-gdn-src/build-gdn/bin/llama-server.exe'
MODEL='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT=8081
N=200
SKIP=20

def wait_health(sec=180):
    for i in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2).status==200:return i+1
        except:pass
        time.sleep(1)
    return None

def start(group=None):
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(4)
    # 关键：不指定 --spec-type → 无 MTP，stream 每 chunk 恰一 token
    args=[EXE,'-m',MODEL,'-ngl','99','--n-cpu-moe','40','-c','98304','-np','1','-fa','on',
          '--cache-type-k','q8_0','--cache-type-v','q4_0','-t','8','-b','4096','-ub','2048','-lm','none',
          '--mmproj',MMPROJ,'--mmproj-offload','--moe-cache-mib','1350','--moe-cache-cpu-share','1.0',
          '--port',str(PORT),'--host','127.0.0.1','--ctx-checkpoints','2','--cache-ram','0',
          '--temp','0.7','--top-p','0.95']
    env=os.environ.copy()
    if group is not None:
        env['GGML_MMID_EXPERT_PARALLEL']='1';env['GGML_MMID_EP_GROUP']=str(group)
    tag='base' if group is None else f'g{group}'
    lf=open(f'D:/Brain/_cleanup_20261118/epfin_{tag}_srv.log','w')
    p=subprocess.Popen(args,stdout=lf,stderr=subprocess.STDOUT,env=env)
    sec=wait_health()
    if not sec:p.kill();lf.close();return None
    # 加载 + 填满 cache（share_q 生效前提）
    for _ in range(5):
        b={'model':MODEL,'prompt':'你好，请介绍一下你自己。'*20,'n_predict':N,'ignore_eos':True,
           'temperature':0.7,'stream':False,'cache_prompt':False}
        try:
            req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(b).encode(),
                                       headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req,timeout=600).read()
        except Exception as e:log(f'  warm ERR {type(e).__name__}')
    return p,lf

def measure_one():
    body={'model':MODEL,'prompt':'你好，请写一篇关于人工智能的长文章。','n_predict':N,
          'ignore_eos':True,'temperature':0.7,'stream':True,'cache_prompt':False}
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(body).encode(),
                               headers={'Content-Type':'application/json'})
    times=[]
    with urllib.request.urlopen(req,timeout=900) as r:
        for raw in r:
            s0=raw.decode('utf-8',errors='replace').strip()
            if not s0.startswith('data:'):continue
            pl=s0[5:].strip()
            if pl=='[DONE]':break
            try:
                j=json.loads(pl)
                if j.get('content'):times.append(time.perf_counter())
            except:pass
    if len(times)<N-2:return None,len(times)
    dur=times[N-1]-times[SKIP]
    return (N-1-SKIP)/dur,len(times)

def bench(label,group,runs=10,warm=2):
    r=start(group)
    if not r:return []
    p,lf=r
    out=[]
    for k in range(-warm,runs):
        try:
            tps,ntok=measure_one()
            if tps is None:
                log(f'  {label:7} warm{runs if k<0 else k} FAIL ntok={ntok}');continue
            tag='w' if k<0 else f'r{k}'
            log(f'  {label:7} {tag:3} {tps:.2f} t/s (ntok={ntok})')
            if k>=0:out.append(tps)
        except Exception as e:
            log(f'  {label:7} ERR {type(e).__name__}')
    p.terminate()
    try:p.wait(timeout=20)
    except:p.kill()
    lf.close();time.sleep(4)
    if out:log(f'  {label:7} MED={statistics.median(out):.2f} MEAN={statistics.mean(out):.2f} SD={statistics.stdev(out):.2f} n={len(out)}')
    return out

CONFIGS=[('base',None),('g1',1),('g2',2),('g4',4)]
results={c[0]:[] for c in CONFIGS}
for rnd in (1,2):
    order=CONFIGS if rnd==1 else list(reversed(CONFIGS))
    log(f'=== ROUND {rnd} (no MTP) ===')
    for label,group in order:
        results[label].extend(bench(f'r{rnd}_{label}',group))

log('=== FINAL ===')
base=results['base']
mb=statistics.mean(base) if base else 0
for label,_ in CONFIGS:
    v=results[label]
    if not v:continue
    m=statistics.mean(v)
    se=math.sqrt(statistics.stdev(v)**2/len(v)+(statistics.stdev(base)**2/len(base) if base else 0))
    t=(m-mb)/se if se>0 else 0
    log(f'  {label}: n={len(v)} mean={m:.2f} sd={statistics.stdev(v):.2f} diff={m-mb:+.2f} t={t:.2f}')
log('=== DONE ===')
