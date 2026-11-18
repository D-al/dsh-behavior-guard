/**
 * 结果反馈捕获单测（波1基础设施）
 * 验证：write/edit 成功/失败都写入 _outcome.jsonl，且含 goal/provenance/status
 */
import { apply } from 'file:///C:/Users/Ad/.dsh/profiles/desktop/node_modules/dsh-agent-harness/index.mjs'
import { readFileSync, existsSync } from 'node:fs'

const OUT = 'D:/Brain/workspace/bench/_outcome.jsonl'
const before = existsSync(OUT) ? readFileSync(OUT, 'utf8').split('\n').filter(Boolean).length : 0

const handlers = new Map()
const ctx = { on: (n, cb) => handlers.set(n, [...(handlers.get(n) || []), cb]), logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, // 测试不写生产探针
  traceEnabled: false, outcomeCaptureEnabled: true,
  auditEnabled: false, criticEnabled: false, deepCheckEnabled: false, plannerCheckEnabled: false,
  continuityEnabled: false, controlEnabled: false, skillsEnabled: false, dangerGuardEnabled: false,
  verifyOnEditEnabled: false, outcomePath: OUT,
})
const emit = async (ev, ...a) => { for (const f of handlers.get(ev) || []) await f(...a) }
const agent = { session: { id: 'outcome-test' }, steer: () => {} }
const pre = async () => { for (const f of handlers.get('agent/pre-step') || []) await f({ agent }, async () => ({ messages: [] })) }

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

;(async () => {
  await emit('session/event', { id: 'outcome-test' }, { type: 'turn/start', data: { turn: 1 } })
  await emit('session/event', { id: 'outcome-test' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个测试文件' }] } })
  await pre()
  // 成功 write
  await emit('session/event', { id: 'outcome-test' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: 'test.txt' }) } })
  await emit('session/event', { id: 'outcome-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'Created file' }] } } })
  // 失败 edit
  await emit('session/event', { id: 'outcome-test' }, { type: 'tool/call', data: { name: 'edit', arguments: JSON.stringify({ file_path: 'missing.txt' }) } })
  await emit('session/event', { id: 'outcome-test' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'Error: cannot read missing.txt' }] } } })

  const rows = readFileSync(OUT, 'utf8').split('\n').filter(Boolean).slice(before).map(JSON.parse)
  check('捕获了 2 条结果反馈', rows.length === 2)
  check('含 OK 状态', rows.some((r) => r.status === 'OK'))
  check('含 FAIL 状态', rows.some((r) => r.status === 'FAIL'))
  check('含目标路径', rows.some((r) => r.target === 'test.txt'))
  check('含用户目标(goal)', rows.every((r) => r.goal && r.goal.length > 0))
  check('含 provenance', rows.every((r) => r.provenance === 'user'))
  console.log(`\n══════ ${pass}/${total} 通过 ══════`)
  process.exit(pass === total ? 0 : 1)
})()
