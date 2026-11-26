#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计攻防演练全部改进落地（2026-11-26 22:4x）

依据 AUDIT_WARGAME_LONGTASK_20261126.md §7 的 P0-P3 清单，逐条修复。

P0-1 语义检查重复写入：同一次 write 会多次跑检查 → 计数虚增误报（报"3次"实际2次）。
     → 加"同 step 只检查一次"守卫 + 报错文案带具体 sha 对比。
P0-2 拦截措辞改差异反馈：不再说"重复写入不是进展"，改为给出具体差异与下一步。
P0-3 空壳机制：已由 patch_sync_mech_fix.py + patch_heal_inject.py 修复（本补丁不重复）。

P1-1 handoff_gate 加"软甩锅"特征：让用户重启/截图/贴结果验证。
P1-2 言行一致性检查：正文说"已重写/已改"但本轮写了相同 sha → 报语义问题。
P1-3 方案回退检测：用户否定过的 slot 名再次出现 → 拦截告警。

P2-1 control_turn：连续 N 步无 write 时强制触发（退化循环期原本 0 次）。
P2-2 verify_on_stop：要求真实 HTTP/URL 验证证据，不只是 read 回读。

P3-1 fep_cycle：converged 判定纳入"产物 hash 是否变化"。

幂等标记：AUDIT_ALLFIX-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'AUDIT_ALLFIX-PATCHED'

# ── P0-1 + P0-2：重复写入守卫 + 差异反馈文案 ──
OLD_REPEAT = """                // ③ 连续相同内容写入（攻击 A2：连写3次相同 client.js）
                try {
                  const absP = path.isAbsolute(String(s.lastProduct)) ? String(s.lastProduct) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(s.lastProduct))
                  if (existsSync(absP)) {
                    const h = createHash('sha256').update(readFileSync(absP)).digest('hex').slice(0, 16)
                    if (h === s.lastProductHash) {
                      s.repeatedWriteCount = (s.repeatedWriteCount || 0) + 1
                      if (s.repeatedWriteCount >= 2) semIssues.push('连续 ' + (s.repeatedWriteCount + 1) + ' 次写入完全相同内容——重复写入不是进展，停止空转')
                    } else { s.repeatedWriteCount = 0; s.lastProductHash = h }
                  }
                } catch { /* ignore */ }"""

NEW_REPEAT = """                // ③ 连续相同内容写入（攻击 A2：连写3次相同 client.js）
                // P0 修复（2026-11-26 审计实测）：原实现同一 step 会多次进入此检查 →
                // 计数虚增（实际写2次却报"3次"）。加同 step 守卫，只计一次。
                // 另：文案改为差异反馈（给出具体 sha 与该做什么），而非"重复写入不是进展"。
                try {
                  const absP = path.isAbsolute(String(s.lastProduct)) ? String(s.lastProduct) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(s.lastProduct))
                  const checkKey = String(s.step) + '|' + absP
                  if (existsSync(absP) && s._lastRepeatCheckKey !== checkKey) {
                    s._lastRepeatCheckKey = checkKey
                    const h = createHash('sha256').update(readFileSync(absP)).digest('hex').slice(0, 16)
                    if (h === s.lastProductHash) {
                      s.repeatedWriteCount = (s.repeatedWriteCount || 0) + 1
                      if (s.repeatedWriteCount >= 2) {
                        semIssues.push('这个文件内容与上次写入完全相同（sha ' + h + '，已连续 '
                          + (s.repeatedWriteCount + 1) + ' 次）。说明修改没有落到文件里：'
                          + '先 read 出当前内容确认实际文本，再针对具体行改——不要整篇重写同一份内容。')
                      }
                    } else {
                      const prev = s.lastProductHash
                      s.repeatedWriteCount = 0; s.lastProductHash = h
                      if (prev) s.lastProductChangeNote = '内容已变化（' + prev + ' → ' + h + '）'
                    }
                  }
                } catch { /* ignore */ }"""

