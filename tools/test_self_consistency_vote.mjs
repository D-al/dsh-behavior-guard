// 杠杆4 K=5 自洽投票验证（单测层 L2/L4）
// mock fetch 返回 5 次不同 verdict，验证：投票 trace、多数票、tie 回退、阈值
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, readFileSync, existsSync } from 'node:fs'

const TRACE = 'D:/Brain/workspace/bench/_tmp_vote_trace.jsonl'
const PY = 'D:/Brain/workspace/bench/_tmp_vote_artifact.py'
let pass = 0, fail = 0
const check = (label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { fail++; console.log(`FAIL  ${label} ${detail}`) }
}
const origFetch = globalThis.fetch

function harness(extra) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, {
    probePath: null, traceEnabled: true, tracePath: TRACE,
    auditEnabled: false, criticEnabled: true, plannerCheckEnabled: false,
    continuityEnabled: false, controlEnabled: false, mindStateEnabled: false,
    verifyOnStopEnabled: false, verifyOnEditEnabled: false, fepEnabled: false,
    specSignalEnabled: false, skillsEnabled: false, dangerGuardEnabled: false,
    deepCheckEnabled: false, learningEnabled: false, injectionScanEnabled: false,
    todoEchoEnabled: false, maxInjectionsPerTurn: 99, maxInjectionsPerSession: 99,
    voteOnCritic: true, ...extra,
  })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const steered = []
  const agent = { session: { id: 'vote-test' }, steer: (m) => steered.push(m.content?.[0]?.text || String(m)) }
  return { emit, steered, agent }
}
function traceRows() {
  if (!existsSync(TRACE)) return []
  return readFileSync(TRACE, 'utf8').split('\n').filter(Boolean)
    .map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean)
}
function mockVerdicts(seq, mode = 'content') {
  let i = 0
  globalThis.fetch = async () => {
    const v = seq[i++ % seq.length]
    const json = JSON.stringify({ verdict: v, confidence: 'high', error_class: 'none', reasons: [], evidence: [] })
    // thinking 模型典型格式：content 空，JSON 在 reasoning_content（callLLMOnce 有兜底）
    const message = mode === 'reasoning'
      ? { content: '', reasoning_content: '思考中...\n' + json }
      : { content: json }
    const body = { choices: [{ message, finish_reason: 'stop' }] }
    return { ok: true, json: async () => body }
  }
}
async function runVote(seq, extra = {}, mode = 'content') {
  try { unlinkSync(TRACE) } catch {}
  mockVerdicts(seq, mode)
  const h = harness({ voteK: seq.length, voteMinAgreement: 4, ...extra })
  await h.emit('session/event', { id: 'vote-test' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 'vote-test' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '做个工具' }] } })
  writeFileSync(PY, 'print("ok")\n')
  await h.emit('session/event', { id: 'vote-test' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: PY }) } })
  await h.emit('session/event', { id: 'vote-test' }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
  await h.emit('session/event', { id: 'vote-test' }, { type: 'tool/call', data: { name: 'present', arguments: '{}' } })
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  return traceRows().filter((r) => r.kind === 'self_consistency_vote')
}

try {
  // ① 4/5 ACCEPT → ACCEPT 胜出
  let votes = await runVote(['ACCEPT', 'ACCEPT', 'ACCEPT', 'ACCEPT', 'REJECT'])
  check('① 投票 trace 出现', votes.length >= 1, `got ${votes.length}`)
  const v1 = votes[votes.length - 1]
  check('① 多数票 ACCEPT 胜出', v1?.verdict === 'ACCEPT', JSON.stringify(v1))
  check('① 5 次采样都记录', (v1?.votes || []).length === 5, JSON.stringify(v1?.votes))
  check('① agreed=4 达标', v1?.agreed === 4 && v1?.minAgreement === 4, `agreed=${v1?.agreed}`)

  // ② tie 2/2/1 → UNCERTAIN（防把困惑封为共识）
  votes = await runVote(['ACCEPT', 'ACCEPT', 'REJECT', 'REJECT', 'UNCERTAIN'])
  const v2 = votes[votes.length - 1]
  check('② tie 回退 UNCERTAIN', v2?.verdict === 'UNCERTAIN', JSON.stringify(v2))
  check('② tie 标志为真', v2?.tie === true, `tie=${v2?.tie}`)

  // ③ 3/5 但 minAgreement=5 → UNCERTAIN
  votes = await runVote(['ACCEPT', 'ACCEPT', 'ACCEPT', 'REJECT', 'REJECT'], { voteMinAgreement: 5 })
  const v3 = votes[votes.length - 1]
  check('③ 低于 minAgreement 回退', v3?.verdict === 'UNCERTAIN', `agreed=${v3?.agreed}`)

  // ④ thinking 模型格式：content 空 + reasoning_content 含 JSON（真实会话 PARSE_FAIL 根因）
  votes = await runVote(['ACCEPT', 'ACCEPT', 'ACCEPT', 'ACCEPT', 'REJECT'], {}, 'reasoning')
  const v4 = votes[votes.length - 1]
  check('④ reasoning_content 里的 JSON 能解析', v4?.verdict === 'ACCEPT', JSON.stringify(v4?.votes))
  check('④ 无 PARSE_FAIL', !(v4?.votes || []).includes('PARSE_FAIL'), JSON.stringify(v4?.votes))
} finally {
  globalThis.fetch = origFetch
  try { unlinkSync(PY) } catch {}
  try { unlinkSync(TRACE) } catch {}
}
console.log(`\n${pass} pass, ${fail} fail`)
process.exit(fail ? 1 : 0)
