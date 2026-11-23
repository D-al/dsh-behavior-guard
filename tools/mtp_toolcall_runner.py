# -*- coding: utf-8 -*-
"""MTP on/off 的工具调用准确率 A/B。
每题跑 REPS 次，统计工具名+参数正确率，以及"该不该调用"的决策正确率。
"""
import subprocess, time, urllib.request, json, statistics, sys
from pathlib import Path
sys.path.insert(0, 'D:/Brain/publish/dsh-behavior-guard/tools')
from toolcall_bench import TOOLS, CASES, grade

LOG = Path('D:/Brain/_cleanup_20261118/mtp_toolcall.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
PRESET = 'D:/Brain/_cleanup_20261118/preset_A_40_1350.ini'
PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
REPS = 2   # 每题重复次数（先 1 次快速看差异）

BASE = [EXE, '--models-preset', PRESET, '--models-max', '1', '--models-memory-margin', '450',
        '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', 'q4_0',
        '-t', '6', '-b', '4096', '-ub', '2048', '-lm', 'none',
        '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1']
MTP = ['--spec-type', 'draft-mtp', '--spec-draft-n-max', '5', '--spec-draft-p-min', '0.8',
       '--ctx-checkpoints', '2', '--cache-ram', '0']

def wait_health(seconds=240):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def ask(case):
    body = {'model': MODEL, 'messages': [{'role': 'user', 'content': case['q']}],
            'tools': TOOLS, 'temperature': 0.7, 'max_tokens': 700, 'stream': False}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    ch = r['choices'][0]
    return ch['message'], ch.get('finish_reason')

def run_cell(label, extra_args):
    log(f'=== CELL {label} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', 'w')
    p = subprocess.Popen(BASE + extra_args, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health()
    log(f'health={sec}s' if sec else 'TIMEOUT')
    if not sec:
        p.terminate(); logf.close(); return None
    # 加载
    try:
        ask(dict(q='你好', id='warm', cat='warm', tool=None))
    except Exception as e:
        log(f'warm ERR {e}')
    results = []
    for case in CASES:
        for rep in range(REPS):
            try:
                msg, fr = ask(case)
                ok, detail = grade(case, msg, fr)
            except Exception as e:
                ok, detail = False, f'ERR {type(e).__name__}'
            results.append((case, ok, detail))
            log(f'{label:8} {case["id"]:3} [{case["cat"]:10}] {"PASS" if ok else "FAIL"} {detail}')
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
    # 汇总
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    bycat = {}
    for c, ok, _ in results:
        bycat.setdefault(c['cat'], [0, 0])
        bycat[c['cat']][0] += 1 if ok else 0
        bycat[c['cat']][1] += 1
    log(f'{label:8} TOTAL {passed}/{total} = {100.0*passed/total:.1f}%')
    for cat, (a, b) in sorted(bycat.items()):
        log(f'{label:8}   {cat:10} {a}/{b}')
    return passed, total, bycat

out = {}
for label, extra in [('mtp_on', MTP), ('mtp_off', [])]:
    r = run_cell(label, extra)
    if r: out[label] = r
log('=== SUMMARY ===')
for k, v in out.items():
    log(f'{k}: {v[0]}/{v[1]} ({100.0*v[0]/v[1]:.1f}%)')
log('=== MTP TOOLCALL DONE ===')
