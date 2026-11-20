# ADR-XXXX：简短标题

- 状态：proposed | accepted | rejected | superseded by [ADR-YYYY]
- 日期：YYYY-MM-DD
- 决策者：（谁拍板的）

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

## Decision（决定）
我们决定做什么。一句话，明确。

## Consequences（后果）
- 正面：（预期收益）
- 负面：（代价 / 风险）
- 验证：（怎么知道决定对不对）
