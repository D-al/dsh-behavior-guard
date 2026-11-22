/** S24 执行层工具失败自愈单测 */
import assert from 'node:assert/strict'
import { extractFailure, healHint, shouldInject } from './tool_failure_healer.mjs'

let pass = 0
function t(name, fn) { fn(); pass++; console.log('PASS', name) }

const names = new Map([['c1', 'edit'], ['c2', 'read'], ['c3', 'ask_user_question']])

t('非失败事件返回null', () => {
  assert.equal(extractFailure({ type: 'tool/result', data: { message: { isError: false } } }, names), null)
})

t('正文含error但isError=false不误判（219误报教训）', () => {
  const ev = { type: 'tool/result', data: { message: { isError: false, content: [{ text: 'Error: foo' }] } } }
  assert.equal(extractFailure(ev, names), null)
})

t('结构化isError=true能识别，不带code', () => {
  const r = extractFailure({ type: 'tool/result', data: { toolCallId: 'c1', message: { isError: true } } }, names)
  assert.equal(r.tool, 'edit'); assert.equal(r.code, 'UNKNOWN')
})

t('FS_EDIT_NOT_FOUND抽取工具与提示', () => {
  const ev = { type: 'tool/result', data: { toolCallId: 'c1', error: { code: 'FS_EDIT_NOT_FOUND', message: 'old_string not found' }, message: { isError: true } } }
  const f = extractFailure(ev, names)
  assert.equal(f.code, 'FS_EDIT_NOT_FOUND'); assert.equal(f.tool, 'edit')
  const h = healHint(f)
  assert.match(h, /重读目标行/); assert.match(h, /最短唯一锚点/); assert.match(h, /不要原样重试/)
})

t('带最新内容时回灌锚点文本', () => {
  const h = healHint({ tool: 'edit', code: 'FS_EDIT_NOT_FOUND', path: '' }, { fileContent: 'def main():\n    pass' })
  assert.match(h, /def main/); assert.match(h, /直接从中复制锚点/)
})

t('FS_NOT_FOUND抽路径+给相近文件', () => {
  const ev = { type: 'tool/result', data: { toolCallId: 'c2', error: { code: 'FS_NOT_FOUND', message: 'cannot read "D:/x/ROADMAP.md": not found' }, message: { isError: true } } }
  const f = extractFailure(ev, names)
  assert.equal(f.path, 'D:/x/ROADMAP.md')
  const h = healHint(f, { nearFiles: ['D:/x/ROADMAP.md.bak'] })
  assert.match(h, /glob 确认/); assert.match(h, /ROADMAP\.md\.bak/)
})

t('用户取消等不注入', () => {
  for (const code of ['ASK_CANCELLED', 'ABORTED', 'WEB_BLOCKED_URL', 'JOB_CONTROLLER_UNAVAILABLE']) {
    assert.equal(healHint({ tool: 'x', code, path: '' }), null, code)
  }
})

t('注入预算：每轮1次每会话4次', () => {
  const f = { tool: 'edit', code: 'FS_EDIT_NOT_FOUND', path: '' }
  assert.equal(shouldInject(f, {}), true)
  assert.equal(shouldInject(f, { healInjectedThisTurn: 1 }), false)
  assert.equal(shouldInject(f, { healInjectedTotal: 4 }), false)
  assert.equal(shouldInject({ tool: 'x', code: 'ASK_CANCELLED' }, {}), false)
})

console.log(`\n${pass} PASS`)
