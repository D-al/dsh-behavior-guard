# -*- coding: utf-8 -*-
"""专家并行速度 A/B：stream=False 稳健版，交叉顺序，含正确性。"""
import subprocess, time, urllib.request, json, statistics, os
from pathlib import Path
LOG=Path('D:/Brain/_cleanup_20261118/ep_group.log')
def log(m):
    line=f'{time.strftime("%H:%M:%S")} {m}'
    print(line,flush=True)
    with open(LOG,'a',encoding='utf-8') as f:f.write(line+'\n')

EXE='D:/llama-gdn-src/build-gdn/bin/llama-server.exe'
MODEL='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT=8081
FILLER="混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。"*500

def wait_health(sec=120):
    for i in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2).status==200:return i+1
        except:pass
        time.sleep(1)
    return None
def post(b,timeout=600):
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(b).encode(),
                               headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req,timeout=timeout).read())
def start(enable, group=1):
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(3)
    args=[EXE,'-m',MODEL,'-ngl','99','--n-cpu-moe','40','-c','98304','-np','1','-fa','on',
          '--cache-type-k','q8_0','--cache-type-v','q4_0','-t','8','-b','4096','-ub','2048','-lm','none',
          '--mmproj',MMPROJ,'--mmproj-offload','--moe-cache-mib','1350','--moe-cache-cpu-share','1.0',
          '--port',str(PORT),'--host','127.0.0.1','--spec-type','draft-mtp','--spec-draft-n-max','5',
          '--spec-draft-p-min','0.8','--ctx-checkpoints','2','--cache-ram','0','--temp','0.7','--top-p','0.95']
    env=os.environ.copy()
    if enable:
        env['GGML_MMID_EXPERT_PARALLEL']='1'
        env['GGML_MMID_EP_GROUP']=str(group)
    lf=open(f'D:/Brain/_cleanup_20261118/eps_{"ON" if enable else "OFF"}_srv.log','w')
    p=subprocess.Popen(args,stdout=lf,stderr=subprocess.STDOUT,env=env)
    sec=wait_health()
    if not sec:p.kill();lf.close();return None
    for _ in range(2):
        try:
            post({'model':MODEL,'prompt':FILLER[:14000],'n_predict':128,'ignore_eos':True,
                  'temperature':0.7,'stream':False,'cache_prompt':False})
        except Exception as e:log(f'  warm ERR {e}')
    return p,lf,sec

def bench(label,enable,runs=3,n=200,group=1):
    r=start(enable,group)
    if not r:return []
    p,lf,sec=r
    tps_list=[];e2e=[]
    for k in range(runs):
        b={'model':MODEL,'prompt':FILLER[:20000],'n_predict':n,'ignore_eos':True,
           'temperature':0.7,'stream':False,'cache_prompt':False}
        t0=time.perf_counter()
        try:
            resp=post(b,timeout=600)
            dt=time.perf_counter()-t0
            tm=resp['timings']
            tps=tm.get('predicted_per_second',0)
            tps_list.append(tps);e2e.append(dt)
            log(f'  {label:8} r{k}: {dt:.1f}s total, {tps:.2f} tps, {tm.get("n_predict",0)} tok')
        except Exception as e:
            log(f'  {label:8} r{k} ERR {type(e).__name__}');continue
    p.terminate()
    try:p.wait(timeout=20)
    except:p.kill()
    lf.close();time.sleep(3)
    if tps_list:
        log(f'  {label:8} MEDIAN tps={statistics.median(tps_list):.2f} (sd {statistics.stdev(tps_list):.2f}) | e2e={statistics.median(e2e):.1f}s')
    return tps_list

log('=== GROUP SCAN ===')
configs=[('base',False,0),('g1',True,1),('g2',True,2),('g4',True,4)]
results={}
# 正反两轮
for rnd in (1,2):
    order=configs if rnd==1 else list(reversed(configs))
    log(f'--- Round {rnd} ---')
    for label,enable,grp in order:
        v=bench(f'r{rnd}_{label}',enable,group=grp)
        if v:results.setdefault(label,[]).extend(v)
log('=== SUMMARY (pooled) ===')
for label,v in results.items():
    log(f'  {label}: n={len(v)} median={statistics.median(v):.2f} mean={statistics.mean(v):.2f} sd={statistics.stdev(v):.2f}')
log('=== DONE ===')
