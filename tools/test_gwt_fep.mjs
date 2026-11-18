/**
 * GWT 共享状态总线（①） + FEP 预期闭环（②）单测
 * 用法: node bench/test_gwt_fep.mjs
 *  ① 验证三消费者（控制回合/Critic/审计）读同一 workspaceSnapshot：
 *     - 控制回合 trace 带 snapshot，字段来自统一状态
 *     - Critic 的 prompt goal == 快照 goal（用 mock fetch 捕获）
 *     - 快照是只读投影，不修改原 state
 *  ② 验证 FEP 预期闭环（见下方，随实现补）
 */
import { apply } from '../index.mjs'
import { writeFileSync, existsSync, readFileSync, unlinkSync } from 'node:fs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const origFetch = globalThis.fetch
const calls = []
globalThis.fetch = async (url, opts) => {
  calls.push({ body: JSON.parse(opts.body) })
  return { ok: true, json: async () => ({ choices: [{ message: { content: '{"verdict":"ACCEPT","reasons":[],"confidence":"high","error_class":"none"}' } }] }) }
}

function harness(config) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, { probePath: null, ...config })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const emitStopping = async (agent) => { for (const fn of handlers.get('agent/turn-stopping') || []) await fn({ agent, turn: 1 }) }
  const pre = async (agent) => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }
  return { emit, emitStopping, pre }
}

