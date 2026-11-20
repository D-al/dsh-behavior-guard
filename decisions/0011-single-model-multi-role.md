# ADR-0011：单权重多角色，不搞多 agent

- 状态：accepted
- 日期：2026-11-17
- 决策者：用户 + 助手

## Context
多 agent 框架生态成熟，但 2025 后反面证据强：MAST（arXiv:2503.13657，已核实）系统分析 1600+ 轨迹的多 agent 失败模式；本机 JudgeBench 实测小模型 judge 一致率仅 45-60%（近抛硬币），支持"单模型分角色 + 确定性门控"而非多 agent 互审。

⚠️ **证据更正（2026-11-20）**：
- "ChatDev 失败率 >66%" = **出处错配，不是编造**：66.7% 这个数字真实存在，但出自 MAST（arXiv:2503.13657）Fig5 的 ChatDev success 33.3%（成功率的补数），**不是** ChatDev 原论文（arXiv:2307.07924）的统计。已改挂 MAST。
- "Google+MIT 180 组实验 -39~-70%" = **真实**：arXiv:2512.08296《Towards a Science of Scaling Agent Systems》摘要原文确认 -70%；180 组是 v1 数字，v3 已改为 260 配置，引用须标版本。
- 结论：本决策的三条外部依据**全部真实**，只是出处/版本需校正；加上本机 45-60% 实测，依据充分。

## Decision
同一模型不同 conditioning 做 5 角色（执行/审计/纠正/Critic/验收），单写者 + steer + 代执行 + 三态验收，零并行 agent 开销。

## Consequences
- 方向踩中社区"单 agent + guardrail 优于多 agent"共识
- 技术本身平凡（role/persona 是 2023 年级基础）——领先在工程组织与权限语义
- 弱点：Critic 与执行者同源，异质 rubric 不解决模型同源偏差（见 ROADMAP 短期目标）
