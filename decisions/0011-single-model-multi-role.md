# ADR-0011：单权重多角色，不搞多 agent

- 状态：accepted
- 日期：2026-11-17
- 决策者：用户 + 助手

## Context
多 agent 框架生态成熟，但 2025 后反面证据强：MAST 1600+trace/κ=0.88、ChatDev 失败率 >66%；Google+MIT 180 组实验顺序任务 -39~-70%。

## Decision
同一模型不同 conditioning 做 5 角色（执行/审计/纠正/Critic/验收），单写者 + steer + 代执行 + 三态验收，零并行 agent 开销。

## Consequences
- 方向踩中社区"单 agent + guardrail 优于多 agent"共识
- 技术本身平凡（role/persona 是 2023 年级基础）——领先在工程组织与权限语义
- 弱点：Critic 与执行者同源，异质 rubric 不解决模型同源偏差（见 ROADMAP 短期目标）
