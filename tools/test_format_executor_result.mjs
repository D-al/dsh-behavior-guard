// test_format_executor_result.mjs — v1 (2026-11-21)
// 单测覆盖失败/list/read三类路径 + 边界/空值/恒真修复
// 每个断言都是真行为断言，无恒真检查。
// 用法: node tools/test_format_executor_result.mjs

import { formatExecutorResult } from './format_executor_result.mjs'

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

function assertFalse(condition, label) {
  if (!condition) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 条件为真（期望假）`)
  }
}

// ── 测试套件 ────────────────────────────────────────────────

console.log('🧪 test_format_executor_result')
console.log('')

// ==================== 正常路径 ====================

// --- [路径 A] exec.ok === true, exec.kind === 'list' ---
console.log('[路径A] list 执行结果')
{
  const pkg = { args: { pattern: '*.mjs' }, tool: 'glob', reason: '列举工具目录' }
  const exec = { ok: true, kind: 'list', target: '/some/path', content: 'a.mjs\nb.mjs\nc.mjs' }
  const result = formatExecutorResult(pkg, exec)

  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正+代执行]'), '以正确前缀开头')
  assertTrue(result.includes('确定了正确目标'), '包含"确定正确目标"语义')
  assertTrue(result.includes('列举工具目录'), '包含自定义理由')
  assertTrue(result.includes('目录：/some/path'), '包含目标路径')
  assertTrue(result.includes('内容：'), '包含内容标记')
  assertTrue(result.includes('无需重新调用工具'), '包含"无需重新调用"指令')
  assertTrue(result.endsWith('也不要改动正确参数。'), '以不改动参数结尾')
}

// --- [路径 B] exec.ok === true, exec.kind === 'read', 未截断 ---
console.log('[路径B] read 执行结果（未截断）')
{
  const pkg = { args: { file_path: 'test.md' }, tool: 'read', reason: '读取配置文件' }
  const exec = { ok: true, kind: 'read', content: '文件内容 ok' }
  const result = formatExecutorResult(pkg, exec)

  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正+代执行]'), '以正确前缀开头')
  assertTrue(result.includes('确定了正确参数'), '包含"确定正确参数"语义')
  assertTrue(result.includes('理由：读取配置文件'), '包含自定义理由')
  assertTrue(result.includes('参数：{"file_path":"test.md"}'), '包含序列化参数')
  assertTrue(result.includes('结果：'), '包含结果标记（无截断提示）')
  assertTrue(result.includes('该文件内容已在上下文中'), '包含"已在上下文中"提示')
  assertTrue(result.includes('后续引用该路径时使用 {"file_path":"test.md"} 中的短路径形式'), '包含短路径引用提示')
  assertFalse(result.includes('已截断'), '未截断时不应含"已截断"标记')
}

// --- [路径 C] exec.ok === true, exec.kind === 'read', 已截断 ---
console.log('[路径C] read 执行结果（已截断）')
{
  const pkg = { args: { file_path: 'large.txt' }, tool: 'read' }
  const exec = { ok: true, kind: 'read', truncated: true, content: '长文本...' }
  const result = formatExecutorResult(pkg, exec)

  assertNotNull(result, '返回值非 null')
  assertTrue(result.includes('（已截断）'), '已截断时应含截断标记')
  assertTrue(result.includes('参数：{"file_path":"large.txt"}'), '包含序列化参数')
}

// ==================== 失败路径 ====================

// --- [路径 D] exec.ok === false, error 不包含 "不存在" ---
console.log('[路径D] 执行失败 — 一般错误')
{
  const pkg = { args: {}, tool: 'read', reason: '权限不足' }
  const exec = { ok: false, error: 'EACCES: permission denied' }
  const result = formatExecutorResult(pkg, exec)

  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正]'), '失败路径前缀不含"+代执行"')
  assertFalse(result.includes('+代执行'), '失败路径不显示"+代执行"后缀')
  assertTrue(result.includes('read 调用方式问题'), '工具名拼接为问题标签')
  assertTrue(result.includes('理由：权限不足'), '包含自定义理由')
  assertTrue(result.includes('不要原样重试上一次调用'), '包含"不要原样重试"指令')
  assertTrue(result.includes('glob 搜工作区 / es.exe 全盘搜索'), '包含替代方法建议')
}

// --- [路径 E] exec.ok === false, error 包含 "不存在" ---
console.log('[路径E] 执行失败 — 目标不存在')
{
  const pkg = { args: { pattern: '*.xyz' }, tool: 'glob', reason: '查找文件' }
  const exec = { ok: false, error: '目标不存在: no matching files' }
  const result = formatExecutorResult(pkg, exec)

  assertNotNull(result, '返回值非 null')
  assertTrue(result.startsWith('[harness 系统修正]'), '失败路径前缀不含"+代执行"')
  assertTrue(result.includes('目标定位错误'), '应判定为目标定位错误而非工具问题')
  assertFalse(result.includes('调用方式问题'), '不应出现"调用方式问题"')
  assertTrue(result.includes('不要原样重试上一次调用'), '包含"不要原样重试"指令')
}

// ==================== 边界情况 ====================

// --- [边界 F] 默认原因 ("见证据") ---
console.log('[边界F] 默认原因用"见证据"')
{
  // list 无 reason → 使用"见证据"（list 路径格式：（${reason}），无"理由："前缀）
  const r1 = formatExecutorResult({ args: {} }, { ok: true, kind: 'list', target: 'x', content: 'y' })
  assertEqual(r1.includes('（见证据）'), true, 'list 无 reason → （见证据）')

  // read 无 reason → 使用"理由：见证据"
  const r2 = formatExecutorResult({ args: {} }, { ok: true, kind: 'read', content: 'z' })
  assertEqual(r2.includes('理由：见证据'), true, 'read 无 reason → "理由：见证据"')

  // 失败无 reason → 使用"理由：见证据"
  const r3 = formatExecutorResult({ args: {}, tool: 'read' }, { ok: false, error: 'err' })
  assertEqual(r3.includes('理由：见证据'), true, '失败无 reason → "理由：见证据"')
}

// --- [边界 G] args 为 undefined/null/空对象 ---
console.log('[边界G] args 为 undefined/null/空对象')
{
  const baseExec = { ok: true, kind: 'read', content: 'ok' }
  const r1 = formatExecutorResult({}, baseExec)
  assertTrue(r1.includes('{}'), 'args 未提供时序列化为 "{}"')

  const r2 = formatExecutorResult({ args: undefined }, baseExec)
  assertTrue(r2.includes('{}'), 'args=undefined 时序列化为 "{}"')

  // null ?? {} → {}，所以 JSON.stringify(null ?? {}) = '{}'
  const r3 = formatExecutorResult({ args: null }, baseExec)
  assertTrue(r3.includes('{}'), 'args=null 时 ?? {} 回退为空对象')
}

// --- [边界 H] error 是数字类型（String() 转换）---
console.log('[边界H] exec.error 非字符串类型')
{
  const pkg = { args: {}, tool: 'read' }
  const result = formatExecutorResult(pkg, { ok: false, error: 404 })
  assertNotNull(result, 'error 为非字符串仍返回有效结果')
  assertTrue(result.includes('read 调用方式问题'), '应正常拼接工具名')
}

// --- [边界 I] 嵌套对象参数序列化 ---
console.log('[边界I] 复杂参数对象序列化')
{
  const pkg = { args: { file_path: 'a/b.md', offset: 1, limit: 50 }, tool: 'read', reason: '分页读取' }
  const exec = { ok: true, kind: 'read', content: '内容' }
  const result = formatExecutorResult(pkg, exec)
  assertTrue(result.includes('file_path'), '包含参数 key')
  assertTrue(result.includes('a/b.md'), '包含参数值')
  assertTrue(result.includes('offset'), '包含多字段参数')
}

// ==================== 异常输入 ====================

// --- [异常 J] pkg 无效 ---
console.log('[异常J] pkg 参数异常')
{
  assertNull(formatExecutorResult(null, { ok: true }), 'pkg=null → null')
  assertNull(formatExecutorResult(undefined, { ok: true }), 'pkg=undefined → null')
  assertNull(formatExecutorResult(42, { ok: true }), 'pkg=number → null')
  assertNull(formatExecutorResult('', { ok: true }), 'pkg=string → null')
  assertNull(formatExecutorResult([], { ok: true }), 'pkg=array → null (Array.isArray守卫)')
}

// --- [异常 K] exec 无效 ---
console.log('[异常K] exec 参数异常')
{
  assertNull(formatExecutorResult({}, null), 'exec=null → null')
  assertNull(formatExecutorResult({}, undefined), 'exec=undefined → null')
  assertNull(formatExecutorResult({}, 42), 'exec=number → null')
  assertNull(formatExecutorResult({}, ''), 'exec=string → null')
  assertNull(formatExecutorResult({}, []), 'exec=array → null (Array.isArray守卫)')
}

// --- [异常 L] pkg/exec 都是空对象 ---
console.log('[异常L] 空对象组合')
{
  const r = formatExecutorResult({}, {})
  // {} 无 ok 属性 → falsy → 进入失败路径
  assertNotNull(r, '两个空对象不抛异常，返回消息字符串')
  assertTrue(r.startsWith('[harness 系统修正]'), '空 exec.ok → 失败路径')
  assertFalse(r.includes('+代执行'), '失败路径不带"+代执行"')
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
