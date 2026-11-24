# -*- coding: utf-8 -*-
"""杠杆2补丁：显式状态板 + 规划闸（P1）。

在控制回合（agent/pre-step 内的 controlTurn）注入状态板：cwd / 已改文件 / 未完成前置项。
纯规则、零 LLM、零显存。含 4096 字节门禁（bridge send 硬限）。
"""
import sys, hashlib
from pathlib import Path

TARGET = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
EXPECTED_SHA = '362e37154586a5c4c8879c1c59973e3cc9bcb09ec1bf73f3f4e5fa0003113520'
PATCHES = []

# ── 补丁 1：buildStateBoard 函数（插在 workspaceSnapshot 函数前）──
PATCHES.append((
    'P1 状态板函数',
    "function workspaceSnapshot",
    r"""// ── P1: 显式状态板（0 LLM；规则驱动，不依赖模型自省）──────────────────────
// 三个字段：cwd / 最近改动文件 / 未完成前置项。
// 硬约束：bridge send 4096 字节（session-bridge/index.mjs:134），超了只保留未完成项+最近3文件。
function buildStateBoard(s, cfg) {
  const st = s || {}
  const lines = []
  let cwd = ''
  try { cwd = process.cwd().replace(/\\\\/g, '/') } catch { cwd = '(unknown)' }
  lines.push(`cwd=${cwd}`)
  const changed = Array.isArray(st.changedFiles) ? st.changedFiles.slice(-8) : []
  lines.push('changed=' + (changed.length ? changed.slice(-3).join(', ') : '(none)'))
  const todos = Array.isArray(st.todos) ? st.todos : []
  const pending = todos.filter((t) => t && t.status !== 'completed' && /\[VERIFY\]/.test(String(t.text || t.title || '')))
  lines.push('unfinished=' + (pending.length ? pending.slice(0, 4).map((t) => String(t.text || t.title).slice(0, 50)).join(' | ') : '(none)'))
  let text = '【状态板】' + lines.join('；')
  // 字节门禁：超 4096 就逐级降级
  if (Buffer.byteLength(text, 'utf8') > 4000) {
    text = '【状态板】cwd=' + cwd + '；unfinished=' + (pending.length ? pending.slice(0, 2).map((t) => String(t.text || t.title).slice(0, 30)).join(' | ') : '(none)')
  }
  if (Buffer.byteLength(text, 'utf8') > 4000) text = '【状态板】unfinished=' + (pending.length || 0)
  return { text, bytes: Buffer.byteLength(text, 'utf8'), pending: pending.length }
}

function workspaceSnapshot""",
))

# ── 补丁 2：DEFAULTS 字段 ──
PATCHES.append((
    'DEFAULTS 字段',
    "  plannerCheckEnabled:",
    """  // ── P1 状态板（2026-11-24）──
  stateBoardEnabled: true,
  stateBoardEverySteps: 4,
  stateBoardMaxBytes: 4000,
  plannerCheckEnabled:""",
))

# ── 补丁 3：state 初始化 ──
PATCHES.append((
    'state 初始化',
    "        verifyEvidence: 0,",
    """        verifyEvidence: 0,
        changedFiles: [], stateBoardCount: 0,""",
))

# ── 补丁 4：tool/call 累积 changedFiles（在 verify-on-stop 证据块后）──
PATCHES.append((
    'changedFiles 累积',
    "          // verify-on-stop 证据：只认【命令型工具的验证动作】",
    """          // ── P1: 累积本轮写过的文件路径（给状态板用）──
          if (WRITE_TOOLS.has(callName)) {
            try {
              const aa = JSON.parse(callFull || '{}') || {}
              for (const kk of ['file_path', 'path', 'filePath', 'target_file', 'notebook_path', 'target']) {
                if (typeof aa[kk] === 'string' && aa[kk].trim()) {
                  if (!Array.isArray(s.changedFiles)) s.changedFiles = []
                  s.changedFiles.push(aa[kk].trim().replace(/\\\\/g, '/'))
                  if (s.changedFiles.length > 40) s.changedFiles.shift()
                  break
                }
              }
            } catch { /* 解析失败跳过 */ }
          }
          // verify-on-stop 证据：只认【命令型工具的验证动作】""",
))

# ── 补丁 5：控制回合注入状态板（在 M1 episodicSearch 前）──
PATCHES.append((
    '控制回合注入状态板',
    "          // ── M1 episodicSearch 情景检索：进入控制回合 parts.push",
    """          // ── P1: 状态板（每 N 步注入一次，计入 shared 预算）──
          if (
            cfg.stateBoardEnabled &&
            (s.step || 0) > 0 &&
            (s.step % Math.max(1, Number(cfg.stateBoardEverySteps) || 4)) === 0 &&
            state.sharedInjections < cfg.sharedMaxPerTurn
          ) {
            const sb = buildStateBoard(s, cfg)
            if (sb.text) {
              state.sharedInjections += 1
              s.stateBoardCount = (s.stateBoardCount || 0) + 1
              parts.push(sb.text)
              trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'state_board_inject',
                step: s.step, bytes: sb.bytes, pending: sb.pending })
            }
          }
          // ── M1 episodicSearch 情景检索：进入控制回合 parts.push""",
))


def main():
    raw = TARGET.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')  # 归一化做替换
    import sys as _sys
    expect = _sys.argv[1] if len(_sys.argv) > 1 else EXPECTED_SHA
    print(f'anchor sha={actual[:16]} expected={expect[:16]} crlf={crlf}')
    if actual != expect:
        print('ABORT: sha 不匹配')
        _sys.exit(1)
    for desc, old, new in PATCHES:
        cnt = s.count(old)
        if cnt != 1:
            print(f'ABORT: [{desc}] 锚点 {cnt} 次')
            sys.exit(1)
        s = s.replace(old, new, 1)
        print(f'  OK [{desc}]')
    out = s.replace('\n', '\r\n') if crlf else s
    TARGET.write_bytes(out.encode('utf-8'))
    print(f'APPLIED patch2 state_board, new sha={hashlib.sha256(s.encode()).hexdigest()[:16]}')


if __name__ == '__main__': main()
