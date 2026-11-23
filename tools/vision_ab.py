# -*- coding: utf-8 -*-
"""视觉编码器 F16 vs Q8_0 质量 A/B：同一张图、同一 prompt，对比 OCR/图表识别。
同时记录显存占用和视觉编码耗时。
"""
import subprocess, time, urllib.request, json, os, base64
from pathlib import Path
LOG=Path('D:/Brain/_cleanup_20261118/vision_ab.log')
def log(m):
    line=f'{time.strftime("%H:%M:%S")} {m}'
    print(line,flush=True)
    with open(LOG,'a',encoding='utf-8') as f:f.write(line+'\n')

EXE='D:/llama.cpp/build/bin/llama-server.exe'
MODEL='D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MM_F16='D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
MM_Q8='D:/GGUF_Download/mmproj-Qwen3.6-35B-A3B-Q8_0.gguf'
IMG='D:/Brain/_cleanup_20261118/vision_test.png'
PRESET='D:/Brain/workspace/bench/llama-router-preset.ini'
PORT=8081
MODEL_ID='Qwen3.6-35B-A3B-UD-Q4_K_XL'
PROMPT='请识别图中所有文字。逐行输出：标题、表格每个单元格的内容（含数字）、柱状图六根柱子的高度数值。不要解释，只输出识别结果。'

def wait_health(sec=240):
    for i in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2).status==200:return i+1
        except:pass
        time.sleep(1)
    return None

def start(mmproj):
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'],capture_output=True);time.sleep(4)
    # 用 preset（生产同款 router 模式），但通过 env 覆盖 mmproj 需要改 preset —— 这里直接改 preset 临时文件
    preset_src=Path(PRESET).read_text(encoding='utf-8')
    # 找到 mmproj 行并替换
    import re
    preset_new=re.sub(r'mmproj\s*=.*', f'mmproj = {mmproj.replace(chr(92),"/")}', preset_src, count=1)
    ptmp=Path('D:/Brain/_cleanup_20261118/vision_preset.ini')
    ptmp.write_text(preset_new,encoding='utf-8')
    args=[EXE,'--models-preset',str(ptmp),'--models-max','1','--models-memory-margin','450',
          '-t','8','--port',str(PORT),'--host','127.0.0.1']
    lf=open(f'D:/Brain/_cleanup_20261118/vision_{"F16" if "F16" in mmproj else "Q8"}_srv.log','w')
    p=subprocess.Popen(args,stdout=lf,stderr=subprocess.STDOUT)
    sec=wait_health()
    if not sec:p.kill();lf.close();return None
    return p,lf

def ask_vision():
    b64=base64.b64encode(Path(IMG).read_bytes()).decode()
    body={'model':MODEL_ID,
          'messages':[{'role':'user','content':[
              {'type':'text','text':PROMPT},
              {'type':'image_url','image_url':{'url':f'data:image/png;base64,{b64}'}}
          ]}],
          'temperature':0.0,'max_tokens':1400,'stream':False}
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions',
                               data=json.dumps(body).encode(),
                               headers={'Content-Type':'application/json'})
    t0=time.perf_counter()
    r=json.loads(urllib.request.urlopen(req,timeout=900).read())
    dt=time.perf_counter()-t0
    msg=r['choices'][0]['message']; content=msg.get('content')
    log(f'  raw message keys={list(msg.keys())} finish={r["choices"][0].get("finish_reason")}')
    log(f'  reasoning={str(msg.get("reasoning_content",""))[:300]}')
    if content is None: content=str(msg)
    usage=r.get('usage',{})
    return content,dt,usage

results={}
for tag,mm in [('F16',MM_F16),('Q8',MM_Q8)]:
    log(f'=== {tag} ({mm}) ===')
    if not Path(mm).exists():
        log('  FILE NOT FOUND');continue
    r=start(mm)
    if not r:log('  START FAIL');continue
    p,lf=r
    # 显存
    try:
        import subprocess as sp
        out=sp.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()
        log(f'  VRAM used={out}')
    except:pass
    try:
        content,dt,usage=ask_vision()
        log(f'  time={dt:.1f}s usage={usage}')
        log(f'  --- OUTPUT ---\n{content}\n--- END ---')
        results[tag]=content
    except Exception as e:
        log(f'  ASK ERR {type(e).__name__}: {str(e)[:200]}')
    p.terminate()
    try:p.wait(timeout=20)
    except:p.kill()
    lf.close();time.sleep(4)

log('=== COMPARISON ===')
if len(results)==2:
    log(f'F16 chars={len(results["F16"])} Q8 chars={len(results["Q8"])}')
    log(f'IDENTICAL: {results["F16"].strip()==results["Q8"].strip()}')
log('=== VISION AB DONE ===')
