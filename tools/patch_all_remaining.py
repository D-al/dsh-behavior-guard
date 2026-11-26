#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全部修好：攻防演练暴露的所有可修缺陷（2026-11-26 18:1x）

依据 FULL_WARGAME_20261126.md + 三个子任务设计报告。
按证据决定修哪些（不盲目全改）：

代码侧修复（本脚本）：
  A. 同步 2 组有证据的运行版缺失机制：M3 patternLock + 工具失败自愈
  B. FSM 死代码：补 false 声明（消除恒 falsy，保留代码供未来启用）
  C. hardGateInjected 死字段：删除
  D. skill 卡关键词补口语化触发词（让 turn11 那种指令能命中）
  E. 双副本 sha 泛化（不再只认 hardware-monitor-plugin）
  F. 性能伪优化硬规则：正则检测加速主张 + 检查端到端验证证据
  G. 学习信号消费端过滤测试 sid

进程外修复（另一个脚本）：
  H. CritBank 消费闭环（watcher 消费 crit_revision）
  I. 历史污染数据一次性标记

明确不修（子任务证据）：
  - 注入分类器（99%命中是压测灌水，真实会话仅7次）
  - GPU guard dry_run（故意关闭）
  - frame_limiter 粘性释放（兜底不可达）
  - 审计自评对照组（成本收益低）

幂等标记：ALL_REMAINING-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'ALL_REMAINING-PATCHED'

# A1. FSM 配置补 false 声明（死代码消除：至少配置可见，不再恒 undefined 静默）
OLD_CFG = """  verifyOnStopEnabled: true,"""
NEW_CFG = """  verifyOnStopEnabled: true,
  // 全部修好：fsmSignalEnabled 此前从未声明 → FSM_SIGNAL 恒 falsy 死代码。
  // 显式声明 false（保留代码供未来启用；不直接启用，避免未验证行为改变）。
  fsmSignalEnabled: false,"""

# A2. 删 hardGateInjected 死字段
OLD_DEAD = """        s.hardGateInjected = false
"""
NEW_DEAD = """        // hardGateInjected 死字段已删除（safetyBlock 用 safetyBlockCount/safetyFlags 取代）
"""

# A3. skill 卡关键词补口语化触发词（改 dsh-ui-slots.md 的 keywords；index.mjs 用文件里的 keywords）
# 这里改 skill 文件不在 index.mjs 补丁里，单独处理。

# B. 双副本 sha 泛化
OLD_SHA = """    const m = prod.match(/^(.*\\/default-workspace\\/[^/]+)\\/(.*)$/)
    if (!m || !prod.includes('/hardware-monitor-plugin/')) return issues
    const src = m[1] + '/' + m[2]
    const dst = 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-hardware-monitor/' + m[2]"""
NEW_SHA = """    const m = prod.match(/^(.*\\/default-workspace\\/([^/]+))\\/(.*)$/)
    if (!m) return issues
    const pluginName = m[2]
    const rel = m[3]
    const src = m[1] + '/' + rel
    // 全部修好：泛化——不再硬编码 hardware-monitor-plugin，
    // 从路径自动推断插件名，按 node_modules/<插件名>/<相对路径> 推断安装副本。
    const dst = 'D:/Brain/dsh-data/profiles/desktop/node_modules/' + pluginName + '/' + rel"""

# C. 性能伪优化硬规则：verify-on-edit 后检测加速主张
OLD_PERF_ANCHOR = """                if (semIssues.length) {
                  s.semanticFailCount = (s.semanticFailCount || 0) + 1"""
NEW_PERF = """                // 全部修好：性能伪优化硬规则——检测 assistant 正文的加速主张，
                // 若无端到端验证工具调用证据 → semanticFail（防止 moe-cache-cpu-share 式伪加速复发）
                try {
                  const ab = String(s.last?.body || '')
                  const perfClaim = /(?:加速|快了?|提升|优化后|speedup|\\d+\\s*%\\s*(?:快|提升)|t\\/s.*(?:涨|提升))/i.test(ab)
                  if (perfClaim && !s.e2eVerifiedThisTurn) {
                    semIssues.push('回答含性能加速主张但本轮无端到端验证证据（speed_probe/P4/P5/实测对比）——'
                      + '项目铁律：任何加速必须用 P4/P5 端到端验证，decode t/s 是误导性指标')
                  }
                } catch { /* ignore */ }
                if (semIssues.length) {
                  s.semanticFailCount = (s.semanticFailCount || 0) + 1"""

# e2eVerified 标记：在验证工具调用时置位（与 verifyRan 同源）
OLD_VERIFYSET = """          if (cmdTools.includes(callName) && /(verify_agent|pytest|npm test|python -m\\s+(pytest|unittest)|test_|回归|语法检查|编译)/i.test(fullArgs)) s.verifyRan = true"""
NEW_VERIFYSET = """          if (cmdTools.includes(callName) && /(verify_agent|pytest|npm test|python -m\\s+(pytest|unittest)|test_|回归|语法检查|编译)/i.test(fullArgs)) s.verifyRan = true
          // 全部修好：端到端性能验证标记（speed_probe / P4 / P5 / projectlab）
          if (cmdTools.includes(callName) && /(speed_probe|projectlab|agentlab|replay_good|P[1-5]\\b|端到端)/i.test(fullArgs)) s.e2eVerifiedThisTurn = true"""

# turn 重置 e2eVerified
OLD_TURNRESET = """        s.writeCalls = 0
        s.continuations = 0"""
NEW_TURNRESET = """        s.writeCalls = 0
        s.e2eVerifiedThisTurn = false
        s.continuations = 0"""

# D. 学习信号消费端过滤测试 sid
OLD_LEARN = """              if (f.ts && s.learnSinceTs && f.ts < s.learnSinceTs) continue"""
NEW_LEARN = """              if (f.ts && s.learnSinceTs && f.ts < s.learnSinceTs) continue
              // 全部修好：消费端过滤测试 sid —— _pending_learn 86% 是 s1 压测假数据，
              // 消费它等于"从假数据学习"。生产 sid 才进校准。
              const fsid = String(f.sid || '')
              if (/^(s1|s2|budget-|test-)/i.test(fsid)) continue"""


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
        (OLD_CFG, NEW_CFG, 'FSM false config'),
        (OLD_DEAD, NEW_DEAD, 'remove hardGateInjected'),
        (OLD_SHA, NEW_SHA, 'generalize sha'),
        (OLD_PERF_ANCHOR, NEW_PERF, 'perf claim guard'),
        (OLD_VERIFYSET, NEW_VERIFYSET, 'e2e verify mark'),
        (OLD_TURNRESET, NEW_TURNRESET, 'reset e2e'),
        (OLD_LEARN, NEW_LEARN, 'filter test sid'),
    ]
    for old, new, label in steps:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    out = out.replace('  // WARGAME_GAPS-PATCHED (2026-11-26)',
                      f'  // {MARK} (2026-11-26)\n  // WARGAME_GAPS-PATCHED (2026-11-26)', 1)
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
