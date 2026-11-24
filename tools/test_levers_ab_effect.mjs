// 杠杆1/2 效果受控实验：验证 guard 门控与 verify 判据真的改变行为（不是只看 trace 命中）
// 战略追溯：G6 开放环境适应（守卫 guard / 门控）/ R2 判据独立性（verify / 假绿防控）
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, existsSync, readFileSync, mkdirSync } from 'node:fs'

const DIR = 'D:/Brain/_cleanup_20261118'
let pass = 0, fail = 0
const check = (label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { fail++; console.log(`FAIL  ${label} ${detail}`) }
}
const origFetch = globalThis.fetch

// 每个场景独立 trace 路径，避免文件轮转/覆盖混淆
function harness(extra, tag) {
  const T = `D:/Brain/workspace/bench/_tmp_lever_${tag}.jsonl`
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
  const steered = []
  const agent = { session: { id: tag }, steer: (m) => steered.push(m.content?.[0]?.text || String(m)) }
  const pre = async () => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }
  const rows = () => existsSync(T) ? readFileSync(T, 'utf8').split('\n').filter(Boolean)
    .map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean) : []
  return { emit, steered, agent, pre, rows, T }
}

// 杠杆1：假完成场景（声称写成功但文件不存在）
async function fakeCompletion(enabled, tag) {
  const target = DIR + '/_ab_fake_' + tag + '.txt'
  try { unlinkSync(target) } catch {}
  const h = harness({ deterministicReadbackEnabled: enabled }, tag)
  await h.emit('session/event', { id: tag }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: tag }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写文件' }] } })
  await h.emit('session/event', { id: tag }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: target }) } })
  await h.emit('session/event', { id: tag }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
  await h.emit('agent/turn-stopping', { agent: h.agent, turn: 1 })
  return { h, target }
}

try {
  mkdirSync(DIR, { recursive: true })
  // L1 A/B
  const off = await fakeCompletion(false, 'l1off')
  const on = await fakeCompletion(true, 'l1on')
  const offRB = off.h.rows().filter((r) => r.kind === 'verify_state_readback')
  const onRB = on.h.rows().filter((r) => r.kind === 'verify_state_readback')
  check('L1-A 关闭时无回读 trace', offRB.length === 0, `got ${offRB.length}`)
  check('L1-B 开启时回读 trace 命中', onRB.length >= 1, `got ${onRB.length}`)
  check('L1-C 开启时识别假完成(ok=false)', onRB[onRB.length - 1]?.ok === false, JSON.stringify(onRB[0]))
  check('L1-D 开启时 steer 拦截(行为改变)', on.h.steered.some((s) => s.includes('确定性状态回读')), on.h.steered.join('|').slice(0, 100))
  check('L1-E 关闭时不拦截(对照组)', !off.h.steered.some((s) => s.includes('确定性状态回读')), off.h.steered.join('|').slice(0, 100))
  try { unlinkSync(on.target) } catch {}

  // L1 正向：文件真落盘 → 不拦截
  const goodTarget = DIR + '/_ab_good.txt'
  writeFileSync(goodTarget, 'real')
  const hGood = harness({ deterministicReadbackEnabled: true }, 'l1good')
  await hGood.emit('session/event', { id: 'l1good' }, { type: 'turn/start', data: { turn: 1 } })
  await hGood.emit('session/event', { id: 'l1good' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写文件' }] } })
  await hGood.emit('session/event', { id: 'l1good' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: goodTarget }) } })
  await hGood.emit('session/event', { id: 'l1good' }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
  await hGood.emit('agent/turn-stopping', { agent: hGood.agent, turn: 1 })
  const goodRB = hGood.rows().filter((r) => r.kind === 'verify_state_readback')
  check('L1-F 真落盘时 ok=true', goodRB[goodRB.length - 1]?.ok === true, JSON.stringify(goodRB[0]))
  check('L1-G 真落盘时不误拦', !hGood.steered.some((s) => s.includes('确定性状态回读')), hGood.steered.join('|').slice(0, 100))
  try { unlinkSync(goodTarget) } catch {}

  // L2：状态板内容进入 prompt
  const h2 = harness({ stateBoardEnabled: true, stateBoardEverySteps: 1, controlEnabled: true, controlEverySteps: 1, maxControlPerSession: 99 }, 'l2')
  await h2.emit('session/event', { id: 'l2' }, { type: 'turn/start', data: { turn: 1 } })
  await h2.emit('session/event', { id: 'l2' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写文件并报告' }] } })
  const f2 = DIR + '/_ab_state.txt'
  writeFileSync(f2, 'x')
  await h2.emit('session/event', { id: 'l2' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: f2 }) } })
  await h2.emit('session/event', { id: 'l2' }, { type: 'tool/result', data: { status: 'OK', message: { content: [{ type: 'text', text: 'ok' }] } } })
  const d = await h2.pre()
  const sbTrace = h2.rows().filter((r) => r.kind === 'state_board_inject')
  const sbMsg = (d.messages || []).map((m) => m.content?.[0]?.text || '').join(' ')
  check('L2-A 状态板 trace 命中', sbTrace.length >= 1, `got ${sbTrace.length}`)
  check('L2-B 状态板内容进入 prompt', sbMsg.includes('【状态板】'), sbMsg.slice(0, 100))
  check('L2-C 含 cwd 字段', sbMsg.includes('cwd='), sbMsg.slice(0, 100))
  check('L2-D 含已改文件', sbMsg.includes('_ab_state.txt'), sbMsg.slice(0, 140))
  check('L2-E 字节数在限制内', (sbTrace[0]?.bytes || 9999) <= 4096, `bytes=${sbTrace[0]?.bytes}`)
  try { unlinkSync(f2) } catch {}
} finally {
  globalThis.fetch = origFetch
  for (const t of ['l1off', 'l1on', 'l1good', 'l2']) { try { unlinkSync(`D:/Brain/workspace/bench/_tmp_lever_${t}.jsonl`) } catch {} }
}
console.log(`\n${pass} pass, ${fail} fail`)
process.exit(fail ? 1 : 0)
