/**
 * S22 真行为断言：禁用工具拦截在 harness 层的实际行为
 *
 * 不是模拟、不是源码 grep——真的 import apply()，emit tool/call 事件，
 * 检查 pendingInject 是否按预期注入。
 *
 * 用法: node tools/test_disabled_tools.mjs
 */
import { apply } from '../index.mjs'

let pass = 0, total = 0
function check(label, ok) {
  total++
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { console.error(`FAIL  ${label}`) }
}

function makeHarness() {
  const handlers = new Map()
  const ctx = {
    on: (name, cb) => { handlers.set(name, [...(handlers.get(name) || []), cb]) },
    logger: { info() {}, warn() {}, error() {} },
  }
  apply(ctx, {
    controlEnabled: false, criticEnabled: false, auditEnabled: false,
    executorEnabled: false, mindStateEnabled: false, injectionClassifierEnabled: false,
    traceEnabled: false,
  })
  return async (sid, ev) => {
    for (const fn of handlers.get('session/event') || []) await fn({ id: sid }, ev)
  }
}

// 通过 pre-step 的 decision.messages 观察 pendingInject 是否注入
function makePre(handlers) {
  return async (sid) => {
    const agent = { session: { id: sid, sid }, steer() {} }
    let decision = { messages: [] }
    for (const fn of handlers.get('agent/pre-step') || []) {
      decision = (await fn({ agent }, async () => decision)) || decision
    }
    return decision
  }
}

function msgText(decision) {
  return (decision?.messages || []).map(m => typeof m === 'string' ? m : JSON.stringify(m)).join('\n')
}

;(async () => {
  console.log('🧪 test_disabled_tools (真行为断言)\n')

  // 用同一 harness 的两个不同 sid，验证跨会话独立
  const handlers = new Map()
  const ctx = {
    on: (name, cb) => { handlers.set(name, [...(handlers.get(name) || []), cb]) },
    logger: { info() {}, warn() {}, error() {} },
  }
  apply(ctx, {
    controlEnabled: false, criticEnabled: false, auditEnabled: false,
    executorEnabled: false, mindStateEnabled: false, injectionClassifierEnabled: false,
    traceEnabled: false,
  })
  const emit = async (sid, ev) => {
    for (const fn of handlers.get('session/event') || []) await fn({ id: sid }, ev)
  }
  const pre = makePre(handlers)

  const sidA = 'disabled-tools-A'
  const sidB = 'disabled-tools-B'

  // 会话 A：首次调用 web_fetch
  await emit(sidA, { type: 'turn/start', data: { turn: 1 } })
  await emit(sidA, { type: 'tool/call', data: { name: 'web_fetch', arguments: '{}' } })
  const a1 = msgText(await pre(sidA))
  check('会话A首次 web_fetch → 收到拦截提示', a1.includes('[harness 工具拦截]') && a1.includes('web_fetch'))

  // 会话 A：二次调用（同会话去重，不应再提示）
  await emit(sidA, { type: 'tool/call', data: { name: 'web_fetch', arguments: '{}' } })
  const a2 = msgText(await pre(sidA))
  check('会话A二次 web_fetch → 不重复提示', !a2.includes('[harness 工具拦截]'))

  // 会话 B：全新会话首次调用（跨会话独立，应收到提示）
  await emit(sidB, { type: 'turn/start', data: { turn: 1 } })
  await emit(sidB, { type: 'tool/call', data: { name: 'web_fetch', arguments: '{}' } })
  const b1 = msgText(await pre(sidB))
  check('会话B首次 web_fetch → 也收到拦截提示（跨会话独立）', b1.includes('[harness 工具拦截]') && b1.includes('web_fetch'))

  // 会话 C：另一个禁用工具 job_output 应独立去重
  const sidC = 'disabled-tools-C'
  await emit(sidC, { type: 'turn/start', data: { turn: 1 } })
  await emit(sidC, { type: 'tool/call', data: { name: 'job_output', arguments: '{}' } })
  const c1 = msgText(await pre(sidC))
  check('会话C job_output → 收到拦截提示+替代建议', c1.includes('[harness 工具拦截]') && c1.includes('job_output'))

  // 正常工具不应触发
  const sidD = 'disabled-tools-D'
  await emit(sidD, { type: 'turn/start', data: { turn: 1 } })
  await emit(sidD, { type: 'tool/call', data: { name: 'read', arguments: '{}' } })
  const d1 = msgText(await pre(sidD))
  check('正常工具 read → 不触发拦截', !d1.includes('[harness 工具拦截]'))

  console.log(`\n📊 ${pass}/${total} 通过`)
  if (pass === total) console.log('✅ All behavior checks passed')
  else { console.error(`⚠️ ${total - pass} failed`); process.exitCode = 1 }
})()
