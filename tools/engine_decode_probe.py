# -*- coding: utf-8 -*-
"""纯净 decode 探针：stream=true，只统计前 N 个 token 的生成时间，消除早停影响。
判据：第 1→N 个 token 的 wall / (N-1) = decode t/s（prefill 不计入）。
用法: python tools/engine_decode_probe.py <port> <label> <runs> <warm>
"""
import json, urllib.request, sys, time, statistics
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
LABEL = sys.argv[2] if len(sys.argv) > 2 else 'x'
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
WARM = int(sys.argv[4]) if len(sys.argv) > 4 else 2
N = 128  # 只取前 128 token
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟。" * 100

def one(tag):
    prompt = FILLER[:20000] + "\n\n请继续写一段技术说明。"
    body = {'model': MODEL, 'prompt': prompt, 'max_tokens': N + 32,
            'temperature': 0.7, 'top_p': 0.95, 'stream': True}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/completions',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    times = []
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw in resp:
            line = raw.decode('utf-8', errors='replace').strip()
            if not line.startswith('data:'): continue
            payload = line[5:].strip()
            if payload == '[DONE]': break
            try:
                chunk = json.loads(payload)
                if chunk.get('choices') and chunk['choices'][0].get('text'):
                    times.append(time.perf_counter() - t0)
            except Exception: continue
            if len(times) >= N: break
    if len(times) < N:
        print(f'{LABEL} {tag} SKIP only {len(times)} tokens', flush=True)
        return None
    # 前 N token 的间隔：t[N-1]-t[0]，除以 N-1
    span = times[N-1] - times[0]
    tps = (N-1) / span
    print(f'{LABEL:8} {tag:7} first{N}tok in {span:.2f}s = {tps:.2f} t/s', flush=True)
    return round(tps, 3)

res = []
for k in range(-WARM, RUNS):
    v = one('warmup' if k < 0 else f'r{k}')
    if k >= 0 and v is not None: res.append(v)
print(f'\n=== {LABEL}: median={statistics.median(res):.3f} t/s mean={statistics.mean(res):.3f} sd={statistics.stdev(res):.3f} ===')
Path(f'D:/Brain/_cleanup_20261118/decode_{LABEL}.json').write_text(
    json.dumps({'label': LABEL, 'vals': res, 'median': statistics.median(res)}, indent=1), encoding='utf-8')