# ── P1-2：言行一致性检查（正文说已改，但 sha 未变）──
OLD_PERF_ANCHOR = """                // 全部修好：性能伪优化硬规则——检测 assistant 正文的加速主张，"""
NEW_PERF_ANCHOR = """                // P1 修复（2026-11-26 审计 E2）：言行一致性——正文声称"已重写/已修改/已更新"，
                // 但本轮产物 sha 与上次相同 → 说明只是嘴上说改了。
                try {
                  const claimBody = String(s.last?.body || '')
                  const claimRewrite = /(?:已(?:经)?(?:重写|修改|改写|更新|修好|完成修改)|重新(?:写|实现)了)/.test(claimBody)
                  if (claimRewrite && s.repeatedWriteCount >= 1) {
                    semIssues.push('你在正文里说已经重写/修改，但这个文件的内容和上次完全相同（sha 未变）。'
                      + '实际没有改到——不要用文字声称完成，请真正修改文件内容或说明具体卡在哪一行。')
                  }
                } catch { /* ignore */ }
                // 全部修好：性能伪优化硬规则——检测 assistant 正文的加速主张，"""

# ── P1-1：handoff_gate 加软甩锅特征 ──
OLD_HANDOFF_RE = """        const handoffRe = /(?:打开|按|去|请).{0,8}(?:F12|控制台)|(?:粘贴|复制).{0,12}(?:代码|脚本|到.*控制台)|(?:手动|自行)(?:执行|运行)/i"""
NEW_HANDOFF_RE = """        // P1 修复（2026-11-26 审计 E4）：原正则只认 F12/控制台/粘贴代码，
        // 认不出"请你重启 DSH / 截图给我 / 测试后告诉我"这类软甩锅（实测 2 次全放行）。
        const handoffRe = /(?:打开|按|去|请).{0,8}(?:F12|控制台)|(?:粘贴|复制).{0,12}(?:代码|脚本|到.*控制台)|(?:手动|自行)(?:执行|运行)|(?:请|你).{0,10}(?:重启|重新启动|关闭).{0,10}(?:DSH|应用|程序|dsh)|(?:请|你).{0,6}(?:截图|测试).{0,14}(?:给我|反馈|告诉我|后)|(?:测试结果|反馈).{0,10}(?:告诉我|贴给|发我)/i"""

# ── P2-1：control_turn 连续无 write 强制触发 ──
OLD_CONTROL = """      if (cfg.controlEnabled && s.step > 0 && s.step % cfg.controlEverySteps === 0 &&
          (s.controlCount || 0) < 1 &&   // 每轮至多一次（controlCount 在 turn/start 清零）
          (s.controlTotal || 0) < cfg.maxControlPerSession) {"""
NEW_CONTROL = """      // P2 修复（2026-11-26 审计）：原条件要求 step % 8 === 0 且每轮至多一次，
      // 导致 21 分钟退化循环期（21:25-21:46）**0 次触发**。加"连续 6 步无 write"旁路：
      // 退化循环的典型特征就是只在 read/grep 打转，此时必须做元决策。
      const _noWriteStreak = (s.stepsSinceWrite || 0)
      const _degradeBypass = _noWriteStreak >= 6 && (s.controlTotal || 0) < cfg.maxControlPerSession &&
        (s.step - (s.lastDegradeControlStep ?? -99) >= 4)
      if (cfg.controlEnabled && s.step > 0 &&
          ((s.step % cfg.controlEverySteps === 0 && (s.controlCount || 0) < 1) || _degradeBypass) &&
          (s.controlTotal || 0) < cfg.maxControlPerSession) {
        if (_degradeBypass) s.lastDegradeControlStep = s.step"""

