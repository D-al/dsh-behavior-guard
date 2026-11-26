#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源头修复补丁：把"软提醒"升级为"硬机制"（2026-11-26）

依据 docs/ROOT_CAUSE_AGENT_BEHAVIOR_20261126.md 的三层根因。8 项修复：
  P0-0  修 checkSyntax 的 cwd bug（相对路径按 workspace 解析）
  P0    语义检查器：client.js slot 存在性 / URL 目标存在性
  P0    交付闸门：拦"让用户去 F12/手动执行"的放弃式完成
  P0    Critic 真触发：turn-stopping 时产物存在但没 present → 视为 present
  P1    目标锚定 + 漂移守卫
  P1    防线2 正则扩展（含"不存在/静默忽略/无效"）
  P1    verify_on_stop 强制读回 + 重复探测第3次代执行
  P2    （skill 卡单独写文件）

幂等：用 BEHAVIOR_ROOTS-PATCHED 标记；重复运行不重复插入。
两版同步：publish 权威源 + runtime 运行版。

用法:
  python tools/patch_behavior_roots.py --apply --dry-run
  python tools/patch_behavior_roots.py --apply
  python tools/patch_behavior_roots.py --check
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'BEHAVIOR_ROOTS-PATCHED'

# ── P0-0: checkSyntax cwd bug ──
OLD_CWD = """function checkSyntax(filePath) {
  if (!filePath) return null
  const p = String(filePath)"""
NEW_CWD = """function checkSyntax(filePath) {
  if (!filePath) return null
  let p = String(filePath)
  // 行为根因P0-0（2026-11-26）：模型写相对路径（如 hardware-monitor-plugin/client.js），
  // 文件真实在 workspace，但此前按 harness cwd 解析 → 5 次假"Cannot find module"，
  // 模型反复 read 不存在的路径形成伪循环。修复：相对路径先按 workspace 根解析。
  if (!path.isAbsolute(p)) {
    for (const root of [WORKSPACE_ROOT_FOR_CHECK, path.dirname(WORKSPACE_ROOT_FOR_CHECK)]) {
      const cand = path.join(root, p)
      if (existsSync(cand)) { p = cand; break }
    }
  }"""

# ──  Semantics checker + constants (插在 checkSyntax 前) ──
SEM_FUNCS = """
// ── 行为根因 P0：语义检查（2026-11-26）──
// 语法检查（node --check）抓不到 slot 名不存在、URL 404 这类语义错误——
// 今天的失败全是语义级。这里做"能机械验证"的部分：slot 存在性 + 本地 URL 目标。
const WORKSPACE_ROOT_FOR_CHECK = (() => {
  const cands = [
    process.env.WORKSPACE_ROOT, 'D:/Brain/workspace/default-workspace',
    'C:/Users/Ad/Documents/deepseek-harness/default-workspace',
  ].filter(Boolean)
  return cands.find((c) => { try { return statSync(c, { throwIfNoEntry: false })?.isDirectory() } catch { return false } })
    || 'D:/Brain/workspace/default-workspace'
})()
const ASAR_PATH = 'D:/Deepseek Harness/resources/app.asar'
let _slotNamesCache = null
function knownSlotNames() {
  if (_slotNamesCache) return _slotNamesCache
  try {
    // 字节级扫描 asar 二进制，抽 slot 名（如 sidebar.right.pane.tab），不解压 asar。
    const buf = readFileSync(ASAR_PATH)
    const txt = buf.toString('latin1')
    const found = new Set()
    const re = /[a-z][a-z0-9]*(?:\\.[a-z0-9]+){2,}/g
    let m
    while ((m = re.exec(txt))) {
      const s = m[0]
      if (s.startsWith('sidebar.') || s.startsWith('conversation.')) found.add(s)
    }
    _slotNamesCache = found
    return found
  } catch { _slotNamesCache = new Set(); return _slotNamesCache }
}
function checkSemanticIssues(filePath, content) {
  const issues = []
  const text = String(content || '')
  // ① slot 存在性：ctx.slots.inject('X') 的 X 必须在 asar 里出现
  const injectRe = /ctx\\.slots\\.inject\\(\\s*['\"]([^'\"]+)['\"]/g
  let m
  const slots = knownSlotNames()
  while ((m = injectRe.exec(text))) {
    const slot = m[1]
    if (slots.size && !slots.has(slot)) {
      issues.push(`slot '${slot}' 在 DSH 中不存在（注册会被静默忽略）。可用 slot 示例：${[...slots].slice(0, 3).join(', ')}`)
    }
  }
  // ② 本地 URL：'/ui' 这类绝对路径若 curl 404，提示（只对明确写在代码里的做检查）
  const urlRe = /(?:src|href|window\\.open)\\s*[:=]\\s*['\"](\\/[a-z0-9/_-]+)['\"]/gi
  while ((m = urlRe.exec(text))) {
    const url = m[1]
    // 只检查 /ui 这类已知易错路径，避免误报
    if (/^\\/ui(\\/|$)/i.test(url)) issues.push(`URL '${url}' 可能 404（服务端未必注册该路由）——请用 / 或 /api/stats 等已确认路径`)
  }
  return issues
}
function checkWrittenSemantics(filePath) {
  try {
    const p = path.isAbsolute(String(filePath)) ? String(filePath) : path.join(WORKSPACE_ROOT_FOR_CHECK, String(filePath))
    if (!existsSync(p)) return []
    if (!/client\\.js$/i.test(p)) return []
    return checkSemanticIssues(p, readFileSync(p, 'utf8'))
  } catch { return [] }
}
"""

