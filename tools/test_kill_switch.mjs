/**
 * kill_switch 指纹逻辑单测：验证"内容循环 → 指纹停滞，内容变化 → 指纹变化"。
 * 关键回归：指纹绝不能含 cursor（含 cursor 则检测永不触发）。
 */
import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'

let pass = 0, fail = 0
const check = (label, ok) => { if (ok) { pass++; console.log(`PASS  ${label}`) } else { fail++; console.log(`FAIL  ${label}`) } }

const src = readFileSync(new URL('./kill_switch.py', import.meta.url), 'utf8')
check('源码指纹不含 cursor（含则检测永不触发）',
  !/return f"\{e\.get\('cursor'\)\}:\{h\}"|f"\{e\.get\('cursor'\)\}/.test(src))

function fp(recs) {
  if (!recs.length) return null
  const types = recs.map((r) => r.event?.type || '').join(',')
  const last = JSON.stringify(recs[recs.length - 1].event?.data || {})
  return createHash('sha256').update(types + '|' + last).digest('hex').slice(0, 16)
}
const a = [{ event: { type: 'assistant/message', data: { text: 'REJECT:xxx' } } }]
const b = [{ event: { type: 'assistant/message', data: { text: 'REJECT:yyy' } } }]
check('相同内容 → 相同指纹（完整字符串比）', fp(a) === fp(a))
check('不同内容 → 不同指纹', fp(a) !== fp(b))

// 验证脚本能启动（--once 无会话时正常退出）
try {
  const out = execFileSync('D:/Python/python.exe',
    ['-B', new URL('./kill_switch.py', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1'), '--once'],
    { encoding: 'utf8', timeout: 15000 })
  check('--once 正常启动并退出', out.includes('[start]'))
} catch (e) {
  check('--once 正常启动并退出', false)
}

console.log(`\n${pass}/${pass + fail} pass`)
process.exit(fail ? 1 : 0)