# ── P2-2：verify_on_stop 要求真实验证证据 ──
OLD_VERIFY_STOP = """      // 行为根因 P1（2026-11-26）：verify_on_stop 到上限后完全放行 →"""
NEW_VERIFY_STOP = """      // P2 修复（2026-11-26 审计 E13）：verify_on_stop 原只数"是否有验证类调用"，
      // 但 read 回读也算验证 → 全程没做过 HTTP/UI 检查仍能通过。
      // 加：若本轮改的是 web/UI 产物（client.js 等），要求出现 http/curl/浏览器类证据。
      try {
        const _prod = String(state.lastProduct || '')
        const _isWeb = /\\.(?:js|jsx|ts|tsx|html|css)$/i.test(_prod) || /client\\.js/i.test(_prod)
        if (_isWeb && state.wroteThisTurn) {
          const _trail = Array.isArray(state.trail) ? state.trail : []
          const _hasHttp = _trail.some((x) => x && x.kind === 'call'
            && /(curl|Invoke-WebRequest|fetch\\(|http:\\/\\/|localhost:\\d+|8999|截图|screenshot|playwright)/i.test(String(x.fullArgs || '')))
          if (!_hasHttp) state.safetyFlags = Object.assign({}, state.safetyFlags, { verifyWeak: true })
        }
      } catch { /* ignore */ }
      // 行为根因 P1（2026-11-26）：verify_on_stop 到上限后完全放行 →"""

# ── P3-1：fep converged 纳入产物 hash 变化 ──
OLD_FEP = """                if (exp.expected.fileExists && !obs.fileExists) deviations.push('product-missing')"""
NEW_FEP = """                if (exp.expected.fileExists && !obs.fileExists) deviations.push('product-missing')
                // P3 修复（2026-11-26 审计）：原 converged 只看"文件存在"，
                // 连写 6 次相同内容仍报 converged:true。加：write 类工具后产物 hash 未变即判未收敛。
                try {
                  if (/^(write|edit|apply_patch)$/i.test(String(exp.tool || '')) && exp.expected.fileExists && obs.fileExists) {
                    const _h = createHash('sha256').update(readFileSync(String(exp.target))).digest('hex').slice(0, 16)
                    if (state.lastProductHash && _h === state.lastProductHash) deviations.push('no-content-change')
                  }
                } catch { /* ignore */ }"""

# ── 状态：stepsSinceWrite 计数（两种形态：publish 原版 / runtime 已被 sync_mech_fix 改过）──
OLD_TOOLCALL_STREAK = """        s.toolCalls += 1
        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) s.writeCalls += 1"""
NEW_TOOLCALL_STREAK = """        s.toolCalls += 1
        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) { s.writeCalls += 1; s.stepsSinceWrite = 0 }
        else { s.stepsSinceWrite = (s.stepsSinceWrite || 0) + 1 }"""

# runtime 形态：writeCalls 单独一行，前面已有 M3 填充块
OLD_TOOLCALL_STREAK_RT = """        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) s.writeCalls += 1"""
NEW_TOOLCALL_STREAK_RT = """        if (cfg.writeTools.includes(String(event.data?.name ?? ''))) { s.writeCalls += 1; s.stepsSinceWrite = 0 }
        else { s.stepsSinceWrite = (s.stepsSinceWrite || 0) + 1 }"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已修" if MARK in t else "未修"} {path.parent.name}'
    if MARK in t:
        return True, f'已修跳过 {path.parent.name}'
    out = t
    steps = [
        (OLD_TOOLCALL_STREAK, NEW_TOOLCALL_STREAK, 'stepsSinceWrite'),
        (OLD_REPEAT, NEW_REPEAT, 'repeat guard+diff'),
        (OLD_PERF_ANCHOR, NEW_PERF_ANCHOR, 'claim consistency'),
        (OLD_HANDOFF_RE, NEW_HANDOFF_RE, 'soft handoff'),
        (OLD_CONTROL, NEW_CONTROL, 'degrade control'),
        (OLD_VERIFY_STOP, NEW_VERIFY_STOP, 'verify http'),
        (OLD_FEP, NEW_FEP, 'fep hash'),
    ]
    for old, new, label in steps:
        if old in out:
            out = out.replace(old, new, 1)
        elif label == 'stepsSinceWrite' and OLD_TOOLCALL_STREAK_RT in out:
            # runtime 形态回退
            out = out.replace(OLD_TOOLCALL_STREAK_RT, NEW_TOOLCALL_STREAK_RT, 1)
        else:
            return False, f'FAIL {path.parent.name}: 锚点 [{label}] 不存在'
    out = out.replace('// ALL_REMAINING-PATCHED (2026-11-26)',
                      f'// {MARK} (2026-11-26)\n// ALL_REMAINING-PATCHED (2026-11-26)', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.parent.name}: 7锚点'


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
