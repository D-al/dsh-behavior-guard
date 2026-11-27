// compaction 存档注入的集成验证：模拟"重复存档 + 未闭环纠错"是否穿透去重
// 直接验证 index.mjs 里的关键逻辑片段（源码级 + 行为级双验）
import fs from 'node:fs'
import { mineCandidates } from './reflection_miner.mjs'

let p = 0, f = 0
const t = (n, c) => { if (c) { p++; console.log('  PASS ' + n) } else { f++; console.log('  **FAIL** ' + n) } }
const src = fs.readFileSync(new URL('../index.mjs', import.meta.url), 'utf8')

console.log('=== 源码级：去重穿透 ===')
t('去重分支保留 _preserve', src.includes('_preserve = parts.filter') && src.includes('parts.push(..._preserve)'))
t('纠错内容标记可被 filter 识别', src.includes('【未闭环的自我纠错（具体值') )
t('archiveSig 不含 reflectionCandidates', (src.match(/archiveSig = JSON\.stringify\([^\n]*/g)||[]).every(l=>!l.includes('reflectionCandidates')))

console.log('=== 行为级：真实纠错句穿透过滤 ===')
const concreteFilter = (c) => c.raw && /(@|[/\\]|\.js|\.py|\.json|\.md|::|=)/.test(c.raw) &&
  !/^(嗯[，,]?)?我(需要|将|会)?(先)?(读取|读|创建|写|按照|执行)/.test(c.raw.trim()) &&
  /(恢复|改回|撤销|还原|是错的|是个错误|搞错|写错|改错|有问题|可能是个问题)/.test(c.signal)

const realCorrection = '我注意到之前的编辑把name改成了@local/...，但这可能是个问题…我应该把这个恢复成原始的dsh-hardware-monitor格式'
const realPlan = '我需要读取 D:/Brain/workspace/bench/critbank.json 然后确认内容'

const c1 = mineCandidates(realCorrection, { sid:'e22d97fd', step:481 })
const c2 = mineCandidates(realPlan, { sid:'plan', step:1 })
t('真纠错句产出候选', c1.length > 0)
t('真纠错句含具体值且通过过滤', c1.filter(concreteFilter).length > 0)
t('纯计划句不通过过滤', c2.filter(concreteFilter).length === 0)

// 模拟 parts 去重流程
const parts = []
parts.push('【重新反思提示（仅信号）】' + c1.map(x=>x.signal).join('；'))
const concrete = c1.filter(concreteFilter).slice(-2)
if (concrete.length) parts.push('【未闭环的自我纠错（具体值，压缩必留）】' + concrete.map(c=>c.raw.slice(0,160)).join('；'))
const preserve = parts.filter(x => String(x).startsWith('【未闭环的自我纠错（具体值'))
parts.length = 0
parts.push(...preserve)
parts.push('[harness 任务存档] 状态未变化（重复 3 次）')
t('去重后纠错内容仍在', parts.some(x=>x.includes('@local')))
t('去重后常规存档仍在', parts.some(x=>x.includes('状态未变化')))
t('去重后信号提示被正确清除', !parts.some(x=>x.includes('仅信号')))

console.log('\n结果 ' + p + ' PASS / ' + f + ' FAIL')
process.exit(f ? 1 : 0)