# ── verify-on-edit 调用点加语义检查 ──
OLD_VERIFY = """              const syntaxErr = checkSyntax(s.lastProduct)
              if (syntaxErr) {
                s.pendingInject = '[harness 语法检查] 刚写入的文件有语法错误：' + syntaxErr +
                  '\\n修复该语法错误后继续（不要跳过——后续步骤都会基于坏文件）。'
                info(`behavior-guard: verify-on-edit 发现语法错误 ${s.lastProduct}: ${String(syntaxErr).slice(0, 60)}`)
              }"""
NEW_VERIFY = """              const syntaxErr = checkSyntax(s.lastProduct)
              if (syntaxErr) {
                s.pendingInject = '[harness 语法检查] 刚写入的文件有语法错误：' + syntaxErr +
                  '\\n修复该语法错误后继续（不要跳过——后续步骤都会基于坏文件）。'
                info(`behavior-guard: verify-on-edit 发现语法错误 ${s.lastProduct}: ${String(syntaxErr).slice(0, 60)}`)
              } else {
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

# ── 防线2 正则扩展 ──
OLD_CORR = "(?:可能是?个?问题|是个错误|搞错了|不对劲|这是错的|猜错了|写错了)/;"
NEW_CORR = "(?:可能是?个?问题|是个错误|搞错了|不对劲|这是错的|猜错了|写错了|不存在|静默忽略|(?:注册|注入)被忽略|这个[\\w.]+无效|没有这个[\\w.]+)/;"

# ── 目标锚定：assistant/message 监听里加漂移守卫 ──
OLD_DRIFT = """        // 防线2：抓取 reasoning 里"发现问题但未修复"的线索，供压缩存档强制保留
        try { captureOpenCorrection(s) } catch { /* 纠错抓取失败不影响主流程 */ }"""
NEW_DRIFT = """        // 防线2：抓取 reasoning 里"发现问题但未修复"的线索，供压缩存档强制保留
        try { captureOpenCorrection(s) } catch { /* 纠错抓取失败不影响主流程 */ }
        // 行为根因 P1：目标锚定——s.anchorInitial 是不可变的用户初始目标（不被 latest 覆盖）
        try {
          if (!s.anchorInitial && s.initial) s.anchorInitial = String(s.initial)
          if (!s.anchorSet && s.initial) { s.anchorSet = true; s.anchorInitial = String(s.initial) }
        } catch { /* ignore */ }"""

# ── turn-stopping 开头：放弃式完成闸门 + Critic 真触发 ──
OLD_TURNSTOP = """      if (state.continuations >= cfg.maxContinuationsPerTurn) return
      if (state.totalContinuations >= cfg.maxContinuationsPerSession) return

      // ── present 前确定性深检"""

