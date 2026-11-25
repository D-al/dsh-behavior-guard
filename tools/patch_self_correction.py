#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 harness index.mjs 打"未闭环自我纠错保留"补丁（防线2）。

缘起（2026-11-26 事故）：dsh 在 seq 481 的 reasoning 里已发现 `@local` bundle 名
是错的并说"应该恢复"，但 compaction（seq 456/528）把线索剔除，最终 seq 646
用坏源码覆盖了 node_modules。根因：harness 的 summarizeAssistant() 只读 text 和
tool-call，主动丢弃 reasoning block；P0 存档去重分支还会 parts.length=0 清空全部。

本补丁做四处最小改动（幂等，重复运行不重复插入）：
  1. 状态加 openCorrections: []
  2. summarizeAssistant 读 reasoning block
  3. assistant/message 监听里检测"自我纠错"并记账
  4. 存档注入：在去重分支【之前】push 未闭环纠错，且把它纳入 archiveSig

用法:
  python tools/patch_self_correction.py --check          # 只检查是否已打补丁
  python tools/patch_self_correction.py --apply          # 打补丁（publish + runtime 两版）
  python tools/patch_self_correction.py --apply --dry-run
"""
import argparse
import re
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]

MARK = 'OPEN_CORRECTION'  # 幂等标记

# 1) 状态字段
OLD_STATE = "lastArchiveSig: '', archiveRepeatCount: 0,  // P0 存档去重：相同存档只完整注入一次（实测 82 次重复）"
NEW_STATE = OLD_STATE + "\n        openCorrections: [],  // 防线2：模型自我发现但未修复的问题（compaction 不得抹掉）"

# 2) summarizeAssistant 读 reasoning
OLD_SUMM = """    if (block.type === 'text' && typeof block.text === 'string') body += block.text
    else if (block.type === 'tool-call') toolCalls += 1
  }
  return { body: body.trim(), toolCalls }"""
NEW_SUMM = """    if (block.type === 'text' && typeof block.text === 'string') body += block.text
    else if (block.type === 'tool-call') toolCalls += 1
    // 防线2：reasoning 里常有"我发现 X 错了，应该修"——事故中被丢弃导致纠错线索丢失
    else if ((block.type === 'reasoning' || block.type === 'thinking') && typeof block.text === 'string') reasoning += block.text
  }
  return { body: body.trim(), toolCalls, reasoning: reasoning.trim() }"""
OLD_SUMM_DECL = """  let body = ''
  let toolCalls = 0
  for (const block of blocks) {"""
NEW_SUMM_DECL = """  let body = ''
  let toolCalls = 0
  let reasoning = ''
  for (const block of blocks) {"""

# 3) assistant/message 监听：检测并记账
OLD_LISTEN = """        s.last = summarizeAssistant(event.data?.message)
        // D5 无进展计数：上一步没有生产性调用（write/edit/todo_write）则 +1，否则清零"""
NEW_LISTEN = """        s.last = summarizeAssistant(event.data?.message)
        // 防线2：抓取 reasoning 里"发现问题但未修复"的线索，供压缩存档强制保留
        try { captureOpenCorrection(s) } catch { /* 纠错抓取失败不影响主流程 */ }
        // D5 无进展计数：上一步没有生产性调用（write/edit/todo_write）则 +1，否则清零"""

# 4) 存档注入：去重分支之前 push，且纳入 archiveSig
OLD_ARCH = """            // 存档签名：初始任务 + todo 状态 + 已排除项。内容不变则视为"同一份存档"。
            archiveSig = JSON.stringify([s.initial, todos.map((t) => [t?.content, t?.status]), (s.rejectedItems || []).slice(-5)])"""
NEW_ARCH = """            // 防线2：未闭环的自我纠错——必须在去重分支之前 push（去重会 parts.length=0 清空）
            if (Array.isArray(s.openCorrections) && s.openCorrections.length) {
              const unresolved = s.openCorrections.filter(c => !c.resolved).slice(-5)
              if (unresolved.length) {
                parts.push('【未闭环的自我纠错】模型曾发现以下问题但尚未修复，继续前先处理：'
                  + unresolved.map((c, i) => (i + 1) + '. ' + c.text.slice(0, 90)).join('；'))
                trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'open_correction_survived_compaction', count: unresolved.length, step: s.step })
              }
            }
            // 存档签名：初始任务 + todo 状态 + 已排除项 + 未闭环纠错。纠错状态变化必须视为"新存档"。
            archiveSig = JSON.stringify([s.initial, todos.map((t) => [t?.content, t?.status]), (s.rejectedItems || []).slice(-5), (s.openCorrections || []).map(c => [c.text, c.resolved])])"""

# 5) 检测函数（插在 summarizeAssistant 之后）
FUNC = """

// ── 防线2：从 reasoning 抓取"自我发现但未修复"的线索 ──
// 事故依据：seq 481 "改成 @local 可能是问题……我应该恢复成 dsh-hardware-monitor"，
// 但 compaction 抹掉后 seq 646 仍用坏源码覆盖。检测要保守：宁可漏报不可误报。
const CORRECTION_RE = /(?:应该|需要|必须|应当|我要|我得)(?:把它|将其|把|将)?(?:改回|恢复|撤销|撤回|还原|修正|改回去|改成|换回|删掉)|(?:可能是?个?问题|是个错误|搞错了|不对劲|这是错的|猜错了|写错了)/;
const CORRECTION_RESOLVED_RE = /(?:已(?:经)?[^。！\n]{0,20}?(?:改回|恢复|撤销|撤回|还原|修正|修复|改成|改好)|已完成修复|now fixed|已改好|已修正)/;
function captureOpenCorrection(s) {
  if (!s || !s.last || !s.last.reasoning) return
  const reasoning = String(s.last.reasoning)
  if (!Array.isArray(s.openCorrections)) s.openCorrections = []
  // 先看是否已解决：后续 reasoning 明确说"已修复"则把现存条目标记 resolved（保留历史供审计）
  if (CORRECTION_RESOLVED_RE.test(reasoning)) {
    for (const c of s.openCorrections) if (!c.resolved) c.resolved = true
    return
  }
  if (!CORRECTION_RE.test(reasoning)) return
  // 同一线索只记一次（用后 240 字去重）
  const key = reasoning.slice(-240).trim()
  if (s.openCorrections.some(c => c.key === key)) return
  s.openCorrections.push({ key, text: key, resolved: false, at: Date.now() })
  if (s.openCorrections.length > 20) s.openCorrections = s.openCorrections.slice(-20)
  try {
    trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'open_correction_captured', step: s.step, text: key.slice(0, 120) })
  } catch { /* trace 失败不影响 */ }
}
"""


def patch_file(path: Path, dry_run: bool, check_only: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    text = path.read_text(encoding='utf-8')
    has_mark = MARK in text
    if check_only:
        return has_mark, f'{"已打补丁" if has_mark else "未打补丁"} {path}'
    if has_mark:
        return True, f'已打补丁，跳过 {path}'

    changes = [
        (OLD_STATE, NEW_STATE, 'state field'),
        (OLD_SUMM_DECL, NEW_SUMM_DECL, 'summarize decl'),
        (OLD_SUMM, NEW_SUMM, 'summarize body'),
        (OLD_LISTEN, NEW_LISTEN, 'assistant listener'),
        (OLD_ARCH, NEW_ARCH, 'archive sig'),
    ]
    out = text
    applied = []
    for old, new, label in changes:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
        applied.append(label)

    # 插入检测函数（在 summarizeAssistant 函数之后）
    anchor = 'const CLAIM_PATTERNS = [WRITE_CLAIM, FUTURE_CLAIM, WILL_CLAIM]'
    if anchor not in out:
        return False, f'FAIL {path.name}: 找不到函数插入锚点'
    out = out.replace(anchor, FUNC + '\n' + anchor, 1)
    applied.append('capture function')

    # 幂等标记
    out = out.replace('const CLAIM_PATTERNS = [WRITE_CLAIM, FUTURE_CLAIM, WILL_CLAIM]',
                      f'// {MARK}-PATCHED (2026-11-26)\nconst CLAIM_PATTERNS = [WRITE_CLAIM, FUTURE_CLAIM, WILL_CLAIM]', 1)

    if not dry_run:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry_run else ""}OK {path.name}: {", ".join(applied)}'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    if not args.check and not args.apply:
        ap.print_help()
        return 2
    ok_all = True
    for p in TARGETS:
        ok, msg = patch_file(p, args.dry_run, args.check)
        print(msg)
        ok_all = ok_all and ok
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
