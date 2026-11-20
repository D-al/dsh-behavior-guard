// format_correction.mjs — v1 (2026-11-21)
// 为什么外置：formatCorrection 是独立于守卫状态的纯格式化逻辑，
//   输入 pkg(action/args/tool/reason)，输出修正消息字符串（或 null）。
//   零外部依赖、零副作用，符合"确定性/零 LLM/fail-closed"原则。
// 设计原则：只读操作、同步返回、不修改任何外部状态。

/**
 * 将纠正器包格式化为人类可读的修正指令字符串。
 * @param {object} pkg - 纠正器包，包含 action 字段
 * @param {'retry_with'|'ask_user'|'abandon'} pkg.action - 行动类型
 * @param {string} [pkg.tool] - 工具名（仅 retry_with 时使用）
 * @param {*} [pkg.args] - 参数对象（仅 retry_with 时使用）
 * @param {string} pkg.reason - 理由说明
 * @returns {string|null} 格式化后的修正消息；action 未知时返回 null
 */
export function formatCorrection(pkg) {
  if (!pkg || typeof pkg !== 'object') return null

  const action = pkg.action
  const reason = pkg.reason || '见证据'

  if (action === 'retry_with' && pkg.tool) {
    const argsStr = JSON.stringify(pkg.args ?? {}, null, 0)
    return `[harness 系统修正] 独立纠正器依据环境证据确定了正确参数（理由：${reason}）。请原样调用：${pkg.tool}，参数：${argsStr}。这是一次性的参数修正——调用时不要改动任何字段。`
  }

  if (action === 'ask_user') {
    return `[harness 系统修正] 独立纠正器认为环境证据不足以继续，需要用户澄清：${pkg.reason || '请向用户确认下一步。'}请立即向用户提问。`
  }

  if (action === 'abandon') {
    return `[harness 系统修正] 独立纠正器依据环境证据判定该目标不可达：${pkg.reason || '目标不存在'}。停止尝试，从任务清单中移除该项并向用户说明。`
  }

  // action 未识别 → fail-closed，返回 null 让上游决定
  return null
}
