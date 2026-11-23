# -*- coding: utf-8 -*-
"""CPU 线程数扫描：-t 6(当前) / 8 / 10 / 12 / 16，测 decode t/s。
既然实测 CPU 590% 满载，试更多线程能否用上 E 核。
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/thread_scan.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
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

def decode_runs(label, runs=5, warm=2, n=128):
    out = []
    for k in range(-warm, runs):
        times = []
        t0 = time.perf_counter()
        body = {'model': MODEL, 'prompt': FILLER[:20000], 'n_predict': n+32,
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
            log(f'{label} ERR {type(e).__name__}'); continue
        if len(times) < n: continue
        tps = (n-1)/(times[n-1]-times[0])
        tag = 'warm' if k < 0 else f'r{k}'
        log(f'{label:8} {tag:5} {tps:.2f} t/s')
        if k >= 0: out.append(tps)
    if out:
        log(f'{label:8} MEDIAN {statistics.median(out):.3f} (sd {statistics.stdev(out):.3f})')
    return out

for t in (8, 6):
    label = f't{t}'
    log(f'=== CELL {label} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [EXE, '--models-preset', PRESET, '--models-max', '1', '--models-memory-margin', '450',
            '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0',
            '-t', str(t), '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1',
            '--spec-type', 'draft-mtp', '--spec-draft-n-max', '5', '--spec-draft-p-min', '0.8',
            '--ctx-checkpoints', '2', '--cache-ram', '0']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', 'w')
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health()
    log(f'health={sec}s' if sec else 'TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); continue
    # 加载 + 填 cache
    try:
        body = {'model': MODEL, 'prompt': FILLER[:8000], 'n_predict': 32, 'ignore_eos': True, 'stream': False}
        urllib.request.urlopen(urllib.request.Request(
            f'http://127.0.0.1:{PORT}/completion', data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'}), timeout=1200).read()
    except Exception as e:
        log(f'LOAD ERR {e}'); p.terminate(); logf.close(); continue
    for _ in range(2):
        try:
            b = {'model': MODEL, 'prompt': FILLER[:14000], 'n_predict': 128,
                 'ignore_eos': True, 'temperature': 0.7, 'stream': False, 'cache_prompt': False}
            urllib.request.urlopen(urllib.request.Request(
                f'http://127.0.0.1:{PORT}/completion', data=json.dumps(b).encode(),
                headers={'Content-Type': 'application/json'}), timeout=900).read()
        except Exception: pass
    decode_runs(label)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== THREAD SCAN DONE ===')
