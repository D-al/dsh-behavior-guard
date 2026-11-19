/**
 * S9 有状态反馈 + 循环上限单测：
 * 验证审计问题写入 reviewState，下一轮 turn/start 回灌 review_echo，超限时给强提示。
 * 用法: node tools/test_review_loop.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, readFileSync } from 'node:fs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const TRACE = 'D:/Brain/workspace/bench/_tmp_review_trace.jsonl'
try { unlinkSync(TRACE) } catch {}
writeFileSync(TRACE, '')

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, traceEnabled: true, tracePath: TRACE,
  auditEnabled: true, reviewFeedbackEnabled: true, reviewMaxCycles: 2, noProgressSteps: 3,
  maxInjectionsPerSession: 99, maxInjectionsPerTurn: 99, sharedMaxPerTurn: 99,
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  skillsEnabled: false, learningEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, continuityEnabled: false,
})
const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
const pre = async (agent) => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }

let auditCalls = 0
const origFetch = globalThis.fetch
globalThis.fetch = async () => {
  auditCalls++
  return { ok: true, json: async () => ({
    choices: [{ message: { content: JSON.stringify({ verdict: 'ISSUE', issue: '产物缺少入口函数', fix: '补 main()' }) } }],
  }) }
}

const agent = { session: { id: 'review-loop' }, steer() {} }
// 第 1 轮：连续 6 步只读 OK（noProgress 门控触发审计，避开 D1/D2 失败信号分支）
await emit('session/event', { id: 'review-loop' }, { type: 'turn/start', data: { turn: 1 } })
await emit('session/event', { id: 'review-loop' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写文件并验证' }] } })
for (let i = 0; i < 6; i++) {
  await emit('session/event', { id: 'review-loop' }, { type: 'tool/call', data: { name: 'read', arguments: JSON.stringify({ path: `/tmp/${i}` }) } })
  await emit('session/event', { id: 'review-loop' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
  // assistant/message 更新 noProgressSteps（读操作非 productive → 累加）
  await emit('session/event', { id: 'review-loop' }, { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: 'thinking' }], tool_calls: [] } } })
  await pre(agent)
}
check('① 审计 ISSUE 已触发', auditCalls >= 1)

// 第 2 轮：turn/start 应标记 pendingReviewEcho，pre-step 注入 review_echo
await emit('session/event', { id: 'review-loop' }, { type: 'turn/start', data: { turn: 2 } })
const d2 = await pre(agent)
const echo = (d2?.messages || []).find((m) => JSON.stringify(m?.content || '').includes('反馈环'))
check('② 下一轮注入 review_echo', !!echo)
if (echo) {
  const txt = (Array.isArray(echo.content) ? echo.content.map((b) => b?.text || '').join('') : String(echo.content))
  check('③ echo 带上轮具体问题', txt.includes('缺少入口函数'))
  check('④ echo 要求先确认是否修复', txt.includes('先确认') || txt.includes('已解决'))
}

const rows = readFileSync(TRACE, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
check('⑤ trace 记录 review_state', rows.some((r) => r.kind === 'review_state' && r.source === 'audit'))
check('⑥ trace 记录 review_echo', rows.some((r) => r.kind === 'review_echo' && r.cycles === 1))

// 第 3 轮：不再回灌（resolved=true 后不重复）
await emit('session/event', { id: 'review-loop' }, { type: 'turn/start', data: { turn: 3 } })
const d3 = await pre(agent)
check('⑦ 已回灌的问题不再重复注入', !(d3?.messages || []).some((m) => JSON.stringify(m?.content || '').includes('反馈环')))

const rows2 = readFileSync(TRACE, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
check('⑧ 无超限误报（cycles=1 未超 2）', !rows2.some((r) => r.kind === 'review_echo' && r.overLimit === true))

globalThis.fetch = origFetch
console.log(`\n══════ ${pass}/${total} 通过 ══════`)
process.exit(pass === total ? 0 : 1)
