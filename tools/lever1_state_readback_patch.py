# -*- coding: utf-8 -*-
"""杠杆1补丁：确定性状态回读门（P0）。

对权威源 index.mjs 做精确字符串替换（带锚点校验，失败即中止不半途应用）。
应用后由 levers_deploy.py 同步到运行版。

锚点基于 2026-11-24 运行版 v2.9.0（2541 行，sha 362e3715...），脚本会先校验 sha。
"""
import sys, hashlib
from pathlib import Path

TARGET = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
EXPECTED_SHA = '362e37154586a5c4c8879c1c59973e3cc9bcb09ec1bf73f3f4e5fa0003113520'

# 每个补丁：(描述, old_string, new_string)
PATCHES = []

# ── 补丁 1：deterministicStateReadback 函数（插在 fileState 之后）──
PATCHES.append((
    'P0 函数定义',
    "const TURN_GUARD_DEFAULTS = {",
    """// ── P0: 确定性状态回读门（0 LLM，纯同步 IO）────────────────────────────────
// 铁律：
//  1) 写目标只取【结构化字段】：s.lastProduct + 最近 tool_calls 的 file_path/path 等；
//  2) 命令型工具只认结构化目标路径，绝不拿 fullArgs 正文做 /verify|pytest|test/ 关键词匹配
//     （:1034-1036 已记录该假绿根因：文件名/内容含 verify 被误判为已验证）；
//  3) mtime 容差复用 fileState 的 since - 1000（与 L1 同语义）。
const RB_CMD_TOOLS = new Set(['pwsh', 'bash', 'shell', 'exec', 'run_command', 'terminal'])
const RB_PATH_KEYS = ['file_path', 'path', 'filePath', 'target_file', 'notebook_path', 'target']

function deterministicStateReadback(state, cfg) {
  const s = state || {}
  const out = { ok: false, targets: [], evidence: [], errors: [] }
  const maxTargets = Math.max(1, Number(cfg?.deterministicReadbackMaxTargets) || 5)
  const seen = new Set()
  const addTarget = (raw, since) => {
    const p = String(raw || '').trim().replace(/\\\\/g, '/')
    if (!p || seen.has(p)) return
    seen.add(p)
    if (out.targets.length < maxTargets) out.targets.push({ path: p, since })
  }
  addTarget(s.lastProduct, s.turnStartedAt || Date.now())
  const trail = Array.isArray(s.trail) ? s.trail : []
  for (const call of trail.slice(-12)) {
    if (!call || call.kind !== 'call') continue
    const name = String(call.name || '')
    if (!WRITE_TOOLS.has(name) && !RB_CMD_TOOLS.has(name)) continue
    let a = {}
    try { a = JSON.parse(call.fullArgs || call.args || '{}') || {} } catch { /* 解析失败跳过，绝不猜 */ }
    for (const k of RB_PATH_KEYS) {
      if (typeof a[k] === 'string' && a[k].trim()) {
        addTarget(a[k], call.ts || s.turnStartedAt || Date.now())
        break
      }
    }
  }
  if (!out.targets.length) {
    out.errors.push('no-structured-write-target')
    return out
  }
  for (const t of out.targets) {
    try {
      const fs1 = fileState(t.path, t.since)
      if (!fs1.exists) { out.errors.push(t.path + ': 不存在'); continue }
      if (!fs1.fresh) { out.errors.push(t.path + ': mtime 非本轮写入'); continue }
      const buf = readFileSync(t.path)
      if (buf.length === 0) { out.errors.push(t.path + ': 空文件'); continue }
      out.evidence.push(t.path + ': exists=1 fresh=1 bytes=' + buf.length)
    } catch (e) {
      out.errors.push(t.path + ': 读取失败 ' + String(e?.message || e).slice(0, 80))
    }
  }
  out.ok = out.errors.length === 0 && out.evidence.length > 0
  return out
}

const TURN_GUARD_DEFAULTS = {""",
))

# ── 补丁 2：DEFAULTS 新增字段 ──
PATCHES.append((
    'DEFAULTS 配置字段',
    "  plannerCheckEnabled:",
    """  // ── P0 确定性状态回读门（2026-11-24；零 LLM，纯同步 IO）──
  deterministicReadbackEnabled: true,
  deterministicReadbackMaxTargets: 5,
  deterministicReadbackMaxPerTurn: 1,
  deterministicReadbackReserveD5: 1,
  plannerCheckEnabled:""",
))

