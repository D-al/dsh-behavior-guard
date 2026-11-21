#!/usr/bin/env python3
"""战略对齐检查单测（2026-11-21）。

验证 roadmap_check.validate_strategy_alignment：
- 违反非目标 → 拒绝
- 触及元治理且 autonomous → 拒绝
- 正常卡 → 通过
- 人工卡（autonomous=False）触及元治理 → 通过（由人类推进，非 agent 自改）

只读，不改任何文件。
"""
import os
import sys
from pathlib import Path

# run_all.sh 优先用 PATH 里的 python3，但该解释器无 PyYAML。
# 自检并 re-exec 到带 yaml 的解释器，避免"测试没跑就假 FAIL"。
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    alt = Path('D:/Python/python.exe')
    if alt.exists() and Path(sys.executable).resolve() != alt.resolve():
        os.execv(str(alt), [str(alt), str(Path(__file__).resolve())] + sys.argv[1:])
    raise

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_check as rc

CASES = [
    ({'id': 'T1', 'autonomous': True},
     {'T1': {'strategy_flags': {'violates_non_goal': '数字生命'}}},
     False, '违反非目标应拒绝'),
    ({'id': 'T2', 'autonomous': True},
     {'T2': {'strategy_flags': {'touches_metagovernance': True}}},
     False, 'autonomous治理卡应拒绝'),
    ({'id': 'T3', 'autonomous': True},
     {'T3': {'strategy_flags': {'touches_metagovernance': False}}},
     True, '正常卡应通过'),
    ({'id': 'T4', 'autonomous': False},
     {'T4': {'strategy_flags': {'touches_metagovernance': True}}},
     True, '人工治理卡应通过'),
    ({'id': 'T5', 'autonomous': True},
     {}, True, '无flags的旧卡应兼容通过'),
]

passed = failed = 0
for item, sem, expect_ok, label in CASES:
    ok, why = rc.validate_strategy_alignment(item, sem)
    if ok == expect_ok:
        print(f'PASS  {label}')
        passed += 1
    else:
        print(f'FAIL  {label}: expected={expect_ok} got={ok} ({why})')
        failed += 1

print(f'\n{passed}/{passed + failed} pass')
sys.exit(1 if failed else 0)
