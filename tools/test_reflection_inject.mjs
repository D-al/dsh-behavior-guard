import fs from 'node:fs'
const src = fs.readFileSync(new URL('../index.mjs', import.meta.url), 'utf8')
const checks = {
  '干预开关默认关': /reflectionInjectEnabled:\s*false/.test(src),
  '干预逻辑存在': src.includes('reflection_live_injected'),
  '验证门槛': src.includes('c.verified === true || c.confidence >= 0.85'),
  '去重防重复注入': src.includes('s.lastReflectionInjectSig !== _sig'),
  '只喂信号非原文': src.includes('_compactMetacognitive(_ready)'),
}
let p = 0, f = 0
for (const [k, v] of Object.entries(checks)) { if (v) { p++; console.log('  PASS ' + k) } else { f++; console.log('  **FAIL** ' + k) } }
console.log(`结果 ${p} PASS / ${f} FAIL`)
process.exit(f ? 1 : 0)
