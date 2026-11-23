# -*- coding: utf-8 -*-
"""share 端到端验证：share=0 vs 1.0，用多步增量 prefill 模拟真实 harness。
判据：总墙钟（不是 decode t/s）。
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/share_e2e.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

PRESET = 'D:/Brain/publish/dsh-behavior-guard/config/llama-router-preset.ini'
EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 400

def wait_health(port, seconds=180):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def e2e_once(port):
    """4 步：20K 首轮 + 1K×3 增量，每步生成 96 token。cache_prompt=True 模拟 harness。"""
    t_start = time.perf_counter()
    rows = []
    ctx = FILLER[:20000]
    for step in range(4):
        if step > 0:
            ctx += '\n\n' + FILLER[:1000]
        # native /completion + ignore_eos so each step emits exactly 96 tokens
        body = {'model': MODEL, 'prompt': ctx, 'n_predict': 96, 'ignore_eos': True,
                'temperature': 0.7, 'top_p': 0.95, 'stream': False, 'cache_prompt': True}
        req = urllib.request.Request(f'http://127.0.0.1:{port}/completion',
                                     data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        dt = time.perf_counter() - t0
        tm = r.get('timings', {})
        rows.append({'wall': round(dt, 2), 'tok': tm.get('predicted_n', 0),
                     'prefill': round(tm.get('prompt_per_second', 0)),
                     'decode': round(tm.get('predicted_per_second', 0), 1)})
    total = time.perf_counter() - t_start
    return total, rows

for label, share in [('e2e_share0', '0'), ('e2e_share10', '1.0')]:
    log(f'=== CELL {label} share={share} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    a = [EXE, '--models-preset', PRESET, '--models-max', '1', '--models-memory-margin', '450',
         '--moe-cache-cpu-share', share, '--port', str(PORT), '--host', '127.0.0.1']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_server.log', 'w')
    p = subprocess.Popen(a, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health(PORT)
    log(f'health after {sec}s' if sec else 'health TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); continue
    # 填满 LRU cache
    for _ in range(4):
        try:
            body = {'model': MODEL, 'prompt': FILLER[:12000], 'n_predict': 128, 'ignore_eos': True,
                    'temperature': 0.7, 'stream': False, 'cache_prompt': False}
            urllib.request.urlopen(urllib.request.Request(
                f'http://127.0.0.1:{PORT}/completion', data=json.dumps(body).encode(),
                headers={'Content-Type': 'application/json'}), timeout=900).read()
        except Exception: pass
    # 2 warmup + 5 正式
    totals = []
    for k in range(-2, 5):
        try:
            total, rows = e2e_once(PORT)
        except Exception as e:
            log(f'{label} ERR {e}'); continue
        tag = 'warmup' if k < 0 else f'r{k}'
        log(f'{label:12} {tag:6} total={total:6.2f}s | ' + ' '.join(f'{r["wall"]}s/{r["tok"]}t/{r["decode"]}d' for r in rows))
        if k >= 0: totals.append(total)
    if totals:
        log(f'{label:12} E2E MEDIAN {statistics.median(totals):.3f}s (sd {statistics.stdev(totals):.3f}) n={len(totals)}')
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== SHARE E2E DONE ===')
