# -*- coding: utf-8 -*-
"""原生 --moe-cache-cpu-share A/B：共享同一生产二进制，三档 share，只测 decode。
prefill 不经过 MoE cache（源码确认 max_batch=32），故不测。
用法: 计划任务执行 python tools/share_ab_runner.py
"""
import subprocess, time, urllib.request, json, statistics
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/share_ab.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

PRESET = 'D:/Brain/publish/dsh-behavior-guard/config/llama-router-preset.ini'
EXE = 'D:/llama.cpp/build/bin/llama-server.exe'   # 生产二进制（master 94f3af3）
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

def gen(port, prompt, max_tokens, stream=False, cache_prompt=True):
    body = {'model': MODEL, 'prompt': prompt, 'max_tokens': max_tokens,
            'temperature': 0.7, 'top_p': 0.95, 'stream': stream, 'cache_prompt': cache_prompt}
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/completions',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=1200)

def decode_probe(port, label, runs=5, warm=2, n=128):
    out = []
    for k in range(-warm, runs):
        prompt = FILLER[:20000] + "\n\n请继续写一段技术说明。"
        times = []
        t0 = time.perf_counter()
        try:
            with gen(port, prompt, n + 32, stream=True) as resp:
                for raw in resp:
                    line = raw.decode('utf-8', errors='replace').strip()
                    if not line.startswith('data:'): continue
                    pl = line[5:].strip()
                    if pl == '[DONE]': break
                    try:
                        c = json.loads(pl)
                        if c.get('choices') and c['choices'][0].get('text'):
                            times.append(time.perf_counter() - t0)
                    except Exception: continue
                    if len(times) >= n: break
        except Exception as e:
            log(f'{label} ERR {e}'); continue
        if len(times) < n:
            log(f'{label} SKIP {len(times)}tok'); continue
        tps = (n - 1) / (times[n-1] - times[0])
        tag = 'warmup' if k < 0 else f'r{k}'
        log(f'{label:12} decode {tag:6} {tps:.2f} t/s')
        if k >= 0: out.append(tps)
    if out:
        log(f'{label:12} decode MEDIAN {statistics.median(out):.3f} t/s (sd {statistics.stdev(out):.3f}) n={len(out)}')
    return out

for label, share in [('share0', '0'), ('share05', '0.5'), ('share10', '1.0')]:
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
    # 填满 LRU cache（share 只在 n_filled == n_slots 时生效）
    for _ in range(4):
        try:
            gen(PORT, FILLER[:12000] + "\n\n总结。", 96).read()
        except Exception: pass
    decode_probe(PORT, label)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    # 抓 cache 统计
    try:
        for line in open(f'D:/Brain/_cleanup_20261118/{label}_server.log', errors='replace'):
            if 'MoE cache size' in line or 'llama_moe_cache' in line:
                log('STAT ' + line.strip()[:190])
    except Exception: pass
    time.sleep(3)
log('=== SHARE AB DONE ===')
