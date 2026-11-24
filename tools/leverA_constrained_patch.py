# -*- coding: utf-8 -*-
"""杠杆A补丁：约束解码（response_format: json_object）。

只打 behavior-guard 两副本（publish 权威源 + node_modules 运行版），
不碰 publish/dsh-agent-harness（1963行旧版，无关）。

设计：
- 默认开（constrainedJsonEnabled: true），但三个调用点各有独立开关便于 A/B
- 用 json_object（只保证合法 JSON，不锁字段值）——规避 8443→844 越界压值陷阱
- 保留 reasoning_content 兜底（thinking 模型 token 不足时仍能提取）
- trace 打点 constrained_json：记录用了约束、解析结果、是否触发兜底
"""
import sys, hashlib, shutil
from pathlib import Path

AUTH = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
RUN = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
PATCHES = []

# ── 补丁1：DEFAULTS 开关 ──
PATCHES.append((
    'A-DEFAULTS',
    "  criticTemperature: 0.7,",
    """  // ── 杠杆A 约束解码（2026-11-24；json_object 只锁形状不锁字段值）──
  constrainedJsonEnabled: true,
  constrainedJsonCritic: true,
  constrainedJsonAudit: true,
  constrainedJsonVote: true,
  criticTemperature: 0.7,""",
))

# ── 补丁2：callLLMOnce 加 response_format 参数 ──
PATCHES.append((
    'A-callLLMOnce签名+body',
    """  async function callLLMOnce(prompt, maxTokens, timeoutMs, sampling = {}) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), timeoutMs)
    // 短期②：Critic 去同源——异质温度/top_k 打破与执行者相同的确定性 conditioning
    const temperature = sampling.temperature ?? 0.0
    const topK = sampling.topK ?? 1
    try {
      const resp = await fetch(cfg.endpoint, {
        method: 'POST',
        body: JSON.stringify({
          model: cfg.model,
          messages: [{ role: 'user', content: prompt }],
          max_tokens: maxTokens, temperature, top_k: topK,
        }),""",
    """  async function callLLMOnce(prompt, maxTokens, timeoutMs, sampling = {}) {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), timeoutMs)
    // 短期②：Critic 去同源——异质温度/top_k 打破与执行者相同的确定性 conditioning
    const temperature = sampling.temperature ?? 0.0
    const topK = sampling.topK ?? 1
    // 杠杆A：约束解码。json_object 只保证合法 JSON 形状，不锁字段值——
    // 规避 schema maximum 把 8443 压成合法 844 的陷阱（调研实证）。
    const useConstrained = cfg.constrainedJsonEnabled !== false && sampling.constrained === true
    const bodyObj = {
      model: cfg.model,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: maxTokens, temperature, top_k: topK,
    }
    if (useConstrained) bodyObj.response_format = { type: 'json_object' }
    try {
      const resp = await fetch(cfg.endpoint, {
        method: 'POST',
        body: JSON.stringify(bodyObj),""",
))

# ── 补丁3：callLLMOnce 返回时记录约束使用（在两个 return parsed 处）──
PATCHES.append((
    'A-trace解析成功',
    """        return { parsed: JSON.parse(out.slice(i, j + 1)), raw: out, finish, emptyContent: !choice?.message?.content, reasoningUsed, reasoningChars: reasoning.length }""",
    """        if (useConstrained && sampling.sid) trace({ ts: new Date().toISOString(), sid: sampling.sid,
          kind: 'constrained_json', applied: true, parsed: true, reasoningUsed, tag: sampling.tag || '' })
        return { parsed: JSON.parse(out.slice(i, j + 1)), raw: out, finish, emptyContent: !choice?.message?.content, reasoningUsed, reasoningChars: reasoning.length }""",
))

# ── 补丁4：三个调用点传 constrained 标志 ──
# Critic：callLLMOnce 经 callLLM 传入 ctx，需在 callLLM 里透传
PATCHES.append((
    'A-callLLM透传constrained',
    """    const sampling = { temperature: ctx.temperature, topK: ctx.topK }
    let r = await callLLMOnce(prompt, maxTokens, timeoutMs, sampling)""",
    """    // 杠杆A：调用点通过 ctx.constrained 请求约束解码（各调用点显式声明）
    const sampling = { temperature: ctx.temperature, topK: ctx.topK,
      constrained: ctx.constrained === true, sid: ctx.sid, tag: ctx.tag }
    let r = await callLLMOnce(prompt, maxTokens, timeoutMs, sampling)""",
))


# 审计调用点
PATCHES.append((
    'A-审计调用点',
    """        sid: snap.sid, tag: 'audit', review_kind: 'audit',""",
    """        sid: snap.sid, tag: 'audit', review_kind: 'audit',
        constrained: cfg.constrainedJsonAudit !== false,""",
))
# Planner 调用点
PATCHES.append((
    'A-Planner调用点',
    """      sid: s.sid || '', tag: 'planner', review_kind: 'planner',""",
    """      sid: s.sid || '', tag: 'planner', review_kind: 'planner',
      constrained: cfg.constrainedJsonEnabled !== false,""",
))
# Critic 调用点（callLLM 分支）
PATCHES.append((
    'A-Critic调用点',
    """      : await callLLM(promptText, cfg.criticMaxTokens ?? 1200, cfg.criticTimeoutMs || 90000, { sid: snap.sid, tag: 'critic', ...sampling })""",
    """      : await callLLM(promptText, cfg.criticMaxTokens ?? 1200, cfg.criticTimeoutMs || 90000, { sid: snap.sid, tag: 'critic', ...sampling, constrained: cfg.constrainedJsonCritic !== false })""",
))
# 投票调用点（直接 callLLMOnce）
PATCHES.append((
    'A-投票调用点',
    """          ...(sampling || {}), temperature: cfg?.voteTemperature ?? 0.7,""",
    """          ...(sampling || {}), temperature: cfg?.voteTemperature ?? 0.7,
          constrained: cfg?.constrainedJsonVote !== false, sid: sid, tag: 'vote',""",
))

PATCHES.append((
    'A-重试路径也带约束',
    """      r = await callLLMOnce(fixPrompt, maxTokens, timeoutMs, {})""",
    """      r = await callLLMOnce(fixPrompt, maxTokens, timeoutMs, { ...sampling })""",
))


def apply_to(path, expected=None):
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if expected and actual != expected:
        print(f'ABORT {path.name}: sha {actual[:12]} != {expected[:12]}')
        return False
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')
    for desc, old, new in PATCHES:
        cnt = s.count(old)
        if cnt != 1:
            print(f'ABORT [{desc}] 锚点 {cnt} 次')
            return False
        s = s.replace(old, new, 1)
        print(f'  OK [{desc}]')
    path.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
    print(f'APPLIED leverA -> {path.name} sha={hashlib.sha256(path.read_bytes()).hexdigest()[:12]}')
    return True


def main():
    cur = sys.argv[1] if len(sys.argv) > 1 else hashlib.sha256(AUTH.read_bytes()).hexdigest()
    if not apply_to(AUTH, cur): sys.exit(1)
    shutil.copy2(AUTH, RUN)
    print(f'同步运行版 sha={hashlib.sha256(RUN.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__': main()
