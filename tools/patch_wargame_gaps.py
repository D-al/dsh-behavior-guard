#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补修攻防演练全修遗漏的 4 个 gap（2026-11-26 17:4x）

子任务复核发现 patch_wargame_fixes.py 有四处不达标：
  D2 预算 3/8 让第4次甩锅穿透，不是"持续到标记清除"
  D3 safetyFlags 仍每轮清零，跨轮拦截不延续
  D7 纯文本 >40 字含卡点/阶段性就清 criticRejected——seq1649 正好命中
  D8 settings.section 在 asar 中不存在（只有 settings.section.icon）→
     用途映射必须配存在性白名单，否则推荐假 slot

修复：
  1. 模块级 safetyFlagsMap（仿 goalAnchors），跨 state 重建持久
  2. turn/start 只清 safetyBlockCount，不清 safetyFlags
  3. 删掉纯文本清 criticRejected，只认工具调用为修正
  4. 预算从"停止拦截"改为"升级措辞"，持续拦截直到标记清除；会话硬上限 20 兜底
  5. slot 用途映射加存在性白名单

幂等标记：WARGAME_GAPS-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'WARGAME_GAPS-PATCHED'

# 1. 模块级 safetyFlagsMap + state 引用同一对象
OLD_MAP = """  const goalAnchors = new Map()
  const consumedFeedback = new Set()"""
NEW_MAP = """  const goalAnchors = new Map()
  // 安全闸门标记跨轮/跨 state 重建持久（2026-11-26 gap 补修）：
  // state 里的 safetyFlags 引用这个 Map 里的对象；turn/start 只清计数不清标记。
  const safetyFlagsMap = new Map()
  const consumedFeedback = new Set()"""

OLD_STATEFLAG = """        safetyFlags: {}, safetyBlockCount: 0, safetySessionBlocks: 0, lastProductHash: '', repeatedWriteCount: 0,"""
NEW_STATEFLAG = """        safetyFlags: (() => { const k = String(id || ''); if (!safetyFlagsMap.has(k)) safetyFlagsMap.set(k, {}); return safetyFlagsMap.get(k) })(),
        safetyBlockCount: 0, safetySessionBlocks: 0, lastProductHash: '', repeatedWriteCount: 0,"""

# 2. turn/start 不清 flags
OLD_RESET = """        s.safetyBlockCount = 0; s.safetyFlags = {}"""
NEW_RESET = """        // gap 补修：safetyFlags 跨轮持久（不清），只清本轮计数
        s.safetyBlockCount = 0"""

# 3. 删纯文本清 criticRejected
OLD_CLEAR = """        // 安全闸门：模型输出"阶段性报告/卡点说明"（非甩锅、非空话）→ 清 criticRejected
        try {
          if (s.safetyFlags && s.safetyFlags.criticRejected && s.last?.body && s.last.body.length > 40 &&
              /(?:已完成|已确认|卡点|阶段性|未能|无法|阻塞|下一步)/.test(s.last.body) && s.last.toolCalls === 0) {
            delete s.safetyFlags.criticRejected
            info('behavior-guard: safetyFlag criticRejected cleared by status report')
          }
        } catch { /* ignore */ }
"""
NEW_CLEAR = """        // gap 补修（2026-11-26）：删除"纯文本报告清 criticRejected"——
        // seq1649 的"阶段性卡点报告"正好命中，等于换个说法就清除。
        // criticRejected 现在只由真实工具调用（写/命令）清除，见 tool/call 段。
"""

# 4. tool/call 里加 criticRejected 由工具清除（写/命令类）
OLD_TOOLCLEAR = """          if (s.safetyFlags && s.safetyFlags.forceStop && (cfg.writeTools.includes(tn) || ['pwsh','bash','exec'].includes(tn))) {
            delete s.safetyFlags.forceStop; info('behavior-guard: safetyFlag forceStop cleared by action=' + tn)
          }"""
NEW_TOOLCLEAR = """          if (s.safetyFlags && s.safetyFlags.forceStop && (cfg.writeTools.includes(tn) || ['pwsh','bash','exec'].includes(tn))) {
            delete s.safetyFlags.forceStop; info('behavior-guard: safetyFlag forceStop cleared by action=' + tn)
          }
          // gap 补修：criticRejected 只由真实修正动作（写/命令）清除，纯文本报告不算
          if (s.safetyFlags && s.safetyFlags.criticRejected && (cfg.writeTools.includes(tn) || ['pwsh','bash','exec'].includes(tn))) {
            delete s.safetyFlags.criticRejected; info('behavior-guard: safetyFlag criticRejected cleared by action=' + tn)
          }"""

