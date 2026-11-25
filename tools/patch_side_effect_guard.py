#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给 harness 打"副作用型破坏识别"补丁（防线3）。

缘起（2026-11-26 事故）：
  seq 388 plugin_manager remove_bundle 是白名单工具；真正毁目录的是它内部
  pnpm 的 EPERM rename（seq 389）。tool/result 是 isError:false + kind:"permission"，
  harness 没识别成破坏，反而让模型以为只是"权限问题"。

补丁（幂等）：
  1. DANGER_BLOCK 加 `Copy-Item -Recurse -Force ... node_modules`（seq 646 用的正是它）
  2. tool/result 钩子加副作用检测：application:failed / ERR_PNPM_EPERM / _tmp_* rename
     → 记 trace + pendingInject（只提醒，不阻断——profile 默认 full-access）
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'SIDE_EFFECT_GUARD-PATCHED'

OLD_BLOCK = "  [/Stop-Process[^|;]*-Name\\s+\\*?\\w/i, '批量 Stop-Process'],\n]"
NEW_BLOCK = "  [/Stop-Process[^|;]*-Name\\s+\\*?\\w/i, '批量 Stop-Process'],\n  [/(?=.*Copy-Item)(?=.*-Recurse)(?=.*-Force)(?=.*node_modules)[^|;]*/i, '覆盖式复制进 node_modules（可能污染插件源码）'],\n]"

OLD_HOOK = """      if (event.type === 'tool/result') {
        // S24 执行层失败自愈：只认结构化 isError/data.error，绝不扫结果正文"""
NEW_HOOK = """      if (event.type === 'tool/result') {
        // ── 防线3：副作用型破坏识别（零 LLM）──
        // 事故依据：remove_bundle 返回 isError:false + kind:permission，实际 pnpm EPERM
        // 已清空无关插件目录。harness 不能只看 isError，要看 application/changed/pnpm 错误。
        try { detectSideEffectDamage(event, s) } catch { /* 副作用检测绝不阻断主流程 */ }
        // S24 执行层失败自愈：只认结构化 isError/data.error，绝不扫结果正文"""

# 运行版（node_modules）的 tool/result 钩子与 publish 不同：它是老版 v3.1 三档状态，
# 没有 S24 自愈注释。这里给一个更通用的锚点（两版都匹配）。
OLD_HOOK_RUNTIME = """      if (event.type === 'tool/result') {
        const c = s.trail.filter((x) => x.kind === 'call').pop()"""

NEW_HOOK_RUNTIME = """      if (event.type === 'tool/result') {
        // ── 防线3：副作用型破坏识别（零 LLM）──
        try { detectSideEffectDamage(event, s) } catch { /* 副作用检测绝不阻断主流程 */ }
        const c = s.trail.filter((x) => x.kind === 'call').pop()"""

FUNC = """

// ── 防线3：识别"工具报成功但内部有破坏性副作用" ──
// 只扫结构化字段和确定性错误特征，不读正文语义（避免误报）。
const SIDE_EFFECT_ERROR_RE = /(ERR_PNPM_EPERM|EPERM:[^\\n]{0,80}rename|_tmp_\\d+\\s*->|application:\\s*\\\\?['"]?failed|changed:\\s*true[^\\n]{0,40}application)/i;
function detectSideEffectDamage(event, s) {
  if (!s || !event?.data?.message?.content) return
  const blocks = Array.isArray(event.data.message.content) ? event.data.message.content : []
  const txt = blocks.map(b => (b && typeof b.text === 'string') ? b.text : '').join('\\n')
  if (!SIDE_EFFECT_ERROR_RE.test(txt)) return
  // 同一工具结果可能重放多次（compaction），按文本前 120 字去重
  const key = txt.slice(0, 120)
  s._sideEffectSeen = s._sideEffectSeen || new Set()
  if (s._sideEffectSeen.has(key)) return
  s._sideEffectSeen.add(key)
  try {
    trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'side_effect_damage', step: s.step, tool: s.toolNamesById?.[event.data?.message?.toolCallId] || '?', text: key.slice(0, 100) })
  } catch { /* trace 失败不影响 */ }
  s.pendingInject = (s.pendingInject || '') + '[harness 副作用告警] 刚执行的工具内部出现 pnpm/rename 类错误（EPERM）或 application:failed/changed:true。'
    + '不要把它当成普通"权限问题"忽略——它可能已经清空或改动了无关插件/配置文件。'
    + '下一步先核对现场文件状态（关键文件是否还在、bundle 名是否被改），再继续。\\n'
}
"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已打补丁" if MARK in t else "未打补丁"} {path}'
    if MARK in t:
        return True, f'已打补丁，跳过 {path.name}'
    out = t
    # DANGER_BLOCK 两版一致
    if OLD_BLOCK not in out:
        return False, f'FAIL {path.name}: 找不到 DANGER_BLOCK 锚点'
    out = out.replace(OLD_BLOCK, NEW_BLOCK, 1)
    # tool/result hook：publish 用 S24 版，runtime 用 v3.1 老版（两版差 580 行）
    hook_old, hook_new = (OLD_HOOK, NEW_HOOK) if OLD_HOOK in out else (OLD_HOOK_RUNTIME, NEW_HOOK_RUNTIME)
    if hook_old not in out:
        return False, f'FAIL {path.name}: 找不到 tool/result 锚点'
    out = out.replace(hook_old, hook_new, 1)
    # 插入函数（在 classifyDanger 之前）
    anchor = 'function classifyDanger(name, argsText) {'
    if anchor not in out:
        return False, f'FAIL {path.name}: 找不到函数锚点'
    out = out.replace(anchor, f'// {MARK} (2026-11-26)\n' + FUNC + '\n' + anchor, 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: DANGER_BLOCK + tool/result hook + detect function'


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
