# -*- coding: utf-8 -*-
"""专家并行可靠测量：stream 逐 token 自计时，不依赖 server 的 tps 字段。
固定生成 token 数，测稳态 decode (跳过前 30 token)，多轮交叉，输出均值/sd/t 检验。
"""
import subprocess, time, urllib.request, json, statistics, os, math
from pathlib import Path
LOG=Path('D:/Brain/_cleanup_20261118/ep_reliable.log')
def log(m):
    line=f'{time.strftime("%H:%M:%S")} {m}'
    print(line,flush=True)
    with open(LOG,'a',encoding='utf-8') as f:f.write(line+'\n')

EXE='D:/llama-gdn-src/build-gdn/bin/llama-server.exe'
MODEL='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT=8081
FILLER="混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。"*500
N_GENERATE=160   # 生成 token 数
SKIP=30          # 跳过前 30 token (MTP draft 启动期)

def wait_health(sec=180):
    for i in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2).status==200:return i+1
        except:pass
        time.sleep(1)
    return None

def start(group=None):
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(4)
    args=[EXE,'-m',MODEL,'-ngl','99','--n-cpu-moe','40','-c','98304','-np','1','-fa','on',
          '--cache-type-k','q8_0','--cache-type-v','q4_0','-t','8','-b','4096','-ub','2048','-lm','none',
          '--mmproj',MMPROJ,'--mmproj-offload','--moe-cache-mib','1350','--moe-cache-cpu-share','1.0',
          '--port',str(PORT),'--host','127.0.0.1','--spec-type','draft-mtp','--spec-draft-n-max','5',
          '--spec-draft-p-min','0.8','--ctx-checkpoints','2','--cache-ram','0','--temp','0.7','--top-p','0.95']
    env=os.environ.copy()
    if group is not None:
        env['GGML_MMID_EXPERT_PARALLEL']='1'
        env['GGML_MMID_EP_GROUP']=str(group)
    lf=open(f'D:/Brain/_cleanup_20261118/eprel_{"base" if group is None else "g"+str(group)}_srv.log','w')
    p=subprocess.Popen(args,stdout=lf,stderr=subprocess.STDOUT,env=env)
    sec=wait_health()
    if not sec:p.kill();lf.close();return None
    # 加载 + 填 cache（cache 未满时 share_q=0，必须填满）
    for _ in range(4):
        b={'model':MODEL,'prompt':FILLER[:16000],'n_predict':128,'ignore_eos':True,
           'temperature':0.7,'stream':False,'cache_prompt':False}
        try:
            req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(b).encode(),
                                       headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req,timeout=600).read()
        except Exception as e:log(f'  warm ERR {type(e).__name__}')
    return p,lf

def measure_one():
    """stream 逐 token 计时，返回稳态 tps 和生成 token 数"""
    body={'model':MODEL,'prompt':FILLER[:20000],'n_predict':N_GENERATE,'ignore_eos':True,
          'temperature':0.7,'stream':True,'cache_prompt':True}
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
    if len(times)<=SKIP+5:return None,len(times)
    # 稳态：SKIP..end
    dur=times[-1]-times[SKIP]
    tps=(len(times)-1-SKIP)/dur
    return tps,len(times)

def bench(label,group,runs=8,warm=3):
    r=start(group)
    if not r:return []
    p,lf=r
    out=[]
    for k in range(-warm,runs):
        try:
            tps,ntok=measure_one()
            tag='warm' if k<0 else f'r{k}'
            if tps is None:
                log(f'  {label:7} {tag:5} FAIL ntok={ntok}');continue
            log(f'  {label:7} {tag:5} {tps:.2f} t/s (ntok={ntok})')
            if k>=0:out.append(tps)
        except Exception as e:
            log(f'  {label:7} ERR {type(e).__name__}')
    p.terminate()
    try:p.wait(timeout=20)
    except:p.kill()
    lf.close();time.sleep(4)
    if out:
        log(f'  {label:7} MED={statistics.median(out):.2f} MEAN={statistics.mean(out):.2f} SD={statistics.stdev(out):.2f} n={len(out)}')
    return out

CONFIGS=[('base',None),('g1',1),('g2',2),('g4',4)]
results={c[0]:[] for c in CONFIGS}
for rnd in (1,2):
    order=CONFIGS if rnd==1 else list(reversed(CONFIGS))
    log(f'=== ROUND {rnd} ===')
    for label,group in order:
        v=bench(f'r{rnd}_{label}',group)
        results[label].extend(v)

log('=== FINAL STATS ===')
base=results['base']
for label,_ in CONFIGS:
    v=results[label]
    if not v or not base:continue
    m=statistics.mean(v);mb=statistics.mean(base)
    se=math.sqrt(statistics.stdev(v)**2/len(v)+statistics.stdev(base)**2/len(base))
    t=(m-mb)/se if se>0 else 0
    log(f'  {label}: n={len(v)} mean={m:.2f} sd={statistics.stdev(v):.2f} | vs base {mb:.2f} diff={m-mb:+.2f} t={t:.2f}')
log('=== DONE ===')
