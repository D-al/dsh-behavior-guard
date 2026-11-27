/**
 * reflection-miner.mjs — 自发反思捕获与分流（2026-11-27）
 *
 * 设计依据（论文）：
 * - SELFDOUBT (arXiv:2604.06389): HVR 犹豫-验证比；无犹豫标记轨迹正确率 96%
 * - 2603.15500: 信号价值在"不确定性外化的信息量"，不在关键词本身
 * - 2605.12978: 原始轨迹是一等证据，整合必须显式 gate（倒 U 型）
 * - 2310.01798: 无外部反馈的反思会把对的改错 → 必须外置验证
 * - ReasoningBank (2509.25140): title/description/content 三元组，检索 Top-1
 *
 * 纯函数、零外部依赖、fail-closed。规范副本在此，index.mjs 只 import。
 */

// 感知信号（抄自 parcadei/continuous-claude-v3 的 PERCEPTION_SIGNALS + 中文扩展）
const HESITATION_RE = [
  /\bactually\b/i, /\brealized?\b/i, /\bthe issue\b/i, /\bturns out\b/i,
  /\bI was wrong\b/i, /\bnow I see\b/i, /\bmisunderstood\b/i,
  /等等|等一下|慢着|不对|我怀疑|不确定|让我重新|先确认|再想想|我意识到|我发现.{0,20}(?:错|误|问题)|我发现自己|原来.*不是|搞错了|写错了|语法有误|有问题|可能是个?问题|是个错误|这是错的|不对劲/i
].map(r => new RegExp(r.source, r.flags.includes('i') ? r.flags : r.flags + 'i'))

// 验证行为：质疑之后是否跟了显式检查（HVR 的分母）
const VERIFICATION_RE = /(验证|确认|检查|核对|读一下|看一下|试一下|测试|compare|verify|check|confirm|read back|trace)/i

// 纠错候选：比原来的 CORRECTION_RE 宽，但仍要求"指向具体动作"或"明确认错"
const CORRECTION_RE = [
  /(?:应该|需要|必须|应当|我要|我得|下次|以后)[^。！\n]{0,60}(?:改|换|用|删|加|恢复|撤销|重试|确认|检查|搜|读|写|测|构建|处理|实现|直接|先|停止|放弃)/,
  /(?:我|刚才|之前)[^。！\n]{0,30}(?:错了|搞错|写错|想错|判断错|漏了|忽略|没看到|没确认|失败)/,
  /(?:可能是?个?问题|是个错误|这是错的|不对劲|方法来(源|路)不对|路径.*(错|不对))/,
  /\b(?:I was wrong|should have|should instead|mistake|incorrect|actually need to)\b/i
].map(r => new RegExp(r.source, r.flags))

// 静默词：模态必须保留，不能写成干净规则（巩固边界安全论文）
const MODAL_RE = /(也许|可能|好像|似乎|大概|也许应该|我猜|可能是|不确定|might|maybe|probably|I think|seems)/i

/**
 * HVR 分流：返回 { shouldCapture, hesitant, verified, confidence, reason }
 * 保守：无犹豫 → 不捕获（96% 正确，不值得记）
 *       有犹豫无验证 → 低置信候选（可记但要 gate）
 *       有犹豫+验证 → 高置信候选
 */
export function hvrGate(reasoning) {
  const text = String(reasoning || '')
  if (!text.trim()) return { shouldCapture: false, hesitant: false, verified: false, confidence: 0, reason: 'empty' }
  const hesitant = HESITATION_RE.some(r => r.test(text))
  if (!hesitant) return { shouldCapture: false, hesitant: false, verified: false, confidence: 0, reason: 'no-hesitation:96%-correct' }
  const verified = VERIFICATION_RE.test(text)
  // 信息量：纠错句数量 + 是否有验证行为（不是简单关键词计数）
  const corrections = CORRECTION_RE.filter(r => r.test(text)).length
  const confidence = Math.min(0.95, 0.55 + (verified ? 0.25 : 0) + Math.min(0.15, corrections * 0.05))
  return {
    shouldCapture: true,
    hesitant: true,
    verified,
    confidence,
    corrections,
    reason: verified ? 'hesitation+verification' : 'hesitation-only'
  }
}

/**
 * 从 reasoning 抽候选条目（保留原始模态词与来源锚点）
 * 不压缩、不整合——原始轨迹是一等证据（2605.12978）
 */
export function mineCandidates(reasoning, meta = {}) {
  const text = String(reasoning || '')
  const gate = hvrGate(text)
  if (!gate.shouldCapture) return []
  const out = []
  for (const r of CORRECTION_RE) {
    const m = text.match(r)
    if (!m) continue
    const i = m.index ?? 0
    out.push({
      id: 'LRN-' + String(meta.ts || Date.now()) + '-' + out.length,
      raw: text.slice(Math.max(0, i - 60), i + 160).trim(),
      signal: m[0].slice(0, 120),
      modality: (text.match(MODAL_RE) || [''])[0],
      verified: false,
      status: 'candidate',
      confidence: gate.confidence,
      source: meta.sid || '',
      step: meta.step || 0,
      evidence_ref: meta.evidenceRef || (meta.sid ? 'trace:' + meta.sid + ':' + (meta.step || 0) : ''),
      created_at: meta.ts || Date.now(),
      patternKey: (m[0].match(/[\u4e00-\u9fa5A-Za-z_]{2,20}/) || [''])[0]
    })
  }
  return out
}

/**
 * 三闸门（社区实证阈值：Recurrence>=3 ∧ 跨2任务 ∧ 30天 + 失败闸门）
 * 只有全部通过才 promote 到 active
 */
export function promotionGate(candidates, history = []) {
  if (!Array.isArray(candidates) || !candidates.length) return { promote: [], hold: [] }
  const now = Date.now()
  const promote = [], hold = []
  for (const c of candidates) {
    const key = c.patternKey || c.signal
    const matches = history.filter(h => (h.patternKey || h.signal) === key && h.status !== 'retired')
    const recent = matches.filter(h => now - (h.created_at || 0) <= 30 * 86400000)
    // 跨任务判定：hist 与当前 candidate 的 source 去重后计数（不能先建 Set 再 +1，会重复计当前 source）
    const sids = new Set([...recent.map(h => h.source), c.source].filter(Boolean))
    const recurrence = recent.length + 1
    const crossTask = sids.size >= 2
    const evidenceOk = c.verified === true || c.confidence >= 0.85
    if (recurrence >= 3 && crossTask && evidenceOk) promote.push(c)
    else hold.push({ ...c, holdReason: !evidenceOk ? 'unverified' : (!crossTask ? 'single-task' : 'low-recurrence') })
  }
  return { promote, hold }
}

/**
 * 紧凑元认知反馈（Metacognitive Harness 2605.14186）
 * retry 时不喂原始 reasoning 全文——只给信号，防锚定
 */
export function compactMetacognitive(candidates) {
  if (!Array.isArray(candidates) || !candidates.length) return ''
  const top = candidates.slice(0, 3)
  return top.map(c => '[元认知] ' + (c.modality ? '(' + c.modality + ') ' : '') + c.signal.slice(0, 80)).join('\n')
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { hvrGate, mineCandidates, promotionGate, compactMetacognitive }
}
