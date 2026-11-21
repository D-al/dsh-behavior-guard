/**
 * 集成测试：formatCorrection 接入守卫后的端到端行为（真断言版 v2 2026-11-22）
 *
 * 旧版 v1 有 3 个恒真断言(check(..., true))——什么都没验证。本版改为：
 *   Test 1: 构造 D2(同参数双失败) → pendingCorrector → mock LLM 返回 retry_with pkg
 *           → 验证 pre-step 返回的 messages 里确实有 formatCorrection 生成的修正文本
 *   Test 2/3: 同样走 pendingCorrector 路径，mock LLM 返回 ask_user/abandon pkg
 *           → 验证 messages 里对应文本（不再写死 true）
 *   Test 4: 干净流程不该有修正（真检查文本的缺失，不是恒真）
 *
 * 覆盖的是 index.mjs 内联的 formatCorrection + runCorrector + pre-step 返回链，
 * 不是 tools/format_correction.mjs 纯函数(那是 test_format_correction.mjs 的职责)。
 *
 * 用法: node tools/test_format_correction_integration.mjs
 */
import { existsSync, unlinkSync } from 'node:fs'
import { apply } from '../index.mjs'

const TRACE = 'D:/Brain/workspace/bench/_tmp_fc_trace.jsonl'
let pass = 0, total = 0
function check(label, ok, detail) {
  total++
  if (ok) { pass++; console.log(`PASS  ${label}`) }
  else { console.error(`FAIL  ${label}${detail ? ' — ' + detail : ''}`) }
}

const origFetch = globalThis.fetch
let llmResponder = null
let llmCalls = 0
globalThis.fetch = async (url, opts) => {
  llmCalls++
  let body = {}
  try { body = JSON.parse(opts.body) } catch (e) { /* 忽略 */ }
  const content = llmResponder ? llmResponder(body) : '{"verdict":"ACCEPT"}'
  return {
    ok: true,
    json: async () => ({ choices: [{ message: { content }, finish_reason: 'stop' }] })
  }
}

function makeHarness(config) {
  const handlers = new Map()
  const ctx = {
    on: (name, cb) => { handlers.set(name, [...(handlers.get(name) || []), cb]) },
    logger: { info() {}, warn() {}, error() {} }
  }
  apply(ctx, config)
  const emit = async (ev, ...args) => {
    for (const fn of handlers.get(ev) || []) await fn(...args)
  }
  return { emit, handlers, ctx }
}

const sid = 'fc-int2'
async function baseFlow(h) {
  await h.emit('session/event', { id: sid }, { type: 'turn/start', data: { turn: 1 } })
  await h.emit('session/event', { id: sid }, {
    type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '读取缺失文件' }] }
  })
}
// 两次同工具同参数失败 → D2 同参双败 → pendingCorrector
async function doubleFail(h) {
  for (let i = 0; i < 2; i++) {
    await h.emit('session/event', { id: sid }, {
      type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"missing.md"}' }
    })
    await h.emit('session/event', { id: sid }, {
      type: 'tool/result', data: { message: { content: [{ type: 'text', text: 'Error: file not found: missing.md' }] } }
    })
  }
}

function messagesText(decision) {
  return (decision?.messages || []).map(m => typeof m === 'string' ? m : JSON.stringify(m)).join('\n')
}

;(async () => {
  try {
    if (existsSync(TRACE)) unlinkSync(TRACE)
    console.log('🧪 test_format_correction_integration v2 (真断言)\n')

    const cfg = {
      controlEnabled: false, criticEnabled: false, auditEnabled: false,
      executorEnabled: false, mindStateEnabled: false,
      maxInjectionsPerSession: 5, traceEnabled: true, tracePath: TRACE,
    }
    const agent = { session: { id: sid, sid }, steer: () => {} }

    // ── Test 1: retry_with pkg 经 D2 → pre-step → messages ──
    {
      console.log('[Test 1] retry_with 端到端')
      llmCalls = 0
      llmResponder = () => JSON.stringify({
        action: 'retry_with', tool: 'glob', args: { pattern: '*.md' }, reason: '路径写错，改用搜索'
      })
      const h = makeHarness(cfg)
      await baseFlow(h)
      await doubleFail(h)
      const decision = await h.handlers.get('agent/pre-step')?.[0]?.({ agent }, async () => ({ messages: [] }))
      check('pre-step 调用了 LLM(pendingCorrector 路径)', llmCalls > 0, `llmCalls=${llmCalls}`)
      const texts = messagesText(decision)
      check('messages 含 [harness 系统修正]', texts.includes('[harness 系统修正]'), texts.slice(0, 200))
      check('messages 含修正工具 glob', texts.includes('glob'), texts.slice(0, 200))
      check('messages 含理由', texts.includes('路径写错'), texts.slice(0, 200))
    }

    // ── Test 2: ask_user pkg ──
    {
      console.log('[Test 2] ask_user 端到端')
      llmResponder = () => JSON.stringify({ action: 'ask_user', reason: '需要用户确认目标路径' })
      const h = makeHarness(cfg)
      await baseFlow(h)
      await doubleFail(h)
      const decision = await h.handlers.get('agent/pre-step')?.[0]?.({ agent }, async () => ({ messages: [] }))
      const texts = messagesText(decision)
      check('messages 含 ask_user 提示', texts.includes('需要用户澄清') && texts.includes('请立即向用户提问'), texts.slice(0, 200))
    }

    // ── Test 3: abandon pkg ──
    {
      console.log('[Test 3] abandon 端到端')
      llmResponder = () => JSON.stringify({ action: 'abandon', reason: '目标不存在' })
      const h = makeHarness(cfg)
      await baseFlow(h)
      await doubleFail(h)
      const decision = await h.handlers.get('agent/pre-step')?.[0]?.({ agent }, async () => ({ messages: [] }))
      const texts = messagesText(decision)
      check('messages 含 abandon 提示', texts.includes('目标不可达') && texts.includes('停止尝试'), texts.slice(0, 200))
    }

    // ── Test 4: 干净流程不该有修正 ──
    {
      console.log('[Test 4] 干净流程无修正')
      llmResponder = () => '{"verdict":"ACCEPT"}'
      const h = makeHarness(cfg)
      await baseFlow(h)
      await h.emit('session/event', { id: sid }, {
        type: 'tool/call', data: { name: 'read', arguments: '{"file_path":"ok.md"}' }
      })
      await h.emit('session/event', { id: sid }, {
        type: 'tool/result', data: { message: { content: [{ type: 'text', text: '文件内容 ok' }] } }
      })
      const decision = await h.handlers.get('agent/pre-step')?.[0]?.({ agent }, async () => ({ messages: [] }))
      const texts = messagesText(decision)
      check('干净流程无系统修正标记', !texts.includes('[harness 系统修正]'), texts.slice(0, 200))
    }

    console.log(`\n📊 ${pass}/${total} tests passed`)
    if (pass === total) console.log('✅ All integration checks passed')
    else { console.error(`⚠️  ${total - pass} check(s) failed`); process.exitCode = 1 }
  } finally {
    globalThis.fetch = origFetch
    if (existsSync(TRACE)) unlinkSync(TRACE)
  }
})()
