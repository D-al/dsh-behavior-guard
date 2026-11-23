# -*- coding: utf-8 -*-
"""cache/NCMOE 配置对照：A=40/1350(基线) vs C1=41/1700 vs C2=41/1600。
share=1.0 固定；测 decode + e2e（4 步增量）。
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/cache_cfg.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500

CFGS = [
    ('A_40_1350', 'D:/Brain/_cleanup_20261118/preset_A_40_1350.ini'),
    ('C1_41_1700', 'D:/Brain/_cleanup_20261118/preset_C_41_1700.ini'),
    ('C2_41_1600', 'D:/Brain/_cleanup_20261118/preset_C_41_1600.ini'),
]

def wait_health(port, seconds=240):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def gen(port, prompt, n_predict=96, stream=False, cache_prompt=True):
    body = {'model': MODEL, 'prompt': prompt, 'n_predict': n_predict, 'ignore_eos': True,
            'temperature': 0.7, 'top_p': 0.95, 'stream': stream, 'cache_prompt': cache_prompt}
    req = urllib.request.Request(f'http://127.0.0.1:{port}/completion',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=1800)

def decode_probe(port, label, runs=5, warm=2, n=128):
    out = []
    for k in range(-warm, runs):
        times = []
        t0 = time.perf_counter()
        try:
            resp = urllib.request.Request(f'http://127.0.0.1:{port}/completion',
                data=json.dumps({'model': MODEL, 'prompt': FILLER[:20000], 'n_predict': n+32,
                                 'ignore_eos': True, 'temperature': 0.7, 'stream': True,
                                 'cache_prompt': True}).encode(),
                headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(resp, timeout=1800) as r:
                for raw in r:
                    line = raw.decode('utf-8', errors='replace').strip()
                    if not line.startswith('data:'): continue
                    pl = line[5:].strip()
                    if pl == '[DONE]': break
                    try:
                        c = json.loads(pl)
                        if c.get('content'): times.append(time.perf_counter() - t0)
                    except Exception: continue
                    if len(times) >= n: break
        except Exception as e:
            log(f'{label} decode ERR {e}'); continue
        if len(times) < n:
            log(f'{label} decode SKIP {len(times)}tok'); continue
        tps = (n-1)/(times[n-1]-times[0])
        log(f'{label:12} decode {"warmup" if k<0 else "r"+str(k):6} {tps:.2f} t/s')
        if k >= 0: out.append(tps)
    if out: log(f'{label:12} DECODE MEDIAN {statistics.median(out):.3f} t/s (sd {statistics.stdev(out):.3f})')

def e2e_probe(port, label, runs=3, warm=1):
    totals = []
    for k in range(-warm, runs):
        ctx = FILLER[:20000]
        t_start = time.perf_counter()
        step_ok = True
        for step in range(4):
            if step > 0: ctx += '\n\n' + FILLER[:1000]
            try:
                r = json.loads(gen(port, ctx).read())
            except Exception as e:
                log(f'{label} e2e ERR {e}'); step_ok = False; break
        if not step_ok: continue
        total = time.perf_counter() - t_start
        log(f'{label:12} e2e {"warmup" if k<0 else "r"+str(k):6} total={total:6.2f}s')
        if k >= 0: totals.append(total)
    if totals: log(f'{label:12} E2E MEDIAN {statistics.median(totals):.3f}s (sd {statistics.stdev(totals):.3f})')

for label, preset in CFGS:
    log(f'=== CELL {label} preset={Path(preset).name} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    a = [EXE, '--models-preset', preset, '--models-max', '1', '--models-memory-margin', '450',
         '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0',
         '-t', '6', '-b', '4096', '-ub', '2048', '-lm', 'none',
         '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_server.log', 'w')
    p = subprocess.Popen(a, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health(PORT)
    log(f'health after {sec}s' if sec else 'health TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); continue
    # 触发加载 + 填 cache
    loaded = False
    for _ in range(6):
        try:
            gen(PORT, FILLER[:12000], 128, cache_prompt=False).read(); loaded = True
        except Exception as e:
            log(f'load attempt ERR {str(e)[:80]}')
    if not loaded:
        log('LOAD FAILED'); p.terminate(); logf.close(); continue
    # 显存 + cache 日志
    subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader'], stdout=logf)
    logf.flush()
    try:
        for line in open(f'D:/Brain/_cleanup_20261118/{label}_server.log', errors='replace'):
            if 'MoE cache size' in line:
                log('CFG ' + line.strip()[:180])
    except Exception: pass
    decode_probe(PORT, label)
    e2e_probe(PORT, label)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== CACHE CFG DONE ===')
