#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步两个有证据的运行版缺失机制（2026-11-26 18:1x）

依据子任务1证据 + 我核验：
- M3 patternLock：全历史 pattern_lock 159 次，trace-only 零风险 → 同步
- 工具失败自愈：全历史 tool_failure 10 次 + 当前会话 22 次 FAIL 未被接住 → 同步
- 注入分类器：99% 命中是压测灌水，真实会话仅 7 次，会引入未验证 steer → 不同步

只改运行版（publish 已有这两个机制）。幂等标记：SYNC_MECHANISMS-PATCHED
"""
import argparse
import shutil
import sys
from pathlib import Path

PUBLISH = Path(r'D:\Brain\publish\dsh-behavior-guard')
RUNTIME = Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness')
TARGETS = [PUBLISH / 'index.mjs', RUNTIME / 'index.mjs']
TOOLS = ['s6_pattern_guard.mjs', 'tool_failure_healer.mjs']
MARK = 'SYNC_MECHANISMS-PATCHED'

OLD_IMPORT = """import { buildTrailText as _buildTrailText } from './tools/build_trail_text.mjs'"""
NEW_IMPORT = """import { buildTrailText as _buildTrailText } from './tools/build_trail_text.mjs'
import { detectPatternLock as s6PatternLock } from './tools/s6_pattern_guard.mjs'
import { extractFailure, healHint, shouldInject } from './tools/tool_failure_healer.mjs'"""

OLD_HEAL = """        try { detectSideEffectDamage(event, s) } catch { /* 副作用检测绝不阻断主流程 */ }"""
NEW_HEAL = """        try { detectSideEffectDamage(event, s) } catch { /* 副作用检测绝不阻断主流程 */ }
        // 同步机制：S24 执行层失败自愈置位（只认结构化 isError/data.error，绝不扫结果正文）
        if (cfg.toolFailureHealEnabled) {
          try {
            const f = extractFailure(event, s.toolNamesById)
            if (f && healHint(f)) {
              s.pendingHeal = f
              s.healInjectedThisTurn = s.healInjectedThisTurn || 0
              s.healInjectedTotal = s.healInjectedTotal || 0
              trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'tool_failure', tool: f.tool, code: f.code, step: s.step })
            }
          } catch { /* 失败钩子绝不阻断主流程 */ }
        }"""

OLD_STEP = """      s.step += 1

      // ── S8 审计自校准结算"""
NEW_STEP = """      // ── M3 反模式匹配观察线（零LLM，只写trace）──
      // 同步机制：检测"工具分布固化 + 距目标重述够远"，与 D1(同工具失败)不重叠。
      if (cfg.patternLockTraceEnabled && s.toolWindow?.length >= 12) {
        const pl = s6PatternLock(s.toolWindow, s.step - (s.goalRestatedStep || 0))
        if (pl.hit && s.step - (s.lastPatternLockStep ?? -99) >= 6) {
          s.lastPatternLockStep = s.step
          trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'pattern_lock',
            step: s.step, dominant: pl.dominant, repetition: pl.repetition,
            stepsSinceGoal: pl.stepsSinceGoal, window: pl.n })
        }
      }

      s.step += 1

      // ── S8 审计自校准结算"""


def patch_runtime(dry: bool, check: bool) -> tuple[bool, str]:
    p = RUNTIME / 'index.mjs'
    if not p.exists():
        return False, f'MISSING {p}'
    t = p.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已同步" if MARK in t else "未同步"} {p.parent.name}'
    if MARK in t:
        return True, f'已同步跳过 {p.parent.name}'
    out = t
    for old, new, label in [(OLD_IMPORT, NEW_IMPORT, 'import'), (OLD_HEAL, NEW_HEAL, 'heal hook'), (OLD_STEP, NEW_STEP, 'patternLock')]:
        if old not in out:
            return False, f'FAIL 运行版锚点 [{label}] 不存在'
        out = out.replace(old, new, 1)
    out = out.replace('import { collectCorrectorInput as _collectCorrectorInput }',
                      f'// {MARK} (2026-11-26)\nimport {{ collectCorrectorInput as _collectCorrectorInput }}', 1)
    if not dry:
        p.write_text(out, encoding='utf-8')
        for tool in TOOLS:
            src, dst = PUBLISH / 'tools' / tool, RUNTIME / 'tools' / tool
            shutil.copy2(src, dst)
    return True, f'{"DRY " if dry else ""}OK 运行版: 3锚点 + 2工具文件'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not a.check and not a.apply:
        ap.print_help(); return 2
    ok, msg = patch_runtime(a.dry_run, a.check)
    print(msg)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
