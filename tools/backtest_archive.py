#!/usr/bin/env python3
"""backtest_archive.py — A1 归档回测（独立、零递归）

为什么需要它：A1 的原判据是 `roadmap_check.py --dry-run`，但 dry-run 会遍历到 A1
并执行它的判据 cmd（又是 dry-run）→ 无限递归。本脚本独立验证"§7 归档项的测试脚本
真实全过"，不读 ROADMAP_GRAPH 的判据、不调用 dry-run，无递归。

输出格式：`PASS <label>` 每行一条，退出码 0 当且仅当全部通过。
"""
import subprocess
import sys

# 12 张归档 done card 对应的真实测试脚本（与 ROADMAP_GRAPH.md 里的 verify.cmd 一致）
TESTS = [
    ('S_GWT',      ['node', 'tools/test_gwt_fep.mjs']),
    ('S_FEP',      ['node', 'tools/test_gwt_fep.mjs']),
    ('S_SCOPE',    ['node', 'tools/test_short_term_goals.mjs']),
    ('S_CRITIC',   ['node', 'tools/test_short_term_goals.mjs']),
    ('S_ARCHIVE',  ['node', 'tools/test_archive_dedup.mjs']),
    ('S_ROLE',     ['node', 'tools/test_role_fixes.mjs']),
    ('S_TRACE',    ['node', 'tools/test_trace_context.mjs']),
    ('S_SECURITY', ['node', 'tools/test_security_boundary.mjs']),
    ('S_OUTCOME',  ['node', 'tools/test_outcome.mjs']),
    ('S_REVIEW',   ['node', 'tools/test_review_loop.mjs']),
    ('S_INJECT',   ['node', 'tools/test_injection_scan.mjs']),
    ('S_BUDGET',   ['node', 'tools/test_injection_budget.mjs']),
]

PY = sys.executable

# 额外：验证 dry-run 的纯统计逻辑（不遍历判据）——用 --graph 的可用性代替，避免递归
EXTRA = [
    ('GRAPH_LOADABLE', [PY, '-B', 'tools/roadmap_check.py', '--graph']),
]


def main():
    passed = failed = 0
    for label, cmd in EXTRA + TESTS:
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            ok = proc.returncode == 0
        except Exception:
            ok = False
        if ok:
            print(f'PASS {label}')
            passed += 1
        else:
            print(f'FAIL {label}')
            failed += 1
    print(f'\nBACKTEST: {passed} PASS / {failed} FAIL')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
