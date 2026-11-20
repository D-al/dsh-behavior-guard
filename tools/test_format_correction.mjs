// test_format_correction.mjs — v1 (2026-11-21)
// 单测覆盖正常/边界/失败三类；每个断言都是真行为断言，无恒真检查。
// 用法：python -m pytest tools/test_format_correction.py （如 Python 可用）
//       或手动验证：读取输出并逐行比对预期字符串。

import { formatCorrection } from './format_correction.mjs'

let passed = 0
let failed = 0

/**
 * 辅助：严格相等断言
 */
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
  if (val !== null && val !== undefined) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 值为 ${val}`)
  }
}

function assertNull(val, label) {
  if (val === null || val === undefined) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 值不为 null，实际为 "${String(val).slice(0, 80)}..."`)
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

// ── 测试套件 ────────────────────────────────────────────────

console.log('🧪 test_format_correction')
console.log('')

// --- 正常路径 ---

console.log('[retry_with]')
{
  const pkg = { action: 'retry_with', tool: 'read', args: { file_path: 'test.md' }, reason: '参数错误' }
  const result = formatCorrection(pkg)
  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正]'), '以正确前缀开头')
  assertTrue(result.includes('独立纠正器依据环境证据确定了正确参数'), '包含"确定正确参数"语义')
  assertTrue(result.includes('请原样调用：read'), '包含工具名 read')
  assertTrue(result.includes('file_path'), '包含参数 key')
  assertTrue(result.includes('理由：参数错误'), '包含理由')
  assertTrue(result.endsWith('。这是一次性的参数修正——调用时不要改动任何字段。'), '以一次性修正提示结尾')
}

console.log('[ask_user]')
{
  const pkg = { action: 'ask_user', reason: '需要确认下一步方向' }
  const result = formatCorrection(pkg)
  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正]'), '以正确前缀开头')
  assertTrue(result.includes('需要用户澄清'), '包含"需要用户澄清"')
  assertTrue(result.includes('请立即向用户提问'), '包含"立即向用户提问"')
}

console.log('[abandon]')
{
  const pkg = { action: 'abandon', reason: '目标不存在于仓库中' }
  const result = formatCorrection(pkg)
  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正]'), '以正确前缀开头')
  assertTrue(result.includes('判定该目标不可达'), '包含"目标不可达"')
  assertTrue(result.includes('停止尝试，从任务清单中移除该项'), '包含"停止尝试"指令')
}

// --- 边界情况 ---

console.log('[默认原因]')
{
  // retry_with 未提供 reason → 使用"见证据"
  const pkg1 = { action: 'retry_with', tool: 'glob', args: { pattern: '*.js' } }
  assertEqual(formatCorrection(pkg1).includes('理由：见证据'), true, 'retry_with 默认原因用"见证据"')

  // ask_user 未提供 reason
  const pkg2 = { action: 'ask_user' }
  assertEqual(formatCorrection(pkg2).includes('请向用户确认下一步'), true, 'ask_user 默认原因含引导语')

  // abandon 未提供 reason
  const pkg3 = { action: 'abandon' }
  assertEqual(formatCorrection(pkg3).includes('目标不存在'), true, 'abandon 默认原因含"目标不存在"')
}

// --- 失败路径 ---

console.log('[未知 action]')
{
  assertNull(formatCorrection({ action: 'unknown_action' }), '未知 action 返回 null')
  assertNull(formatCorrection({ action: '' }), '空字符串 action 返回 null')
  assertNull(formatCorrection(null), 'null 输入返回 null')
  assertNull(formatCorrection(undefined), 'undefined 输入返回 null')
  assertNull(formatCorrection(42), '数字输入返回 null')
  assertNull(formatCorrection([]), '数组输入返回 null')
}

console.log('[retry_without_tool — fail-closed]')
{
  // retry_with 但没有 tool 字段 → 不匹配任何分支，应返回 null（fail-closed）
  assertNull(formatCorrection({ action: 'retry_with', reason: '无工具名' }), 'retry_with 缺 tool 返回 null')
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
