#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精修：目标锚定改叠加语义 + handoff 正则收紧（2026-11-26）

子任务复核指出：
1. 目标锚定当前是"覆盖回最初目标"，但崩溃/连接失败是用户**合法新增目标**，
   覆盖会丢掉它们。改为 goalStack 叠加：原始目标 + 新增目标都保留。
2. handoff 正则太宽，"请确认"类正常提问可能误报。收紧为三条件：
   指令性移交 + 代码/控制台证据 + JS 全局对象证据。

幂等标记：BEHAVIOR_REFINE-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'BEHAVIOR_REFINE-PATCHED'

# 1. handoff 正则收紧
OLD_HANDOFF = """        const handoffRe = /(?:F12|控制台|粘贴.*(?:代码|脚本)|手动(?:执行|运行)|请你(?:自己|手动)|复制到.*控制台)/i
        if (handoffRe.test(body) && state.toolCalls === 0) {"""
NEW_HANDOFF = """        // 收紧（2026-11-26 复核）：三条件——指令性移交 + 代码/控制台证据 + JS全局对象证据。
        // 避免把"请确认走哪个方案"这类正常提问误判为放弃式交付。
        const handoffRe = /(?:打开|按|去|请).{0,8}(?:F12|控制台)|(?:粘贴|复制).{0,12}(?:代码|脚本|到.*控制台)|(?:手动|自行)(?:执行|运行)/i
        const jsEvidenceRe = /(?:window\\.|document\\.|Object\\.keys\\(|console\\.log|querySelector|__ModuleLoader__)/i
        const isHandoff = handoffRe.test(body) && jsEvidenceRe.test(body) && state.toolCalls === 0
        if (isHandoff) {"""
OLD_HANDOFF_TRACE = "step: state.step, blocked: handoffRe.test(body) })"
NEW_HANDOFF_TRACE = "step: state.step, blocked: isHandoff })"

# 2. 目标锚定：叠加语义
OLD_ANCHOR = """            const anchored = goalAnchors.get(sk)
            // 叠加语义：合法新增目标（崩溃/连接失败）不该被抹掉——加进 goalStack 而非覆盖。
            if (anchored) {
              if (!goalAnchors.has(sk + ':stack')) goalAnchors.set(sk + ':stack', [anchored])
              const stack = goalAnchors.get(sk + ':stack')
              // 新增目标在 s.latest（每条 user message 更新），s.initial 只首次赋值不覆盖。
              // 用 latest 才能把"崩溃/连接失败"这类用户后续明确目标加进栈。
              const cur = String(s.latest || s.initial || '').slice(0, 100)
              if (cur && !stack.some((g) => String(g).slice(0, 100) === cur) && !/^(?:<system-reminder>|harness)/i.test(cur)) {
                stack.push(cur)
                if (stack.length > 4) stack.shift()
              }
              // 存档里显示完整目标栈（原始 + 新增），不丢合法新目标
              s.goalStack = stack.slice()
            }"""
# anchor 已在 patch_goal_anchor.py + 手动 s.latest 修正中完成，本补丁不再改它
NEW_ANCHOR = OLD_ANCHOR

OLD_ARCHIVE = """          // 目标锚定：存档里的【初始任务】必须用模块级锚点，不用可能被覆盖的 s.initial
          try {
            const ak = String(s.sid || '')
            const anchored = goalAnchors.get(ak)
            if (anchored) s.initial = anchored
          } catch { /* ignore */ }
          parts.push('【初始任务】' + s.initial)"""
NEW_ARCHIVE = """          // 目标锚定（叠加）：原始目标 + 合法新增目标都显示，避免压缩把目标漂移固化
          try {
            const ak = String(s.sid || '')
            const anchored = goalAnchors.get(ak)
            const stack = goalAnchors.get(ak + ':stack') || (anchored ? [anchored] : [])
            if (stack.length > 1) {
              parts.push('【初始任务（原始）】' + String(stack[0]).slice(0, 300))
              parts.push('【后续新增目标（均为用户明确提出）】' + stack.slice(1).map((g, i) => (i + 1) + '. ' + String(g).slice(0, 120)).join('；'))
            } else if (anchored) {
              parts.push('【初始任务】' + anchored)
            } else {
              parts.push('【初始任务】' + s.initial)
            }
          } catch { /* ignore */ parts.push('【初始任务】' + s.initial) }"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已打补丁" if MARK in t else "未打补丁"} {path}'
    if MARK in t:
        return True, f'已打补丁跳过 {path.name}'
    out = t
    for old, new, label in [
        (OLD_HANDOFF, NEW_HANDOFF, 'handoff regex'),
        (OLD_HANDOFF_TRACE, NEW_HANDOFF_TRACE, 'handoff trace'),
        (OLD_ARCHIVE, NEW_ARCHIVE, 'archive goal stack'),
    ]:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    out = out.replace('  // GOAL_ANCHOR-PATCHED (2026-11-26)',
                      f'  // {MARK} (2026-11-26)\n  // GOAL_ANCHOR-PATCHED (2026-11-26)', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 4锚点'


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
