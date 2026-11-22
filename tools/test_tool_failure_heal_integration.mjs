/**
 * S24 执行层工具失败自愈 —— 集成测试（换测法）
 *
 * 旧测法：靠 35B 自然犯错 + 看 trace → 模型用 write 绕开，测的是运气
 * 新测法：用真实事件结构直接驱动 harness 接线（session/event → pre-step），确定性验证
 */
import assert from 'node:assert/strict'
import { apply } from '../index.mjs'

let pass = 0
function check(label, ok) { assert.ok(ok, label); pass++; console.log('PASS', label) }

function harness(config = {}) {
  const handlers = new Map()
  const infos = []
  const ctx = {
    on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) },
    logger: { info: (m) => infos.push(String(m)), warn: (m) => infos.push(String(m)) }
  }
  apply(ctx, { probePath: null, traceEnabled: false, auditEnabled: false, criticEnabled: false,
    plannerCheckEnabled: false, presentGateEnabled: false, controlEnabled: false,
    mindStateEnabled: false, fepEnabled: false, learningEnabled: false,
    verifyOnEditEnabled: false, toolFailureHealEnabled: true, ...config })
  const emit = async (ev, ...a) => { for (const f of handlers.get(ev) || []) await f(...a) }
  const pre = async (agent) => {
    let d = { messages: [] }
    for (const f of handlers.get('agent/pre-step') || []) d = (await f({ agent }, async () => d)) || d
    return d
  }
  return { emit, pre, infos }
}

const sid = 's24-integration'
async function base(h) {
  await h.emit('session/event', { id: sid }, { type: 'turn/start', data: { turn: 1 } })
}

// 真实 FS_STALE_VERSION 事件结构（2026-11-22 实测抓到）
const staleEvent = () => ({
  type: 'tool/result',
  data: {
    turn: 1, step: 1, toolCallId: 'c-s24',
    error: { name: 'FsError', code: 'FS_STALE_VERSION' },
    message: {
      role: 'tool', isError: true, source: { kind: 'tool', callId: 'c-s24' },
      content: [{ type: 'text', text: 'Error: cannot edit "D:/x/a.txt": file changed since it was read — re-read the file, then retry' }]
    }
  }
})

{
  const h = harness()
  await base(h)
  const agent = { session: { id: sid } }
  await h.emit('session/event', { id: sid }, { type: 'tool/call', data: { callId: 'c-s24', name: 'edit', arguments: '{}' } })
  await h.emit('session/event', { id: sid }, staleEvent())
  const d = await h.pre(agent)
  const texts = (d.messages || []).map(m => m.content?.[0]?.text || '').join(' ')
  check('FS_STALE_VERSION 失败触发执行层注入（真实事件结构）', texts.includes('[harness 工具自愈]') && texts.includes('先 read 目标文件'))
  const d2 = await h.pre(agent)
  const texts2 = (d2.messages || []).map(m => m.content?.[0]?.text || '').join(' ')
  check('注入只发生一次不重复（pendingHeal 已清）', !texts2.includes('[harness 工具自愈]'))
}

{
  const h = harness({ toolFailureHealEnabled: false })
  await base(h)
  const agent = { session: { id: sid } }
  await h.emit('session/event', { id: sid }, { type: 'tool/call', data: { callId: 'c-s24', name: 'edit', arguments: '{}' } })
  await h.emit('session/event', { id: sid }, staleEvent())
  const d = await h.pre(agent)
  const texts = (d.messages || []).map(m => m.content?.[0]?.text || '').join(' ')
  check('开关关闭时不注入', !texts.includes('[harness 工具自愈]'))
}

{
  const h = harness()
  await base(h)
  const agent = { session: { id: sid } }
  // 用户取消类错误：不注入（避免提示风暴）
  await h.emit('session/event', { id: sid }, { type: 'tool/call', data: { callId: 'c-cancel', name: 'ask_user_question', arguments: '{}' } })
  await h.emit('session/event', { id: sid }, { type: 'tool/result', data: {
    toolCallId: 'c-cancel', error: { code: 'ASK_CANCELLED' },
    message: { isError: true, source: { kind: 'tool', callId: 'c-cancel' }, content: [{ type: 'text', text: 'cancelled' }] }
  } })
  const d = await h.pre(agent)
  const texts = (d.messages || []).map(m => m.content?.[0]?.text || '').join(' ')
  check('用户取消不注入自愈提示', !texts.includes('[harness 工具自愈]'))
}

console.log(`\n${pass} PASS`)
