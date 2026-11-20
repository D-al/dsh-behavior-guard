/**
 * 假绿修复验证：把原测试里的恒真断言/零check段，改成真行为反向测试。
 * 用 mock fetch 避免真调 35B（上次直接触发被 SIGTERM）。
 *
 * 覆盖：① MTP 低接受率触发审计 ② tokenEstimate 真值 ③ G4 confidence=low→UNCERTAIN
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, readFileSync, existsSync } from 'node:fs'

let pass = 0, fail = 0
const check = (label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { fail++; console.log(`FAIL  ${label} ${detail}`) }
}

const TRACE = 'D:/Brain/workspace/bench/_tmp_falsegreen_trace.jsonl'
const SPEC = 'D:/Brain/workspace/bench/_tmp_falsegreen_spec.log'
const PY = 'D:/Brain/workspace/bench/_tmp_falsegreen.py'
const origFetch = globalThis.fetch

function harness(extra) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, {
    probePath: null, traceEnabled: true, tracePath: TRACE,
    auditEnabled: true, criticEnabled: false, plannerCheckEnabled: false,
    continuityEnabled: false, controlEnabled: false, mindStateEnabled: false,
    verifyOnStopEnabled: false, verifyOnEditEnabled: false, fepEnabled: false,
    specSignalEnabled: true, specLogPath: SPEC, specAcceptanceMin: 0.65,
    skillsEnabled: false, dangerGuardEnabled: false, deepCheckEnabled: false,
    learningEnabled: false, injectionScanEnabled: false, todoEchoEnabled: false,
    maxInjectionsPerTurn: 99, maxInjectionsPerSession: 99,
    ...extra,
  })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const steered = []
  const agent = { session: { id: 'fg' }, steer: (m) => steered.push(m.content?.[0]?.text || String(m)) }
  const pre = async () => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }
  return { emit, steered, agent, pre }
}
function traceRows() {
  if (!existsSync(TRACE)) return []
  return readFileSync(TRACE, 'utf8').split('\n').filter(Boolean)
    .map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean)
}
const startTurn = async (h) => {
  await h.emit('session/event', { id: 'fg' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 'fg' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"a.txt"}' } })
  await h.emit('session/event', { id: 'fg' }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
}

try {
  // ① MTP：低接受率应触发审计 llm trace；高接受率不触发
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ choices: [{ message: { content: JSON.stringify({ verdict: 'OK', reason: 'none' }) } }] }) })
  for (const [label, acc, expectAudit] of [['低0.50', 0.5, true], ['高0.95', 0.95, false]]) {
    try { unlinkSync(TRACE) } catch {}
    writeFileSync(SPEC, `slot print_timing: id 0 | task 1 | draft acceptance = ${acc.toFixed(5)} ( 100 accepted / 100 generated)\n`)
    const h = harness({})
    await startTurn(h)
    await h.pre()
    const audited = traceRows().some((r) => r.kind === 'llm' && r.tag === 'audit')
    check(`① MTP ${label} → 审计触发=${audited}（期望${expectAudit}）`, audited === expectAudit)
  }

  // ② tokenEstimate：有注入时字段必须为正数（原 >=0 恒真）
  try { unlinkSync(TRACE) } catch {}
  const hb = harness({ continuityEnabled: true })
  const ag = { session: { id: 'fg' }, steer() {} }
  await hb.emit('session/event', { id: 'fg' }, { type: 'turn/start', data: { turn: 1 } })
  await hb.emit('session/event', { id: 'fg' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'task' }] } })
  await hb.emit('session/event', { id: 'fg' }, { type: 'compaction/prune', data: {} })
  const d = await hb.pre()
  const msgs = d?.messages || []
  const withTok = msgs.filter((m) => typeof m.tokenEstimate === 'number')
  if (withTok.length === 0) {
    console.log('SKIP  ② 本场景未产生注入消息——不算通过，需换能触发注入的场景')
  } else {
    check(`② 注入消息 ${withTok.length} 条，tokenEstimate 全为正数`,
      withTok.every((m) => m.tokenEstimate > 0), JSON.stringify(withTok.map((m) => m.tokenEstimate)))
  }

  // ③ G4：confidence=low 的 REJECT 必须降级为 UNCERTAIN（不硬拒）
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ choices: [{ message: { content: JSON.stringify({
    verdict: 'REJECT', confidence: 'low', error_class: 'none', reasons: ['证据不足'], fix: '补证据'
  }) } }] }) })
  const hc = harness({ criticEnabled: true, auditEnabled: false })
  await hc.emit('session/event', { id: 'fg' }, { type: 'turn/start', data: { turn: 1 } })
  await hc.emit('session/event', { id: 'fg' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '做个工具' }] } })
  writeFileSync(PY, 'print("ok")\n')
  await hc.emit('session/event', { id: 'fg' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: PY }) } })
  await hc.emit('session/event', { id: 'fg' }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
  await hc.emit('session/event', { id: 'fg' }, { type: 'tool/call', data: { name: 'present', arguments: '{}' } })
  await hc.emit('agent/turn-stopping', { agent: hc.agent, turn: 1 })
  const rv = traceRows().filter((r) => r.kind === 'review_verdict' && r.review_kind === 'critic')
  check(`③ G4: Critic REJECT+low 产生判定（${rv.length}条）`, rv.length >= 1)
  const hardReject = hc.steered.some((s) => /C-REJECT/.test(s))
  check('③ G4: confidence=low 不硬拒（无 C-REJECT 注入）', !hardReject,
    hc.steered.filter((s) => /C-REJECT/.test(s)).join('|').slice(0, 120))
} finally {
  globalThis.fetch = origFetch
  for (const f of [SPEC, PY]) { try { unlinkSync(f) } catch {} }
}

console.log(`\n${pass} pass, ${fail} fail`)
process.exit(fail ? 1 : 0)
