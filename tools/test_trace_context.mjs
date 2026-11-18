/**
 * S3 频次收尾单测：trace 自动带 turn / controlTotal，让频次审计能区分跨轮/跨会话。
 * 用法: node tools/test_trace_context.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, readFileSync } from 'node:fs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const TR = 'D:/Brain/workspace/bench/_tmp_trace_ctx.jsonl'
try { unlinkSync(TR) } catch {}
writeFileSync(TR, '')

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, traceEnabled: true, tracePath: TR,
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  auditEnabled: false, skillsEnabled: false, learningEnabled: false, fepEnabled: false,
})
const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }

// turn=7 的会话里产生一次 tool_call trace
await emit('session/event', { id: 'trace-ctx' }, { type: 'turn/start', data: { turn: 7 } })
await emit('session/event', { id: 'trace-ctx' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'test' }] } })
await emit('session/event', { id: 'trace-ctx' }, { type: 'tool/call', data: { name: 'read', arguments: '{}' } })

const rows = readFileSync(TR, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
check('① trace 有记录', rows.length >= 1)
const tc = rows.find((r) => r.kind === 'tool_call')
check('② tool_call trace 自动带 turn 字段', !!tc && tc.turn === 7)
check('③ tool_call trace 自动带 controlTotal 字段', !!tc && tc.controlTotal === 0)
check('④ step 每轮重置但 turn 保留（可区分跨轮）', !!tc && tc.step < tc.turn)

// 显式传入的字段不被覆盖
const TR2 = 'D:/Brain/workspace/bench/_tmp_trace_ctx2.jsonl'
try { unlinkSync(TR2) } catch {}
writeFileSync(TR2, '')
const h2 = new Map()
const ctx2 = { on: (n, cb) => { h2.set(n, [...(h2.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx2, { probePath: null, traceEnabled: true, tracePath: TR2, controlEnabled: false, mindStateEnabled: false,
  verifyOnStopEnabled: false, criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  auditEnabled: false, skillsEnabled: false, learningEnabled: false, fepEnabled: false })
const em2 = async (ev, ...a) => { for (const f of h2.get(ev) || []) await f(...a) }
await em2('session/event', { id: 'x2' }, { type: 'turn/start', data: { turn: 3 } })
await em2('session/event', { id: 'x2' }, { type: 'tool/call', data: { name: 'read', arguments: '{}' } })
const rows2 = readFileSync(TR2, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
check('⑤ 无 user/message 场景也有 turn 字段', rows2.some((r) => r.turn === 3))

console.log(`\n══════ ${pass}/${total} 通过 ══════`)
process.exit(pass === total ? 0 : 1)
