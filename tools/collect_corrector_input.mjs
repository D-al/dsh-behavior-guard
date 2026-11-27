/**
 * collectCorrectorInput — 外置模块
 *
 * 从 trail 中提取失败详情与成功证据，供 v2 纠正器使用。
 * 2026-11-27 攻防演练加固：
 *   - "绿灯不算证据"从 prompt 劝阻下沉到代码校验（原来只看工具名+OK 状态）
 *   - 同源多次成功去重（原来全部塞进 evidence）
 */
const GREEN_ONLY = /^(?:(?:pass|success|ok|全绿|成功|完成)(?:\s|[.!:,，。！：]|$))+$/i

export function collectCorrectorInput(trail) {
  const fails = trail.filter((x) => x.kind === 'call' && x.ok === false)
  const evid = trail.filter((x) => x.kind === 'call' && x.ok === true && x.fullEvidence)
  const failDetail = fails.slice(-4).map((x) =>
    `step${x.step} ${x.name} 参数=${x.args}\n  错误=${(x.result || '').slice(0, 150)}`).join('\n')

  // 绿灯不算证据：只含状态字样、没有可照抄实际内容 → 丢弃
  const substantive = evid.filter((x) => {
    const r = String(x.result || '').trim()
    if (!r) return false
    if (GREEN_ONLY.test(r)) return false
    // 至少要有路径/引号/行号/等号之一，才算"可照抄的事实"
    return /[\/"'=:#]|[\u4e00-\u9fa5]{2,}/.test(r)
  })
  // 同源去重：相同 tool+args 只保留最后一条（避免 3 次 PASS 挤满 evidence）
  const byKey = new Map()
  for (const x of substantive) byKey.set(x.name + '|' + String(x.args || ''), x)
  const deduped = [...byKey.values()]

  const evidence = deduped.map((x) =>
    `step${x.step} ${x.name}(${(x.args || '').slice(0, 100)}) 返回：\n${x.result}`).join('\n---\n')
  return { failDetail, evidence }
}

// 兼容旧版 require 风格调用
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { collectCorrectorInput }
}
