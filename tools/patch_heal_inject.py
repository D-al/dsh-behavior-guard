#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补 tool_failure_heal 的注入点（2026-11-26 22:3x）

上一步(sync_mech_fix)补了 toolNamesById 填充和 pendingHeal 置位，
但 pendingHeal 没有任何消费点 → heal 提示永远不会注入。
本补丁在 pre-step 的 Skills 段之前插入 heal 注入。幂等标记：HEAL_INJECT-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs')]
MARK = 'HEAL_INJECT-PATCHED'

OLD = """      // ── Skills 技能卡（按任务关键词命中一次，零 LLM）──"""
NEW = """      // ── S24 工具失败自愈注入（2026-11-26 修：补齐消费点）──
      if (cfg.toolFailureHealEnabled && s.pendingHeal) {
        try {
          if (shouldInject(s.pendingHeal, s)) {
            const hint = healHint(s.pendingHeal)
            if (hint) {
              s.healInjectedThisTurn = (s.healInjectedThisTurn || 0) + 1
              s.healInjectedTotal = (s.healInjectedTotal || 0) + 1
              trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'tool_failure_heal', code: s.pendingHeal.code, step: s.step })
              const msg = createMessage(hint, 'tool-failure-healer', s)
              s.pendingHeal = null
              const messages = Array.isArray(decision?.messages) ? [...decision.messages, msg] : [msg]
              return { ...decision, messages }
            }
          } else { s.pendingHeal = null }
        } catch { /* 自愈失败不影响主流程 */ }
      }

      // ── Skills 技能卡（按任务关键词命中一次，零 LLM）──"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已修" if MARK in t else "未修"}'
    if MARK in t:
        return True, '已修跳过'
    if OLD not in t:
        return False, 'FAIL 锚点不存在'
    out = t.replace(OLD, NEW, 1)
    out = out.replace('// SYNC_MECH_FIX-PATCHED (2026-11-26)',
                      f'// {MARK} (2026-11-26)\n// SYNC_MECH_FIX-PATCHED (2026-11-26)', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK: heal 注入点已补'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not a.check and not a.apply:
        ap.print_help(); return 2
    for p in TARGETS:
        ok, msg = patch(p, a.dry_run, a.check)
        print(msg)
        if not ok: return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
