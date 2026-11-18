# ADR-0012：确定性门控优先

- 状态：accepted
- 日期：2026-11-18
- 决策者：用户 + 助手

## Context
LLM judge 慢（1.5-5.9s）、贵、随模型版本漂移；2026 社区收敛到"确定性 cascade"。

## Decision
L0-L3 + D1-D5 + verify-on-edit + present 深检 + 危险分级全部确定性（0 LLM），LLM 只在风险门控触发时介入。

## Consequences
- 确定性接住大部分已知失败，成本 0
- 社区 2026 共识一致 → 方向对但不领先（见 COMPETITIVE_ANALYSIS）
