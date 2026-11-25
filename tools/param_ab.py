# -*- coding: utf-8 -*-
"""轻量参数 A/B：短 prompt + 短生成 + 每变体重启 server + 交叉顺序。

解决之前 nmax_ab.py 的三个问题：
1. 20K prompt 单请求 ~43s → 2K prompt + 64 token 压到 <10s
2. LRU 槽位耦合 → 每变体重启 server（不是每请求）
3. timeout 不够 → 默认 900s

用法：python param_ab.py <标签> <变体1|变体2> [runs]
例：python param_ab.py nmax "--spec-draft-n-max 3|--spec-draft-n-max 5" 4
    python param_ab.py nmax "--spec-draft-n-max 3|--spec-draft-n-max 5" 4
"""
import subprocess, time, urllib.request, json, statistics, os, sys, random, string
from pathlib import Path

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'  # 固定生产 build
MODEL = 'D:/GGUF_Download/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf'
MMPROJ = 'D:/GGUF_Download/Qwen3.6-35B-A3B-mmproj-F16.gguf'
PORT = 8081
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟。" * 200
BASE_ARGS = ['-m', MODEL, '-ngl', '99', '--n-cpu-moe', '40', '-c', '98304', '-np', '1', '-fa', 'on',
             '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0', '-t', '8', '-b', '4096', '-ub', '2048', '-lm', 'none',
             '--mmproj', MMPROJ, '--mmproj-offload', '--moe-cache-mib', '1350', '--moe-cache-cpu-share', '1.0',
             '--port', str(PORT), '--host', '127.0.0.1', '--spec-type', 'draft-mtp',
             '--spec-draft-n-max', '5', '--spec-draft-p-min', '0.8', '--ctx-checkpoints', '2',
             '--cache-ram', '0', '--temp', '0.7', '--top-p', '0.95']


def log(m, LOG):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def wait_health(sec=120):
    for _ in range(sec):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=1).status == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def post(prompt, n=64):
    b = {'model': MODEL, 'prompt': prompt, 'n_predict': n, 'ignore_eos': True,
         'temperature': 0.7, 'stream': False, 'cache_prompt': False}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/completion',
                                 data=json.dumps(b).encode(), headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=180).read())


def start(extra_args, lf):
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(2)
    # 变体参数覆盖 BASE：同名参数替换；"!param" 删除该参数；新参数追加
    args = list(BASE_ARGS)
    toks = extra_args.split()
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.startswith('!'):
            key = t[1:]
            if key in args:
                j = args.index(key)
                del args[j:j + 2]  # 删参数及其值
            i += 1
        elif t.startswith('-') and i + 1 < len(toks):
            key = t
            if key in args:
                j = args.index(key)
                args[j + 1] = toks[i + 1]
            else:
                args.extend([key, toks[i + 1]])
            i += 2
        else:
            i += 1
    lf = open(lf, 'w')
    p = subprocess.Popen([EXE] + args, stdout=lf, stderr=subprocess.STDOUT)
    if not wait_health():
        p.kill(); lf.close(); return None
    return p, lf


def bench_variant(label, extra, runs, LOG):
    r = start(extra, f'D:/Brain/_cleanup_20261118/ab_{label}_srv.log')
    if not r:
        log(f'  {label}: START FAILED', LOG); return []
    p, lf = r
    tps = []
    # 1 次 warm（不同前缀）
    try:
        post('warmup ' + FILLER[:1000], 16)
    except Exception:
        pass
    for k in range(runs):
        tag = ''.join(random.choice(string.ascii_lowercase) for _ in range(32))
        try:
            resp = post(tag + ' ' + FILLER[:2000], 64)
            t = resp['timings']['predicted_per_second']
            tps.append(t)
            log(f'  {label} r{k}: {t:.2f} t/s', LOG)
        except Exception as e:
            log(f'  {label} r{k} ERR {type(e).__name__}', LOG)
    p.terminate()
    try: p.wait(timeout=15)
    except Exception: p.kill()
    lf.close(); time.sleep(2)
    return tps


def main():
    label = sys.argv[1]
    variants = sys.argv[2].split('|')
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    LOG = f'D:/Brain/_cleanup_20261118/ab_{label}.log'
    log(f'=== {label} exe={EXE} runs={runs} variants={variants} ===', LOG)
    results = {v: [] for v in variants}
    # 交叉顺序：v1,v2,v2,v1 抵消热漂移
    order = variants + list(reversed(variants))
    for i, v in enumerate(order):
        log(f'--- round {i}: {v[:60]} ---', LOG)
        results[v].extend(bench_variant(f'{label}_{order.index(v)}_{i}', v, runs, LOG))
    for v, vals in results.items():
        if vals:
            log(f'RESULT {v[:60]}: median={statistics.median(vals):.2f} '
                f'mean={statistics.mean(vals):.2f} sd={statistics.stdev(vals):.2f} n={len(vals)}', LOG)
        else:
            log(f'RESULT {v[:60]}: NO DATA', LOG)
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    log('=== DONE ===', LOG)


if __name__ == '__main__':
    main()
