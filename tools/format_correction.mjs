/**
 * formatCorrection — 规范副本（2026-11-21；2026-11-27 攻防加固 S4）
 * 纯函数：无副作用、零外部依赖；fail-closed。
 * S4 加固：工具白名单（只读）、危险参数拒绝、reason 提示注入中和。
 */
const SAFE_TOOLS = new Set(['read', 'glob', 'grep', 'list_agents', 'job_output'])
const DANGEROUS_ARG = /\b(rm\s+-rf|del\s+\/[sS]|format\s+[a-zA-Z]:|DROP\s+TABLE|shutdown|reboot|curl\s+.*\||wget\s+.*\|)\b/i
const INJECT_RE = /(忽略.{0,8}(之前|上述|所有).{0,4}(指令|规则)|ignore (all )?(previous|prior) instructions|你现在是|you are now a (different|new))/i

function defaultReasonFor(action) {
  if (action == 'ask_user') return '请向用户确认下一步。'
  if (action == 'abandon') return '目标不存在'
  return '见证据'
}

function sanitizeReason(r) {
  let s = String(r || '见证据').replace(/[\r\n]+/g, ' ')
  if (s.length > 200) s = s.slice(0, 200) + '…'
  if (INJECT_RE.test(s)) s = '[已过滤疑似指令内容] ' + s.replace(INJECT_RE, '')
  return s
}

export function formatCorrection(pkg) {
  if (!pkg || typeof pkg !== 'object') return null

  const action = pkg.action
  const reason = sanitizeReason(pkg.reason || defaultReasonFor(action))

  if (action === 'retry_with' && pkg.tool) {
    // S4：工具白名单——纠正器不得建议任意工具（原漏洞：danger_shell 原样注入）
    if (!SAFE_TOOLS.has(pkg.tool)) return null
    const argsStr = JSON.stringify(pkg.args ?? {}, null, 0)
    if (DANGEROUS_ARG.test(argsStr)) return null
    return `[harness 系统修正] 独立纠正器依据环境证据确定了正确参数（理由：${reason}）。请原样调用：${pkg.tool}，参数：${argsStr}。这是一次性的参数修正——调用时不要改动任何字段。`
  }

  if (action === 'ask_user') {
    return `[harness 系统修正] 独立纠正器认为环境证据不足以继续，需要用户澄清：${reason}。请立即向用户提问。`
  }

  if (action === 'abandon') {
    return `[harness 系统修正] 独立纠正器依据环境证据判定该目标不可达：${reason}。停止尝试，从任务清单中移除该项并向用户说明。`
  }

  // action 未识别 → fail-closed
  return null
}
