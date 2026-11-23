# -*- coding: utf-8 -*-
"""长上下文（60K 字符 ≈13K token）share=0 vs 1.0 对照，固定 96 token 输出。
专门覆盖记忆里 P5 翻车的长任务场景。
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/share_long.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

PRESET = 'D:/Brain/publish/dsh-behavior-guard/config/llama-router-preset.ini'
EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 700

def wait_health(port, seconds=180):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def run_long(port, label, ctx_chars, runs=3, warm=1):
    dec, pref, walls = [], [], []
    for k in range(-warm, runs):
        body = {'model': MODEL, 'prompt': FILLER[:ctx_chars], 'n_predict': 96, 'ignore_eos': True,
                'temperature': 0.7, 'top_p': 0.95, 'stream': False, 'cache_prompt': False}
        req = urllib.request.Request(f'http://127.0.0.1:{port}/completion',
                                     data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        except Exception as e:
            log(f'{label} ERR {e}'); continue
        dt = time.perf_counter() - t0
        tm = r.get('timings', {})
        tag = 'warmup' if k < 0 else f'r{k}'
        log(f'{label:10} {ctx_chars//1000}k {tag:6} wall={dt:5.1f}s ptok={tm.get("prompt_n")} '
            f'prefill={tm.get("prompt_per_second",0):.0f} decode={tm.get("predicted_per_second",0):.1f}')
        if k >= 0:
            dec.append(tm.get('predicted_per_second', 0))
            pref.append(tm.get('prompt_per_second', 0))
            walls.append(dt)
    if dec:
        log(f'{label:10} {ctx_chars//1000}k RESULT prefill_med={statistics.median(pref):.0f} '
            f'decode_med={statistics.median(dec):.1f} wall_med={statistics.median(walls):.1f}s')

for label, share in [('long_s0', '0'), ('long_s10', '1.0')]:
    log(f'=== CELL {label} share={share} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    a = [EXE, '--models-preset', PRESET, '--models-max', '1', '--models-memory-margin', '450',
         '--moe-cache-cpu-share', share, '--port', str(PORT), '--host', '127.0.0.1']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_server.log', 'w')
    p = subprocess.Popen(a, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health(PORT)
    log(f'health after {sec}s' if sec else 'TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); continue
    # 先填 cache
    for _ in range(3):
        try:
            b = {'model': MODEL, 'prompt': FILLER[:15000], 'n_predict': 128, 'ignore_eos': True,
                 'temperature': 0.7, 'stream': False, 'cache_prompt': False}
            urllib.request.urlopen(urllib.request.Request(
                f'http://127.0.0.1:{PORT}/completion', data=json.dumps(b).encode(),
                headers={'Content-Type': 'application/json'}), timeout=900).read()
        except Exception: pass
    run_long(PORT, label, 60000)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== SHARE LONG DONE ===')
