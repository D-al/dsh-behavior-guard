# Changelog

所有迭代以本地时间记录（UTC+8）。

## [2.1.0] - 2026-11-18 01:35

### Added（控制回合 / meta-reasoning controller）
- 每 8 步注入一次「控制回合」摘要（**零 LLM**）：已确立（completed 项）/ 当前项 / 已排除 /
  「列 2-3 个候选动作，评估收益再选一个」——把 Meta 论文 Controller 的四个动作
  （consolidate → explore → assess → dispatch）落成模型侧提示
- 依据：《Thinking Before Thinking: Scaling Agentic Inference Through Meta-Reasoning》
  (arXiv 2609.38147, Meta 2026-09)：ProgramBench **71.5% vs Codex 58.0%（+13.5pp）**，
  其他基准 +3.6~4.2；"structured control becomes more important as agents scale to longer runs"
- 配置：controlEverySteps=8、maxControlPerSession=6；每轮重置

### Tests
- 30/30（新增 4 例：第 N 步触发/含已确立/含候选提示/次数上限）

## [2.0.0] - 2026-11-18 01:45

### Changed（合并两个插件为一个包）
- **合并 dsh-behavior-guard v1.2.0 + dsh-task-continuity v1.0.4**
- 理由：两者事件面相同（session/event + agent/pre-step）、共享同一份会话状态
  （todo/失败轨迹/压缩事件）、注入预算需统一；分开维护曾导致双挂载
  （preset 显式 + bundle patch → 所有注入成对出现）
- 包名 `dsh-agent-harness`，插件 id `agent-harness`

### Added（合并时的增量修复）
- state 初始化补 `todoCalls` / `sinceLastTodo`（合并时遗漏会导致 P1 闹钟永不触发——测试发现）
- 单一探针路径 `_agent_harness_loaded.json`（加载验证一目了然）
- 统一配置项（两插件原配置合并，见 cordis.patch.yml）

### Tests
- 26（turn-guard）+ 28（new_guards，含 continuity 的 P0/P1.5/P1 三项合并验证）
- 历史版本（各自仓库）：behavior-guard v1.0.0→v1.2.0、task-continuity v1.0.0→v1.0.4
