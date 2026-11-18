/**
 * S5 角色失效修复单测：
 * ① 角色 LLM 失败写明确 error 字段（不再静默）
 * ② Critic content 空时从 reasoning_content 兜底解析 JSON
 * ③ 验收员 spawn 后 N 步无 wait → 主动代验收（新版 dsh 无 wait_agent）
 * 用法: node tools/test_role_fixes.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync, existsSync } from 'node:fs'

// 初始化测试用 trace 文件（makeTracer 需要文件存在才能追加）
for (const f of [
  'D:/Brain/workspace/bench/_tmp_role_trace.jsonl',
  'D:/Brain/workspace/bench/_tmp_role_trace2.jsonl',
  'D:/Brain/workspace/bench/_tmp_role_trace3.jsonl',
]) { try { unlinkSync(f) } catch {}; writeFileSync(f, '') }

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

function harness(config, fetchImpl) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  const orig = globalThis.fetch
  globalThis.fetch = fetchImpl
  apply(ctx, { probePath: null, ...config })
  const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
  const pre = async (agent) => { let d = { messages: [] }; for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d; return d }
  const stopping = async (agent) => { for (const fn of handlers.get('agent/turn-stopping') || []) await fn({ agent, turn: 1 }) }
  return { emit, pre, stopping, restore: () => { globalThis.fetch = orig } }
}

const base = {
  probePath: null,
  traceEnabled: true, tracePath: 'D:/Brain/workspace/bench/_tmp_role_trace.jsonl',
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  auditEnabled: false, auditEverySteps: 9999, auditEveryStepsAnomaly: 9999,
  skillsEnabled: false, learningEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, maxInjectionsPerSession: 99, maxInjectionsPerTurn: 99, sharedMaxPerTurn: 99,
}

// ── ① 失败 error 字段 ──────────────────────────────────────────
{
  const fs = await import('node:fs')
  fs.writeFileSync('D:/Brain/workspace/bench/_tmp_role_prod0.txt', 'print(0)')
  const { emit, stopping, restore } = harness({ ...base,
    criticEnabled: true, criticTimeoutMs: 200, criticMaxTokens: 1200, deepCheckEnabled: false,
  }, async () => { throw new Error('fetch failed') })
  const agent = { session: { id: 'role-fail' }, steer() {} }
  await emit('session/event', { id: 'role-fail' }, { type: 'turn/start', data: { turn: 1 } })
  await emit('session/event', { id: 'role-fail' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写文件并验证' }] } })
  await emit('session/event', { id: 'role-fail' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: 'D:/Brain/workspace/bench/_tmp_role_prod0.txt' }) } })
  await emit('session/event', { id: 'role-fail' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
  await emit('session/event', { id: 'role-fail' }, { type: 'tool/call', data: { name: 'present', arguments: '{}' } })
  await stopping(agent)
  const rows = fs.readFileSync(base.tracePath, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  const bad = rows.filter((r) => r.kind === 'llm' && !r.ok)
  check('① 失败 LLM 调用有 error 字段', bad.length > 0 && bad.every((r) => typeof r.error === 'string' && r.error.length > 0))
  restore()
}

// ── ② Critic 从 reasoning 兜底 ────────────────────────────────
{
  const fs = await import('node:fs')
  try { fs.unlinkSync('D:/Brain/workspace/bench/_tmp_role_prod.txt') } catch {}
  fs.writeFileSync('D:/Brain/workspace/bench/_tmp_role_prod.txt', "def main():\n    print('ok')\n\nif __name__ == '__main__':\n    main()\n")
  const { emit, stopping, restore } = harness({ ...base,
    criticEnabled: true, criticMaxTokens: 1200, criticTemperature: 0.7, criticTopK: 20,
    tracePath: 'D:/Brain/workspace/bench/_tmp_role_trace2.jsonl',
  }, async (url, opts) => {
    const body = JSON.parse(opts.body)
    return { ok: true, json: async () => ({
      choices: [{ finish_reason: 'length', message: {
        role: 'assistant', content: '',  // content 空——thinking 吃光 token
        reasoning_content: '我需要判断是否达标... \n{"verdict":"ACCEPT","reasons":["1 达标"],"evidence":["产物有 main"],"confidence":"high","error_class":"none"}',
      } }],
    }) }
  })
  const agent = { session: { id: 'role-reason' }, steer() {} }
  await emit('session/event', { id: 'role-reason' }, { type: 'turn/start', data: { turn: 1 } })
  await emit('session/event', { id: 'role-reason' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个带 main 的 python 文件' }] } })
  // write 产物 → 设置 lastProduct（runCritic 需要）
  await emit('session/event', { id: 'role-reason' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: 'D:/Brain/workspace/bench/_tmp_role_prod.txt' }) } })
  await emit('session/event', { id: 'role-reason' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
  // present 触发 Critic
  await emit('session/event', { id: 'role-reason' }, { type: 'tool/call', data: { name: 'present', arguments: '{}' } })
  await stopping(agent)
  const rows = fs.readFileSync('D:/Brain/workspace/bench/_tmp_role_trace2.jsonl', 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  const criticCalls = rows.filter((r) => r.kind === 'llm' && r.tag === 'critic')
  check('② Critic 被调用', criticCalls.length >= 1)
  check('② reasoning 兜底后 ok=true', criticCalls.some((r) => r.ok === true))
  check('② 记录 reasoningUsed/emptyContent', criticCalls.some((r) => r.reasoningUsed === true && r.emptyContent === true))
  restore()
}

// ── ③ 验收员 spawn 触发 ────────────────────────────────────────
{
  const fs = await import('node:fs')
  try { fs.unlinkSync('D:/Brain/workspace/bench/_tmp_role_prod2.txt') } catch {}
  fs.writeFileSync('D:/Brain/workspace/bench/_tmp_role_prod2.txt', 'print("verified")')
  let verifyCalls = 0
  const { emit, stopping, restore } = harness({ ...base,
    verifySpawnSteps: 2,
    verifyTimeoutMs: 5000,
    tracePath: 'D:/Brain/workspace/bench/_tmp_role_trace3.jsonl',
  }, async () => {
    verifyCalls++
    return { ok: true, json: async () => ({ choices: [{ message: { content: 'OK' } }] }) }
  })
  const agent = { session: { id: 'role-verify' }, steer() {} }
  await emit('session/event', { id: 'role-verify' }, { type: 'turn/start', data: { turn: 1 } })
  await emit('session/event', { id: 'role-verify' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写文件并 spawn 验收' }] } })
  // 先写产物
  await emit('session/event', { id: 'role-verify' }, { type: 'tool/call', data: { name: 'write', arguments: JSON.stringify({ file_path: 'D:/Brain/workspace/bench/_tmp_role_prod2.txt' }) } })
  await emit('session/event', { id: 'role-verify' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
  // spawn
  await emit('session/event', { id: 'role-verify' }, { type: 'tool/call', data: { name: 'spawn_teammate', arguments: JSON.stringify({ description: '验收产物', prompt: '检查文件存在' }) } })
  await emit('session/event', { id: 'role-verify' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'spawned' }] } } })
  // 无 wait_agent，直接走 2 步其他工具（模拟异步回注期间的普通操作）
  for (let i = 0; i < 3; i++) {
    await emit('session/event', { id: 'role-verify' }, { type: 'tool/call', data: { name: 'read', arguments: '{}' } })
    await emit('session/event', { id: 'role-verify' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'x' }] } } })
  }
  await stopping(agent)
  const rows = fs.readFileSync('D:/Brain/workspace/bench/_tmp_role_trace3.jsonl', 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
  const triggered = rows.filter((r) => r.kind === 'verify_triggered')
  check('③ spawn 后无 wait 也触发代验收', triggered.length === 1 && triggered[0].source === 'spawn-no-wait')
  check('③ verify_triggered 记录产物路径', triggered.length > 0 && !!triggered[0].product)
  restore()
}

console.log(`\n══════ ${pass}/${total} 通过 ══════`)
process.exit(pass === total ? 0 : 1)
