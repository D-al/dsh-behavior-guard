# -*- coding: utf-8 -*-
"""最小化专家并行验证：stream=False，短 prompt，逐步定位死锁/正确性问题。"""
import subprocess, time, urllib.request, json, os
from pathlib import Path
LOG = Path('D:/Brain/_cleanup_20261118/ep_min.log')
def log(m):
    line=f'{time.strftime("%H:%M:%S")} {m}'
    print(line,flush=True)
    with open(LOG,'a',encoding='utf-8') as f:f.write(line+'\n')

EXE='D:/llama-gdn-src/build-gdn/bin/llama-server.exe'
MODEL='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT=8081

def wait_health(sec=120):
    for i in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2).status==200:return i+1
        except:pass
        time.sleep(1)
    return None

def post(body,timeout=300):
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(body).encode(),
                               headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req,timeout=timeout).read())

for enable in (False,True):
    tag='ON' if enable else 'OFF'
    log(f'=== {tag} ===')
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(3)
    args=[EXE,'-m',MODEL,'-ngl','99','--n-cpu-moe','40','-c','98304','-np','1','-fa','on',
          '--cache-type-k','q8_0','--cache-type-v','q4_0','-t','8','-b','4096','-ub','2048','-lm','none',
          '--mmproj',MMPROJ,'--mmproj-offload','--moe-cache-mib','1350','--moe-cache-cpu-share','1.0',
          '--port',str(PORT),'--host','127.0.0.1','--spec-type','draft-mtp','--spec-draft-n-max','5',
          '--spec-draft-p-min','0.8','--ctx-checkpoints','2','--cache-ram','0','--temp','0','--top-p','1']
    env=os.environ.copy()
    if enable:env['GGML_MMID_EXPERT_PARALLEL']='1'
    lf=open(f'D:/Brain/_cleanup_20261118/epmin_{tag}_srv.log','w')
    p=subprocess.Popen(args,stdout=lf,stderr=subprocess.STDOUT,env=env)
    sec=wait_health();log(f'health={sec}s' if sec else 'TIMEOUT')
    if not sec:
        p.kill();lf.close();continue
    # 5 个短请求，逐个计时
    for i in range(5):
        b={'model':MODEL,'prompt':'1+1等于几？只回答数字。','n_predict':16,'temperature':0,
           'ignore_eos':True,'stream':False,'cache_prompt':False}
        t0=time.perf_counter()
        try:
            r=post(b,timeout=120)
            dt=time.perf_counter()-t0
            log(f'  {tag} q{i}: {dt:.2f}s | {r["content"].strip()[:40]!r} | tps={r["timings"].get("predicted_per_second",0):.1f}')
        except Exception as e:
            log(f'  {tag} q{i} ERR {type(e).__name__} after {time.perf_counter()-t0:.1f}s')
            break
    p.terminate()
    try:p.wait(timeout=20)
    except:p.kill()
    lf.close();time.sleep(3)
log('=== EP MIN DONE ===')
