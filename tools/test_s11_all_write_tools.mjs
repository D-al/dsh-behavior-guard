/**
 * S11 动态验证：8 种写工具里除了 write/edit 的另 6 种，是否真的进了 verify-on-edit。
 * 不是静态断言——真实 emit tool/result，看是否产生语法错误注入。
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync } from 'node:fs'

let pass = 0, total = 0
const check = (label, ok) => { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, traceEnabled: false,
  verifyOnEditEnabled: true, learningEnabled: false,
  auditEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
  presentGateEnabled: false, controlEnabled: false, mindStateEnabled: false,
  verifyOnStopEnabled: false, skillsEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, continuityEnabled: false,
})
const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
const pre = async (agent) => {
  let d = { messages: [] }
  for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d
  const arr = Array.isArray(d?.messages) ? d.messages : []
  const last = arr[arr.length - 1]
  const c = last?.content
  return Array.isArray(c) ? c.map((x) => (typeof x?.text === 'string' ? x.text : '')).join('\n') : (typeof c === 'string' ? c : '')
}

// 6 种原本不进 lastProduct 的写工具
const tools = ['apply_patch', 'multi_edit', 'create_file', 'str_replace', 'write_file', 'notebook_edit']
const sid = 's11-runtime'
const agent = { session: { id: sid }, steer() {} }

for (const tool of tools) {
  const bad = `D:/Brain/workspace/bench/_tmp_s11_${tool}.json`
  writeFileSync(bad, '{ this is NOT valid json ]\n')
  await emit('session/event', { id: sid }, { type: 'turn/start', data: { turn: 1 } })
  await emit('session/event', { id: sid }, { type: 'tool/call', data: { name: tool, arguments: JSON.stringify({ file_path: bad }) } })
  await emit('session/event', { id: sid }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'OK' }] }, status: 'OK' } })
  const injected = await pre(agent)
  const hit = injected && injected.includes('语法检查')
  check(`${tool}: 坏 JSON 触发 verify-on-edit 注入`, hit)
  try { unlinkSync(bad) } catch {}
}

console.log(`\n${pass}/${total} pass`)
process.exit(pass === total ? 0 : 1)
