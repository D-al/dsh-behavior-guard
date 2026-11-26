#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 sync_missing_mechanisms 的空壳 bug（2026-11-26 22:2x）

长任务实证发现：同步进运行版的 M3 patternLock 与 工具失败自愈**实际是死的**——
只加了 import 和调用点，漏了状态来源填充：
  - s.toolWindow 从没被 push → `s.toolWindow?.length >= 12` 恒 false → pattern_lock 恒 0
  - s.toolNamesById 从没被赋值 → extractFailure 拿不到工具名 → tool_failure 恒 0
  - s.pendingHeal 置位后没有消费点（pre-step 注入缺失）

本补丁补齐 3 处缺失的状态链。幂等标记：SYNC_MECH_FIX-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'SYNC_MECH_FIX-PATCHED'

# 1. state 初始化补 toolWindow 等
OLD_STATE = """        bdi: { goal: '', belief: '', preference: '', updatedAt: 0 } }"""
NEW_STATE = """        bdi: { goal: '', belief: '', preference: '', updatedAt: 0 },
        // 2026-11-26 修：M3 反模式锁 + S24 自愈的状态容器（此前缺失导致机制恒不触发）
        toolWindow: [], goalRestatedStep: 0, lastPatternLockStep: -99,
        toolNamesById: new Map(), pendingHeal: null, healInjectedThisTurn: 0, healInjectedTotal: 0 }"""

# 2. tool/call 填充 toolWindow + toolNamesById
OLD_TOOLCALL = """      if (event.type === 'tool/call') {
        // turn-guard：工具调用计数 + writeTools 计数（L2/L3 判定依据）
        s.toolCalls += 1"""
NEW_TOOLCALL = """      if (event.type === 'tool/call') {
        // turn-guard：工具调用计数 + writeTools 计数（L2/L3 判定依据）
        s.toolCalls += 1
        // 2026-11-26 修：M3 滑窗 + S24 callId→工具名映射（此前从未填充 → 两机制恒不触发）
        try {
          const _tn0 = String(event.data?.name || '')
          if (!Array.isArray(s.toolWindow)) s.toolWindow = []
          s.toolWindow.push(_tn0)
          if (s.toolWindow.length > 24) s.toolWindow.shift()
          const _cid0 = String(event.data?.callId || '')
          if (_cid0 && _tn0) { if (!(s.toolNamesById instanceof Map)) s.toolNamesById = new Map(); s.toolNamesById.set(_cid0, _tn0) }
        } catch { /* 状态填充失败不影响主流程 */ }"""

# 3. user/message 锚点 goalRestatedStep
OLD_USERANCHOR = """          s.latest = t.slice(0, 1000)"""
NEW_USERANCHOR = """          s.latest = t.slice(0, 1000)
          s.goalRestatedStep = s.step  // 2026-11-26 修：M3 目标重述锚点"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已修" if MARK in t else "未修"} {path.parent.name}'
    if MARK in t:
        return True, f'已修跳过 {path.parent.name}'
    out = t
    for old, new, label in [(OLD_STATE, NEW_STATE, 'state init'),
                            (OLD_TOOLCALL, NEW_TOOLCALL, 'toolWindow+map'),
                            (OLD_USERANCHOR, NEW_USERANCHOR, 'goalRestatedStep')]:
        if old not in out:
            return False, f'FAIL 锚点 [{label}] 不存在'
        out = out.replace(old, new, 1)
    out = out.replace('// SYNC_MECHANISMS-PATCHED (2026-11-26)',
                      f'// {MARK} (2026-11-26)\n// SYNC_MECHANISMS-PATCHED (2026-11-26)', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.parent.name}: 3锚点'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not a.check and not a.apply:
        ap.print_help(); return 2
    ok_all = True
    for p in TARGETS:
        ok, msg = patch(p, a.dry_run, a.check)
        print(msg); ok_all = ok_all and ok
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
