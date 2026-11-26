#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控实验暴露的 4 个漏洞修复（2026-11-26 17:1x）

实验证据：docs/ACCEPTANCE_CONTROLLED_EXPERIMENT_20261126.md
1. handoff_gate 用 state.toolCalls===0（本轮累计），但甩锅发生在 step44 → 永不触发。
   改为 state.last.toolCalls===0（最后一条消息纯文本甩锅）。
2. D1 "强制停止"只是文本，模型继续跑到 step44 → 加 forceStop 硬标记。
3. 双副本不同步（它声称一致实际不同）→ deep check 加 sha 比对硬闸门。
4. Critic C-REJECT 只是 steer，模型继续跑完 completed → criticRejected 硬标记。

幂等标记：EXPERIMENT_FIXES-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'EXPERIMENT_FIXES-PATCHED'

# 1. handoff 条件：本轮累计 → 最后一条消息纯文本
OLD_HANDOFF_COND = """        const isHandoff = handoffRe.test(body) && jsEvidenceRe.test(body) && state.toolCalls === 0
        if (isHandoff) {
          agent.steer(createSteeringMessage(
            '[harness 交付闸门] 检测到把工作甩给用户手动执行（F12/粘贴代码）且本轮无工具调用。'
            + '这不是完成交付。要么自己调用工具完成验证，要么明确说明具体卡点并请求用户指示——'
            + '不要以"让用户手动执行"收尾。', 'behavior-guard'))
          return
        }"""
NEW_HANDOFF_COND = """        // 修复（2026-11-26 受控实验）：原条件 state.toolCalls===0（本轮累计）在"干了一堆活后甩锅"
        // 场景永远不成立（实验 step44 toolCalls=44）。改为判断**最后一条 assistant 消息本身**
        // 是否纯文本（toolCalls=0）——甩锅消息必然是纯文本。
        const lastMsgToolCalls = state.last?.toolCalls ?? 0
        const isHandoff = handoffRe.test(body) && jsEvidenceRe.test(body) && lastMsgToolCalls === 0
        if (isHandoff) {
          state.handoffBlocked = true
          state.sharedInjections += 1
          trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'handoff_gate',
            step: state.step, blocked: true, lastMsgToolCalls })
          agent.steer(createSteeringMessage(
            '[harness 交付闸门] 检测到把工作甩给用户手动执行（F12/粘贴代码/控制台）。'
            + '这是未完成交付——即使前面做了很多步，最后一步甩锅不算完成。'
            + '要么自己调用工具完成验证，要么明确说明具体卡点并请求用户指示。', 'behavior-guard'))
          return
        }"""

# 2. D1 强制停止：置硬标记
OLD_D1_MSG = """              ? `[harness 强制停止] ${c.name} 已调用 ${probeN} 次（${sameNameBad} 次无结果）。重复探测不是进展。立即结束本轮，输出阶段性报告说明卡点与已确认事实——不要再调用任何工具继续探测。`
              : `[harness 系统修正] 检测到 ${c.name} 已调用 ${sameNameCalls.length} 次、其中 ${sameNameBad} 次超时或无结果。`"""
NEW_D1_MSG = """              ? `[harness 强制停止] ${c.name} 已调用 ${probeN} 次（${sameNameBad} 次无结果）。重复探测不是进展。立即结束本轮，输出阶段性报告说明卡点与已确认事实——不要再调用任何工具继续探测。`
              : `[harness 系统修正] 检测到 ${c.name} 已调用 ${sameNameCalls.length} 次、其中 ${sameNameBad} 次超时或无结果。`
            // 硬标记（2026-11-26 实验）：原"强制停止"只是文本，模型继续跑到 step44。
            // 置位后 turn-stopping 层会硬拦 completed，直到模型输出阶段性报告。
            if (probeN >= 3) s.forceStop = true"""

# 3. deep check 加双副本 sha 比对
OLD_DEEP = """          const deepIssues = checkArtifactDeep(state.lastProduct)
          // 交付物清单对照：todo 里未完成的 [VERIFY] 项（声明了验收却没做）"""
NEW_DEEP = """          const deepIssues = checkArtifactDeep(state.lastProduct)
          // 双副本一致性硬检查（2026-11-26 实验）：它声称"双位置同步 ✅"但实际不同步。
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
          // 交付物清单对照：todo 里未完成的 [VERIFY] 项（声明了验收却没做）"""

# 4a. Critic REJECT 置硬标记
OLD_CRITIC_REJECT = """          } else if (critic && critic.verdict === 'REJECT') {
            state.sharedInjections += 1
            agent.steer(createSteeringMessage("""
NEW_CRITIC_REJECT = """          } else if (critic && critic.verdict === 'REJECT') {
            state.sharedInjections += 1
            state.criticRejected = true
            agent.steer(createSteeringMessage("""

# 4b. turn-stopping 开头硬拦：forceStop / criticRejected / handoffBlocked
OLD_TS_GUARD = """      if (state.continuations >= cfg.maxContinuationsPerTurn) return
      if (state.totalContinuations >= cfg.maxContinuationsPerSession) return

      // ── 行为根因 P0：放弃式完成闸门（零 LLM）──"""
NEW_TS_GUARD = """      if (state.continuations >= cfg.maxContinuationsPerTurn) return
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
      } catch { /* 硬闸门失败不影响主流程 */ }

      // ── 行为根因 P0：放弃式完成闸门（零 LLM）──"""


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
        (OLD_HANDOFF_COND, NEW_HANDOFF_COND, 'handoff condition'),
        (OLD_D1_MSG, NEW_D1_MSG, 'D1 forceStop'),
        (OLD_DEEP, NEW_DEEP, 'dual-copy sha'),
        (OLD_CRITIC_REJECT, NEW_CRITIC_REJECT, 'critic hard flag'),
        (OLD_TS_GUARD, NEW_TS_GUARD, 'turn-stopping hard gate'),
    ]
    for old, new, label in steps:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    # turn 开始时重置硬闸门标记
    old_reset = "        s.last = undefined\n        s.sharedInjections = 0"
    new_reset = ("        s.last = undefined\n        s.sharedInjections = 0\n"
                 "        // 实验修复：硬闸门标记每轮重置（否则一个 turn 的 forceStop 污染后续所有 turn）\n"
                 "        s.forceStop = false; s.criticRejected = false; s.handoffBlocked = false\n"
                 "        s.hardGateInjected = false")
    if old_reset in out:
        out = out.replace(old_reset, new_reset, 1)

    # createHash import：纳入已有的 node:crypto import（原逻辑误判"已有 crypto"就不加，导致 ReferenceError）
    old_imp = "import { randomUUID } from 'node:crypto'"
    new_imp = "import { randomUUID, createHash } from 'node:crypto'"
    if old_imp in out:
        out = out.replace(old_imp, new_imp, 1)
    out = out.replace('  const states = new Map()', f'  // {MARK} (2026-11-26)\n  const states = new Map()', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 5锚点'


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
