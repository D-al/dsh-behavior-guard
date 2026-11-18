/**
 * 心智状态层单测（合成心智，2026-11-18）
 * 验证：① 分布式重复检测（跨步、非连续）② 触发式注入 ③ 收尾自检 ④ 注入上限
 * 用法: node bench/test_mind_state.mjs
 */
import { apply } from 'file:///C:/Users/Ad/.dsh/profiles/desktop/node_modules/dsh-agent-harness/index.mjs'

const results = []
function check(label, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  results.push(ok)
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}  actual=${JSON.stringify(actual)} expected=${JSON.stringify(expected)}`)
}

function harness(config) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, { probePath: null, ...(config || {}) }) // 测试不写生产探针
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const emitPreStep = async (agent) => {
    let captured = null
    const next = async () => ({ messages: [] })
    for (const fn of handlers.get('agent/pre-step') || []) {
      const d = await fn({ agent }, next)
      if (d && Array.isArray(d.messages) && d.messages.length > 0) {
        captured = d.messages[d.messages.length - 1].content[0].text
      }
    }
    return captured
  }
  const agent = { session: { id: 'mind-test' }, steer: () => {} }
  return { emit, emitPreStep, agent }
}

const cfg = {
  auditEnabled: false, criticEnabled: false, deepCheckEnabled: false, plannerCheckEnabled: false,
  continuityEnabled: false, controlEnabled: false, skillsEnabled: false, dangerGuardEnabled: false,
  traceEnabled: false, mindStateEnabled: true, mindStateLoopThreshold: 3, maxMindStateInjections: 2,
  todoEchoEnabled: false, maxTodoInjectionsPerTurn: 0, maxTodoInjectionsPerSession: 0,
}

// ── 测试 1：非连续的同工具重复（read A → 列目录 → read A → write → read A）──
{
  const h = harness(cfg)
  for (const ev of [
    { type: 'turn/start', data: { turn: 1 } },
    { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '做个测试页' }] } },
  ]) await h.emit('session/event', { id: 'mind-test' }, ev)
  // 手动构造 trail（模拟跨步重复，中间夹其它工具）
  const agent = h.agent
  // 通过事件推进 step 并塞 trail
  let lastMsg = null
  for (let i = 0; i < 9; i++) {
    await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/call', data: { name: 'read', arguments: JSON.stringify({ file_path: 'hardware-monitor-plugin/demo.html' }) } })
    await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    if (i === 1) {
      await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/call', data: { name: 'glob', arguments: '{}' } })
      await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'a.html' }] } } })
    }
    const m = await h.emitPreStep(agent)   // 推进 step
    if (m && /心智状态|重复/.test(m)) { lastMsg = m; break }
  }
  const msg = lastMsg
  check('T1 触发式注入检出跨步重复', /重复|换一条/.test(msg || ''), true)
  check('T1b 中性事实+退出许可（无质疑式二选一）', /事实：/.test(msg || '') && /可以直接结束本轮/.test(msg || '') && !/A\. 产物已交付/.test(msg || ''), true)
}

// ── 测试 2：上限保护（maxMindStateInjections=2，第 3 次不再注入）──
{
  const h = harness(cfg)
  await h.emit('session/event', { id: 'mind-test' }, { type: 'turn/start', data: { turn: 1 } })
  let injected = 0
  for (let i = 0; i < 20; i++) {
    await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/call', data: { name: 'read', arguments: JSON.stringify({ file_path: 'x.html' }) } })
    await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    const msg = await h.emitPreStep(h.agent)   // 每步推进，跨过 gap 阈值
    if (msg && /harness 状态/.test(msg)) injected++
  }
  check('T2 触发式注入确实发生且<=上限', injected >= 1 && injected <= 2, true)
}

// ── 测试 3：无重复时不误报 ──
{
  const h = harness(cfg)
  await h.emit('session/event', { id: 'mind-test' }, { type: 'turn/start', data: { turn: 1 } })
  const tools = ['read', 'edit', 'glob', 'web_search']
  for (const t of tools) {
    await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/call', data: { name: t, arguments: '{}' } })
    await h.emit('session/event', { id: 'mind-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
  }
  const msg = await h.emitPreStep(h.agent)
  check('T3 无重复时不注入', /检测到你正在重复/.test(msg || ''), false)
}

const passed = results.filter(Boolean).length
console.log(`\n══════ ${passed}/${results.length} 通过 ══════`)
process.exit(passed === results.length ? 0 : 1)
