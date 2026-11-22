/**
 * M3 反模式匹配观察线集成测试：真实事件流 → pattern_lock trace（只写trace不steer）
 */
import assert from 'node:assert/strict'
import { apply } from '../index.mjs'
import { readFileSync, existsSync, unlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

let pass = 0
function check(label, ok) { assert.ok(ok, label); pass++; console.log('PASS', label) }

const tracePath = join(tmpdir(), `pattern-lock-${process.pid}.jsonl`)
try { unlinkSync(tracePath) } catch {}

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, tracePath, traceEnabled: true,
  patternLockTraceEnabled: true, driftSignalEnabled: false, bdiEnabled: false,
  controlEnabled: false, auditEnabled: false, criticEnabled: false,
  plannerCheckEnabled: false, presentGateEnabled: false, mindStateEnabled: false,
  fepEnabled: false, learningEnabled: false, verifyOnEditEnabled: false,
  injectionClassifierEnabled: false, injectionScanEnabled: false,
  todoEchoEnabled: false, skillsEnabled: false,
  sharedMaxPerTurn: 30
})
const emit = async (ev, ...a) => { for (const f of handlers.get(ev) || []) await f(...a) }
const pre = async (agent) => {
  let d = { messages: [] }
  for (const f of handlers.get('agent/pre-step') || []) d = (await f({ agent }, async () => d)) || d
  return d
}

const sid = 'pattern-lock-test'
await emit('session/event', { id: sid }, { type: 'turn/start', data: { turn: 1 } })
const agent = { session: { id: sid }, steer() {} }
// 先设 goalRestatedStep=0（首条用户消息），再灌 14 次同一工具调用
await emit('session/event', { id: sid }, { type: 'user/message', data: {
  source: { kind: 'user' }, content: [{ type: 'text', text: '读文件 A' }] } })
for (let i = 0; i < 14; i++) {
  await emit('session/event', { id: sid }, { type: 'tool/call', data: { callId: 'c' + i, name: 'read', arguments: '{}', step: i } })
  await pre(agent)
}

const lines = existsSync(tracePath) ? readFileSync(tracePath, 'utf8').split('\n').filter(Boolean) : []
const locks = lines.map(l => { try { return JSON.parse(l) } catch { return null } }).filter(r => r?.kind === 'pattern_lock')
check('工具锁定产生 pattern_lock trace', locks.length > 0)
check('trace 带 dominant/repetition/stepsSinceGoal', locks.length > 0 && locks[0].dominant === 'read' &&
  locks[0].repetition >= 0.6 && typeof locks[0].stepsSinceGoal === 'number')
const d = await pre(agent)
check('只写trace不steer（messages无安全提示）', !(d.messages || []).some(m =>
  String(m.content?.[0]?.text || '').includes('pattern') || String(m.content?.[0]?.text || '').includes('循环')))
check('冷却生效（14步锁定只报1-2次，非每步刷屏）', locks.length <= 3)

try { unlinkSync(tracePath) } catch {}
console.log(`\n${pass} PASS`)
