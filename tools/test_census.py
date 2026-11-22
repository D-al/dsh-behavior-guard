#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6 判据1：测试收集普查（collection census）

问题：新增测试文件但没接进 run_all.sh → 测试从不执行 → 代码改坏也全绿。
      S22 改坏 self_harness_gate.py 时 43/43 就是这么过的。

做法（抄社区 collection census）：
1. 扫描 tools/ 下所有测试文件（test_*.mjs / test_*.py / *gate*.py with self_test）
2. 解析 run_all.sh 实际执行集合（mjs glob + py 显式列表）
3. diff → missing_in_gate（测试存在但门禁不跑）
4. 与基线快照 diff → 新增/删除测试报警（删除需白名单豁免）

用法: D:/Python/python.exe -B tools/test_census.py [--update-baseline]
退出码: 0=全覆盖且无未声明变更; 1=有缺失或未声明变更
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
RUN_ALL = TOOLS / 'run_all.sh'
BASELINE = TOOLS / '_test_census_baseline.json'
# 允许删除/不在门禁的白名单（需说明理由）
WHITELIST = {
    # 示例: 'test_foo.py': '2026-11-22 已合并进 test_bar.py'
}


def discover_tests():
    """扫描所有测试文件"""
    mjs = {p.name for p in TOOLS.glob('test_*.mjs')}
    py = {p.name for p in TOOLS.glob('test_*.py')}
    # 非 test_ 命名但有 self_test 的脚本
    selftest = set()
    for p in TOOLS.glob('*.py'):
        try:
            text = p.read_text(encoding='utf-8', errors='replace')
            if 'def self_test' in text or '--self-test' in text:
                selftest.add(p.name)
        except OSError:
            pass
    return {'test_*.mjs': mjs, 'test_*.py': py, 'self_test_script': selftest -
            py}  # 已在py里的不重复


def parse_gate():
    """解析 run_all.sh 实际执行集合"""
    text = RUN_ALL.read_text(encoding='utf-8')
    executed = set()
    # mjs: glob 自动全纳入
    if 'tools/test_*.mjs' in text:
        executed |= {p.name for p in TOOLS.glob('test_*.mjs')}
    # py: 显式列表 或 glob 自动发现
    executed |= set(re.findall(r'tools/([\w]+\.py)', text))
    if re.search(r'tools/test_\*\.py', text):
        # glob 模式：所有 test_*.py 自动纳入
        executed |= {p.name for p in TOOLS.glob('test_*.py')}
    return executed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update-baseline', action='store_true')
    args = ap.parse_args()

    discovered = discover_tests()
    all_tests = discovered['test_*.mjs'] | discovered['test_*.py'] | discovered['self_test_script']
    executed = parse_gate()

    missing = sorted(all_tests - executed)
    print(f'[CENSUS] discovered={len(all_tests)} '
          f'(mjs={len(discovered["test_*.mjs"])} py={len(discovered["test_*.py"])} '
          f'selftest={len(discovered["self_test_script"])})')
    print(f'[CENSUS] executed_in_gate={len(executed)}')
    print(f'[CENSUS] missing_in_gate={len(missing)}')
    for m in missing:
        print(f'  MISSING  {m}')

    baseline = {}
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding='utf-8')).get('tests', {})

    added = sorted(all_tests - set(baseline))
    removed = sorted(set(baseline) - all_tests)
    unexplained_removed = [r for r in removed if r not in WHITELIST]
    if added:
        print(f'[CENSUS] newly_added={added}')
    if removed:
        print(f'[CENSUS] removed={removed} (unexplained={unexplained_removed})')

    if args.update_baseline:
        BASELINE.write_text(json.dumps({'tests': sorted(all_tests)}, indent=2), encoding='utf-8')
        print(f'[CENSUS] baseline updated: {BASELINE}')
        return 0

    ok = not missing and not unexplained_removed
    print(f'[CENSUS] VERDICT: {"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
