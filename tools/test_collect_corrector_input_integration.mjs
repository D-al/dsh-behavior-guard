/**
 * 集成测试：验证 index.mjs 中的 collectCorrectorInput 实际调用了外置模块
 * 
 * 策略：直接检查 index.mjs 源码是否 import 了 tools/collect_corrector_input.mjs，
 *       并验证内联函数体是委托调用而非重复实现。
 */

import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

const __dirname = join(process.cwd(), 'tools')
const indexPath = join(__dirname, '..', 'index.mjs')
const indexContent = readFileSync(indexPath, 'utf-8')

let pass = 0, fail = 0
const check = (label, ok, detail = '') => {
  if (ok) { pass++; console.log(`PASS  ${label}`) } else { fail++; console.error(`FAIL  ${label} ${detail}`) }
}

// ── 测试 1：确认有 import 语句 ──
check('1. index.mjs import 了外置模块',
  /import\s+{.*collectCorrectorInput.*}\s+from\s+['"]\.\/tools\/collect_corrector_input\.mjs/.test(indexContent))

// ── 测试 2：内联函数体是委托调用（不是完整实现） ──
const inlineMatch = indexContent.match(/function\s+collectCorrectorInput\s*\([^)]*\)\s*\{[^}]*\}/)
if (inlineMatch) {
  const fnBody = inlineMatch[0]
  // 不应包含 .filter(.kind === 'call') 这种完整实现代码
  const hasCompleteImpl = /\.filter\s*\(\s*\(x\)\s*=>\s*x\.kind\s*===\s*'call'/.test(fnBody)
  check('2. 内联函数是委托调用（非完整实现）', !hasCompleteImpl,
    hasCompleteImpl ? '内联函数仍包含完整 filter 实现' : `函数体: ${fnBody.slice(0, 80)}...`)
  
  // 应包含 _collectCorrectorInput 别名调用或 .trail 访问
  const usesTrail = /\.trail\b/.test(fnBody) || /_collectCorrectorInput/.test(fnBody)
  check('3. 内联函数使用 trail 参数或别名导入', usesTrail)
} else {
  check('2&3. 存在 collectCorrectorInput 函数定义', false, '未找到函数定义')
}

// ── 测试 4：验证 runCorrector 仍然能正确调用（通过检查源码中的调用点） ──
// 子任务反向检验修正(2026-11-21)：原测试4是纯存在性断言(if match → check true)，
// 等于恒真假绿。改为真检查：runCorrector 函数体内必须真的调用 collectCorrectorInput，
// 且调用点带 .trail 参数——这才是"接入生效"的证据，而非"函数存在"。
const runCorrectorMatch = indexContent.match(/async function\s+runCorrector\s*\([^)]*\)\s*\{[\s\S]*?\n  \}/)
if (runCorrectorMatch) {
  const body = runCorrectorMatch[0]
  const callsFn = /collectCorrectorInput\s*\(\s*s\s*\)/.test(body)
  check('4a. runCorrector 真调用 collectCorrectorInput(s)', callsFn,
    callsFn ? '' : '函数体内无调用——存在性不等于接入')
} else {
  check('4a&4b. runCorrector 函数存在', false, '未找到 runCorrector 定义')
}

// 4b: 转发函数体必须取 s.trail 传给外置版（外置函数签名只吃 trail）
check('4b. 转发体取 s.trail 传外置函数',
  /function\s+collectCorrectorInput\s*\(s\)\s*\{\s*return\s+_collectCorrectorInput\s*\(\s*s\.trail\s*\)/.test(indexContent))

// ── 负对照：证明上面的文本判据不是恒真（防止未来被空文件骗过）──
check('5. 负对照：空源码不应匹配 import 判据',
  !/import\s+{.*collectCorrectorInput.*}/.test('// empty file'))

// ── 输出结果 ──
console.log(`\n${pass}/${pass + fail} pass`)
process.exit(fail ? 1 : 0)
