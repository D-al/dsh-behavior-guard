# -*- coding: utf-8 -*-
"""校准：MTP on 下 stream chunk 数 vs server n_gen 的比例是否稳定。
若比例稳定 → 历史 stream 逐 chunk 的相对 A/B 有效（比例抵消）
若比例随配置变化 → 历史 A/B 可能失真
"""
import subprocess, time, urllib.request, json, os
from pathlib import Path
LOG=Path('D:/Brain/_cleanup_20261118/calibration.log')
def log(m):
    line=f'{time.strftime("%H:%M:%S")} {m}'
    print(line,flush=True)
    with open(LOG,'a',encoding='utf-8') as f:f.write(line+'\n')

EXE='D:/llama.cpp/build/bin/llama-server.exe'  # 用生产二进制（原版）
MODEL='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PRESET='D:/Brain/workspace/bench/llama-router-preset.ini'
PORT=8081
FILLER="混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。"*500

def wait_health(sec=180):
    for i in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2).status==200:return i+1
        except:pass
        time.sleep(1)
    return None

# 起 server（用生产 CLI，router 模式但端口对）
subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(3)
args=[EXE,'--models-preset',PRESET,'--models-max','1','--models-memory-margin','450',
      '-t','8','--port',str(PORT),'--host','127.0.0.1']
lf=open('D:/Brain/_cleanup_20261118/cal_srv.log','w')
p=subprocess.Popen(args,stdout=lf,stderr=subprocess.STDOUT)
sec=wait_health()
log(f'health={sec}s')
if sec:
    # 预热
    for _ in range(3):
        try:
            b={'model':'Qwen3.6-35B-A3B-UD-Q4_K_XL','prompt':FILLER[:8000],'n_predict':128,
               'ignore_eos':True,'temperature':0.7,'stream':False,'cache_prompt':False}
            req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(b).encode(),
                                       headers={'Content-Type':'application/json'})
            urllib.request.urlopen(req,timeout=600).read()
        except Exception as e:log(f'warm ERR {e}')
    # 校准：stream 请求，数 chunk，同时从 usage 读 token
    for k in range(8):
        body={'model':'Qwen3.6-35B-A3B-UD-Q4_K_XL','prompt':FILLER[:20000],'n_predict':128,
              'ignore_eos':True,'temperature':0.7,'stream':True,'cache_prompt':True}
        req=urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',data=json.dumps(body).encode(),
                                   headers={'Content-Type':'application/json'})
        nchunk=0;n_content=0;usage=None
        with urllib.request.urlopen(req,timeout=900) as r:
            for raw in r:
                s0=raw.decode('utf-8',errors='replace').strip()
                if not s0.startswith('data:'):continue
                pl=s0[5:].strip()
                if pl=='[DONE]':break
                try:
                    j=json.loads(pl)
                    nchunk+=1
                    if j.get('content'):n_content+=1
                    if 'usage' in j and j['usage']:usage=j['usage']
                except:pass
        log(f'  k{k}: chunks={nchunk} content_chunks={n_content} usage={usage}')
p.terminate()
try:p.wait(timeout=20)
except:p.kill()
lf.close()
log('=== CALIBRATION DONE ===')
