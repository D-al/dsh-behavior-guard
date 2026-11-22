/**
 * 维护性更新（v2.12.0）回归测试：验证 P0/P1 修复确实生效
 * - P0-1 trace 轮转：renameSync 已导入，超阈值时真轮转
 * - P0-2 配置合并先于初始化：skillsEnabled:false / 自定义 tracePath 生效
 * - P0-3 outcomeCaptureEnabled 单独开启也能写 outcome
 * - P0-5 无关 read 不再把 verifyRan 置真（verify-on-stop 不被短路）
 * - P1-1 sessionInjections 按会话隔离
 * - P1-3 控制回合会话级上限生效
 */
import { apply } from '../index.mjs'
import { writeFileSync, existsSync, unlinkSync, readdirSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }
const tmp = tmpdir()
function harness(config) {
  const handlers = new Map()
  const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
  apply(ctx, { probePath: null, ...config })
  const emit = async (ev, ...a) => { for (const f of handlers.get(ev) || []) await f(...a) }
  const stopping = async (agent) => { for (const f of handlers.get('agent/turn-stopping') || []) await f({ agent, turn: 1 }) }
  const pre = async (agent) => { let d = { messages: [] }; for (const f of handlers.get('agent/pre-step') || []) d = (await f({ agent }, async () => d)) || d; return d }
  return { emit, stopping, pre }
}

