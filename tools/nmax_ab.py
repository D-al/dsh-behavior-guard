# -*- coding: utf-8 -*-
"""nmax 3 vs 5 A/B：用生产 build，固定单一变量。
用法：python nmax_ab.py [3,5] [runs] [exe]
"""
import subprocess, time, urllib.request, json, statistics, os, sys
from pathlib import Path

EXE = sys.argv[3] if len(sys.argv) > 3 else 'D:/llama.cpp/build/bin/llama-server.exe'
MODEL = 'D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ = 'D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT = 8081
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500
LOG = Path('D:/Brain/_cleanup_20261118/nmax_ab.log')


def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def wait_health(sec=120):
    for _ in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def post(b, timeout=600):
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',
                                 data=json.dumps(b).encode(), headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def start(nmax):
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [EXE, '-m', MODEL, '-ngl', '99', '--n-cpu-moe', '40', '-c', '98304', '-np', '1', '-fa', 'on',
            '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0', '-t', '8', '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--mmproj', MMPROJ, '--mmproj-offload', '--moe-cache-mib', '1350', '--moe-cache-cpu-share', '1.0',
            '--port', str(PORT), '--host', '127.0.0.1', '--spec-type', 'draft-mtp', '--spec-draft-n-max', str(nmax),
            '--spec-draft-p-min', '0.8', '--ctx-checkpoints', '2', '--cache-ram', '0', '--temp', '0.7', '--top-p', '0.95']
    lf = open(f'D:/Brain/_cleanup_20261118/nmax_{nmax}_srv.log', 'w')
    p = subprocess.Popen(args, stdout=lf, stderr=subprocess.STDOUT)
    if not wait_health():
        p.kill(); lf.close(); return None
    for i in range(2):
        post({'model': MODEL, 'prompt': ('warm%d ' % i) + FILLER[:14000], 'n_predict': 128, 'ignore_eos': True,
              'temperature': 0.7, 'stream': False, 'cache_prompt': False})
    return p, lf


def bench(nmax, runs):
    r = start(nmax)
    if not r:
        return []
    p, lf = r
    tps = []
    for k in range(runs):
        # 随机前缀避免 LCP 相似触发宿主 prompt 缓存同步 save/load（实测会卡死）
        import random, string
        tag = ''.join(random.choice(string.ascii_lowercase) for _ in range(64))
        b = {'model': MODEL, 'prompt': tag + ' ' + FILLER[:20000], 'n_predict': 200, 'ignore_eos': True,
             'temperature': 0.7, 'stream': False, 'cache_prompt': False}
        try:
            resp = post(b)
            t = resp['timings']['predicted_per_second']
            tps.append(t)
            log(f'  nmax{nmax} r{k}: {t:.2f} t/s')
        except Exception as e:
            log(f'  nmax{nmax} r{k} ERR {type(e).__name__}')
    p.terminate()
    try:
        p.wait(timeout=20)
    except Exception:
        p.kill()
    lf.close(); time.sleep(3)
    return tps


def main():
    variants = [int(x) for x in sys.argv[1].split(',')] if len(sys.argv) > 1 else [3, 5]
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    log(f'=== nmax A/B exe={EXE} runs={runs} variants={variants} ===')
    # 交叉顺序：3,5,5,3 抵消热漂移
    order = []
    for v in variants: order.append(v)
    for v in reversed(variants): order.append(v)
    results = {}
    for v in order:
        results.setdefault(v, []).extend(bench(v, runs))
    for v, vals in results.items():
        if vals:
            log(f'  nmax{v}: median={statistics.median(vals):.2f} mean={statistics.mean(vals):.2f} sd={statistics.stdev(vals):.2f} n={len(vals)}')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    log('=== DONE ===')


if __name__ == '__main__':
    main()
