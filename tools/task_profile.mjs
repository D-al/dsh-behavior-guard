/**
 * 任务级上下文（2026-11-21）：给所有守卫一个共享的"这是什么任务"信号。
 *
 * 根因：今晚 4 个守卫假阳性（todo 闹钟/深检路径/Critic 截断/交付闸门）共同点是——
 * 每个守卫只看自己管的场景发生了没，却不知道"这个任务到底需要多少守卫"。
 * 本模块把"任务类型"外置成纯函数，守卫共享它，而不是各自用代理指标猜。
 *
 * 设计原则（ADR-0012 确定性优先、零 LLM）：
 * - 只用 state 里已有的确定性信号（writeCalls / lastProduct / verifyRan / step）
 * - 不调模型、不猜语义——猜语义是 M9 分类器的事，且需独立标签，今晚未满足前提
 * - 保守：信号不足时返回"需要守卫"（fail-closed），只在明确只读时放松
 */

/**
 * @param {object} s - harness 的 session state
 * @returns {{kind, needsTodo, needsVerify, needsDeepReview, needsTreeCheck, reason}}
 */
export function taskProfile(s) {
  // state 缺失 = 信号不足 → fail-closed（要求全部守卫），绝不因缺信号而放松
  if (!s || typeof s !== 'object') {
    return { kind: 'unknown', needsTodo: true, needsVerify: true, needsDeepReview: true,
      needsTreeCheck: true, reason: 'state 缺失——fail-closed，不放松任何守卫' }
  }
  const state = s
  const writeCalls = Number(state.writeCalls || 0)
  const product = String(state.lastProduct || '')
  const hasProduct = product.length > 0

  // 只读任务：本轮没有任何写调用，也没有产物——纯查询/读取/问答
  if (writeCalls === 0 && !hasProduct) {
    return {
      kind: 'read-only',
      needsTodo: false,
      needsVerify: false,
      needsDeepReview: false,
      needsTreeCheck: false,
      reason: '本轮无写调用且无产物——纯只读任务，交付/验证/深检守卫不适用',
    }
  }

  // 有写调用或产物：按 ADR-0013 append-only 与 verify-on-stop 纪律，需要验证
  return {
    kind: hasProduct ? 'artifact' : 'mutating',
    needsTodo: true,
    needsVerify: true,
    needsDeepReview: true,
    needsTreeCheck: true,
    reason: hasProduct ? '有产物，需验收/深检' : '有写调用，需验证',
  }
}
