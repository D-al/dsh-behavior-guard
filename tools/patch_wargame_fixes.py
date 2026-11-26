#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""攻防演练暴露的 8 个缺陷统一修复（2026-11-26 17:3x）

依据 docs/WARGAME_FULL_AUDITOR_20261126.md：识别≠阻止。
不再堆散补丁——做统一的 safetyBlock 硬闸门层：
  1. 安全检查提到 continuations 短路之前
  2. 硬闸门持续拦截直到标记被真实验证动作清除（有预算上限防死循环）
  3. 标记清除：tool/call 里真正调用工具时清对应标记
  4. 语义检查从软 pendingInject 升级为硬标记 + slot 用途映射
  5. 双副本 sha 从 deepChecked 一次性移到 verify-on-edit 每次写后
  6. 连续相同内容写入检测
  7. forceStop 在探测循环中持续拦（不限于纯文本收尾）
  8. verify_on_stop 溢出不再完全放行

幂等标记：WARGAME_FIXES-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'WARGAME_FIXES-PATCHED'

# ══ 1. 状态字段：加 safety 相关字段 ══
OLD_STATE = """        continuations: 0, totalContinuations: 0, last: undefined, sharedInjections: 0, sessionInjections: 0,"""
NEW_STATE = """        continuations: 0, totalContinuations: 0, last: undefined, sharedInjections: 0, sessionInjections: 0,
        // 统一安全闸门（2026-11-26 攻防演练）：硬标记 + 预算
        safetyFlags: {}, safetyBlockCount: 0, safetySessionBlocks: 0, lastProductHash: '', repeatedWriteCount: 0,"""

# ══ 2. tool/call 里清标记（模型真正行动时）══
OLD_TOOLCLEAR = """        s.toolCalls += 1
        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) s.writeCalls += 1"""
NEW_TOOLCLEAR = """        s.toolCalls += 1
        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) s.writeCalls += 1
        // 安全闸门标记清除（2026-11-26）：模型真正调用工具=在行动，不是甩锅。
        // handoffBlocked 在任意工具调用后清除；forceStop 在写/命令类工具后清除。
        try {
          const tn = String(event.data?.name || '')
          if (s.safetyFlags && s.safetyFlags.handoffBlocked) { delete s.safetyFlags.handoffBlocked; info('behavior-guard: safetyFlag handoffBlocked cleared by tool=' + tn) }
          if (s.safetyFlags && s.safetyFlags.forceStop && (cfg.writeTools.includes(tn) || ['pwsh','bash','exec'].includes(tn))) {
            delete s.safetyFlags.forceStop; info('behavior-guard: safetyFlag forceStop cleared by action=' + tn)
          }
          // verifyFail：跑真实验证命令（含 verify/test/compile 关键词）后清除
          const targs = String(event.data?.arguments || '')
          if (s.safetyFlags && s.safetyFlags.verifyFail && /(verify|test|compile|pytest|py_compile|node --check)/i.test(targs)) {
            delete s.safetyFlags.verifyFail; info('behavior-guard: safetyFlag verifyFail cleared by verify tool=' + tn)
          }
        } catch { /* ignore */ }"""

# ══ 3. assistant/message 里：检测"阶段性报告"清 criticRejected ══
OLD_ASSISTANT_CLEAR = """        // 防线2：抓取 reasoning 里"发现问题但未修复"的线索，供压缩存档强制保留
        try { captureOpenCorrection(s) } catch { /* 纠错抓取失败不影响主流程 */ }"""
NEW_ASSISTANT_CLEAR = """        // 防线2：抓取 reasoning 里"发现问题但未修复"的线索，供压缩存档强制保留
        try { captureOpenCorrection(s) } catch { /* 纠错抓取失败不影响主流程 */ }
        // 安全闸门：模型输出"阶段性报告/卡点说明"（非甩锅、非空话）→ 清 criticRejected
        try {
          if (s.safetyFlags && s.safetyFlags.criticRejected && s.last?.body && s.last.body.length > 40 &&
              /(?:已完成|已确认|卡点|阶段性|未能|无法|阻塞|下一步)/.test(s.last.body) && s.last.toolCalls === 0) {
            delete s.safetyFlags.criticRejected
            info('behavior-guard: safetyFlag criticRejected cleared by status report')
          }
        } catch { /* ignore */ }"""

