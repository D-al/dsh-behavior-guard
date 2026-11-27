/**
 * collectCorrectorInput — 外置模块
 *
 * 从 trail 中提取失败详情与成功证据，供 v2 纠正器使用。
 * 2026-11-27 攻防演练加固：
 *   - "绿灯不算证据"从 prompt 劝阻下沉到代码校验（只过滤纯状态字样）
 *   - 同源多次成功去重（避免 3 次相同 PASS 挤满 evidence）
 */
// 只匹配"纯状态字样"——保守过滤，避免误杀 content_a / b.md,c.md 这类真实内容
const TOOL_GUARD = new Set(['read', 'glob', 'grep', 'pwsh', 'list_agents', 'job_output'])  // S10 二道防线：工具名二次校验
const GREEN_ONLY = /^(?:pass|success|ok|全绿|成功|完成|done|true|1)[\\s.!:,，。！：]*$/i

export function collectCorrectorInput(trail) {
  const fails = trail.filter((x) => x.kind === 'call' && x.ok === false)
  const evid = trail.filter((x) => x.kind === 'call' && x.ok === true && x.fullEvidence)
  const failDetail = fails.slice(-4).map((x) =>
    `step${x.step} ${x.name} 参数=${x.args}\n  错误=${(x.result || '').slice(0, 150)}`).join('\n')

  // 绿灯不算证据：只含状态字样 → 丢弃
  const substantive = evid.filter((x) => {
    if (!TOOL_GUARD.has(x.name)) return false  // S10：不认工具名就不可信
    const r = String(x.result || '').trim()
    return r && !GREEN_ONLY.test(r)
  })
  // 同源去重：相同 tool+args 只保留最后一条
  const byKey = new Map()
  for (const x of substantive) byKey.set(x.name + '|' + String(x.args || ''), x)
  const deduped = [...byKey.values()]

  const evidence = deduped.map((x) =>
    `step${x.step} ${x.name}(${(x.args || '').slice(0, 100)}) 返回：\n${x.result}`).join('\n---\n')
  return { failDetail, evidence }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { collectCorrectorInput }
}