;(async () => {
  // P0-1 trace 轮转
  {
    const dir = join(tmp, `harness-rotate-${process.pid}`)
    const { mkdirSync, rmSync } = await import('node:fs')
    try { rmSync(dir, { recursive: true, force: true }) } catch {}
    mkdirSync(dir, { recursive: true })
    const TR = join(dir, 'trace.jsonl')
    writeFileSync(TR, 'x'.repeat(120) + '\n')
    const h = harness({ traceEnabled: true, tracePath: TR, maxTraceBytes: 10, controlEnabled: false,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, verifyOnStopEnabled: false, mindStateEnabled: false,
      maxInjectionsPerSession: 4, frameEnabled: false, fepEnabled: false, learningEnabled: false })
    // 轮转在下次 trace() 调用时发生——触发一次工具调用
    await h.emit('session/event', { id: 'rotate' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'rotate' }, { type: 'tool/call', data: { name: 'read', arguments: '{}' } })
    const files = readdirSync(dir)
    check('P0-1 trace 超阈值后真轮转（旧文件改名归档）', files.length >= 2 && files.some((f) => f.startsWith('trace-')))
    try { rmSync(dir, { recursive: true, force: true }) } catch {}
  }

  // P0-2 配置合并先于初始化（skillsEnabled:false 生效）
  {
    const h = harness({ skillsEnabled: false, traceEnabled: false, controlEnabled: false,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, verifyOnStopEnabled: false, mindStateEnabled: false,
      maxInjectionsPerSession: 4, frameEnabled: false, fepEnabled: false, learningEnabled: false })
    await h.emit('session/event', { id: 'skills-off' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'skills-off' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: 'release plugin web fetch 触发技能关键词' }] } })
    const d = await h.pre({ session: { id: 'skills-off' }, steer: () => {} })
    const injected = (d.messages || []).map((m) => m.content?.[0]?.text || '').join('\n')
    check('P0-2 skillsEnabled:false 生效（无技能卡注入）', !injected.includes('技能可用'))
  }

  // P0-3 outcomeCaptureEnabled 单独开启
  {
    const OUT = join(tmp, `harness-outcome-only-${process.pid}.jsonl`)
    try { if (existsSync(OUT)) unlinkSync(OUT) } catch {}
    const h = harness({ learningEnabled: false, outcomeCaptureEnabled: true, outcomePath: OUT,
      traceEnabled: false, controlEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
      presentGateEnabled: false, auditEnabled: false, auditEverySteps: 9999,
      verifyOnStopEnabled: false, mindStateEnabled: false, maxInjectionsPerSession: 4,
      frameEnabled: false, fepEnabled: false, verifyOnEditEnabled: false })
    await h.emit('session/event', { id: 'outcome-only' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'outcome-only' }, { type: 'tool/call', data: { name: 'write', arguments: '{"file_path":"a.txt"}' } })
    await h.emit('session/event', { id: 'outcome-only' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    const rows = existsSync(OUT) ? readFileSync(OUT, 'utf8').split('\n').filter(Boolean) : []
    check('P0-3 outcomeCaptureEnabled 单独开启也写 outcome', rows.length > 0)
    try { if (existsSync(OUT)) unlinkSync(OUT) } catch {}
  }

  // P0-5 无关 read 不短路 verify-on-stop
  {
    let steered = 0
    const h = harness({ verifyOnStopEnabled: true, maxVerifyOnStopSteers: 2, frameEnabled: true,
      traceEnabled: false, controlEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
      presentGateEnabled: false, auditEnabled: false, auditEverySteps: 9999, mindStateEnabled: false,
      maxInjectionsPerSession: 4, fepEnabled: false, learningEnabled: false, verifyOnEditEnabled: false })
    const agent = { session: { id: 'verify-gate' }, steer: () => { steered++ } }
    await h.emit('session/event', { id: 'verify-gate' }, { type: 'turn/start', data: { turn: 1 } })
    // 写之前有一次无关 read —— 不能把 verifyRan 置真
    await h.emit('session/event', { id: 'verify-gate' }, { type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"unrelated.txt"}' } })
    await h.emit('session/event', { id: 'verify-gate' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    // 然后写文件、不做验证、尝试收尾 → verify-on-stop 应拦截
    await h.emit('session/event', { id: 'verify-gate' }, { type: 'tool/call', data: { name: 'write', arguments: '{"file_path":"a.txt"}' } })
    await h.emit('session/event', { id: 'verify-gate' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.emit('session/event', { id: 'verify-gate' }, { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: '完成' }] } } })
    await h.stopping(agent)
    check('P0-5 无关 read 不短路 verify-on-stop（闸门仍拦截）', steered > 0)
  }

  // 2026-11-22 修复：verify-on-stop 提示与 S13 判据一致性
  // 旧提示叫模型"read 一下就能收尾"，判据却不认普通 read → 二次拦截死循环
  {
    const steers = []
    const h = harness({ verifyOnStopEnabled: true, maxVerifyOnStopSteers: 2, frameEnabled: true,
      traceEnabled: false, controlEnabled: false, criticEnabled: false, plannerCheckEnabled: false,
      presentGateEnabled: false, auditEnabled: false, auditEverySteps: 9999, mindStateEnabled: false,
      maxInjectionsPerSession: 4, fepEnabled: false, learningEnabled: false, verifyOnEditEnabled: false })
    const agent = { session: { id: 'consistency-gate' }, steer: (m) => { steers.push(m?.content?.[0]?.text || '') } }
    await h.emit('session/event', { id: 'consistency-gate' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'consistency-gate' }, { type: 'tool/call', data: { name: 'write', arguments: '{"file_path":"a.txt"}' } })
    await h.emit('session/event', { id: 'consistency-gate' }, { type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'ok' }] } } })
    await h.emit('session/event', { id: 'consistency-gate' }, { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: '完成' }] } } })
    await h.stopping(agent)
    const t = steers.join(' ')
    check('verify-on-stop 提示不再说普通 read 就能收尾', steers.length > 0 && !t.includes('读回之后才能收尾'))
    check('verify-on-stop 提示给出判据认可的动作', t.includes('真实验证命令') && t.includes('[VERIFY]'))
  }

  // P1-1 sessionInjections 按会话隔离
  {
    const h = harness({ traceEnabled: false, controlEnabled: true, controlEverySteps: 1, maxControlPerSession: 5,
      criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
      auditEnabled: false, auditEverySteps: 9999, verifyOnStopEnabled: false, mindStateEnabled: false,
      maxInjectionsPerSession: 1, frameEnabled: false, fepEnabled: false, learningEnabled: false })
    // 会话A 用满预算
    const a = { session: { id: 'session-A' }, steer: () => {} }
    await h.emit('session/event', { id: 'session-A' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'session-A' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '任务A' }] } })
    await h.emit('session/event', { id: 'session-A' }, { type: 'step/end', data: {} })
    await h.pre(a); await h.pre(a)
    // 会话B 是新会话，应有自己的预算
    const b = { session: { id: 'session-B' }, steer: () => {} }
    await h.emit('session/event', { id: 'session-B' }, { type: 'turn/start', data: { turn: 1 } })
    await h.emit('session/event', { id: 'session-B' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '任务B' }] } })
    await h.emit('session/event', { id: 'session-B' }, { type: 'step/end', data: {} })
    const db = await h.pre(b)
    const t = (db.messages || []).map((m) => m.content?.[0]?.text || '').join(' ')
    check('P1-1 会话B 不受会话A 预算影响（有控制回合注入）', t.includes('控制回合'))
  }

  console.log(`\n══════ ${pass}/${total} 通过 ══════`)
  process.exit(pass === total ? 0 : 1)
})().catch((e) => { console.error(e); process.exit(1) })
