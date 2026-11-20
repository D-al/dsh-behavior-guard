/**
 * A1_7 评审机制可观测性单测
 * 验证：rubric_version / dimensions_checked / verdict 三个字段真的会进 trace，
 * 而不只是"代码里写了"（这正是 A1_7 要防的假绿）。
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = readFileSync(path.join(root, 'index.mjs'), 'utf8')
let pass = 0, fail = 0
const check = (label, ok) => { if (ok) { pass++; console.log(`PASS  ${label}`) } else { fail++; console.log(`FAIL  ${label}`) } }

const count = (re) => (src.match(re) || []).length

// 1. callLLM 的 llm trace 必须透传 ctx 的评审元数据（否则 ctx 塞了也进不了 trace）
check('callLLM trace 透传 review_kind/rubric_version/dimensions_checked',
  /ctx\.review_kind\s*\?\s*\{\s*review_kind:/.test(src) &&
  /rubric_version:\s*ctx\.rubric_version/.test(src) &&
  /dimensions_checked:\s*ctx\.dimensions_checked/.test(src))

// 2. 三处评审 verdict 专属 trace（critic/audit/planner）
const verdictTraces = count(/kind:\s*'review_verdict'/g)
check(`review_verdict trace 出现 ${verdictTraces} 次（期望 3: critic/audit/planner）`, verdictTraces === 3)
check('critic verdict trace 带 verdict 字段', /review_kind:\s*'critic'[\s\S]{0,200}verdict:/.test(src))
check('audit verdict trace 带 verdict 字段', /review_kind:\s*'audit'[\s\S]{0,200}verdict:/.test(src))
check('planner verdict trace 带 verdict 字段', /review_kind:\s*'planner'[\s\S]{0,200}verdict:/.test(src))

// 3. 每个 verdict trace 都必须带 rubric_version 和 dimensions_checked（不能只记"调用过"）
const blocks = src.match(/trace\(\{[^}]*kind:\s*'review_verdict'[^}]*\}\)/g) || []
check(`review_verdict 块数 ${blocks.length} 且每块带 rubric_version`,
  blocks.length === 3 && blocks.every((b) => b.includes('rubric_version')))
check('每个 review_verdict 块带 dimensions_checked',
  blocks.length === 3 && blocks.every((b) => b.includes('dimensions_checked')))

// 4. 三个角色调用点把 rubric 元数据塞进 callLLM ctx
check('critic 调用点传 review_kind/dimensions_checked',
  /tag:\s*'critic'[\s\S]{0,300}review_kind:\s*'critic'[\s\S]{0,200}dimensions_checked/.test(src))
check('audit 调用点传 review_kind/dimensions_checked',
  /tag:\s*'audit'[\s\S]{0,300}review_kind:\s*'audit'[\s\S]{0,200}dimensions_checked/.test(src))
check('planner 调用点传 review_kind/dimensions_checked',
  /tag:\s*'planner'[\s\S]{0,300}review_kind:\s*'planner'[\s\S]{0,200}dimensions_checked/.test(src))

console.log(`\n${pass} pass, ${fail} fail`)
process.exit(fail ? 1 : 0)