# 5. 预算：持续拦截（改成升级措辞），会话硬上限 20
OLD_GATE = """        if (hardFlags.length && (state.safetyBlockCount || 0) < 3 && (state.safetySessionBlocks || 0) < 8) {
          state.safetyBlockCount = (state.safetyBlockCount || 0) + 1
          state.safetySessionBlocks = (state.safetySessionBlocks || 0) + 1
          state.sharedInjections += 1
          // 兼容旧字段：同步置位，让下游旧逻辑也能读到
          state.forceStop = !!(sf.forceStop || state.forceStop)
          state.criticRejected = !!(sf.criticRejected || state.criticRejected)
          trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'safety_gate_block',
            step: state.step, flags: hardFlags, n: state.safetyBlockCount })
          agent.steer(createSteeringMessage(
            '[harness 安全闸门] 本轮不能结束（第 ' + state.safetyBlockCount + ' 次拦截）：' + hardFlags.join('；') + '。'
            + '这些标记只会在你真正调用工具修正/验证后清除——输出纯文本报告不算完成。'
            + '下一步：调用工具修正产物，或跑验证命令确认。', 'behavior-guard'))
          return
        }
        if (hardFlags.length && ((state.safetyBlockCount || 0) >= 3 || (state.safetySessionBlocks || 0) >= 8)) {
          trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'safety_gate_exhausted',
            step: state.step, flags: hardFlags, n: state.safetyBlockCount })
        }"""
NEW_GATE = """        // gap 补修：持续拦截直到标记清除——预算不再停止拦截，只升级措辞。
        // 会话硬上限 20 是极端兜底（模型死活不调用工具时避免永久卡死）。
        if (hardFlags.length && (state.safetySessionBlocks || 0) < 20) {
          state.safetyBlockCount = (state.safetyBlockCount || 0) + 1
          state.safetySessionBlocks = (state.safetySessionBlocks || 0) + 1
          state.sharedInjections += 1
          state.forceStop = !!(sf.forceStop || state.forceStop)
          state.criticRejected = !!(sf.criticRejected || state.criticRejected)
          trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'safety_gate_block',
            step: state.step, flags: hardFlags, n: state.safetyBlockCount, sessionN: state.safetySessionBlocks })
          const n = state.safetyBlockCount
          const msg = n <= 2
            ? '这些标记只会在你真正调用工具修正/验证后清除——输出纯文本报告不算完成。下一步：调用工具修正产物，或跑验证命令确认。'
            : n <= 5
              ? '已连续拦截 ' + n + ' 次仍未修正。停止文字说明，立即调用 write/pwsh 工具修正产物或验证。'
              : '已拦截 ' + n + ' 次。这是未完成交付；只有工具调用能解除拦截。不要再用文字声称完成。'
          agent.steer(createSteeringMessage('[harness 安全闸门] 本轮不能结束（第 ' + n + ' 次）：' + hardFlags.join('；') + '。' + msg, 'behavior-guard'))
          return
        }
        if (hardFlags.length && (state.safetySessionBlocks || 0) >= 20) {
          trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'safety_gate_exhausted',
            step: state.step, flags: hardFlags, n: state.safetyBlockCount })
        }"""

# 6. slot 用途映射加存在性白名单
OLD_SLOTFN = """function checkSlotUsage(filePath, state) {
  const issues = []
  try {
    const p = path.isAbsolute(String(filePath)) ? String(filePath) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(filePath))
    if (!/client\\.js$/i.test(p) || !existsSync(p)) return issues
    const text = readFileSync(p, 'utf8')
    const slots = [...String(text).matchAll(/ctx\\.slots\\.inject\\(\\s*['\"]([^'\"]+)['\"]/g)].map(m => m[1])
    if (!slots.length) return issues"""
NEW_SLOTFN = """function checkSlotUsage(filePath, state) {
  const issues = []
  try {
    const p = path.isAbsolute(String(filePath)) ? String(filePath) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(filePath))
    if (!/client\\.js$/i.test(p) || !existsSync(p)) return issues
    const text = readFileSync(p, 'utf8')
    const slots = [...String(text).matchAll(/ctx\\.slots\\.inject\\(\\s*['\"]([^'\"]+)['\"]/g)].map(m => m[1])
    if (!slots.length) return issues
    // gap 补修：存在性白名单先过一遍——settings.section 在 asar 中不存在（只有 settings.section.icon），
    // 用途映射不能推荐假 slot。精确不存在才报错（knownSlotNames 可能漏抽，故只在确定集合非空时判）。
    const known = knownSlotNames()
    if (known.size) {
      for (const slot of slots) {
        if (!known.has(slot)) issues.push('slot ' + slot + ' 在 DSH 中不存在（注册会被静默忽略）')
      }
    }"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已打补丁" if MARK in t else "未打补丁"} {path}'
    if MARK in t:
        return True, f'已打补丁跳过 {path.name}'
    out = t
    steps = [
        (OLD_MAP, NEW_MAP, 'safetyFlagsMap'),
        (OLD_STATEFLAG, NEW_STATEFLAG, 'state ref'),
        (OLD_RESET, NEW_RESET, 'no clear flags'),
        (OLD_CLEAR, NEW_CLEAR, 'remove text clear'),
        (OLD_TOOLCLEAR, NEW_TOOLCLEAR, 'critic tool clear'),
        (OLD_GATE, NEW_GATE, 'persistent gate'),
        (OLD_SLOTFN, NEW_SLOTFN, 'slot existence whitelist'),
    ]
    for old, new, label in steps:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    out = out.replace('  // WARGAME_FIXES-PATCHED (2026-11-26)',
                      f'  // {MARK} (2026-11-26)\n  // WARGAME_FIXES-PATCHED (2026-11-26)', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 7锚点'


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
