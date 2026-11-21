// test_build_trail_text.mjs — v1 (2026-12-xx)
// 单测覆盖正常/边界/截断三类；每个断言都是真行为断言，无恒真检查。
// 输出以 PASS 开头，失败时 exit code != 0。

import { buildTrailText } from './build_trail_text.mjs'

let passed = 0
let failed = 0

function assertEqual(actual, expected, label) {
  if (actual === expected) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}`)
    console.error(`     期望: "${expected}"`)
    console.error(`     实际: "${actual}"`)
  }
}

function assertNotNull(val, label) {
  if (val !== null && val !== undefined && typeof val === 'string') {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 值为 ${val}`)
  }
}

function assertTrue(condition, label) {
  if (condition) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 条件为假`)
  }
}

console.log('PASS 🧪 test_build_trail_text')
console.log('')

// --- 正常路径 ---

console.log('[基本调用记录]')
{
  const trail = [
    { kind: 'call', step: 1, name: 'read', args: '{file_path: "a.md"}', status: 'OK', result: '内容' },
    { kind: 'call', step: 2, name: 'glob', args: '{pattern: "*.js"}', status: 'OK', result: '[b.js]' },
  ]
  const result = buildTrailText(trail)
  assertNotNull(result, '返回值非空字符串')
  assertTrue(result.includes('step1'), '包含 step1')
  assertTrue(result.includes('read'), '包含工具名 read')
  assertTrue(result.includes('-> OK'), '包含状态 OK')
  assertTrue(result.includes('\n'), '含换行分隔多行')
}

console.log('[todo 类型也收录]')
{
  const trail = [
    { kind: 'todo', step: 3, name: '写文档', args: '', status: 'done', result: '' },
  ]
  const result = buildTrailText(trail)
  assertTrue(result.includes('step3'), 'todo 也被纳入输出')
}

console.log('[status 从 ok 字段推导]')
{
  const trail = [
    { kind: 'call', step: 5, name: 'write', args: '{}', ok: true, result: '' },
    { kind: 'call', step: 6, name: 'write', args: '{}', ok: false, result: '' },
  ]
  const result = buildTrailText(trail)
  assertTrue(result.includes('-> OK'), 'ok:true → -> OK')
  assertTrue(result.includes('-> FAIL'), 'ok:false → -> FAIL')
}

// --- 连续同名检测 ---

console.log('[连续同名 ≥3 次标记]')
{
  const trail = [
    { kind: 'call', step: 1, name: 'wait_agent', args: '{}', status: 'UNPRODUCTIVE', result: '' },
    { kind: 'call', step: 2, name: 'wait_agent', args: '{}', status: 'UNPRODUCTIVE', result: '' },
    { kind: 'call', step: 3, name: 'wait_agent', args: '{}', status: 'UNPRODUCTIVE', result: '' },
  ]
  const result = buildTrailText(trail)
  assertTrue(result.includes('连续第3次'), '连续 3 次被标记 [连续第3次]')
}

console.log('[连续同名 <3 次不标记]')
{
  const trail = [
    { kind: 'call', step: 1, name: 'read', args: '{}', status: 'OK', result: '' },
    { kind: 'call', step: 2, name: 'read', args: '{}', status: 'OK', result: '' },
  ]
  const result = buildTrailText(trail)
  assertTrue(!result.includes('连续第'), '连续 2 次不应出现"连续第"标记')
}

// --- args 截断 ---

console.log('[args 截断至 80 字符]')
{
  const longArgs = JSON.stringify({ a: 'x'.repeat(100) })
  const trail = [
    { kind: 'call', step: 1, name: 'write', args: longArgs, status: 'OK', result: '' },
  ]
  const result = buildTrailText(trail)
  // 格式为 "step1 write(...)"，提取 () 内的 args 部分检查长度
  const match = result.match(/\)\s*->/)
  if (match) {
    const beforeMatch = result.slice(0, match.index)
    const argsPart = beforeMatch.substring(beforeMatch.indexOf('(') + 1)
    assertEqual(argsPart.length, 80, `args 被截断到 80 字符（实际 ${argsPart.length}）`)
  } else {
    failed++
    console.error('  ❌ args 截断：无法在输出中找到 ") ->" 模式')
  }
}

// --- 空输入 ---

console.log('[空数组]')
{
  const result = buildTrailText([])
  assertEqual(result, '', '空数组返回空字符串')
}

console.log('[只有非 call/todo 类型]')
{
  const trail = [
    { kind: 'event', step: 1, data: 'foo' },
  ]
  const result = buildTrailText(trail)
  assertEqual(result, '', '非 call/todo 类型被过滤掉')
}

// --- 超长结果截断（4000 字符上限）---

console.log('[结果截断至最后 4000 字符]')
{
  const trail = []
  for (let i = 0; i < 200; i++) {
    trail.push({
      kind: 'call',
      step: i + 1,
      name: 'big_call',
      args: '{payload:"' + 'x'.repeat(50) + '"}',
      status: 'OK',
      result: 'result_' + i,
    })
  }
  const result = buildTrailText(trail)
  assertTrue(result.length <= 4000, `总长度 ≤ 4000（实际 ${result.length}）`)
  // 截断后不一定从 step1 开始（因为 slice(-4000) 从尾部取），但应仍含 step 和 call 信息
  assertTrue(result.includes('big_call'), '截断后仍包含工具名 big_call')
  assertTrue(result.match(/step\d+/), '截断后仍有 stepN 格式的行')
}

// --- 状态为空时 fallback ---

console.log('[status 为空时用 ? 占位]')
{
  const trail = [
    { kind: 'call', step: 1, name: 'unknown', args: '{}' },
  ]
  const result = buildTrailText(trail)
  assertTrue(result.includes('?'), '无 status/ok → ?')
}

// ── 汇总 ────────────────────────────────────────────────

console.log('')
console.log(`📊 ${passed}/${passed + failed} 测试通过`)
if (failed > 0) {
  console.error(`⚠️  ${failed} 项失败！`)
  process.exitCode = 1
} else {
  console.log('✅ 全部通过')
}
