// 三杠杆通用 A/B 效果测试骨架
// 每个杠杆一个独立场景，开关对照，验证"行为改变"而非仅 trace 命中
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, existsSync, readFileSync, mkdirSync } from 'node:fs'

const DIR = 'D:/Brain/_cleanup_20261118'
const PREFIX = 'D:/Brain/workspace/bench/_tmp_ab3_'
let pass = 0, fail = 0
const results = []
const check = (lever, label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  [${lever}] ${label}`) }
  else { fail++; console.log(`FAIL  [${lever}] ${label} ${detail.slice(0, 120)}`) }
  results.push({ lever, label, ok })
}

function harness(extra, tag) {
  const T = PREFIX + tag + '.jsonl'
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

// mock LLM：可返回各种畸形/正常响应
function mockLLM(respond) {
  globalThis.fetch = respond
}

export { harness, check, mockLLM, DIR, results, getCounts: () => ({ pass, fail }) }
