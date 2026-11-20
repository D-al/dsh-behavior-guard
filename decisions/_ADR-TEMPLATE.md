# ADR-XXXX：简短标题

- 状态：proposed | accepted | rejected | superseded by [ADR-YYYY]
- 日期：YYYY-MM-DD
- 决策者：（谁拍板的）
- **决策层级**：一般决策 G / 重要决策 I / 关键决策 K（见 lineage/DECISION_CHAIN.md）
  - G=参数/工具/单次开关；I=机制/架构，默认 ≥2 条**独立** G 支撑；K=身份/方向，默认 ≥2 条**独立** I 支撑
  - ⚠️ "≥2"是经验阈值（团队约定非科学定律）；看独立性不看条数——详见 lineage/METHODOLOGY_AUDIT.md
- **支撑决策**（层级用）：本决策依赖的前置决策 ID（Gxx/Ixx/Kxx）

## Options（考虑过的方案）— 必填
> 用户 2026-11-20 纪律：每个决策要列出有哪些方案，以及为什么选这个

| 方案 | 做法 | 优点 | 代价/风险 | 结论 |
|---|---|---|---|---|
| A | | | | |
| B（选中）| | | | ✅ |
| C | | | | |

## Context（背景）
当时面对什么问题？有哪些约束？（事实，不写结论）

## Evidence（引用依据）— 2026-11-20 起必填
> 用户架构级要求：决策必须与引用依据严格对应。

- [ ] 本决策的外部引用已全部登记到 `config/citation_ledger.json`（格式 `arxiv:ID` / `url:slug` / `github:repo#N`）
- [ ] 每条引用的 status 为 `verified` 或 `n/a`（本机实测）；`partial` 只能作背景、不能作为唯一依据；
      `hallucinated`/`missing`/`pending` **禁止**作为决策依据
- [ ] `decision_uses` 已填本 ADR 编号（引用台账反向对应）
- [ ] 引用声称的**具体数字/结论**与台账 note 一致（不是"论文真所以数字也真"）
- 本决策依据：`<ledger-id>` — <一句话：它凭什么支撑这个决定>

机器校验：`python tools/citation_guard.py`（FAIL 则本 ADR 不得 accepted）

## Counter-evidence（反证）— 必填，对抗确认偏误
> 只记支持证据的决策必然过度自信。2026-11-21 调研：
> Fischhoff(1975) 后见之明偏差、Nickerson(1998) 确认偏误——决策记录若不强制写反证，
> 会退化成事后合理化（见 lineage/METHODOLOGY_AUDIT.md §7）。写不出反证 = 没认真找过。

- **反对本决策的最强理由**：（如果错了，最可能错在哪？）
- **什么信号会让我们翻案**：（写下可证伪条件，如"若 A/B 显示 X 则撤销"）
- **汇聚独立性自查**：（支撑证据是否同源？同源多条 = 独立性 0，不算汇聚）

## Decision（决定）
我们决定做什么。一句话，明确。

## Consequences（后果）
- 正面：（预期收益）
- 负面：（代价 / 风险）
- 验证：（怎么知道决定对不对）
