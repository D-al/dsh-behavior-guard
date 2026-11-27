# -*- coding: utf-8 -*-
"""critbank 一致性门禁（2026-11-27 根治双副本漂移 + 裸文件名复发）

检查三件事（fail-closed）：
  1. config/critbank.json 与 bench/critbank.json SHA256 一致
  2. lesson 里无裸文件名 `verify_agent.py`（必须是绝对路径）
  3. 条目 ID 连续无缺（C-001..C-N）

用法: python tools/critbank_gate.py
退出码: 0=通过, 1=漂移, 2=文件缺失/损坏

依据: docs/CAPABILITY_MISMATCH_P1_EXECUTED_20261127.md 待办
"""
import hashlib, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config' / 'critbank.json'
BENCH = Path('D:/Brain/workspace/bench/critbank.json')
BARE = re.compile(r'(?<![/\\A-Za-z0-9:])verify_agent\.py')

errors = []

if not CONFIG.is_file():
    print('FATAL: config/critbank.json 缺失'); sys.exit(2)
if not BENCH.is_file():
    print('FATAL: bench/critbank.json 缺失'); sys.exit(2)

h1 = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
h2 = hashlib.sha256(BENCH.read_bytes()).hexdigest()
if h1 != h2:
    errors.append(f'副本漂移: config={h1[:16]} bench={h2[:16]}（运行版读 bench；发布版读 config）')

try:
    data = json.loads(BENCH.read_text(encoding='utf-8'))
except Exception as e:
    print('FATAL: bench/critbank.json JSON 损坏:', e); sys.exit(2)

ids = [x.get('id') for x in data if isinstance(x, dict)]
expected = [f'C-{i:03d}' for i in range(1, len(ids) + 1)]
if ids != expected:
    errors.append(f'ID 不连续: 实际={ids} 期望={expected}')

for x in data:
    if not isinstance(x, dict): continue
    lesson = str(x.get('lesson', ''))
    if BARE.search(lesson):
        errors.append(f'{x.get("id")} lesson 含裸文件名 verify_agent.py（模型看不到脚本路径）')
    for key in ('id', 'tags', 'signal', 'lesson', 'source'):
        if key not in x:
            errors.append(f'{x.get("id")} 缺字段 {key}')

if errors:
    print('CRITBANK GATE FAIL')
    for e in errors: print('  -', e)
    sys.exit(1)
print(f'CRITBANK GATE OK: {len(data)} 条, sha256={h1[:16]}, 两副本一致, 无裸文件名')
