/**
 * 压缩存档去重单测：相同 todo 状态的存档只完整注入一次，后续给简短"未变化"提示。
 * 依据：s1 会话 82 次压缩注入完全相同的存档（todos=2/完成=0），形成自我强化循环。
 * 用法: node tools/test_archive_dedup.mjs
 */
import { apply } from '../index.mjs'
import { writeFileSync, unlinkSync } from 'node:fs'

let pass = 0, total = 0
function check(label, ok) { total++; if (ok) pass++; console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}`) }

const TRACE = 'D:/Brain/workspace/bench/_tmp_archive_trace.jsonl'
const LEDGER = 'D:/Brain/workspace/bench/_tmp_archive_ledger.jsonl'
try { unlinkSync(TRACE) } catch {}
try { unlinkSync(LEDGER) } catch {}
writeFileSync(TRACE, '')
writeFileSync(LEDGER, '')

const handlers = new Map()
const ctx = { on: (n, cb) => { handlers.set(n, [...(handlers.get(n) || []), cb]) }, logger: { info() {}, warn() {} } }
apply(ctx, {
  probePath: null,
  continuityEnabled: true,
  traceEnabled: true, tracePath: TRACE,
  ledgerPath: LEDGER,
  // 关掉其他注入源，避免干扰
  controlEnabled: false, mindStateEnabled: false, verifyOnStopEnabled: false,
  criticEnabled: false, plannerCheckEnabled: false, presentGateEnabled: false,
  auditEnabled: false, auditEverySteps: 9999, auditEveryStepsAnomaly: 9999,
  skillsEnabled: false, learningEnabled: false, fepEnabled: false,
  specSignalEnabled: false, todoEchoEnabled: false, dangerGuardEnabled: false,
  deepCheckEnabled: false, maxInjectionsPerSession: 99, maxInjectionsPerTurn: 99,
})

const emit = async (ev, ...args) => { for (const fn of handlers.get(ev) || []) await fn(...args) }
const pre = async (agent) => {
  let d = { messages: [] }
  for (const fn of handlers.get('agent/pre-step') || []) d = (await fn({ agent }, async () => d)) || d
  return d
}

const agent = { session: { id: 'archive-test' }, steer() {} }

function archiveText(d) {
  const msg = (d?.messages || []).find((m) => JSON.stringify(m?.content || '').includes('任务存档'))
  const c = msg?.content
  if (typeof c === 'string') return c
  if (Array.isArray(c)) return c.map((b) => String(b?.text || '')).join('\n')
  return ''
}

// 场景 1：首次压缩 → 完整存档
await emit('session/event', { id: 'archive-test' }, { type: 'turn/start', data: { turn: 1 } })
await emit('session/event', { id: 'archive-test' }, { type: 'user/message', data: { source: { kind: 'user' }, content: [{ type: 'text', text: '写一个脚本并验证它' }] } })
await emit('session/event', { id: 'archive-test' }, { type: 'todo/write', data: { todos: [
  { content: '写脚本 [VERIFY]', status: 'in_progress' },
  { content: '跑验证', status: 'pending' },
] } })
await emit('session/event', { id: 'archive-test' }, { type: 'compaction/summary', data: {} })
let d = await pre(agent)
const first = archiveText(d)
check('① 首次压缩注入完整存档', first.includes('【初始任务】') && first.includes('写一个脚本') && first.includes('【压缩后自检】'))
check('① 首次含 todo 合同', first.includes('【任务合同】') || first.includes('【开放问题】'))

// 场景 2：相同存档再次压缩 → 简短"未变化"提示，无完整存档
await emit('session/event', { id: 'archive-test' }, { type: 'compaction/summary', data: {} })
d = await pre(agent)
const second = archiveText(d)
check('② 重复压缩不再注入完整存档', !second.includes('【初始任务】') && !second.includes('【压缩后自检】'))
check('② 重复压缩给出"未变化"提示', second.includes('完全没有变化') && second.includes('已重复 1 次'))
check('② 重复压缩带防重复指令', second.includes('不要因此重新规划'))

// 场景 3：todo 状态变化后压缩 → 重新注入完整存档
await emit('session/event', { id: 'archive-test' }, { type: 'todo/write', data: { todos: [
  { content: '写脚本 [VERIFY]', status: 'completed' },
  { content: '跑验证', status: 'in_progress' },
] } })
await emit('session/event', { id: 'archive-test' }, { type: 'compaction/summary', data: {} })
d = await pre(agent)
const third = archiveText(d)
check('③ 状态变化后重新注入完整存档', third.includes('【初始任务】') && third.includes('【压缩后自检】'))
check('③ 变化后反映已完成项', third.includes('【已验证决策】'))

// 场景 4：trace 记录 archive_dedup
const traceRows = (await import('node:fs')).readFileSync(TRACE, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
const dedup = traceRows.filter((r) => r.kind === 'archive_dedup')
check('④ trace 记录 archive_dedup 事件', dedup.length === 1 && dedup[0].repeats === 1)

// 场景 5：ledger 带 repeated 字段
const ledgerRows = (await import('node:fs')).readFileSync(LEDGER, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l))
check('⑤ ledger 记录 repeated 次数', ledgerRows.length === 3 && ledgerRows[1].repeated === 1 && ledgerRows[0].repeated === 0)

console.log(`\n══════ ${pass}/${total} 通过 ══════`)
try { unlinkSync(TRACE) } catch {}
try { unlinkSync(LEDGER) } catch {}
process.exit(pass === total ? 0 : 1)
