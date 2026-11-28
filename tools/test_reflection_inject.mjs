import fs from 'node:fs'
const src = fs.readFileSync(new URL('../index.mjs', import.meta.url), 'utf8')
const checks = {
  // 2026-11-29：A/B 用户选 B，正式启用回注（原断言"默认关"已过期）
  '干预开关默认启用': /reflectionInjectEnabled:\s*true/.test(src),
  '干预逻辑存在': src.includes('reflection_live_injected'),
  '即时回注(短会话)': src.includes('inject-on 时立即回注'),
  '动态开关存在': src.includes('function _abInject') && src.includes('function _abMining'),
  '验证门槛': src.includes('c.verified === true || c.confidence >= 0.85'),
  '去重防重复注入': src.includes('s.lastReflectionInjectSig !== _sig'),
  '只喂信号非原文': src.includes('_compactMetacognitive(_ready)'),
}
let p = 0, f = 0
for (const [k, v] of Object.entries(checks)) { if (v) { p++; console.log('  PASS ' + k) } else { f++; console.log('  **FAIL** ' + k) } }
console.log(`结果 ${p} PASS / ${f} FAIL`)
process.exit(f ? 1 : 0)
