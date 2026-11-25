# ADR-0018：Self-Harness 分两阶段落地，安全面不进搜索空间

- 状态：accepted
- 日期：2026-11-19
- 决策者：项目所有者确认"先提方案"后采纳（方案见 [SELF_HARNESS_PLAN](../docs/AUTONOMY_AND_SELF_HARNESS_20261122.md)）

## Context（背景）

[Self-Harness](https://arxiv.org/abs/2606.09498) 证明了固定模型可以通过"弱点挖掘 → 候选提案 → 回归验证"的闭环改进自己的 harness，Qwen3.5-35B-A3B 在同族上获得 +18.7pp 提升。我们的项目本来就在手工做同类事情（根据 trace 调注入规则、CritBank 沉淀教训），但缺三样东西：失败签名聚类、可编辑面白名单、双 split 回归门禁。

同时有两个约束：① 本地 35B 提案质量不确定，直接放开改 2000 行 index.mjs 风险极高；② 权限预设、verify 闸门、GWT/FEP 通道是安全边界，一旦被"优化"掉会造成静默退化（参考 v2.12.0 审计中 verifyRan 短路两道闸门的教训）。

## Decision（决定）

1. Self-Harness 定位为 ROADMAP **短期①「技能自进化数据闭环」的实现路径**，不新增并列目标。分 P0（白名单+评测台）→ P1（弱点挖掘）→ P2（最小闭环）→ P3（常态化，可选）四阶段，**一波没验收不开始下一波**（继承 ADR-0017 的执行铁律）。
2. 分两步走：先由 WorkBuddy agent 作 proposer 离线跑通协议（**Meta-Harness**），验证评测台与门禁可信；再由本地 35B 自己作 proposer（**Self-Harness**）。不跳步。
3. 建立 **editable surfaces 白名单**：仅 prompt 措辞、阈值类 runtime control、技能草稿、受限 middleware 模板可改。权限预设 / approval-delegate / L0-L3 硬规则 / verify 闸门 / GWT/FEP 通道**禁止改**。
4. 候选只改一个 surface，写在隔离目录（`SELF_HARNESS_CANDIDATE_WORKSPACE`），不直接改运行版；通过门禁的候选先生成 patch + 人工确认再部署（继承 ADR-0015 的审批原则）。
5. 接受规则照搬论文：任一 split 不退化且至少一个提升；`repeats≥2`；`decline` 是合法结果。

## Consequences（后果）

- 正面：把"凭经验手调 harness"升级为"有证据、有对照、可审计"的闭环；弱点挖掘直接复用已有 3300+ 行 trace；`recovered_friction` 类可显式保护"上下文不堪但承接成功"的有效机制。
- 负面：P0 评测台成本高（24 任务 × 2 repeats ≈ 2-4 小时/轮）；35B 提案可能大量 decline，需接受"本轮无进展"；白名单外的改进机会被放弃（这是有意的）。
- 验证：
  - P0：基线 pass-rate 方差 <10%；acceptance gate 单测覆盖 accept/reject/no-op。
  - P1：监测插件会话真实 trace 聚类出可区分的 failure cluster。
  - P2：人为关闭 `verifyOnStopEnabled`，闭环能提出恢复它的候选并通过门禁。
  - 红线：任何阶段都不允许学习信号占运行时注入通道（ADR-0017）。
