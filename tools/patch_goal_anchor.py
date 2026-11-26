#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""目标锚定加固：anchorInitial 跨 state 重建持久化（2026-11-26）

发现：part1 的 anchorInitial 存在 s 上，但 state 在压缩后会重建，
重建时 s.initial 已被覆盖成最新指令 → 锚定失效。实测存档 seq180/977/1308
的【初始任务】从"修插件"→"ERR_CONNECTION_REFUSED"→"左侧入口"漂移了三次。

修复：用模块级 Map（key=sessionId）持久化最初目标，state 重建后仍可恢复。
幂等标记：GOAL_ANCHOR-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'GOAL_ANCHOR-PATCHED'

OLD_STATES = "  const states = new Map()"
NEW_STATES = """  const states = new Map()
  // 目标锚定（2026-11-26）：模块级持久化最初用户目标——state 在压缩后会重建，
  // 存在 s 上的 anchorInitial 会丢失，实测存档【初始任务】漂移了三次。
  const goalAnchors = new Map()"""

OLD_ANCHOR = """        // 行为根因 P1：目标锚定——s.anchorInitial 是不可变的用户初始目标（不被 latest 覆盖）
        try {
          if (!s.anchorInitial && s.initial) s.anchorInitial = String(s.initial)
          if (!s.anchorSet && s.initial) { s.anchorSet = true; s.anchorInitial = String(s.initial) }
        } catch { /* ignore */ }"""
NEW_ANCHOR = """        // 行为根因 P1：目标锚定——从模块级 Map 恢复（跨 state 重建不丢）
        try {
          const sk = String(s.sid || '')
          if (sk) {
            // 首次：以当前 s.initial 为准写入 Map（此时它还是最初的 user message）
            if (!goalAnchors.has(sk) && s.initial) goalAnchors.set(sk, String(s.initial))
            // 恢复：state 重建后 s.initial 可能已被污染，用 Map 里的原始目标覆盖回来
            const anchored = goalAnchors.get(sk)
            if (anchored && s.initial !== anchored) s.initial = anchored
          }
        } catch { /* ignore */ }"""

OLD_ARCHIVE = "          parts.push('【初始任务】' + s.initial)"
NEW_ARCHIVE = """          // 目标锚定：存档里的【初始任务】必须用模块级锚点，不用可能被覆盖的 s.initial
          try {
            const ak = String(s.sid || '')
            const anchored = goalAnchors.get(ak)
            if (anchored) s.initial = anchored
          } catch { /* ignore */ }
          parts.push('【初始任务】' + s.initial)"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已打补丁" if MARK in t else "未打补丁"} {path}'
    if MARK in t:
        return True, f'已打补丁跳过 {path.name}'
    out = t
    for old, new, label in [(OLD_STATES, NEW_STATES, 'goalAnchors map'),
                             (OLD_ANCHOR, NEW_ANCHOR, 'anchor restore'),
                             (OLD_ARCHIVE, NEW_ARCHIVE, 'archive uses anchor')]:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    out = out.replace('  const states = new Map()', f'  // {MARK} (2026-11-26)\n  const states = new Map()', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 3锚点'


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
