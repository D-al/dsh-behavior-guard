/**
 * 反模式匹配检测器（M3 重定位的独立可落地部件，2026-11-22）
 *
 * 论文依据：Apollo Research arXiv:2505.02709 通过消融实验证明
 * "state complexity cannot explain goal drift"，漂移主因是长上下文的 pattern-matching。
 * 因此本检测器不建"更大的意图槽"，只检测**行为序列是否固化成重复模式**。
 *
 * 设计纪律：
 * - 零 LLM、零网络——纯数组统计
 * - 只写 trace 不 steer（观察线，与 S6 分类器同档）
 * - 与 D1 重复探测不重叠：D1 要求"同工具失败≥2次"；本检测器不要求失败，
 *   只要求"工具分布固化 + 距上次目标重述够远"（无进展的形态信号）
 */

/**
 * @param {string[]} window 最近 N 次工具名
 * @param {number} stepsSinceGoal 距上次目标重述（用户指令）的步数
 * @param {object} opts {minWindow, repetitionThreshold, minStepsSinceGoal}
 */
export function detectPatternLock(window, stepsSinceGoal = 999, opts = {}) {
  const minWindow = opts.minWindow ?? 12
  const repThreshold = opts.repetitionThreshold ?? 0.6
  const minSteps = opts.minStepsSinceGoal ?? 6
  if (!Array.isArray(window) || window.length < minWindow) {
    return { hit: false, reason: 'too-short', n: window?.length || 0 }
  }
  const recent = window.slice(-minWindow)
  const counts = new Map()
  for (const name of recent) counts.set(name, (counts.get(name) || 0) + 1)
  let dominant = '', top = 0
  for (const [name, n] of counts) if (n > top) { dominant = name; top = n }
  const repetition = top / minWindow
  // 时机维度（StepShield 教训：高召回但时机随机=没用）——
  // 只有"目标重述后已过足够步数"的锁定才算可疑；刚重述完的重复可能是正常执行。
  const hit = repetition >= repThreshold && stepsSinceGoal >= minSteps
  return {
    hit, reason: hit ? 'pattern-lock' : 'ok',
    n: window.length, dominant, repetition: Number(repetition.toFixed(3)),
    stepsSinceGoal,
  }
}