# ══ 4. verify-on-edit：语义检查升级 + sha 每次写后 + 重复写入检测 ══
OLD_SEM_HOOK = """              } else {
                // 行为根因 P0：语法过了再做语义检查（slot/URL 存在性）
                const semIssues = checkWrittenSemantics(s.lastProduct)
                if (semIssues.length) {
                  s.semanticFailCount = (s.semanticFailCount || 0) + 1
                  s.pendingInject = '[harness 语义检查] 刚写入的文件存在语义问题：' + semIssues.join('；') +
                    '\\n这不是语法错误，node --check 查不出来。先修正再继续。'
                  trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'semantic_check_fail',
                    step: s.step, file: s.lastProduct, issues: semIssues.slice(0, 2) })
                  info(`behavior-guard: 语义检查失败 ${s.lastProduct}: ${semIssues.join(';').slice(0, 100)}`)
                }
              }"""
NEW_SEM_HOOK = """              } else {
                // 攻防演练修复：语法过了做语义检查（slot 用途映射）+ sha 每次写后 + 重复写入检测
                const semIssues = checkWrittenSemantics(s.lastProduct)
                // ① slot 用途错位（用户要左侧却注入 settings.*）
                const usageIssues = checkSlotUsage(s.lastProduct, s)
                semIssues.push(...usageIssues)
                // ② 双副本 sha（每次写后，不再受 deepChecked 一次性限制）
                const shaIssues = checkDualCopy(s.lastProduct)
                semIssues.push(...shaIssues)
                // ③ 连续相同内容写入（攻击 A2：连写3次相同 client.js）
                try {
                  const absP = path.isAbsolute(String(s.lastProduct)) ? String(s.lastProduct) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(s.lastProduct))
                  if (existsSync(absP)) {
                    const h = createHash('sha256').update(readFileSync(absP)).digest('hex').slice(0, 16)
                    if (h === s.lastProductHash) {
                      s.repeatedWriteCount = (s.repeatedWriteCount || 0) + 1
                      if (s.repeatedWriteCount >= 2) semIssues.push('连续 ' + (s.repeatedWriteCount + 1) + ' 次写入完全相同内容——重复写入不是进展，停止空转')
                    } else { s.repeatedWriteCount = 0; s.lastProductHash = h }
                  }
                } catch { /* ignore */ }
                if (semIssues.length) {
                  s.semanticFailCount = (s.semanticFailCount || 0) + 1
                  // 硬标记：语义失败持续到真正修正（不再只是软提醒）
                  if (!s.safetyFlags) s.safetyFlags = {}
                  s.safetyFlags.semanticFail = true
                  s.pendingInject = '[harness 语义检查] 刚写入的文件存在语义问题：' + semIssues.join('；') +
                    '\\n这不是语法错误，node --check 查不出来。先修正再继续。'
                  trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'semantic_check_fail',
                    step: s.step, file: s.lastProduct, issues: semIssues.slice(0, 2) })
                  info(`behavior-guard: 语义检查失败 ${s.lastProduct}: ${semIssues.join(';').slice(0, 100)}`)
                } else if (s.safetyFlags && s.safetyFlags.semanticFail) {
                  delete s.safetyFlags.semanticFail
                }
              }"""

# ══ 5. 新增 helper 函数：slot 用途映射 + 双副本 sha ══
OLD_HELPER_ANCHOR = """function checkWrittenSemantics(filePath) {"""
NEW_HELPERS = """// 攻防演练修复：slot 用途映射——用户要"左侧入口"却注入 settings.* → 错位。
// 依据 app.asar 实测 slot 名前缀规律：sidebar.*=导航/侧栏，conversation.composer.*/input.*=输入框，settings.*=设置页。
const SLOT_USAGE = [
  { re: /左侧|左边|侧边栏|侧栏|left|sidebar|nav|入口/i, allow: /^sidebar\\./, deny: /^(?:settings\\.|conversation\\.composer\\.|conversation\\.input\\.)/ },
]
function checkSlotUsage(filePath, state) {
  const issues = []
  try {
    const p = path.isAbsolute(String(filePath)) ? String(filePath) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(filePath))
    if (!/client\\.js$/i.test(p) || !existsSync(p)) return issues
    const text = readFileSync(p, 'utf8')
    const slots = [...String(text).matchAll(/ctx\\.slots\\.inject\\(\\s*['\"]([^'\"]+)['\"]/g)].map(m => m[1])
    if (!slots.length) return issues
    const goal = String(state?.anchorInitial || state?.initial || state?.latest || '')
    for (const rule of SLOT_USAGE) {
      if (!rule.re.test(goal)) continue
      for (const slot of slots) {
        if (rule.deny.test(slot) && !rule.allow.test(slot)) {
          issues.push('slot 用途错位：用户目标含"' + goal.slice(0, 30) + '"，但注入的是 ' + slot +
            '（' + (slot.startsWith('settings.') ? '设置页' : slot.startsWith('conversation.composer') ? '输入框停靠区' : '非侧栏') +
            '）——需注入 sidebar.* 类 slot')
        }
      }
    }
  } catch { /* ignore */ }
  return issues
}
function checkDualCopy(filePath) {
  const issues = []
  try {
    const prod = String(filePath || '').replace(/\\\\/g, '/')
    const m = prod.match(/^(.*\\/default-workspace\\/[^/]+)\\/(.*)$/)
    if (!m || !prod.includes('/hardware-monitor-plugin/')) return issues
    const src = m[1] + '/' + m[2]
    const dst = 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-hardware-monitor/' + m[2]
    if (!existsSync(src) || !existsSync(dst)) return issues
    const sh = (f) => { try { return createHash('sha256').update(readFileSync(f)).digest('hex').slice(0, 16) } catch { return '' } }
    const a = sh(src), b = sh(dst)
    if (a && b && a !== b) issues.push('双副本不同步（源 ' + a + ' / 安装 ' + b + '）——改了不生效')
  } catch { /* ignore */ }
  return issues
}
function checkWrittenSemantics(filePath) {"""

