/**
 * 阶段边界标记单测（2026-11-21）
 * 验证：同会话切卡时注入确定性分隔符，切断跨任务注意力污染。
 * 首轮不触发 / 切卡指令触发 / 普通追问不触发 / 每轮至多一次 / 每会话上限。
 * 用法: node tools/test_phase_boundary.mjs
 */
import { apply } from '../index.mjs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null,
  phaseBoundaryEnabled: true, phaseBoundaryMaxPerSession: 2,
  // 关掉其他注入源
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  auditEnabled: false, auditEverySteps: 9999, auditEveryStepsAnomaly: 9999,
  skillsEnabled: false, learningEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, maxInjectionsPerSession: 99, maxInjectionsPerTurn: 99,
  traceEnabled: false,
})

const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
const pre = async () => {
  let d = { messages: [] }
  for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d
  return d
}
const agent = { session: { id: 'phase-test' }, steer() {} }
const session = { id: 'phase-test' }
const userMsg = (text) => emit('session/event', session, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text }] } })
const turnStart = (n) => emit('session/event', session, { type: 'turn/start', data: { turn: n } })
const boundaryText = (d) => (d?.messages || []).map((m) => JSON.stringify(m?.content || '')).join('\n')

// 首轮：初始指令即使含切卡词也不触发（真实时序：turnStart → userMsg → pre）
await turnStart(1)
await userMsg('继续推进 S23 前缀 KV 稳定守护')
let d = await pre()
check('首轮含切卡词也不注入（无上一张）', !boundaryText(d).includes('阶段边界'))

// 第二轮：显式切卡指令 → 触发
await turnStart(2)
await userMsg('很好，S23 已完成。现在在同一会话继续推进下一张卡 S12')
d = await pre()
check('切卡指令注入阶段边界', boundaryText(d).includes('[harness 阶段边界]'))
check('边界标记含上一张归档提示', boundaryText(d).includes('失败轨迹'))
check('边界标记含本段指令', boundaryText(d).includes('S12'))

// 同一轮再 pre 一次 → 不重复注入
d = await pre()
check('每轮至多注入一次', !boundaryText(d).includes('[harness 阶段边界]'))

// 第三轮：普通追问（无切卡词）→ 不触发
await turnStart(3)
await userMsg('这个测试结果怎么样？')
d = await pre()
check('普通追问不注入边界', !boundaryText(d).includes('[harness 阶段边界]'))

// 第四、五轮：两次切卡（达到上限2）→ 都触发
await turnStart(4)
await userMsg('继续推进下一张卡 S18')
d = await pre()
check('第二次切卡触发（上限2）', boundaryText(d).includes('[harness 阶段边界]'))

await turnStart(5)
await userMsg('继续推进下一张卡 S19')
d = await pre()
check('超过每会话上限后不再触发', !boundaryText(d).includes('[harness 阶段边界]'))

console.log(`\n${pass}/${total} pass`)
process.exit(pass === total ? 0 : 1)
