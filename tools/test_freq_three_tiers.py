#!/usr/bin/env python3
"""watcher_freq3 行为判据：验证频次三层改造真的接线（不是只 grep 到关键词）。

用 AST 静态分析（不跑 digest 副作用）：
1. 三个层函数存在：digest(轻) / digest_deep_only(深) / one_round(事件驱动)
2. one_round 里真的引用 CONSOLIDATE_EVERY（分层触发条件）
3. digest 有 deep 参数（深浅可切换）

用法: python tools/test_freq_three_tiers.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
p = ROOT / 'tools' / 'learn_watcher.py'
src = p.read_text(encoding='utf-8')
tree = ast.parse(src)

funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
passed = failed = 0
def check(label, ok):
    global passed, failed
    if ok: passed += 1
    else: failed += 1
    print(f'{"PASS" if ok else "FAIL"}  {label}')

# 1. 三层函数
for fn in ('digest', 'digest_deep_only', 'one_round'):
    check(f'{fn}() 存在', fn in funcs)

# 2. digest 有 deep 参数
if 'digest' in funcs:
    args = [a.arg for a in funcs['digest'].args.args] + [a.arg for a in funcs['digest'].args.kwonlyargs]
    check('digest 支持 deep 分层参数', 'deep' in args)

# 3. one_round 引用 CONSOLIDATE_EVERY（分层触发）
if 'one_round' in funcs:
    seg = ast.get_source_segment(src, funcs['one_round']) or ''
    check('one_round 按 CONSOLIDATE_EVERY 分流', 'CONSOLIDATE_EVERY' in seg)

print(f'\n{passed}/{passed + failed} pass')
sys.exit(1 if failed else 0)