# ── 补丁 3：state 初始化 ──
PATCHES.append((
    'state 初始化字段',
    "        verifyEvidence: 0,",
    """        verifyEvidence: 0,
        // P0 确定性状态回读门
        stateReadbackOk: false, stateReadbackEvidence: [], stateReadbackErrors: [], deterministicReadbackCount: 0,""",
))

# ── 补丁 4：turn-stopping gate（深检后 Critic 前）──
PATCHES.append((
    'turn-stopping 回读门',
    "      // ── verify-on-stop（合并补漏：改了文件没验证证据就否决退出，纯规则 0 LLM）──",
    """      // ── P0 确定性状态回读门（Critic 后、verify-on-stop 前；0 LLM，纯同步 IO）──
      if (
        cfg.deterministicReadbackEnabled &&
        taskProfile(state).needsVerify &&
        state.writeCalls > 0 &&
        (state.deterministicReadbackCount || 0) < cfg.deterministicReadbackMaxPerTurn
      ) {
        state.deterministicReadbackCount = (state.deterministicReadbackCount || 0) + 1
        let rb
        try { rb = deterministicStateReadback(state, cfg) }
        catch (e) { rb = { ok: false, evidence: [], errors: ['readback-throw: ' + String(e?.message || e)], targets: [] } }
        state.stateReadbackOk = rb.ok === true
        state.stateReadbackEvidence = Array.isArray(rb.evidence) ? rb.evidence : []
        state.stateReadbackErrors = Array.isArray(rb.errors) ? rb.errors : []
        trace({ ts: new Date().toISOString(), sid: sessionId || '', kind: 'verify_state_readback',
          step: state.step, ok: rb.ok, targets: (rb.targets || []).length,
          evidence: state.stateReadbackEvidence.slice(0, 5), errors: state.stateReadbackErrors.slice(0, 3) })
        const d5Reserve = Math.max(0, Number(cfg.deterministicReadbackReserveD5) || 0)
        if (!rb.ok && state.sharedInjections + 1 <= cfg.sharedMaxPerTurn - d5Reserve) {
          state.sharedInjections += 1
          agent.steer(createSteeringMessage(
            '[harness 确定性状态回读] 本轮声明的写产物回读失败，不能交付：' +
            (state.stateReadbackErrors.slice(0, 2).join('；') || '未找到可回读的写产物') +
            '。现在立刻用 write 工具把内容真正写到目标路径（或用 pwsh 确认文件已落盘），' +
            '不要只在正文里声称已写入；看到工具成功结果后再 present。',
            'behavior-guard'
          ))
          info(`behavior-guard: [确定性回读] FAIL session=${sessionId} — ${state.stateReadbackErrors.slice(0, 2).join(' | ')}`)
          return
        }
      }

      // ── verify-on-stop（合并补漏：改了文件没验证证据就否决退出，纯规则 0 LLM）──""",
))

# ── 补丁 5：verified 字段拆分 ──
PATCHES.append((
    'verified 字段拆分',
    "    verified: !!(st.verifyRan || st.verifiedThisTurn || (st.verifyEvidence || 0) > 0),",
    """    verifiedByLLM: !!(st.verifyRan || st.verifiedThisTurn || (st.verifyEvidence || 0) > 0),
    verifiedDeterministic: st.stateReadbackOk === true,
    verified: !!(st.verifyRan || st.verifiedThisTurn || (st.verifyEvidence || 0) > 0 || st.stateReadbackOk === true),""",
))


def main():
    import sys as _sys
    raw = TARGET.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')
    expect = _sys.argv[1] if len(_sys.argv) > 1 else EXPECTED_SHA
    print(f'anchor sha={actual[:16]} expected={expect[:16]} crlf={crlf}')
    if actual != expect:
        print('ABORT: sha 不匹配')
        _sys.exit(1)
    for desc, old, new in PATCHES:
        cnt = s.count(old)
        if cnt != 1:
            print(f'ABORT: [{desc}] 锚点出现 {cnt} 次（期望恰好 1 次），不应用')
            _sys.exit(1)
        s = s.replace(old, new, 1)
        print(f'  OK [{desc}]')
    out = s.replace('\n', '\r\n') if crlf else s
    TARGET.write_bytes(out.encode('utf-8'))
    final = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    print(f'APPLIED patch1 state_readback, new sha={final[:16]}')


if __name__ == '__main__': main()
