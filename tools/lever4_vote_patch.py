# -*- coding: utf-8 -*-
"""杠杆4补丁：同模型 K=5 自洽投票（P2，高风险决策才开）。

区别于已证伪的"多 judge 投票"（9 judge≈2 票）：这是同一模型多次采样投票。
关键防线：一致性阈值 + 置信度低仍弃权（防"把困惑封为共识"）。

挂点：runCritic（插件唯一自己持有 prompt + 采样接口的决策点）。
工具选择在 dsh 模型生成内部，插件拿不到，故不在那里做。
"""
import sys, hashlib
from pathlib import Path

TARGET = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
EXPECTED_SHA = '362e37154586a5c4c8879c1c59973e3cc9bcb09ec1bf73f3f4e5fa0003113520'
PATCHES = []

# ── 补丁1：DEFAULTS ──
PATCHES.append((
    'DEFAULTS 投票字段',
    "  criticTemperature: 0.7,",
    """  criticTemperature: 0.7,
  // ── P2 同模型 K=5 自洽投票（2026-11-24；默认关，高风险决策才开）──
  voteK: 5,
  voteTemperature: 0.7,
  voteMinAgreement: 4,
  voteMaxTotalMs: 180000,""",
))

# ── 补丁2：callLLMVote 函数（插在 runCritic 之前）──
PATCHES.append((
    'P2 投票函数',
    "  async function runCritic(s) {",
    """  // ── P2: 同模型自洽投票（推理时，无需训练）────────────────────────────────
  // 实证：GSM8K +17.9%（K=5-10 边际最大）；我们的 65-78% 基础能力刚好跨过
  // "不会把困惑封为共识"的门槛。与多 judge 投票（已证伪 9 judge≈2 票）不同：这是同模型采样。
  // 防线：必须过 minAgreement 且不能无条件信任高一致度；tie/uncertain 回退 UNCERTAIN。
  async function callLLMVote(prompt, maxTokens, timeoutMs, sampling, cfg, sid) {
    const K = Math.max(2, Number(cfg?.voteK) || 5)
    const minAgreement = Math.max(2, Math.min(K, Number(cfg?.voteMinAgreement) || Math.ceil(K * 0.8)))
    const totalMs = Math.max(10000, Number(cfg?.voteMaxTotalMs) || 180000)
    const started = Date.now()
    const votes = []
    for (let i = 0; i < K; i++) {
      if (Date.now() - started > totalMs - 20000) break  // 留 20s 余量
      let out = null
      try {
        out = await callLLMOnce(prompt, maxTokens, 20000, {
          ...(sampling || {}), temperature: cfg?.voteTemperature ?? 0.7,
        })
      } catch (e) {
        votes.push({ i, verdict: 'ERROR', error: String(e?.message || e).slice(0, 80) })
        continue
      }
      let verdict = out?.verdict || out?.parsed?.verdict || 'PARSE_FAIL'
      if (verdict !== 'ACCEPT' && verdict !== 'REJECT' && verdict !== 'UNCERTAIN') verdict = 'PARSE_FAIL'
      votes.push({ i, verdict })
    }
    const tally = votes.reduce((a, v) => { a[v.verdict] = (a[v.verdict] || 0) + 1; return a }, {})
    const sorted = Object.entries(tally).sort((a, b) => b[1] - a[1])
    const top = sorted[0] || ['UNCERTAIN', 0]
    const second = sorted[1] || ['', 0]
    const agreed = top[1]
    const tie = second[1] === agreed
    // 一致性阈值 + tie 回退：防"5 次全错但一致"
    const ok = agreed >= minAgreement && !tie && top[0] !== 'PARSE_FAIL' && top[0] !== 'ERROR'
    const result = {
      verdict: ok ? top[0] : 'UNCERTAIN',
      votes: votes.map((v) => v.verdict),
      tally, agreed, minAgreement, tie,
      elapsedMs: Date.now() - started,
    }
    trace({ ts: new Date().toISOString(), sid: sid || '', kind: 'self_consistency_vote',
      verdict: result.verdict, votes: result.votes, tally: result.tally,
      agreed: result.agreed, minAgreement: result.minAgreement, tie: result.tie,
      elapsedMs: result.elapsedMs })
    return result
  }

  async function runCritic(s) {""",
))

# ── 补丁3：runCritic 里替换单次 callLLM 为投票（受开关控制）──
PATCHES.append((
    'runCritic 投票开关',
    "    const out = await callLLM(CRITIC_PROMPT(criticTask, product, content), cfg.criticMaxTokens ?? 1200, cfg.criticTimeoutMs || 90000, {\n      sid: snap.sid, tag: 'critic',\n      temperature: cfg.criticTemperature, topK: cfg.criticTopK,\n      review_kind: 'critic', rubric_version: CRITIC_RUBRIC?.version || 'builtin',\n      dimensions_checked: criticDims,\n    })",
    """    const promptText = CRITIC_PROMPT(criticTask, product, content)
    const sampling = {
      temperature: cfg.criticTemperature, topK: cfg.criticTopK,
      review_kind: 'critic', rubric_version: CRITIC_RUBRIC?.version || 'builtin',
      dimensions_checked: criticDims,
    }
    const out = cfg.voteOnCritic
      ? await callLLMVote(promptText, cfg.criticMaxTokens ?? 1200, cfg.criticTimeoutMs || 90000, sampling, cfg, snap.sid)
      : await callLLM(promptText, cfg.criticMaxTokens ?? 1200, cfg.criticTimeoutMs || 90000, { sid: snap.sid, tag: 'critic', ...sampling })""",
))

# ── 补丁4：voteOnCritic 开关（默认关）──
PATCHES.append((
    'voteOnCritic 开关',
    "  voteMaxTotalMs: 180000,",
    """  voteMaxTotalMs: 180000,
  voteOnCritic: false,   // 默认关；A/B 验证增益后再开""",
))


def main():
    raw = TARGET.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')  # 归一化做替换
    import sys as _sys
    expect = _sys.argv[1] if len(_sys.argv) > 1 else EXPECTED_SHA
    print(f'anchor sha={actual[:16]} expected={expect[:16]} crlf={crlf}')
    if actual != expect:
        print('ABORT: sha 不匹配')
        _sys.exit(1)
    for desc, old, new in PATCHES:
        cnt = s.count(old)
        if cnt != 1:
            print(f'ABORT: [{desc}] 锚点 {cnt} 次（期望 1）')
            sys.exit(1)
        s = s.replace(old, new, 1)
        print(f'  OK [{desc}]')
    out = s.replace('\n', '\r\n') if crlf else s
    TARGET.write_bytes(out.encode('utf-8'))
    print(f'APPLIED patch4 self_consistency, new sha={hashlib.sha256(s.encode()).hexdigest()[:16]}')


if __name__ == '__main__': main()
