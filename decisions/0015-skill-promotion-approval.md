# ADR-0015：技能写回必须审批

- 状态：accepted
- 日期：2026-11-18
- 决策者：用户 + 助手

## Context
SkillsBench（arXiv:2602.12670，**v1**：self-generated skills 无收益，84 任务中 16 个为负；v4 已改口径，引用须标 v1）；
SkillLearnBench（arXiv:2604.20087：self-feedback alone induces recursive drift）；
真实 marketplace 研究（arXiv:2601.10338：31,132 技能中 26.1% 含至少一个漏洞）——三条均经 2026-11-20 WebFetch 核实。

⚠️ **引用更正（2026-11-20）**：原挂 arXiv:2603.25158（Trace2Skill，真论文但摘要无上述内容）是误挂，已替换为以上三条真实出处。
注意边界：SkillLearnBench 的 drift 结论限于"无外部新信号的自我反馈"，不是所有更新都有害；
26.1% 是检出风险模式，非确认攻击。

## Decision
草稿先进 `_skill_drafts/pending/` 隔离区，经 `--promote` 审批才入库；保留 supersede/归档审计链。

## Consequences
- 零训练下"变聪明"= 写文件，但不能无门控
- 验证：未审批技能不出现在 skills/ 目录