NEW_TURNSTOP = """      if (state.continuations >= cfg.maxContinuationsPerTurn) return
      if (state.totalContinuations >= cfg.maxContinuationsPerSession) return

      // ── 行为根因 P0：放弃式完成闸门（零 LLM）──
      // 检测"让用户去 F12 粘代码/手动执行"但没有对应工具调用 → 未完成交付，不允许 completed。
      try {
        const body = String(state.last?.body || '')
        const handoffRe = /(?:F12|控制台|粘贴.*(?:代码|脚本)|手动(?:执行|运行)|请你(?:自己|手动)|复制到.*控制台)/i
        if (handoffRe.test(body) && state.toolCalls === 0) {
          agent.steer(createSteeringMessage(
            '[harness 交付闸门] 检测到把工作甩给用户手动执行（F12/粘贴代码）且本轮无工具调用。'
            + '这不是完成交付。要么自己调用工具完成验证，要么明确说明具体卡点并请求用户指示——'
            + '不要以"让用户手动执行"收尾。', 'behavior-guard'))
          return
        }
        trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'handoff_gate',
          step: state.step, blocked: handoffRe.test(body) })
      } catch { /* 闸门失败不影响主流程 */ }

      // ── 行为根因 P0：让 Critic/深检真触发──
      // 原设计所有闸门挂 presentCalled===true，但模型可能全程不调 present 就直接收尾。
      // 修复：产物存在（lastProduct）但没 present 时，视为已 present，触发深检/Critic。
      try {
        if (!state.presentCalled && state.lastProduct && taskProfile(state).needsDeepReview) {
          let verified = false
          try {
            const p = path.isAbsolute(state.lastProduct) ? state.lastProduct : path.join(WORKSPACE_ROOT_FOR_CHECK, state.lastProduct)
            verified = statSync(p, { throwIfNoEntry: false })?.isFile() === true
          } catch { verified = false }
          if (verified && !state.autoPresented) {
            state.presentCalled = true
            state.autoPresented = true
            trace({ ts: new Date().toISOString(), sid: sessionId.slice(0, 8), kind: 'auto_present_for_gate',
              step: state.step, product: state.lastProduct })
          }
        }
      } catch { /* ignore */ }

      // ── present 前确定性深检"""


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
        (OLD_CWD, NEW_CWD, 'P0-0 cwd fix'),
        (OLD_VERIFY, NEW_VERIFY, 'P0 semantic check hook'),
        (OLD_CORR, NEW_CORR, 'P1 correction regex'),
        (OLD_DRIFT, NEW_DRIFT, 'P1 goal anchor'),
        (OLD_TURNSTOP, NEW_TURNSTOP, 'P0 handoff gate + critic trigger'),
    ]
    for old, new, label in steps:
        if old not in out:
            return False, f'FAIL {path.name}: 找不到锚点 [{label}]'
        out = out.replace(old, new, 1)
    # 插入语义检查函数 + 常量（在 checkSyntax 定义前）
    anchor = '// ── verify-on-edit：确定性语法检查（0 LLM 成本，仅 .py/.json/.yml/.yaml）──'
    if anchor not in out:
        return False, f'FAIL {path.name}: 找不到函数插入锚点'
    out = out.replace(anchor, SEM_FUNCS + '\n' + anchor, 1)
    out = out.replace(anchor, f'// {MARK} (2026-11-26)\n' + anchor, 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: 5锚点+函数插入'


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
