/**
 * collectCorrectorInput — 外置模块
 * 
 * 从 trail 中提取失败详情与成功证据，供 v2 纠正器使用。
 * 依赖：无外部依赖，纯函数
 */

export function collectCorrectorInput(trail) {
  const fails = trail.filter((x) => x.kind === 'call' && x.ok === false)
  const evid = trail.filter((x) => x.kind === 'call' && x.ok === true && x.fullEvidence)
  const failDetail = fails.slice(-4).map((x) =>
    `step${x.step} ${x.name} 参数=${x.args}\n  错误=${(x.result || '').slice(0, 150)}`).join('\n')
  const evidence = evid.map((x) =>
    `step${x.step} ${x.name}(${(x.args || '').slice(0, 100)}) 返回：\n${x.result}`).join('\n---\n')
  return { failDetail, evidence }
}

// 兼容旧版 require 风格调用
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { collectCorrectorInput }
}
