# -*- coding: utf-8 -*-
"""GDN patch A/B runner: start server with urllib health check, run decode probe.
Launched via scheduled task (interactive, full speed). No PowerShell IWR.
"""
import subprocess, sys, time, urllib.request, os, signal
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/gdn_ab2.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

PY = 'D:/Python/python.exe'
PROBE = 'D:/Brain/publish/dsh-behavior-guard/tools/engine_decode_probe.py'
PRESET = 'D:/Brain/publish/dsh-behavior-guard/config/llama-router-preset.ini'
CONFIGS = [
    ('gdn3_patch', 'D:/llama-gdn-src/build-gdn/bin/llama-server.exe', 8081),
    ('gdn3_stock', 'D:/llama-master-src/build/bin/llama-server.exe', 8081),
]

def wait_health(port, seconds=120):
    for i in range(seconds):
        try:
            r = urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=2)
            if r.status == 200: return i+1
        except Exception: pass
        time.sleep(1)
    return None

for label, exe, port in CONFIGS:
    log(f'CELL {label} exe={exe}')
    subprocess.run(['taskkill','/F','/IM','llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [exe, '--models-preset', PRESET, '--models-max', '1',
            '--models-memory-margin', '450', '--port', str(port), '--host', '127.0.0.1']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_server.log', 'w')
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health(port)
    log(f'health after {sec}s' if sec else 'health TIMEOUT')
    if sec:
        r = subprocess.run([PY, '-B', PROBE, str(port), label, '5', '2'],
                           capture_output=True, text=True, timeout=600)
        for line in r.stdout.splitlines(): log(line)
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== GDN A/B2 DONE ===')
