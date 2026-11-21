// test_selective_verification.mjs — S15 反向测试套件 (v1, 2026-11-21)
// 覆盖：只读跳过、写操作触发、边界/错误处理、门控逻辑正确性
// 每个断言都是真行为断言，无恒真检查（|| true / >=0 / ===true 等）

import { taskProfile, verifyGate } from './selective_verification.mjs'

let passed = 0
let failed = 0

// ── 严格断言 helpers ──────────────────────────────────────
function eq(actual, expected, label) {
  if (actual === expected) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 期望 "${expected}", 实际 "${String(actual)}"`)
  }
}

function deepEq(actual, expected, label) {
  const aStr = JSON.stringify(actual)
  const eStr = JSON.stringify(expected)
  if (aStr === eStr) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 期望 ${eStr}, 实际 ${aStr}`)
  }
}

function typeOf(val, typeName, label) {
  if (typeof val === typeName) {
    passed++
    console.log(`  ✅ ${label}`)
  } else {
    failed++
    console.error(`  ❌ ${label}: 期望 typeof ${typeName}, 实际 ${typeof val}`)
  }
}

// ── 测试套件 ───────────────────────────────────────────────

console.log('🧪 test_selective_verification')
console.log('')

// ═══ 第一部分：taskProfile 基础路径 ══════════════════════

console.log('[taskProfile] 只读任务 → kind=read-only')
{
  const result = taskProfile({ writeCalls: 0, lastProduct: '' })
  eq(result.kind, 'read-only', 'kind 为 read-only')
  eq(result.needsTodo, false, 'needsTodo=false')
  eq(result.needsVerify, false, 'needsVerify=false')
  eq(result.needsDeepReview, false, 'needsDeepReview=false')
  eq(result.needsTreeCheck, false, 'needsTreeCheck=false')
  deepEq(result.reason.includes('read-only'), true, 'reason 包含 read-only 语义')
}

console.log('[taskProfile] 有写调用无产物 → kind=mutating')
{
  const result = taskProfile({ writeCalls: 1, lastProduct: '' })
  eq(result.kind, 'mutating', 'kind 为 mutating')
  eq(result.needsDeepReview, true, 'needsDeepReview=true for mutating')
  eq(result.needsTreeCheck, true, 'needsTreeCheck=true for mutating')
}

console.log('[taskProfile] 有产物 → kind=artifact')
{
  const result = taskProfile({ writeCalls: 2, lastProduct: 'tools/new_file.mjs' })
  eq(result.kind, 'artifact', 'kind 为 artifact')
  eq(result.needsDeepReview, true, 'needsDeepReview=true for artifact')
  eq(result.needsVerify, true, 'needsVerify=true for artifact')
}

console.log('[taskProfile] 空 state → kind=unknown')
{
  eq(taskProfile(null).kind, 'unknown', 'null → unknown')
  eq(taskProfile(undefined).kind, 'unknown', 'undefined → unknown')
  eq(taskProfile(42).kind, 'unknown', '数字 → unknown')
  eq(taskProfile([]).kind, 'unknown', '数组 → unknown')
  eq(taskProfile('').kind, 'unknown', '空字符串 → unknown')
}

console.log('[taskProfile] writeCalls=0 且 lastProduct 非空 → kind=artifact')
{
  // 边界：没调写工具但 lastProduct 被外部设为非空（如前次残留）
  const result = taskProfile({ writeCalls: 0, lastProduct: 'some_artifact.md' })
  eq(result.kind, 'artifact', 'lastProduct 非空 → artifact（即使 writeCalls=0）')
  eq(result.needsVerify, true, 'artifact 需要验证')
}

// ═══ 第二部分：verifyGate 门控逻辑 ══════════════════════

console.log('[verifyGate] 只读任务 → skip=true, level=none')
{
  const gate = verifyGate({ writeCalls: 0, lastProduct: '' })
  eq(gate.skip, true, 'skip=true 跳过只读')
  eq(gate.level, 'none', 'level=none')
  eq(gate.gate, 'skip-read-only', 'gate=skip-read-only')
  eq(gate.profile.kind, 'read-only', 'profile.kind=read-only')
  eq(gate.profile.needsDeepReview, false, 'profile.needsDeepReview=false')
}

console.log('[verifyGate] 写操作 → skip=false, level=deep')
{
  const gate = verifyGate({ writeCalls: 1, lastProduct: '' })
  eq(gate.skip, false, 'skip=false 不跳过写操作')
  eq(gate.level, 'deep', 'level=deep')
  eq(gate.gate, 'require-verify', 'gate=require-verify')
  eq(gate.profile.kind, 'mutating', 'profile.kind=mutating')
}

console.log('[verifyGate] 有产物 → skip=false, level=deep')
{
  const gate = verifyGate({ writeCalls: 3, lastProduct: 'docs/README.md' })
  eq(gate.skip, false, 'skip=false 不跳过硬产物验证')
  eq(gate.level, 'deep', 'level=deep for artifact')
  eq(gate.gate, 'require-verify', 'gate=require-verify')
  eq(gate.profile.kind, 'artifact', 'profile.kind=artifact')
}

