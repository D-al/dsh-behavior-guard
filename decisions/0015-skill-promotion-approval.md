# ADR-0015：技能写回必须审批

- 状态：accepted
- 日期：2026-11-18
- 决策者：用户 + 助手

## Context
SkillsBench：自动生成的技能收益不一致；SkillLearnBench：持续更新会 drift/regress；marketplace 26.1% 技能有漏洞。

## Decision
草稿先进 `_skill_drafts/pending/` 隔离区，经 `--promote` 审批才入库；保留 supersede/归档审计链。

## Consequences
- 零训练下"变聪明"= 写文件，但不能无门控
- 验证：未审批技能不出现在 skills/ 目录
