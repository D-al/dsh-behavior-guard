# -*- coding: utf-8 -*-
"""max_batch 32->256 补丁验证。
关键：patch 只在 33..94 token 批生效（>94 被 n_slots 挡住，<=32 本来就走 share）。
所以工作负载用 60 token 增量，而不是 1K。
baseline = 生产二进制；patch = build-share 二进制。同 preset A，share=1.0。
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/mb256.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
PRESET = 'D:/Brain/_cleanup_20261118/preset_A_40_1350.ini'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500
# 60 token 增量（在 patch 有效窗口 33..94 内）
INC = "工具调用返回的结果需要用自然语言总结，并说明下一步计划是什么。请注意保持简洁但信息完整，不要遗漏关键细节，也不要重复已经说过的内容。" * 2

BINS = [
    ('base_mb32', 'D:/llama.cpp/build/bin/llama-server.exe'),
    ('patch_mb256', 'D:/llama-gdn-src/build-gdn/bin/llama-server.exe'),
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

def bench(label, runs=5, warm=2):
    """20K 首轮 + 60token x 3 增量，测总墙钟"""
    tot, dec = [], []
    for k in range(-warm, runs):
        ctx = FILLER[:20000]
        t0 = time.perf_counter()
        ok = True
        last_d = 0
        for step in range(4):
            if step > 0: ctx += '\n\n' + INC
            try:
                r = post('/completion', {'model': MODEL, 'prompt': ctx, 'n_predict': 96,
                                         'ignore_eos': True, 'temperature': 0.7,
                                         'stream': False, 'cache_prompt': True})
                last_d = r['timings'].get('predicted_per_second', 0)
            except Exception as e:
                log(f'{label} ERR {type(e).__name__}'); ok = False; break
        if not ok: continue
        dt = time.perf_counter() - t0
        tag = 'warm' if k < 0 else f'r{k}'
        log(f'{label:12} {tag:5} {dt:6.2f}s  last_decode={last_d:.1f}')
        if k >= 0: tot.append(dt); dec.append(last_d)
    if tot:
        log(f'{label:12} MED {statistics.median(tot):.3f}s (sd {statistics.stdev(tot):.3f}) '
            f'| decode_med {statistics.median(dec):.1f}')

for label, exe in BINS:
    log(f'=== CELL {label} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [exe, '--models-preset', PRESET, '--models-max', '1', '--models-memory-margin', '450',
            '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0',
            '-t', '6', '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', 'w')
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health()
    log(f'health={sec}s' if sec else 'TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); continue
    # 加载 + 填 cache
    try:
        post('/completion', {'model': MODEL, 'prompt': FILLER[:8000], 'n_predict': 32,
                             'ignore_eos': True, 'stream': False, 'cache_prompt': False})
    except Exception as e:
        log(f'LOAD ERR {e}'); p.terminate(); logf.close(); continue
    for _ in range(2):
        try:
            post('/completion', {'model': MODEL, 'prompt': FILLER[:14000], 'n_predict': 128,
                                 'ignore_eos': True, 'temperature': 0.7, 'stream': False,
                                 'cache_prompt': False})
        except Exception: pass
    log('cache filled')
    bench(label)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== MB256 DONE ===')
