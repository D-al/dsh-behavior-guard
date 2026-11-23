# -*- coding: utf-8 -*-
"""只测 MoE cache 命中率/上传量（机制判据，比墙钟可靠）。
关键：优雅关闭（CTRL_BREAK_EVENT）才能触发 ~impl() -> log_stats()。
"""
import subprocess, time, urllib.request, json, signal, os
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/cache_hitrate.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
PORT = 8091
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
FILLER = "混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，预填充瓶颈在 GPU 矩阵乘。" * 500

CFGS = [
    ('A_40_1350', 'D:/Brain/_cleanup_20261118/preset_A_40_1350.ini'),
    ('C1_41_1700', 'D:/Brain/_cleanup_20261118/preset_C_41_1700.ini'),
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

for label, preset in CFGS:
    log(f'=== CELL {label} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [EXE, '--models-preset', preset, '--models-max', '1', '--models-memory-margin', '450',
            '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0',
            '-t', '6', '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1', '-lv', '4']
    srvlog = f'D:/Brain/_cleanup_20261118/{label}_hr.log'
    logf = open(srvlog, 'w')
    # CREATE_NEW_PROCESS_GROUP 以便发 CTRL_BREAK 触发优雅退出
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    sec = wait_health()
    log(f'health={sec}s' if sec else 'TIMEOUT')
    if not sec:
        p.kill(); logf.close(); continue
    try:
        post('/completion', {'model': MODEL, 'prompt': FILLER[:8000], 'n_predict': 32,
                             'ignore_eos': True, 'stream': False, 'cache_prompt': False})
    except Exception as e:
        log(f'LOAD ERR {e}'); p.kill(); logf.close(); continue
    # 固定工作量：20 次 20K decode（每次 96 token），保证两配置可比
    for i in range(20):
        try:
            post('/completion', {'model': MODEL, 'prompt': FILLER[:20000], 'n_predict': 96,
                                 'ignore_eos': True, 'temperature': 0.7, 'stream': False,
                                 'cache_prompt': True})
        except Exception as e:
            log(f'gen{i} ERR {type(e).__name__}')
    log('workload done, graceful shutdown...')
    # 优雅关闭
    try:
        p.send_signal(signal.CTRL_BREAK_EVENT)
    except Exception as e:
        log(f'CTRL_BREAK failed {e}')
        try: os.kill(p.pid, signal.CTRL_BREAK_EVENT)
        except Exception: pass
    try: p.wait(timeout=60)
    except Exception:
        log('graceful timeout, kill'); p.kill()
    logf.flush(); logf.close()
    time.sleep(2)
    # 解析命中率
    try:
        txt = open(srvlog, errors='replace').read()
        found = False
        for line in txt.splitlines():
            if 'llama_moe_cache' in line:
                log('HIT ' + line.strip()[:200]); found = True
            if 'MoE cache size' in line:
                log('CFG ' + line.strip()[:170])
        if not found: log('!! 无命中率日志（可能未优雅退出）')
    except Exception as e:
        log(f'parse ERR {e}')
    time.sleep(2)
log('=== HITRATE DONE ===')
