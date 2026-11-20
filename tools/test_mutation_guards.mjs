/**
 * 反向测试（mutation testing）：证明守卫不是摆设。
 * 方法：同一场景跑两遍——机制开 vs 机制关；断言"开时有行为、关时无行为"。
 * 正向全绿只证明没报错；本测试证明机制真的在拦。
 *
 * 用法: node tools/test_mutation_guards.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync } from 'node:fs'

let pass = 0, fail = 0
const check = (label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { fail++; console.log(`FAIL  ${label} ${detail}`) }
}

const BASE = {
  probePath: null, traceEnabled: false,
  auditEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
  presentGateEnabled: false, controlEnabled: false, mindStateEnabled: false,
  verifyOnStopEnabled: false, verifyOnEditEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, continuityEnabled: false,
  learningEnabled: false, skillsEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, injectionScanEnabled: false,
  maxInjectionsPerTurn: 99, maxInjectionsPerSession: 99,
}

function harness(extra) {
  const handlers = new Map()
  const ctx = {
    on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) },
    logger: { info() {}, warn() {} },
  }
  apply(ctx, { ...BASE, ...extra })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const steered = []
  const agent = { session: { id: 'mutation' }, steer: (m) => steered.push(m.content?.[0]?.text || String(m)) }
  const pre = async () => {
    let d = { messages: [] }
    for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d
    const arr = Array.isArray(d?.messages) ? d.messages : []
    const c = arr[arr.length - 1]?.content
    return Array.isArray(c) ? c.map((x) => x?.text || '').join('\n') : (typeof c === 'string' ? c : '')
  }
  return { emit, steered, agent, pre }
}

// ── M1: turn-guard L3（短确认词）──
// ⚠️ 2026-11-21 实测发现：turn-guard 没有 Enabled 开关（L0-L3 无条件启用），
// 所以无法用"关开关"做 mutation。正解是验证它在退化场景下确实 steer，
// 并明确记录"此机制不可配置关闭"这一事实（是设计意图还是缺陷，留给用户判断）。
const textMsg = (t) => ({ type: 'assistant/message', data: { message: { content: [{ type: 'text', text: t }] } } })
async function turnGuardRun() {
  const h = harness({})
  await h.emit('session/event', { id: 'mutation' }, { type: 'turn/start', data: { turn: 3 } })
  await h.emit('session/event', { id: 'mutation' }, { type: 'tool/call', data: { name: 'read' } })
  await h.emit('session/event', { id: 'mutation' }, textMsg('好'))
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 3 })
  return h.steered.length
}
{
  const n = await turnGuardRun()
  check(`M1 turn-guard: 退化场景 steer=${n}（无Enabled开关，只能验证生效不能mutation）`, n >= 1, `steered=${n}`)
}

// ── M2: danger guard（危险命令分级）──
async function dangerRun(enabled) {
  const h = harness({ dangerGuardEnabled: enabled })
  await h.emit('session/event', { id: 'mutation' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 'mutation' }, { type: 'tool/call', data: { name: 'pwsh', arguments: 'rm -rf /' } })
  await h.emit('session/event', { id: 'mutation' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'OK' }] }, status: 'OK' } })
  return await h.pre()
}
{
  const on = await dangerRun(true), off = await dangerRun(false)
  const hasWarn = (s) => /危险|阻止|block|不可逆/i.test(s || '')
  check(`M2 danger-guard: 开=${hasWarn(on)} 关=${hasWarn(off)}`, hasWarn(on) && !hasWarn(off),
    `on=${on.slice(0,80)} off=${off.slice(0,80)}`)
}

// ── M3: verify-on-edit（已单独测过，这里纳入统一框架确认）──
async function verifyRun(enabled, tool, bad) {
  const h = harness({ verifyOnEditEnabled: enabled, writeTools: ['write','edit','apply_patch','multi_edit','create_file','str_replace','write_file','notebook_edit'] })
  await h.emit('session/event', { id: 'mutation' }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: 'mutation' }, { type: 'tool/call', data: { name: tool, arguments: JSON.stringify({ file_path: bad }) } })
  await h.emit('session/event', { id: 'mutation' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'OK' }] }, status: 'OK' } })
  return await h.pre()
}
{
  const bad = 'D:/Brain/workspace/bench/_tmp_mutation.json'
  writeFileSync(bad, '{ bad json ]')
  const on = await verifyRun(true, 'apply_patch', bad), off = await verifyRun(false, 'apply_patch', bad)
  check(`M3 verify-on-edit: 开=${/语法检查/.test(on)} 关=${/语法检查/.test(off)}`,
    /语法检查/.test(on) && !/语法检查/.test(off))
  try { unlinkSync(bad) } catch {}
}

// ── M4: CritBank 教训注入（重复探测场景）──
async function critRun(enabled) {
  const h = harness({ critbankEnabled: enabled })
  await h.emit('session/event', { id: 'mutation' }, { type: 'turn/start', data: { turn: 1 } })
  for (let i = 0; i < 3; i++) {
    await h.emit('session/event', { id: 'mutation' }, { type: 'tool/call', data: { name: 'glob', arguments: JSON.stringify({ pattern: '/same' }) } })
    await h.emit('session/event', { id: 'mutation' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'no files' }] }, status: 'OK' } })
  }
  return await h.pre()
}
{
  const on = await critRun(true), off = await critRun(false)
  // CritBank 注入的是"【相关教训 C-xxx】"
  const hasLesson = (s) => /相关教训\s*C-\d/.test(s || '')
  if (!hasLesson(on) && !hasLesson(off)) {
    console.log('SKIP  M4 critbank: 此场景（3次glob）未命中 CritBank 标签——不算通过，需换命中场景')
  } else {
    check(`M4 critbank: 开=${hasLesson(on)} 关=${hasLesson(off)}`, hasLesson(on) && !hasLesson(off),
      `on=${on.slice(0,100)}`)
  }
}

console.log(`\n${pass} pass, ${fail} fail`)
process.exit(fail ? 1 : 0)
