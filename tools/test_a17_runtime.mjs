/**
 * A1_7 动态验证：真的触发一次 Critic，检查 trace 里有 review_verdict + 维度字段。
 * 不是静态断言——证明打点在运行时真的落盘，而非"代码里写了"。
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, readFileSync, existsSync } from 'node:fs'

let pass = 0, total = 0
const check = (label, ok) => { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const TRACE = 'D:/Brain/workspace/bench/_tmp_a17_trace.jsonl'
const PRODUCT = 'D:/Brain/workspace/bench/_tmp_a17_product.txt'
try { unlinkSync(TRACE) } catch {}
writeFileSync(TRACE, '')
writeFileSync(PRODUCT, '这是一个测试产物，包含 main 入口和完整实现。\n'.repeat(5))

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null, traceEnabled: true, tracePath: TRACE,
  criticEnabled: true, criticMaxTokens: 200, criticTimeoutMs: 5000,
  maxCriticPerSession: 2,
  auditEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  skillsEnabled: false, learningEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, continuityEnabled: false,
  workspaceRoot: 'D:/Brain/workspace/bench',
  // 让 workspaceSnapshot 把 product 指向我们的测试文件
})

const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
const pre = async (agent) => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }

let criticCalls = 0
const origFetch = globalThis.fetch
globalThis.fetch = async () => {
  criticCalls++
  return { ok: true, json: async () => ({
    choices: [{ message: { content: JSON.stringify({
      verdict: 'ACCEPT', reasons: ['1 达标'], evidence: ['产物第1行'], confidence: 'high', error_class: 'none'
    }) } }]
  }) }
}

const sid = 'a17-runtime'
const agent = { session: { id: sid }, steer() {} }
await emit('session/event', { id: sid }, { type: 'turn/start', data: { turn: 1 } })
await emit('session/event', { id: sid }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '请评审这个产物' }] } })
// 先通过一次成功的 write 设置 lastProduct（Critic 的 product 来源）
await emit('session/event', { id: sid }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: PRODUCT }) } })
await emit('session/event', { id: sid }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'OK' }] }, status: 'OK' } })
// presentCalled=true 触发 Critic（Critic 在 turn-stopping 钩子里，不在 pre-step）
await emit('session/event', { id: sid }, { type: 'tool/call', data: { name: 'present', arguments: '{}' } })
await emit('agent/turn-stopping', { agent, turn: 1 })
globalThis.fetch = origFetch

check('① Critic 被真实调用', criticCalls >= 1)
const rows = existsSync(TRACE) ? readFileSync(TRACE, 'utf8').split('\n').filter(Boolean).map((l) => { try { return JSON.parse(l) } catch { return null } }).filter(Boolean) : []
const verdicts = rows.filter((r) => r.kind === 'review_verdict' && r.review_kind === 'critic')
check(`② review_verdict trace 落盘（找到 ${verdicts.length} 条）`, verdicts.length >= 1)
if (verdicts.length) {
  const v = verdicts[verdicts.length - 1]
  check('③ verdict 字段是真实判定值', v.verdict === 'ACCEPT')
  check('④ rubric_version 字段存在', typeof v.rubric_version === 'string' && v.rubric_version.length > 0)
  check('⑤ dimensions_checked 含第7维', Array.isArray(v.dimensions_checked) && v.dimensions_checked.includes(7))
  check('⑥ llm trace 也带评审元数据', rows.some((r) => r.kind === 'llm' && r.review_kind === 'critic' && Array.isArray(r.dimensions_checked)))
}
try { unlinkSync(PRODUCT) } catch {}

console.log(`\n${pass}/${total} pass`)
process.exit(pass === total ? 0 : 1)
