# -*- coding: utf-8 -*-
"""cache/NCMOE 配置对照 v2：更稳的实现，每步打日志。
A=40/1350(基线) vs C1=41/1700 vs C2=41/1600，share=1.0 固定。
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/cache_cfg2.log')
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

def post(path, body, timeout=1800):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}{path}',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())

def wait_health(seconds=240):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def do_decode(label, runs=5, warm=2, n=128):
    out = []
    for k in range(-warm, runs):
        times = []
        t0 = time.perf_counter()
        body = {'model': MODEL, 'prompt': FILLER[:20000], 'n_predict': n + 32,
                'ignore_eos': True, 'temperature': 0.7, 'stream': True, 'cache_prompt': True}
        req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',
                                     data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                for raw in r:
                    s = raw.decode('utf-8', errors='replace').strip()
                    if not s.startswith('data:'): continue
                    pl = s[5:].strip()
                    if pl == '[DONE]': break
                    try:
                        if json.loads(pl).get('content'):
                            times.append(time.perf_counter() - t0)
                    except Exception: pass
                    if len(times) >= n: break
        except Exception as e:
            log(f'{label} decode ERR {type(e).__name__} {str(e)[:60]}'); continue
        if len(times) < n:
            log(f'{label} decode SKIP {len(times)}tok'); continue
        tps = (n - 1) / (times[n-1] - times[0])
        tag = 'warm' if k < 0 else f'r{k}'
        log(f'{label:11} decode {tag:5} {tps:.2f} t/s')
        if k >= 0: out.append(tps)
    if out:
        log(f'{label:11} DECODE_MED {statistics.median(out):.3f} (sd {statistics.stdev(out):.3f})')

def do_e2e(label, runs=3, warm=1):
    tot = []
    for k in range(-warm, runs):
        ctx = FILLER[:20000]
        t0 = time.perf_counter()
        ok = True
        for step in range(4):
            if step > 0: ctx += '\n\n' + FILLER[:1000]
            try:
                post('/completion', {'model': MODEL, 'prompt': ctx, 'n_predict': 96,
                                     'ignore_eos': True, 'temperature': 0.7,
                                     'stream': False, 'cache_prompt': True})
            except Exception as e:
                log(f'{label} e2e ERR {type(e).__name__}'); ok = False; break
        if not ok: continue
        dt = time.perf_counter() - t0
        tag = 'warm' if k < 0 else f'r{k}'
        log(f'{label:11} e2e {tag:5} {dt:6.2f}s')
        if k >= 0: tot.append(dt)
    if tot:
        log(f'{label:11} E2E_MED {statistics.median(tot):.3f} (sd {statistics.stdev(tot):.3f})')

for label, preset in CFGS:
    log(f'=== CELL {label} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [EXE, '--models-preset', preset, '--models-max', '1', '--models-memory-margin', '450',
            '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0',
            '-t', '6', '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1', '-lv', '4']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', 'w')
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health()
    log(f'health={sec}s' if sec else 'health TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); continue
    # 首次加载（大）
    try:
        post('/completion', {'model': MODEL, 'prompt': FILLER[:8000], 'n_predict': 32,
                             'ignore_eos': True, 'stream': False, 'cache_prompt': False}, timeout=1800)
        log('model loaded')
    except Exception as e:
        log(f'LOAD ERR {type(e).__name__} {str(e)[:80]}')
        p.terminate(); logf.close(); continue
    # 填 cache（2 次足够）
    for i in range(2):
        try:
            post('/completion', {'model': MODEL, 'prompt': FILLER[:14000], 'n_predict': 128,
                                 'ignore_eos': True, 'temperature': 0.7, 'stream': False,
                                 'cache_prompt': False})
        except Exception: pass
    log('cache filled')
    # 显存 + cache 配置
    smi = subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader'],
                         capture_output=True, text=True)
    log(f'VRAM_USED {smi.stdout.strip()}')
    logf.flush()
    try:
        for line in open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', errors='replace'):
            if 'MoE cache size' in line:
                log('CFG ' + line.strip()[:170]); break
    except Exception: pass
    do_decode(label)
    do_e2e(label)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== CACHE CFG2 DONE ===')
