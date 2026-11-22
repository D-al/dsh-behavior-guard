/**
 * M3 价值复核（2026-11-22）：⑤ 意图漂移 trace 埋点 + ⑥ BDI 死代码删除
 * - ⑤ 在线检测已有但零可观测 → 补 intent_drift kind
 * - ⑥ 条件恒假（bdi.goal 与 latest.slice(0,250) 同源）→ 删除，避免虚假宣称
 */
import assert from 'node:assert/strict'
import { apply } from '../index.mjs'
import { readFileSync, existsSync, unlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

let pass = 0
function check(label, ok) { assert.ok(ok, label); pass++; console.log('PASS', label) }

const tracePath = join(tmpdir(), `intent-drift-trace-${process.pid}.jsonl`)
try { unlinkSync(tracePath) } catch {}

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, tracePath, traceEnabled: true,
  driftSignalEnabled: true, bdiEnabled: true,
  controlEnabled: true, controlEverySteps: 1, maxControlPerSession: 24,
  auditEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
  presentGateEnabled: false, mindStateEnabled: false, fepEnabled: false,
  learningEnabled: false, verifyOnEditEnabled: false,
  injectionClassifierEnabled: false, injectionScanEnabled: false,
  todoEchoEnabled: false, skillsEnabled: false,
  maxInjectionsPerSession: 20, sharedMaxPerTurn: 20
})
const emit = async (ev, ...a) => { for (const f of handlers.get(ev) || []) await f(...a) }
const pre = async (agent) => {
  let d = { messages: [] }
  for (const f of handlers.get('agent/pre-step') || []) d = (await f({ agent }, async () => d)) || d
  return d
}

const sid = 'drift-trace-test'
await emit('session/event', { id: sid }, { type: 'turn/start', data: { turn: 1 } })
// initial + latest 在控制回合前就设置好（控制回合每会话只触发第一次）
await emit('session/event', { id: sid }, { type: 'user/message', data: {
  source: { kind: 'user' }, content: [{ type: 'text', text: '分析显存分配策略和专家缓存命中率的优化空间' }]
} })
await emit('session/event', { id: sid }, { type: 'user/message', data: {
  source: { kind: 'user' }, content: [{ type: 'text', text: '改成写一个咖啡店网页，要有菜单和预定按钮' }]
} })
const agent = { session: { id: sid }, steer() {} }
await emit('session/event', { id: sid }, { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: '进展' }] } } })
await pre(agent)

const lines = existsSync(tracePath) ? readFileSync(tracePath, 'utf8').split('\n').filter(Boolean) : []
const drifts = lines.map(l => { try { return JSON.parse(l) } catch { return null } }).filter(r => r?.kind === 'intent_drift')
check('⑤ 漂移检测有 intent_drift trace 埋点', drifts.length > 0)
check('trace 带 overlap/drifted 字段', drifts.length > 0 &&
  typeof drifts[0].overlap === 'number' && typeof drifts[0].drifted === 'boolean')
check('trace 带时机字段(StepShield: 时机才有用)', drifts.length > 0 &&
  typeof drifts[0].stepsSinceLastDrift === 'number' &&
  typeof drifts[0].stepsSinceGoal === 'number' &&
  typeof drifts[0].controlCount === 'number')
const anyDrifted = drifts.some(r => r.drifted)
check('换话题后能检出 drifted=true', anyDrifted)

// ⑥ BDI 死代码：源码里不再有该文案
const src = readFileSync(new URL('../index.mjs', import.meta.url), 'utf8')
check('⑥ 用户意图（BDI）死代码已删除', !src.includes('⑥ 用户意图（BDI）'))

try { unlinkSync(tracePath) } catch {}
console.log(`\n${pass} PASS`)