const TRACE = 'D:/Brain/workspace/bench/_tmp_gwt_trace.jsonl'
function traceRows() { return existsSync(TRACE) ? readFileSync(TRACE, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : [] }

;(async () => {
  // ── ① GWT ──
  {
    if (existsSync(TRACE)) unlinkSync(TRACE)
    calls.length = 0
    const h = harness({
      controlEnabled: true, controlEverySteps: 1, maxControlPerSession: 3,
      traceEnabled: true, tracePath: TRACE,
      frameEnabled: true, bdiEnabled: true, driftSignalEnabled: false,
      todoEchoEnabled: false, // 隔离：避免 P1.5 回灌抢在控制回合前 return
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, maxInjectionsPerSession: 4,
      verifyOnStopEnabled: false, mindStateEnabled: false, specSignalEnabled: false,
      deepCheckEnabled: false, verifyOnEditEnabled: false,
    })
    const agent = { session: { id: 'gwt-test' }, steer: () => {} }
    await h.emit('session/event', { id: 'gwt-test' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'gwt-test' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个登录函数并验证' }] } })
    await h.emit('session/event', { id: 'gwt-test' }, { type: 'todo/write', data: { todos: [
      { content: '实现登录函数 [VERIFY]', status: 'in_progress' },
      { content: '跑测试', status: 'completed' },
    ] } })
    await h.emit('session/event', { id: 'gwt-test' }, { type: 'tool/call', data: { name: 'pwsh', arguments: '{"command":"pytest"}' } })
    await h.emit('session/event', { id: 'gwt-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.pre(agent)

    const ctl = traceRows().filter((r) => r.kind === 'control_turn')
    check('① 控制回合 trace 带共享快照', ctl.length > 0 && !!ctl[ctl.length - 1].snapshot)
    if (ctl.length) {
      const s = ctl[ctl.length - 1].snapshot
      check('① 快照 goal 来自统一任务字段', typeof s.goal === 'string' && s.goal.includes('登录函数'))
      check('① 快照 done/inProgress 来自同一 todo 清单', s.done === 1 && s.inProgress.includes('登录函数'))
      check('① 快照 verified 来自 frame.evidence∪verifyRan', s.verified === true)
      check('① 快照 wrote/rejected 字段存在', typeof s.wrote === 'boolean' && typeof s.rejected === 'number')
      check('① 快照 bdiGoal 同源', typeof s.bdiGoal === 'string' && s.bdiGoal.includes('登录函数'))
    }
  }

  // ── ① Critic 读快照 goal ──
  {
    calls.length = 0
    const h = harness({
      criticEnabled: true, criticTemperature: 0.7, criticTopK: 20,
      presentGateEnabled: false, deepCheckEnabled: false, plannerCheckEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, maxInjectionsPerSession: 4,
      traceEnabled: false, specSignalEnabled: false, verifyOnStopEnabled: false,
      mindStateEnabled: false, controlEnabled: false,
    })
    const agent = { session: { id: 'gwt-critic' }, steer: () => {} }
    const tmp = 'D:/Brain/workspace/bench/_tmp_gwt_product.txt'
    writeFileSync(tmp, 'def login(): return True\n')
    await h.emit('session/event', { id: 'gwt-critic' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'gwt-critic' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '实现一个登录函数并返回布尔值' }] } })
    await h.emit('session/event', { id: 'gwt-critic' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: tmp }) } })
    await h.emit('session/event', { id: 'gwt-critic' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.emit('session/event', { id: 'gwt-critic' }, { type: 'tool/call', data: { name: 'present', arguments: '{"files":[]}' } })
    await h.emitStopping(agent)
    const critic = calls.find((c) => JSON.stringify(c.body.messages || []).includes('产物评审员'))
    check('① Critic 被调用', !!critic)
    if (critic) {
      const prompt = critic.body.messages[0].content
      check('① Critic 的 goal 与共享快照同源（同一任务文本）', prompt.includes('实现一个登录函数并返回布尔值'))
      check('① Critic 仍不看执行过程', prompt.includes('看不到') && !prompt.includes('"kind":"call"'))
    }
    unlinkSync(tmp)
  }

  // ── ② FEP 预期闭环 ──
  {
    if (existsSync(TRACE)) unlinkSync(TRACE)
    const PEND = 'D:/Brain/workspace/bench/_tmp_fep_pending.jsonl'
    const PRODUCT = 'D:/Brain/workspace/bench/_tmp_fep_product.txt'
    if (existsSync(PEND)) unlinkSync(PEND)
    calls.length = 0
    const h = harness({
      fepEnabled: true,
      learningEnabled: true, pendingLearnPath: PEND,
      traceEnabled: true, tracePath: TRACE,
      frameEnabled: true, verifyOnEditEnabled: false,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, maxInjectionsPerSession: 4,
      verifyOnStopEnabled: false, mindStateEnabled: false, controlEnabled: false,
      specSignalEnabled: false, deepCheckEnabled: false, todoEchoEnabled: false,
    })
    const agent = { session: { id: 'fep-test' }, steer: () => {} }
    await h.emit('session/event', { id: 'fep-test' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'fep-test' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个文件并验证' }] } })
    // 场景A：写成功 + 读回验证 → converged
    await h.emit('session/event', { id: 'fep-test' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: PRODUCT }) } })
    writeFileSync(PRODUCT, 'hello\n') // 模拟真实落盘
    await h.emit('session/event', { id: 'fep-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.emit('session/event', { id: 'fep-test' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"_tmp_fep_product.txt"}' } })
    await h.emit('session/event', { id: 'fep-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'hello' }] } } })
    await h.pre(agent)
    // 场景B：写成功但产物未落盘 + 无验证 → deviation
    const MISSING = 'D:/Brain/workspace/bench/_tmp_fep_missing.txt'
    try { if (existsSync(MISSING)) unlinkSync(MISSING) } catch {}
    await h.emit('session/event', { id: 'fep-test' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: MISSING }) } })
    await h.emit('session/event', { id: 'fep-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.pre(agent)

    const cycles = traceRows().filter((r) => r.kind === 'fep_cycle')
    check('② FEP 每轮写操作记一个 fep_cycle', cycles.length === 2)
    if (cycles.length === 2) {
      check('② 写+落盘 → converged（验证在后续步骤，不当场判）', cycles[0].converged === true && cycles[0].deviation.length === 0)
      check('② 预期含 goal/fileExists/verifiable', !!cycles[0].expected && typeof cycles[0].expected.fileExists === 'boolean')
      check('② 观察含实际 fileExists/verified', !!cycles[0].observed && typeof cycles[0].observed.fileExists === 'boolean')
      check('② 产物未落盘 → deviation 非空', cycles[1].converged === false && cycles[1].deviation.length > 0)
      check('② 偏差含 product-missing', cycles[1].deviation.includes('product-missing'))
    }
    const pend = existsSync(PEND) ? readFileSync(PEND, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []
    check('② 偏差写入 pendingLearn 队列供 B 段沉淀', pend.some((p) => p.kind === 'fep_deviation'))
    for (const f of [PEND, PRODUCT, MISSING]) { try { if (existsSync(f)) unlinkSync(f) } catch {} }
  }

  globalThis.fetch = origFetch
  for (const f of [TRACE, 'D:/Brain/workspace/bench/_tmp_gwt_product.txt']) { try { if (existsSync(f)) unlinkSync(f) } catch {} }
  console.log(`\n══════ ${pass}/${total} 通过 ══════`)
  process.exit(pass === total ? 0 : 1)
})().catch((e) => { globalThis.fetch = origFetch; console.error(e); process.exit(1) })
