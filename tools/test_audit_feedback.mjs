/**
 * S8 审计自校准落盘单测：
 * 验证审计注入后 3 步，_audit_feedback.jsonl 生成且 effective 字段正确。
 * 原 bug：结算放在审计门控内部，要求"再次触发审计"才结算——门控低频导致文件从未生成。
 * 用法: node tools/test_audit_feedback.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, readFileSync, existsSync } from 'node:fs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const TRACE = 'D:/Brain/workspace/bench/_tmp_audit_trace.jsonl'
const FEEDBACK = 'D:/Brain/workspace/bench/_tmp_audit_feedback.jsonl'
for (const f of [TRACE, FEEDBACK]) { try { unlinkSync(f) } catch {}; writeFileSync(f, '') }

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null,
  traceEnabled: true, tracePath: TRACE,
  auditFeedbackPath: FEEDBACK,
  auditEnabled: true, auditEverySteps: 2, auditEveryStepsAnomaly: 2,
  maxInjectionsPerSession: 99, maxInjectionsPerTurn: 99, sharedMaxPerTurn: 99,
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  skillsEnabled: false, learningEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  injectionClassifierEnabled: false,  // 隔离：本测审计自校准，不跑注入分类器(它有独立测试)
  deepCheckEnabled: false, continuityEnabled: false,
})

const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
const pre = async (agent) => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }

// mock 审计员：第一次返回 ISSUE（触发注入+设置 auditEval），之后返回 OK
let auditCalls = 0
const origFetch = globalThis.fetch
globalThis.fetch = async () => {
  auditCalls++
  const verdict = auditCalls === 1 ? 'ISSUE' : 'OK'
  return { ok: true, json: async () => ({
    choices: [{ message: { content: JSON.stringify({ verdict, issue: 'need fix', fix: 'do it' }) } }],
  }) }
}

const agent = { session: { id: 'audit-fb' }, steer() {} }
await emit('session/event', { id: 'audit-fb' }, { type: 'turn/start', data: { turn: 1 } })
await emit('session/event', { id: 'audit-fb' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个文件并验证' }] } })
// 制造 2 次 FAIL 触发审计门控（D5 是风险门控，不是固定周期）
// 注意：用不同参数/不同工具名，避开 D2「同参数双败」提前 return 抢走门控
for (let i = 0; i < 2; i++) {
  await emit('session/event', { id: 'audit-fb' }, { type: 'tool/call', data: { name: i === 0 ? 'read' : 'glob', arguments: JSON.stringify({ path: `/tmp/${i}` }) } })
  await emit('session/event', { id: 'audit-fb' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'Error: not found' }] } } })
}
await pre(agent)

// 再走 3+ 步（每步 pre-step），让结算触发
for (let i = 0; i < 4; i++) {
  await emit('session/event', { id: 'audit-fb' }, { type: 'tool/call', data: { name: 'read', arguments: '{}' } })
  await emit('session/event', { id: 'audit-fb' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'x' }] } } })
  await pre(agent)
}

globalThis.fetch = origFetch

check('① 审计员确实被调用', auditCalls >= 1)
const exists = existsSync(FEEDBACK)
check('② _audit_feedback.jsonl 已生成', exists)
if (exists) {
  const rows = readFileSync(FEEDBACK, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  check('③ 至少有一条自校准记录', rows.length >= 1)
  check('④ 记录含 effective 字段', rows.length > 0 && typeof rows[0].effective === 'boolean')
  check('⑤ 记录含 badNow/stepNow', rows.length > 0 && typeof rows[0].badNow === 'number' && typeof rows[0].stepNow === 'number')
  check('⑥ 记录含 gate/rubric 上下文', rows.length > 0 && 'rubric' in rows[0])
}

console.log(`\n══════ ${pass}/${total} 通过 ══════`)
process.exit(pass === total ? 0 : 1)
