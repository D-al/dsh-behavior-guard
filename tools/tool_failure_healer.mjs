/**
 * tool_failure_healer —— 执行层工具失败自愈（S24）
 *
 * 纯函数：输入结构化的工具错误（isError + error.code），输出给模型的修正提示。
 * 不扫结果正文（219 次误报教训），只认结构化字段。
 *
 * 与 S14 分工：S14 在 AGENTS.md 教模型"edit 前先 read、失败用最短锚点"（提示层，
 * 实测无效：落地后 edit 锚点失败反从 2 涨到 8/天）；S24 在执行层兜底——
 * 失败发生了就自动注入修正指令，不依赖模型记得协议。
 */

/** 从 dsh 的 tool/result 事件中提取结构化失败信息。
 *  @returns {{tool:string, code:string, path:string}|null} 非失败返回 null */
export function extractFailure(event, toolNameById) {
  if (!event || event.type !== 'tool/result') return null
  const data = event.data || {}
  const msg = data.message || {}
  // 只认结构化字段，绝不扫正文文本
  const isErr = msg.isError === true || !!data.error
  if (!isErr) return null
  const err = typeof data.error === 'object' && data.error !== null
    ? data.error : null
  const code = err?.code || 'UNKNOWN'
  const cid = data.toolCallId || msg.source?.callId
  const tool = toolNameById?.get(cid) || msg.source?.tool || '?'
  // 从 error.message 里抽路径（结构化字段内，不是扫大段结果正文）
  const em = String(err?.message || '')
  const pm = em.match(/(?:cannot (?:read|write|modify)|no such file)[^"]*"([^"]+)"/i)
  const path = pm ? pm[1] : ''
  return { tool, code, path }
}

/** 生成修正提示。返回 null 表示该错误不需要兜底（如用户取消、正常中断）。
 *  @param {{tool:string, code:string, path:string}} failure
 *  @param {{fileContent?:string, nearFiles?:string[]}} ctx 可选的补充上下文
 */
export function healHint(failure, ctx = {}) {
  if (!failure) return null
  const { tool, code, path } = failure
  switch (code) {
    // FS_STALE_VERSION：真实环境对"文件在读之后被改/不存在"返回此码（2026-11-22 实测），
    // 与锚点失配同类——重读后再试。
    case 'FS_STALE_VERSION':
      return '[harness 工具自愈] 上一次 edit 失败（FS_STALE_VERSION：文件在读之后已变化或不存在）。不要原样重试——先 read 目标文件获取当前版本，再用重读到的最短唯一锚点重新 edit。'
    case 'FS_EDIT_NOT_FOUND': {
      let s = '[harness 工具自愈] 上一次 edit 失败（old_string 在文件中找不到）。'
      s += '不要原样重试。按协议：重读目标行±10行，取从第一个非空白字符起的最短唯一锚点，再发一次 edit。'
      if (ctx.fileContent) {
        const clip = String(ctx.fileContent).slice(0, 800)
        s += `\n以下是该区域的最新内容，直接从中复制锚点：\n${clip}`
      }
      return s
    }
    case 'FS_NOT_FOUND': {
      let s = `[harness 工具自愈] 上一次 ${tool} 失败：路径 "${path || '（未解析）'}" 不存在。`
      s += '不要凭记忆拼路径——先用 glob 确认真实路径再操作。'
      if (ctx.nearFiles?.length) {
        s += `\n相近文件（仅供参考，需自行确认）：\n${ctx.nearFiles.slice(0, 5).map(f => '  - ' + f).join('\n')}`
      }
      return s
    }
    case 'SUBPROCESS_SPAWN_NOT_FOUND':
      return '[harness 工具自愈] 上一次 pwsh 失败：命令程序不存在。先确认命令是否可用（Get-Command），换用已安装的工具。'
    case 'SEARCH_FAILED':
      return '[harness 工具自愈] 上一次搜索失败：检查 path 是否为绝对路径、目录是否存在，必要时先 glob 摸底。'
    // 用户取消、中断、能力禁用等：不是模型犯错，不注入（避免提示风暴）
    case 'ASK_CANCELLED':
    case 'ABORTED':
    case 'JOB_CONTROLLER_UNAVAILABLE':
    case 'WEB_BLOCKED_URL':
      return null
    default:
      return null
  }
}

/** 是否属于"同一会话内重复失败"——用于限制注入次数。
 *  调用方维护计数，本函数只判定是否该注入。 */
export function shouldInject(failure, state = {}) {
  if (!healHint(failure)) return false
  const n = state.healInjectedThisTurn || 0
  const total = state.healInjectedTotal || 0
  return n < 1 && total < 4
}
