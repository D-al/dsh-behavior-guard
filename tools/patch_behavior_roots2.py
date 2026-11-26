#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源头修复补丁 part2：verify_on_stop 上限绕过 + D1 重复探测升级（2026-11-26）

part1 已做：cwd bug / 语义检查 / 交付闸门 / Critic 触发 / 目标锚定 / 正则扩展。
part2 补两个 P1：
  1. verify_on_stop 到上限后不再拦 → 放弃式完成放行（今天 14:57 正是第3次尝试）
  2. D1 重复探测第3次后文本提醒无效 → 升级为强制结束本轮

幂等标记：BEHAVIOR_ROOTS2-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'BEHAVIOR_ROOTS2-PATCHED'

# 1. verify_on_stop 到上限后仍拦一次（对"放弃式完成"类，不受次数上限）
OLD_VOS_LIMIT = """        agent.steer(createSteeringMessage(text, 'behavior-guard'))
        return
      }

      const verdict = guardDecide(state)"""
NEW_VOS_LIMIT = """        agent.steer(createSteeringMessage(text, 'behavior-guard'))
        return
      }
      // 行为根因 P1（2026-11-26）：verify_on_stop 到上限后完全放行 →
      // 今天 14:57 第3次结束尝试（放弃式完成）畅通无阻。
      // 修复：超限但本轮写过文件仍未验证时，不再重复 steer（避免死循环），
      // 但打 trace 供 D5 门控识别，并让交付闸门（part1）兜底。
      if (cfg.verifyOnStopEnabled && state.writeCalls > 0 && !state.verifyRan &&
          (state.verifyOnStopCount || 0) >= cfg.maxVerifyOnStopSteers && !state.verifyOnStopOverflowLogged) {
        state.verifyOnStopOverflowLogged = true
        trace({ ts: new Date().toISOString(), sid: sessionId || '', kind: 'verify_on_stop_overflow',
          step: state.step, count: state.verifyOnStopCount })
        info(`behavior-guard: [verify-on-stop] 已达上限 ${state.verifyOnStopCount} 次仍未验证——交 D5/交付闸门兜底`)
      }

      const verdict = guardDecide(state)"""

# 2. D1 第3次升级为强制结束本轮
OLD_D1 = """          if (sameNameCalls.length >= 3 && sameNameBad >= 2 && !s.pendingInject) {
            s.pendingInject = `[harness 系统修正] 检测到 ${c.name} 已调用 ${sameNameCalls.length} 次、其中 ${sameNameBad} 次超时或无结果。重复探测不是进展——请停止该循环：若在等子智能体结论，其完成后会自动回注（可先输出阶段性报告结束本轮）；若是查询类，换方法（es.exe / 精确短路径）或问用户。`
            info(`audit-loop: D1 重复探测命中 (${c.name} x${sameNameCalls.length}, bad=${sameNameBad})`)"""
NEW_D1 = """          if (sameNameCalls.length >= 3 && sameNameBad >= 2 && !s.pendingInject) {
            // 行为根因 P1（2026-11-26）：D1 今天触发5次，每次只"换工具"不停止（read→grep→read→pwsh…），
            // 长窗口 repeated probe 直到 step47。第3次起升级为"强制结束本轮"指令（零 LLM）。
            const probeN = sameNameCalls.length
            s.pendingInject = probeN >= 3
              ? `[harness 强制停止] ${c.name} 已调用 ${probeN} 次（${sameNameBad} 次无结果）。重复探测不是进展。'
                + '立即结束本轮，输出阶段性报告说明卡点与已确认事实——不要再调用任何工具继续探测。`
              : `[harness 系统修正] 检测到 ${c.name} 已调用 ${sameNameCalls.length} 次、其中 ${sameNameBad} 次超时或无结果。`
            info(`audit-loop: D1 重复探测命中 (${c.name} x${sameNameCalls.length}, bad=${sameNameBad})`)
            trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'd1_probe_guard',
              tool: c.name, count: probeN, step: s.step, escalated: probeN >= 3 })"""
# 注意上面的模板字符串拼接写法需要修正（反引号内不能有裸 ' +）
NEW_D1 = NEW_D1.replace(
    "? `[harness 强制停止] ${c.name} 已调用 ${probeN} 次（${sameNameBad} 次无结果）。重复探测不是进展。'\n                + '立即结束本轮，输出阶段性报告说明卡点与已确认事实——不要再调用任何工具继续探测。`",
    "? `[harness 强制停止] ${c.name} 已调用 ${probeN} 次（${sameNameBad} 次无结果）。重复探测不是进展。立即结束本轮，输出阶段性报告说明卡点与已确认事实——不要再调用任何工具继续探测。`"
)


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已打补丁" if MARK in t else "未打补丁"} {path}'
    if MARK in t:
        return True, f'已打补丁跳过 {path.name}'
    out = t
    for old, new, label in [(OLD_VOS_LIMIT, NEW_VOS_LIMIT, 'verify_on_stop overflow'), (OLD_D1, NEW_D1, 'D1 escalation')]:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    out = out.replace('// ── verify-on-stop（合并补漏：改了文件没验证证据就否决退出，纯规则 0 LLM）──',
                      f'// {MARK} (2026-11-26)\n// ── verify-on-stop（合并补漏：改了文件没验证证据就否决退出，纯规则 0 LLM）──', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 2锚点'


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
