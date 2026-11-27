/**
 * 单测：collect_corrector_input.mjs
 * 
 * 验证外置模块的 collectCorrectorInput 函数正确性
 */

import { collectCorrectorInput } from './collect_corrector_input.mjs'

let passed = 0
let failed = 0

function assert(condition, msg) {
  if (condition) {
    passed++
  } else {
    console.error(`FAIL: ${msg}`)
    failed++
  }
}

// ── 测试 1：基本功能 - 有失败和成功证据 ──
const trail1 = [
  { kind: 'call', step: 1, name: 'read', ok: true, fullEvidence: true, args: '{file:"a.md"}', result: 'content_a' },
  { kind: 'call', step: 2, name: 'pwsh', ok: false, result: '权限被拒绝' },
  { kind: 'call', step: 3, name: 'glob', ok: true, fullEvidence: true, args: '{pattern:"*.md"}', result: 'b.md,c.md' },
  { kind: 'call', step: 4, name: 'edit', ok: false, result: '路径不存在' },
]

const result1 = collectCorrectorInput(trail1)
assert(result1.failDetail.includes('step2 pwsh'), '应包含 step2 失败详情')
assert(result1.failDetail.includes('step4 edit'), '应包含 step4 失败详情')
assert(result1.evidence.includes('step1 read'), '应包含 step1 证据')
assert(result1.evidence.includes('step3 glob'), '应包含 step3 证据')
assert(!result1.failDetail.includes('step1'), '不应包含成功的 step1 到失败列表')

// ── 测试 2：空 trail ──
const result2 = collectCorrectorInput([])
assert(result2.failDetail === '', '空 trail 的 failDetail 应为空字符串')
assert(result2.evidence === '', '空 trail 的 evidence 应为空字符串')

// ── 测试 3：只有失败的 trail ──
const trail3 = [
  { kind: 'call', step: 1, name: 'test1', ok: false, result: 'err1' },
  { kind: 'call', step: 2, name: 'test2', ok: false, result: 'err2' },
]
const result3 = collectCorrectorInput(trail3)
assert(result3.failDetail.includes('step1 test1'), '应包含所有失败')
assert(result3.evidence === '', '无成功证据时 evidence 为空')

// ── 测试 4：只取最近 4 个失败 ──
const trail4 = []
for (let i = 0; i < 6; i++) {
  trail4.push({ kind: 'call', step: i, name: `fail_${i}`, ok: false, result: `error_${i}` })
}
const result4 = collectCorrectorInput(trail4)
assert(!result4.failDetail.includes('step0'), '不应包含超出最近4个的失败(step0)')
assert(!result4.failDetail.includes('step1'), '不应包含超出最近4个的失败(step1)')
assert(result4.failDetail.includes('step5'), '应包含最近的失败(step5)')
assert(result4.failDetail.includes('step2'), '应包含最近的失败(step2)')

// ── 测试 5：fullEvidence=false 的成功调用不计入证据 ──
const trail5 = [
  { kind: 'call', step: 1, name: 'read', ok: true, fullEvidence: false, args: '{}', result: 'data' },
  { kind: 'call', step: 2, name: 'write', ok: true, fullEvidence: true, args: '{file:"x.md"}', result: 'wrote x.md line 1' },
]
const result5 = collectCorrectorInput(trail5)
assert(!result5.evidence.includes('step1'), 'fullEvidence=false 不应计入')
assert(result5.evidence.includes('step2'), 'fullEvidence=true + 实质内容 应计入')

// ── 测试 6：非 call 类型的 trail 项被忽略 ──
const trail6 = [
  { kind: 'trace', step: 1, data: 'ignored' },
  { kind: 'call', step: 2, name: 'test', ok: false, result: 'fail' },
  { kind: 'other', step: 3, ignored: true },
]
const result6 = collectCorrectorInput(trail6)
assert(result6.failDetail.includes('step2'), '只处理 kind=call 的项')
assert(!result6.failDetail.includes('step1'), 'kind=trace 应被忽略')
assert(!result6.failDetail.includes('step3'), 'kind=other 应被忽略')

// ── 测试 7：args 截断验证（>100字符） ──
const longArgs = 'a'.repeat(150)
const trail7 = [
  { kind: 'call', step: 1, name: 'big_call', ok: true, fullEvidence: true, args: longArgs, result: 'ok_result' },
]
const result7 = collectCorrectorInput(trail7)
const argMatch = result7.evidence.match(/big_call\(([^)]+)\)/)
if (argMatch) {
  assert(argMatch[1].length <= 100, `args 应被截断到100字符内，实际${argMatch[1].length}`)
} else {
  assert(false, '应匹配到 args')
}

// ── 输出结果 ──
console.log(`PASS: ${passed}/${passed + failed} tests passed`)
if (failed > 0) {
  console.error(`FAILED: ${failed} tests failed`)
  process.exitCode = 1
}
