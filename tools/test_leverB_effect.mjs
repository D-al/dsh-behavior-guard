// 杠杆B 错误恢复剧本 A/B 效果测试
// 战略追溯：G6 开放环境适应（guard 门控 / 适应）/ R2 判据独立性（verify / 假绿防控）
// 验证：首次失败给确定性动作（不是泛泛劝告），开关对照，同类错误一轮只注入一次
import { apply } from '../index.mjs'
import { readFileSync, unlinkSync, existsSync, writeFileSync } from 'node:fs'

const P = 'D:/Brain/workspace/bench/_tmp_leverB_'
const DIR = 'D:/Brain/_cleanup_20261118'
let pass = 0, fail = 0
const check = (label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { fail++; console.log(`FAIL  ${label} ${String(detail).slice(0, 150)}`) }
}
const origFetch = globalThis.fetch

function harness(extra, tag) {
  const T = P + tag + '.jsonl'
  try { unlinkSync(T) } catch {}
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, {
    probePath: null, traceEnabled: true, tracePath: T,
    auditEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
    continuityEnabled: false, controlEnabled: false, mindStateEnabled: false,
    verifyOnStopEnabled: false, verifyOnEditEnabled: false, fepEnabled: false,
    specSignalEnabled: false, skillsEnabled: false, dangerGuardEnabled: false,
    deepCheckEnabled: false, learningEnabled: false, injectionScanEnabled: false,
    todoEchoEnabled: false, maxInjectionsPerTurn: 99, maxInjectionsPerSession: 99,
    ...extra,
  })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const agent = { session: { id: tag }, steer: () => {} }
  const pending = []
  const pre = async () => {
    let d = { messages: [] }
    for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d
    return d
  }
  const rows = () => existsSync(T) ? readFileSync(T, 'utf8').split('\n').filter(Boolean)
    .map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean) : []
  return { emit, agent, pre, rows, T }
}

// 构造一次失败的工具调用（参数名错：filename 而非 file_path）
async function failWithArgs(enabled, args, tag, status = 'FAIL', extra = {}) {
  const h = harness({ errorPlaybookEnabled: enabled, ...extra }, tag)
  await h.emit('session/event', { id: tag }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: tag }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'test' }] } })
  await h.emit('session/event', { id: tag }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify(args) } })
  await h.emit('session/event', { id: tag }, { type: 'tool/result', data: { status, message: { content: [{ type: 'text', text: 'Error: not found' }] }, ...extra } })
  const d = await h.pre()
  const injected = (d.messages || []).map((m) => m.content?.[0]?.text || '').join(' ')
  return { h, injected, rows: h.rows() }
}

try {
  // ① 开关对照：关闭时无剧本注入
  const off = await failWithArgs(false, { filename: 'x.txt' }, 'b-off')
  check('B-1 关闭时无剧本动作', !off.injected.includes('错误剧本'), off.injected.slice(0, 100))

  // ② 参数名错 → 确定性动作
  const on = await failWithArgs(true, { filename: 'x.txt' }, 'b-on')
  check('B-2 参数名错给出确定性动作', on.injected.includes('错误剧本') && on.injected.includes('file_path'), on.injected.slice(0, 160))

  // ③ trace 打点
  const ep = on.rows.filter((r) => r.kind === 'error_playbook')
  check('B-3 error_playbook trace 命中', ep.length >= 1, `got ${ep.length}`)
  check('B-4 trace 含错误类型', ep[0]?.errorType === 'param-key', JSON.stringify(ep[0] || {}).slice(0, 100))

  // ④ 同类错误不重复注入（连续两次 filename 错）
  const h2 = harness({ errorPlaybookEnabled: true }, 'b-repeat')
  await h2.emit('session/event', { id: 'b-repeat' }, { type: 'turn/start', data: { turn: 1 } })
  await h2.emit('session/event', { id: 'b-repeat' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'test' }] } })
  for (let i = 0; i < 2; i++) {
    await h2.emit('session/event', { id: 'b-repeat' }, { type: 'tool/call', data: { name: 'write', arguments: '{"filename":"x.txt"}' } })
    await h2.emit('session/event', { id: 'b-repeat' }, { type: 'tool/result', data: { status: 'FAIL', message: { content: [{ type: 'text', text: 'err' }] } } })
  }
  const d2 = await h2.pre()
  const inj2 = (d2.messages || []).map((m) => m.content?.[0]?.text || '').join(' ')
  check('B-5 同类错误只注入一次', (inj2.match(/错误剧本/g) || []).length <= 1, inj2.slice(0, 160))

  // ⑤ 成功时不注入（不误伤正常流程）
  const h3 = harness({ errorPlaybookEnabled: true }, 'b-ok')
  await h3.emit('session/event', { id: 'b-ok' }, { type: 'turn/start', data: { turn: 1 } })
  await h3.emit('session/event', { id: 'b-ok' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'test' }] } })
  await h3.emit('session/event', { id: 'b-ok' }, { type: 'tool/call', data: { name: 'write', arguments: '{"file_path":"D:/Brain/_cleanup_20261118/_bok.txt"}' } })
  await h3.emit('session/event', { id: 'b-ok' }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
  const d3 = await h3.pre()
  const inj3 = (d3.messages || []).map((m) => m.content?.[0]?.text || '').join(' ')
  check('B-6 成功时不误注入', !inj3.includes('错误剧本'), inj3.slice(0, 100))
  try { unlinkSync(DIR + '/_bok.txt') } catch {}
} finally {
  globalThis.fetch = origFetch
  for (const t of ['b-off', 'b-on', 'b-repeat', 'b-ok']) { try { unlinkSync(P + t + '.jsonl') } catch {} }
}
console.log(`\n${pass} pass, ${fail} fail`)
process.exit(fail ? 1 : 0)
