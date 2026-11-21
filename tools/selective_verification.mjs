// selective_verification.mjs — S15: Selective Verification Gate (v1, 2026-11-21)
// 纯规则门控版（零 LLM）。复用 taskProfile 的 needsDeepReview/needsTreeCheck 信号，
// 只对高风险写操作做深度验证，只读任务跳过。

/**
 * taskProfile — 轻量实现（与 index.mjs §33 等价，独立可测）
 */
export function taskProfile(s) {
  if (!s || typeof s !== 'object' || Array.isArray(s)) {  // 2026-11-21: typeof []==='object'，数组须单独排除（同 formatExecutorResult 踩过的坑）
    return { kind: 'unknown', needsTodo: true, needsVerify: true, needsDeepReview: true,
      needsTreeCheck: true, reason: 'state missing — fail-closed' }
  }
  const writeCalls = Number(s.writeCalls || 0)
  const hasProduct = String(s.lastProduct || '').length > 0

  // 只读任务：无写调用且无产物 → 全跳过
  if (writeCalls === 0 && !hasProduct) {
    return { kind: 'read-only', needsTodo: false, needsVerify: false,
      needsDeepReview: false, needsTreeCheck: false,
      reason: 'read-only: no writes and no product this turn' }
  }

  // 有产物或有写调用 → 需要验证
  return { kind: hasProduct ? 'artifact' : 'mutating', needsTodo: true,
    needsVerify: true, needsDeepReview: true, needsTreeCheck: true,
    reason: hasProduct ? 'has product -> verify+deep review' : 'has write calls -> verify' }
}

/**
 * verifyGate — 选择性验证门控
 * @param {object} state - agent session state
 * @returns {{ skip: boolean, level: string, profile: object, gate: string }}
 */
export function verifyGate(state) {
  const profile = taskProfile(state)

  // 确定性硬门：空状态 fail-closed，必须深检
  if (profile.kind === 'unknown') {
    return { skip: false, level: 'deep', profile, gate: 'hard-fail-close' }
  }

  // 只读任务：直接放行，跳过深度验证
  if (profile.kind === 'read-only') {
    return { skip: true, level: 'none', profile, gate: 'skip-read-only' }
  }

  // artifact / mutating：需要完整验证
  return { skip: false, level: profile.needsDeepReview ? 'deep' : 'basic', profile, gate: 'require-verify' }
}