# ══ 6. 统一 safetyBlock：替换旧硬闸门，放短路之前 ══
OLD_SHORTGATE = """      if (state.continuations >= cfg.maxContinuationsPerTurn) return
      if (state.totalContinuations >= cfg.maxContinuationsPerSession) return

      // ── 硬闸门（2026-11-26 实验）：soft steer 被忽略的兜底 ──
      // D1 forceStop / Critic REJECT / handoff 任一置位，且最后一条消息是纯文本收尾 →
      // 不允许 completed，强制注入"输出阶段性报告"指令。
      try {
        const hardFlags = []
        if (state.forceStop) hardFlags.push('重复探测已达上限')
        if (state.criticRejected) hardFlags.push('产物评审未通过')
        if (state.handoffBlocked) hardFlags.push('上一轮甩锅未被修正')
        const lastMsgTC = state.last?.toolCalls ?? 0
        if (hardFlags.length && lastMsgTC === 0 && !state.hardGateInjected) {
          state.hardGateInjected = true
          state.sharedInjections += 1
          trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'hard_gate_block',
            step: state.step, flags: hardFlags })
          agent.steer(createSteeringMessage(
            '[harness 硬闸门] 本轮不能结束：' + hardFlags.join('；') + '。'
            + '请输出一段阶段性报告说明已确认事实与卡点，不要说"已完成"——'
            + '硬闸门会在这些标记清除前持续阻止 completed。', 'behavior-guard'))
          return
        }
      } catch { /* 硬闸门失败不影响主流程 */ }"""
NEW_SHORTGATE = """      // ══ 统一安全闸门（2026-11-26 攻防演练重构）══
      // 必须在 continuations 短路之前——原设计短路后所有闸门跳过，是最大漏洞。
      // 持续拦截直到标记被真实动作清除；预算上限防死循环（每轮 3 次 / 每会话 8 次）。
      try {
        const sf = state.safetyFlags || {}
        const hardFlags = []
        if (sf.forceStop || state.forceStop) hardFlags.push('重复探测已达上限')
        if (sf.criticRejected || state.criticRejected) hardFlags.push('产物评审未通过')
        if (sf.handoffBlocked || state.handoffBlocked) hardFlags.push('甩锅未被修正')
        if (sf.semanticFail) hardFlags.push('产物语义问题未修正')
        if (sf.verifyFail) hardFlags.push('收尾验证缺失')
        if (hardFlags.length && (state.safetyBlockCount || 0) < 3 && (state.safetySessionBlocks || 0) < 8) {
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
        }
      } catch { /* 安全闸门失败不影响主流程 */ }

      if (state.continuations >= cfg.maxContinuationsPerTurn) return
      if (state.totalContinuations >= cfg.maxContinuationsPerSession) return

      // 旧硬闸门已由上方 safetyBlock 统一接管（保留 state.forceStop 等字段兼容旧读取点）"""

# ══ 7. turn/start 重置 safetyBlockCount（session 预算不重置）══
OLD_TURN_RESET = """        s.forceStop = false; s.criticRejected = false; s.handoffBlocked = false
        s.hardGateInjected = false"""
NEW_TURN_RESET = """        s.forceStop = false; s.criticRejected = false; s.handoffBlocked = false
        s.hardGateInjected = false
        s.safetyBlockCount = 0; s.safetyFlags = {}"""

# ══ 8. D1 forceStop 同时置 safetyFlags ══
OLD_D1_FLAG = """            if (probeN >= 3) s.forceStop = true"""
NEW_D1_FLAG = """            if (probeN >= 3) { s.forceStop = true; if (!s.safetyFlags) s.safetyFlags = {}; s.safetyFlags.forceStop = true }"""