console.log('[verifyGate] 未知状态 → fail-closed, skip=false, level=deep')
{
  const gate1 = verifyGate(null)
  eq(gate1.skip, false, 'null → 不跳过 (fail-closed)')
  eq(gate1.level, 'deep', 'null → deep')
  eq(gate1.gate, 'hard-fail-close', 'gate=hard-fail-close')

  const gate2 = verifyGate(undefined)
  eq(gate2.skip, false, 'undefined → 不跳过')
  eq(gate2.level, 'deep', 'undefined → deep')

  const gate3 = verifyGate(42)
  eq(gate3.skip, false, '数字 → 不跳过')
  eq(gate3.level, 'deep', '数字 → deep')
}

// ═══ 第三部分：失败对照（证明门控真的会跳）═════════════

console.log('[gate contrast] 只读 vs 写操作 — 门控行为差异')
{
  // 这是核心反向测试：同一 state 结构，仅改 writeCalls，验证 gate 结果不同
  const readState = { writeCalls: 0, lastProduct: '' }
  const writeState = { writeCalls: 5, lastProduct: '' }

  const readGate = verifyGate(readState)
  const writeGate = verifyGate(writeState)

  // 关键断言：两个门的 skip 值必须相反
  eq(readGate.skip, true, '[contrast] 只读任务 skip=true')
  eq(writeGate.skip, false, '[contrast] 写操作 skip=false')

  // level 也必须不同
  eq(readGate.level, 'none', '[contrast] 只读 level=none')
  eq(writeGate.level, 'deep', '[contrast] 写操作 level=deep')

  // gate 字符串必须不同（证明走了不同分支）
  eq(readGate.gate, 'skip-read-only', '[contrast] 只读 gate=skip-read-only')
  eq(writeGate.gate, 'require-verify', '[contrast] 写操作 gate=require-verify')

  // profile.kind 也必须不同
  eq(readGate.profile.kind, 'read-only', '[contrast] 只读 profile.kind=read-only')
  eq(writeGate.profile.kind, 'mutating', '[contrast] 写操作 profile.kind=mutating')
}

// ═══ 第四部分：边界场景 ═══════════════════════════════

console.log('[edge] writeCalls 类型转换')
{
  const result1 = taskProfile({ writeCalls: '3', lastProduct: '' })
  eq(result1.kind, 'mutating', 'writeCalls="3"（字符串）→ mutating (Number() 转换正常)')

  const result2 = taskProfile({ writeCalls: null, lastProduct: '' })
  eq(result2.kind, 'read-only', 'writeCalls=null → read-only (Number(null)=0)')

  const result3 = taskProfile({ writeCalls: NaN, lastProduct: '' })
  eq(result3.kind, 'read-only', 'writeCalls=NaN → read-only (Number(NaN)=0)')
}

console.log('[edge] lastProduct 空值处理')
{
  // undefined
  const r1 = taskProfile({})
  eq(r1.kind, 'read-only', '{} → read-only (lastProduct undefined → "")')

  // 零长度字符串
  const r2 = taskProfile({ writeCalls: 0, lastProduct: '' })
  eq(r2.kind, 'read-only', 'lastProduct="" → read-only')

  // 仅空格（String.trim 后非空？不，这里是 String() 直接转）
  const r3 = taskProfile({ writeCalls: 0, lastProduct: '   ' })
  eq(r3.kind, 'artifact', "lastProduct='   ' → artifact (空格串长度为>0)")
}

// ═══ 第五部分：门控不可绕过性 ══════════════════════════

console.log('[security] 无法通过伪造字段绕过门控')
{
  // 尝试用不存在的字段欺骗：如 set skip=true 在 state 里
  const fakeState = { writeCalls: 0, lastProduct: '', skip: true }
  const gate = verifyGate(fakeState)
  eq(gate.skip, true, 'fake skip=true 在 state 中不影响 gate（由 writeCalls 决定）')
  eq(gate.gate, 'skip-read-only', 'gate 仍然基于真实信号')

  // 有写调用但伪装产物为空
  const realWrite = { writeCalls: 10, lastProduct: '' }
  const wGate = verifyGate(realWrite)
  eq(wGate.skip, false, 'writeCalls=10 → 不能跳过')
  eq(wGate.level, 'deep', 'writeCalls=10 → deep review')
}

// ── 汇总 ────────────────────────────────────────────────

console.log('')
const total = passed + failed
if (failed === 0) {
  console.log(`PASS ${passed}/${total} 测试通过`)
  console.log('✅ S15 selective verification gate: all assertions passed')
} else {
  console.error(`FAIL ${passed}/${total} 测试通过, ${failed} 失败`)
  process.exitCode = 1
}
