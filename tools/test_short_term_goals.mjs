/**
 * ROADMAP 短期①②③ 单测（2026-11-18 19:50）
 * ① spec 阈值分类标定：creative 任务在低 acceptance 时不再误触发审计
 * ② Critic 去同源：Critic LLM 调用用异质 temperature/top_k，且 prompt 不含过程信息
 * ③ test-time 自适应：控制回合按双信号路由，trace 记 adaptive_route
 * 用法: node bench/test_short_term_goals.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, existsSync, readFileSync } from 'node:fs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

// mock fetch：记录所有 LLM 请求体，返回合法 JSON
const originalFetch = globalThis.fetch
const calls = []
function installMock() {
  globalThis.fetch = async (url, opts) => {
    const body = JSON.parse(opts.body)
    calls.push({ url, body })
    return {
      ok: true,
      json: async () => ({ choices: [{ message: { content: '{"verdict":"ACCEPT","reasons":[],"confidence":"high","error_class":"none"}' } }] }),
    }
  }
}
function restoreFetch() { globalThis.fetch = originalFetch }

function harness(config) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, { probePath: null, ...config })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const emitStopping = async (agent) => { for (const fn of handlers.get('agent/turn-stopping') || []) await fn({ agent, turn: 1 }) }
  const emitPreStep = async (agent) => {
    let decision = { messages: [] }
    for (const fn of handlers.get('agent/pre-step') || []) decision = (await fn({ agent }, async () => decision)) || decision
    return decision
  }
  return { emit, emitPreStep, emitStopping }
}

const SPEC_LOG = 'D:/Brain/workspace/bench/_tmp_spec_goal.log'
const TRACE = 'D:/Brain/workspace/bench/_tmp_trace_goal.jsonl'
function writeSpecLog(acc) {
  writeFileSync(SPEC_LOG, `slot print_timing: id 0 | draft acceptance = ${acc.toFixed(5)} ( 99 accepted / 161 generated)\n`)
}
function traceLines() {
  return existsSync(TRACE) ? readFileSync(TRACE, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []
}

;(async () => {
  installMock()

  // ── ① spec 分类阈值：creative 低 acceptance 不误触发 ──
  {
    // acceptance=0.55：全局 0.65 会误触发（creative 正常区间 0.45-0.60）
    writeSpecLog(0.55)
    calls.length = 0
    const h = harness({
      specSignalEnabled: true, specLogPath: SPEC_LOG, specAcceptanceMin: 0.65,
      specThresholdByTaskEnabled: true,
      specAcceptanceByType: { dialogue: 0.70, code: 0.60, creative: 0.50, general: 0.65 },
      auditFeedbackPath: 'D:/Brain/workspace/bench/_tmp_auditfb_goal.jsonl',
      maxInjectionsPerTurn: 1, maxInjectionsPerSession: 4,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      verifyOnStopEnabled: false, mindStateEnabled: false, controlEnabled: false,
      traceEnabled: false,
    })
    const agent = { session: { id: 'spec-creative' }, steer: () => {} }
    await h.emit('session/event', { id: 'spec-creative' }, { type: 'turn/start', data: { turn: 1 } })
    // 用户指令是创意任务 → 分类 creative → 阈值 0.50 → 0.55 不触发审计
    await h.emit('session/event', { id: 'spec-creative' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '帮我写一个故事的开头，要有创意和文采' }] } })
    await h.emit('session/event', { id: 'spec-creative' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"a.txt"}' } })
    await h.emit('session/event', { id: 'spec-creative' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.emitPreStep(agent)
    const auditCalls = calls.filter((c) => JSON.stringify(c.body.messages || []).includes('审计'))
    check('① creative@0.55 分类阈值0.50 → 不触发审计', auditCalls.length === 0)

    // 对照：全局 0.65（关闭分类）→ 会触发
    calls.length = 0
    const h2 = harness({
      specSignalEnabled: true, specLogPath: SPEC_LOG, specAcceptanceMin: 0.65,
      specThresholdByTaskEnabled: false,
      auditFeedbackPath: 'D:/Brain/workspace/bench/_tmp_auditfb_goal.jsonl',
      maxInjectionsPerTurn: 1, maxInjectionsPerSession: 4,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      verifyOnStopEnabled: false, mindStateEnabled: false, controlEnabled: false, traceEnabled: false,
    })
    const agent2 = { session: { id: 'spec-global' }, steer: () => {} }
    await h2.emit('session/event', { id: 'spec-global' }, { type: 'turn/start', data: { turn: 1 } })
    await h2.emit('session/event', { id: 'spec-global' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '帮我写一个故事的开头' }] } })
    await h2.emit('session/event', { id: 'spec-global' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"a.txt"}' } })
    await h2.emit('session/event', { id: 'spec-global' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h2.emitPreStep(agent2)
    const auditCalls2 = calls.filter((c) => JSON.stringify(c.body.messages || []).includes('审计'))
    check('① 对照：全局0.65 → creative@0.55 触发审计（证明分类确有效果）', auditCalls2.length > 0)
  }

  // ── ② Critic 去同源：异质温度 + prompt 无过程信息 ──
  {
    calls.length = 0
    const h = harness({
      criticEnabled: true, criticTemperature: 0.7, criticTopK: 20,
      presentGateEnabled: false, deepCheckEnabled: false, plannerCheckEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, maxInjectionsPerSession: 4,
      traceEnabled: false, specSignalEnabled: false, verifyOnStopEnabled: false,
      mindStateEnabled: false, controlEnabled: false,
    })
    const agent = { session: { id: 'critic-het' }, steer: () => {} }
    const tmpProduct = 'D:/Brain/workspace/bench/_tmp_critic_product.txt'
    writeFileSync(tmpProduct, '这是一个测试产物，包含完整的内容和入口点。\ndef main():\n    return 42\n')
    await h.emit('session/event', { id: 'critic-het' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'critic-het' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个返回42的函数' }] } })
    await h.emit('session/event', { id: 'critic-het' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: tmpProduct }) } })
    await h.emit('session/event', { id: 'critic-het' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.emit('session/event', { id: 'critic-het' }, { type: 'tool/call', data: { name: 'present', arguments: '{"files":[]}' } })
    await h.emitStopping(agent)
    const criticCalls = calls.filter((c) => JSON.stringify(c.body.messages || []).includes('产物评审员'))
    check('② Critic 确实被调用', criticCalls.length > 0)
    if (criticCalls.length) {
      check('② Critic 用异质温度 0.7', criticCalls[0].body.temperature === 0.7)
      check('② Critic 用异质 top_k 20', criticCalls[0].body.top_k === 20)
      const prompt = criticCalls[0].body.messages[0].content
      check('② Critic prompt 明确不看过程/推理链', prompt.includes('看不到') && prompt.includes('不要推测'))
      check('② Critic prompt 不含 trace trail 内容', !prompt.includes('"kind":"call"'))
    }
    unlinkSync(tmpProduct)
  }

  // ── ③ test-time 自适应路由 ──
  {
    writeSpecLog(0.92) // 高 acceptance → 简单题
    if (existsSync(TRACE)) unlinkSync(TRACE)
    calls.length = 0
    const h = harness({
      adaptiveThinkEnabled: true, adaptiveSimpleThreshold: 0.85,
      specSignalEnabled: true, specLogPath: SPEC_LOG,
      controlEnabled: true, controlEverySteps: 1, maxControlPerSession: 5,
      traceEnabled: true, tracePath: TRACE,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, maxInjectionsPerSession: 4,
      verifyOnStopEnabled: false, mindStateEnabled: false,
    })
    const agent = { session: { id: 'adaptive' }, steer: () => {} }
    await h.emit('session/event', { id: 'adaptive' }, { type: 'turn/start', data: { turn: 1 } })
    // 先触发一次 pre-step 让 specAcceptance 读入 s（audit 门控段在所有 pre-step 都跑）
    await h.emitPreStep(agent)
    // 推进 step 到 1（controlEverySteps=1）
    await h.emit('session/event', { id: 'adaptive' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '读一下 a.txt' }] } })
    await h.emit('session/event', { id: 'adaptive' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"a.txt"}' } })
    await h.emit('session/event', { id: 'adaptive' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    const decision = await h.emitPreStep(agent)
    const routes = traceLines().filter((r) => r.kind === 'adaptive_route')
    check('③ adaptive_route 已记录到 trace', routes.length > 0)
    if (routes.length) check('③ 高 acceptance → skip-deep-think 路由', routes[0].route === 'skip-deep-think')
  }

  restoreFetch()
  for (const f of [SPEC_LOG, TRACE, 'D:/Brain/workspace/bench/_tmp_auditfb_goal.jsonl']) { try { if (existsSync(f)) unlinkSync(f) } catch {} }
  console.log(`\n══════ ${pass}/${total} 通过 ══════`)
  process.exit(pass === total ? 0 : 1)
})().catch((e) => { restoreFetch(); console.error(e); process.exit(1) })
