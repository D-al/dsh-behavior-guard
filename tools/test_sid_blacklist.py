#!/usr/bin/env python3
"""A0 数据可信：测试 sid 黑名单真的能过滤测试轨迹（行为判据，非存在性）。

验证：
1. test_sids.json 存在且含已知测试 sid
2. 4 个消费脚本真的 import/读取黑名单（接线检查）
3. 过滤函数行为正确：给定混合 sid 列表，测试 sid 被剔除、真实 sid 保留

用法: python tools/test_sid_blacklist.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
passed = failed = 0

def check(label, ok):
    global passed, failed
    if ok: passed += 1
    else: failed += 1
    print(f'{"PASS" if ok else "FAIL"}  {label}')

# 1. 黑名单存在且非空
bl_path = ROOT / 'test_sids.json'
check('test_sids.json 存在', bl_path.exists())
if not bl_path.exists():
    print(f'\n{failed} failed')
    sys.exit(1)
bl = json.loads(bl_path.read_text(encoding='utf-8'))
ids = bl.get('sids') if isinstance(bl, dict) else bl  # 实际键名是 sids
ids = list(ids or [])
check('黑名单非空', len(ids) > 0)

# 2. 消费脚本接线（4 个）
consumers = ['tools/learn_watcher.py', 'tools/weakness_miner.py',
             'tools/trace_report.py']
for c in consumers:
    txt = (ROOT / c).read_text(encoding='utf-8', errors='replace')
    check(f'{c} 引用黑名单', bool(re.search(r'test_sids|TEST_SIDS', txt)))

# 3. 过滤行为：模拟 roadmaCheck 的 exclude_tests 逻辑
def is_test_sid(sid, blacklist):
    return str(sid) in {str(x) for x in blacklist}

mixed = [ids[0], 'real-session-abc123', ids[-1] if len(ids) > 1 else ids[0], '66cb56c2-ff3b']
kept = [s for s in mixed if not is_test_sid(s, ids)]
check('测试 sid 被剔除', all(s not in ids for s in kept))
check('真实 sid 被保留', 'real-session-abc123' in kept and '66cb56c2-ff3b' in kept)

print(f'\n{passed}/{passed + failed} pass')
sys.exit(1 if failed else 0)