# ══ 9. Critic REJECT 同时置 safetyFlags ══
OLD_CRITIC_FLAG = """            state.criticRejected = true"""
NEW_CRITIC_FLAG = """            state.criticRejected = true
            if (!state.safetyFlags) state.safetyFlags = {}
            state.safetyFlags.criticRejected = true"""

# ══ 10. handoff 同时置 safetyFlags ══
OLD_HANDOFF_FLAG = """          state.handoffBlocked = true"""
NEW_HANDOFF_FLAG = """          state.handoffBlocked = true
          if (!state.safetyFlags) state.safetyFlags = {}
          state.safetyFlags.handoffBlocked = true"""

# ══ 11. verify_on_stop 溢出：持续拦（不再完全放行）══
OLD_OVERFLOW = """        state.verifyOnStopOverflowLogged = true
        trace({ ts: new Date().toISOString(), sid: sessionId || '', kind: 'verify_on_stop_overflow',
          step: state.step, count: state.verifyOnStopCount })
        info(`behavior-guard: [verify-on-stop] 已达上限 ${state.verifyOnStopCount} 次仍未验证——交 D5/交付闸门兜底`)"""
NEW_OVERFLOW = """        trace({ ts: new Date().toISOString(), sid: sessionId || '', kind: 'verify_on_stop_overflow',
          step: state.step, count: state.verifyOnStopCount })
        // 攻防演练修复：溢出不再完全放行——置 safetyFlag 让安全闸门持续拦到真验证
        if (!state.safetyFlags) state.safetyFlags = {}
        state.safetyFlags.verifyFail = true
        info(`behavior-guard: [verify-on-stop] 已达上限 ${state.verifyOnStopCount} 次仍未验证——安全闸门接管`)"""


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
        (OLD_STATE, NEW_STATE, 'state fields'),
        (OLD_TOOLCLEAR, NEW_TOOLCLEAR, 'tool clear flags'),
        (OLD_ASSISTANT_CLEAR, NEW_ASSISTANT_CLEAR, 'assistant clear critic'),
        (OLD_SEM_HOOK, NEW_SEM_HOOK, 'verify-on-edit upgrade'),
        (OLD_HELPER_ANCHOR, NEW_HELPERS, 'helper functions'),
        (OLD_SHORTGATE, NEW_SHORTGATE, 'unified safety gate'),
        (OLD_TURN_RESET, NEW_TURN_RESET, 'turn reset'),
        (OLD_D1_FLAG, NEW_D1_FLAG, 'D1 flag'),
        (OLD_CRITIC_FLAG, NEW_CRITIC_FLAG, 'critic flag'),
        (OLD_HANDOFF_FLAG, NEW_HANDOFF_FLAG, 'handoff flag'),
        (OLD_OVERFLOW, NEW_OVERFLOW, 'overflow persist'),
    ]
    # 删除深检里的旧 sha 块（已被 verify-on-edit 的 checkDualCopy 取代，且受 deepChecked 一次性限制）
    OLD_DEEP_SHA = """          // 双副本一致性硬检查（2026-11-26 实验）：它声称"双位置同步 ✅"但实际不同步。
          // 对 workspace 下的插件文件，比对 workspace 源与 node_modules 安装副本的 sha。
          try {
            const prod = String(state.lastProduct || '').replace(/\\\\/g, '/')
            const m = prod.match(/^(.*\\/default-workspace\\/[^/]+)\\/(.*)$/)
            if (m && prod.includes('/hardware-monitor-plugin/')) {
              const src = m[1] + '/' + m[2]
              const dst = 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-hardware-monitor/' + m[2]
              if (existsSync(src) && existsSync(dst)) {
                const sh = (f) => { try { return createHash('sha256').update(readFileSync(f)).digest('hex').slice(0, 16) } catch { return '' } }
                const a = sh(src), b = sh(dst)
                if (a && b && a !== b) deepIssues.push('双副本不同步：workspace 源(' + a + ') 与安装目录(' + b + ') 不一致——改了不生效，必须同步')
              }
            }
          } catch { /* 比对失败不阻断 */ }
"""
    NEW_DEEP_SHA = """          // 双副本 sha 检查已移到 verify-on-edit（每次写后），不再放这里——
          // 原位置受 deepChecked 每会话一次限制，会和 [VERIFY] 检查抢名额（2026-11-26 攻防演练修复）。
"""
    if OLD_DEEP_SHA in out:
        out = out.replace(OLD_DEEP_SHA, NEW_DEEP_SHA, 1)
    for old, new, label in steps:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    out = out.replace('  const goalAnchors = new Map()', f'  // {MARK} (2026-11-26)\n  const goalAnchors = new Map()', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 11锚点'


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
