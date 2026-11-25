# ADR-0020：战略目标 v3.1 落地——从"合成心智"到可证伪的目标体系

- 状态：accepted
- 日期：2026-11-22
- 决策者：用户（显式批准："我批准；开始"，2026-11-22 13:23）
- 决策层级：关键决策 K（身份/方向——改变顶层目标）
- 支撑决策：ADR-0017（长期地基优先）、STRAT1（STRATEGY.md 战略陈述）

## Options（考虑过的方案）— 必填

| 方案 | 做法 | 优点 | 代价/风险 | 结论 |
|---|---|---|---|---|
| A 维持原目标 | STRATEGY.md §0"完善合成心智"不动 | 零改动 | §2 六指标 4 项无基线；不可证伪；投入 48% 检查/9% 建设 | ❌ |
| B 直接替换全文 | 用 v3.1 重写 STRATEGY.md | 一步到位 | 6 KR 全 N/M；无迁移映射会产生双轨目标；无 ADR | ❌ |
| C 渐进落地（选中）| 先建 KR1 打点 + 快照，再写 ADR 登记迁移映射与证据源，最后改 §0/§2 | 可回滚、可验证、无双轨 | 多几步流程 | ✅ |

## Context（背景）

经多轮调研与实测：
1. 原目标"完善合成心智"作为 vision 合适，作为唯一工程目标踩中 Rumelt"目标冒充战略"、
   Popper 不可证伪、Bridgman 不可操作化。
2. 实测投入分布 48% 检查/9% 建设——目标里唯一可操作的是"可审计可回滚"。
3. STRATEGY.md §2.1 六项能力指标中 4 项无基线（可追溯率实测 29.7% vs 目标 95%）。
4. 提案 v3 经独立批判评审 13 项，全部处置（见 `docs/GOAL_STATEMENT_EVOLUTION_20261122.md` 附录 A）。
5. 落地就绪度检查 `tools/landing_readiness.py` 实测 0/5 → 经本 ADR 与打点后应为 5/5。

## Evidence（引用依据）— 必填

- [x] 本决策的外部引用为内部调研文档（非新论文），已登记于 `docs/` 各调研文档
- [x] 每条结论来自本机实测或标注出处的调研
- [x] `decision_uses` 已填本 ADR 编号（见 config/citation_ledger.json 更新）
- [x] 具体数字与来源一致

本决策依据（本地实测为主）：
- `docs/SYSTEMIC_DECAY_ASSESSMENT_20261122.md` — ratchet 10.3%、热点 71%、投入 48%/9%
- `docs/GOAL_STATEMENT_EVOLUTION_20261122.md` — 13 项批判处置、6 个二值 KR、means-end 闭合
- `docs/GOAL_STATEMENT_EVOLUTION_20261122.md` — 5 条落地判据、6 前置工作量
- 本机实测：`goal_verify.py` KR1-6 全 N/M；`landing_readiness.py` 0/5 → 本 ADR 后 5/5

## Counter-evidence（反证）— 必填，对抗确认偏误

- **反对本决策的最强理由**：6 个 KR 全部 NOT_MEASURABLE，此时落地等于"目标进了权威源但一条都测不了"——
  与刚修的"done 卡判据不过"同构，是第 7 次虚报风险。
- **什么信号会让我们翻案**：若落地后 1 个月内 KR1 仍无 live 数据、或出现两套目标口径并存的证据，
  则回滚本 ADR（快照 `snapshots/20261122_132415`）。
- **汇聚独立性自查**：支撑证据同源风险高——13 项批判和落地计划均由同一 agent 产出并经用户审阅，
  独立性有限。缓解：独立批判评审是异构 agent；用户显式批准是外部锚点。

## Decision（决定）

1. **STRATEGY.md §0** 用 v3.1 Vision 替换：
   "在本机持续建设一个可靠、可成长的计算体：能感知环境、采取行动、从经验中改进自身，
   在固定可验证任务集上稳定达到预设能力基线，并始终处于人类可理解、可关闭的边界内。"
   保留"可治理可关闭边界"内核；标注 aspirational、非验收。
2. **§2.1 六项能力指标并入 KR**：G1→KR3；G2/G3→KR1；G4→KR2；G5→KR2；G6→KR2/KR4。
   不再作为独立验收源（防双轨）。
3. **§2.2 七项 guardrail、§2.3 不验收、§3 非目标、§4 假设、§5 元治理锁全部保留**；
   §5 强化"KR 判定权不在 agent"。
4. **新增 KR 判定权条款**：判定者为外部脚本或人类抽样，agent 不得自判达标。
5. **证据源登记**（sha 在落地时写入）：
   - `_trace.jsonl`（KR1，已存在）
   - `_benchmark_holdout.jsonl`（KR2，待建）
   - `_capability_ledger.json`（KR3，待建）
   - `_event_replay_results.jsonl`（KR4，待建）
   - `_expert_baseline_frozen.json`（KR5，待建，须 approved_by+sha）
   - `_kill_switch_drill.jsonl`（KR6，待建）
6. **KR1 打点已落地**：`tools/task_trace.py` + `tools/flow_orchestrator.py` 三分支；
   probe 数据不作验收（goal_verify 过滤）。
7. **标注**：STRATEGY.md 新增"目标已生效但 KR 未达成"状态说明。

## Consequences（后果）

- 正面：目标可证伪、无双轨、判定权外部化、可回滚（快照已建）。
- 负面：6 KR 全 N/M 期间，目标"生效但未达成"；KR1 需积累 10 条 live 数据才能判。
- 验证：`landing_readiness.py` 五条全 READY；`consistency_guard.py` 三处 sha 一致；
  `goal_verify.py` 三态结果如实；全门禁 61/61。
- 回滚：必要时恢复 `snapshots/20261122_132415`。
