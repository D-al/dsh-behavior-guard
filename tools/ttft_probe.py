# -*- coding: utf-8 -*-
"""冷启动 + TTFT 分解测量。

三段指标：
1. 进程启动 → /health 就绪（模型加载）
2. 请求发出 → 第一个 token 到达（TTFT，含 prefill）
3. 整段生成 decode t/s

用法：python ttft_probe.py [exe] [prompt_len] [runs]
"""
import subprocess, time, urllib.request, json, sys, statistics
from pathlib import Path

EXE = sys.argv[1] if len(sys.argv) > 1 else 'D:/llama.cpp/build/bin/llama-server.exe'
PLEN = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
MODEL = 'D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ = 'D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT = 8081
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500
LOG = Path('D:/Brain/_cleanup_20261118/ttft_probe.log')


def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def wait_health(sec=180):
    t0 = time.perf_counter()
    for _ in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return time.perf_counter() - t0
        except Exception:
            pass
        time.sleep(1)
    return None


def stream_first_token(prompt, timeout=600):
    """流式请求，测首个 token 到达时间。"""
    body = {'model': MODEL, 'prompt': prompt, 'n_predict': 64, 'ignore_eos': True,
            'temperature': 0.7, 'stream': True, 'cache_prompt': False}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',
                                 data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    resp = urllib.request.urlopen(req, timeout=timeout)
    first = None
    for line in resp:
        txt = line.decode('utf-8', errors='replace').strip()
        if not txt.startswith('data:'):
            continue
        try:
            d = json.loads(txt[5:].strip())
        except Exception:
            continue
        if d.get('content'):
            first = time.perf_counter() - t0
            break
    total = time.perf_counter() - t0
    return first, total


def start_server():
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [EXE, '-m', MODEL, '-ngl', '99', '--n-cpu-moe', '40', '-c', '98304', '-np', '1', '-fa', 'on',
            '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0', '-t', '8', '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--mmproj', MMPROJ, '--mmproj-offload', '--moe-cache-mib', '1350', '--moe-cache-cpu-share', '1.0',
            '--port', str(PORT), '--host', '127.0.0.1', '--spec-type', 'draft-mtp', '--spec-draft-n-max', '5',
            '--spec-draft-p-min', '0.8', '--ctx-checkpoints', '2', '--cache-ram', '0', '--temp', '0.7', '--top-p', '0.95']
    lf = open('D:/Brain/_cleanup_20261118/ttft_srv.log', 'w')
    p = subprocess.Popen(args, stdout=lf, stderr=subprocess.STDOUT)
    load_s = wait_health()
    return p, lf, load_s


def main():
    log(f'=== TTFT probe exe={EXE} prompt_len={PLEN} runs={RUNS} ===')
    p, lf, load_s = start_server()
    if load_s is None:
        log('LOAD TIMEOUT'); p.kill(); lf.close(); return
    log(f'  冷启动(进程→health) = {load_s:.1f}s')
    ttfts, totals = [], []
    for i in range(RUNS):
        import random, string
        tag = ''.join(random.choice(string.ascii_lowercase) for _ in range(64))
        try:
            first, total = stream_first_token(tag + ' ' + FILLER[:PLEN])
            ttfts.append(first); totals.append(total)
            log(f'  run{i}: TTFT={first:.2f}s  64tok总={total:.2f}s' + (f'  (首token=None)' if first is None else ''))
        except Exception as e:
            log(f'  run{i} ERR {type(e).__name__}: {str(e)[:80]}')
    if ttfts:
        vals = [x for x in ttfts if x is not None]
        if vals:
            log(f'  TTFT median={statistics.median(vals):.2f}s n={len(vals)}')
    p.terminate()
    try: p.wait(timeout=20)
    except Exception: p.kill()
    lf.close()
    log('=== DONE ===')


if __name__ == '__main__':
    main()
