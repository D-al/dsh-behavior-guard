# -*- coding: utf-8 -*-
"""分块并发下载 HF 大文件（绕过单连接限速）"""
import urllib.request, threading, time, os
from pathlib import Path
URL='https://huggingface.co/ggml-org/Qwen3.6-35B-A3B-GGUF/resolve/main/mmproj-Qwen3.6-35B-A3B-Q8_0.gguf'
OUT=Path('D:/GGUF_Download/mmproj-Qwen3.6-35B-A3B-Q8_0.gguf')
TOTAL=614194304
NCHUNK=16
chunk=TOTAL//NCHUNK
progress=[0]*NCHUNK

def get(i):
    s=i*chunk; e=TOTAL if i==NCHUNK-1 else (i+1)*chunk
    part=Path(f'D:/Brain/_cleanup_20261118/mmpart_{i}')
    if part.exists() and part.stat().st_size==e-s:
        progress[i]=e-s;return
    for attempt in range(5):
        try:
            req=urllib.request.Request(URL,headers={'Range':f'bytes={s}-{e-1}','User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=60) as r, open(part,'wb') as f:
                while True:
                    b=r.read(256*1024)
                    if not b:break
                    f.write(b);progress[i]+=len(b)
            if part.stat().st_size==e-s:return
        except Exception as ex:
            print(f'chunk{i} attempt{attempt} {type(ex).__name__}',flush=True)
            progress[i]=0
            time.sleep(2)
    raise RuntimeError(f'chunk {i} failed')

t0=time.perf_counter()
ths=[threading.Thread(target=get,args=(i,),daemon=True) for i in range(NCHUNK)]
for t in ths:t.start()
while any(t.is_alive() for t in ths):
    time.sleep(10)
    print(f'{sum(progress)/1024/1024:.0f}/{TOTAL/1024/1024:.0f} MiB {sum(progress)/1024/1024/(time.perf_counter()-t0):.1f} MB/s',flush=True)
for t in ths:t.join()
# 合并
with open(OUT,'wb') as out:
    for i in range(NCHUNK):
        part=Path(f'D:/Brain/_cleanup_20261118/mmpart_{i}')
        out.write(part.read_bytes())
print('MERGED',OUT.stat().st_size,'in',round(time.perf_counter()-t0,1),'s')
