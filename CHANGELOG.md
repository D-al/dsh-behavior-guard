# Changelog

所有迭代以本地时间记录（UTC+8）。

## [2.2.1] - 2026-11-18 03:35

### Changed
- **planner rubric 外置接入**：P2 检查的判据从硬编码改为读 `bench/rubrics/planner_v1.json`
  （此前 critic/audit 已外置，planner 漏了 → 三个 rubric 现在全部"单一来源 + 被代码使用"）
- skills 关键词收紧（防误注入）：verify-artifact 去掉"检查/测试"、release-plugin 去掉"版本"、
  git-workflow 改为短语（"git commit/tag/push"）；新增 session-debug / harness-debug 两个技能（共 7 个）

### Verified
- 26/26 + 38/38 + 门禁 29/29
- **P5 PASS**（17 步 551.8s，六维画像全 OK）/ **P4 PASS**（11 步 300.0s，比历史 -38% 墙钟）
- 显存观察：长任务余量 107~113 MiB（低于 450 安全线）→ 跑长任务前建议重启清 MoE cache

## [2.2.0] - 2026-11-18 02:25

### Added（社区 harness 组件清单的四个缺口）

**1. Observability（per-step trace）**
- `_trace.jsonl`：每次工具调用/结果、每次 LLM 调用（审计/纠正/评审/规划）记录
  时间、耗时、输入输出字符数、状态、是否重试；超 8MB 自动轮转
- `bench/trace_report.py`：按会话统计步数/工具分布/失败率/LLM 调用耗时与重试
- 依据：Keyhole/Praison/ZOOZ 三家 harness 清单都把 observability 列为必需层——
  **没有 trace 就无法度量，没有度量就无法优化**

**2. 输出鲁棒性（JSON 解析重试）**
- `callLLMOnce` 拆分 + `callLLM` 包装：解析失败自动附"只输出纯 JSON、不要代码块"重试一次
  （`jsonRetryTimes=1`），重试次数计入 trace
- 依据：社区标准（guibai）——"解析失败 → 附格式纠正重试"，而非静默丢弃

**3. Skills（渐进披露的过程性知识）**
- `bench/skills/*.md`（frontmatter: name/summary/keywords），插件按任务关键词命中注入
  "技能卡"（名称+摘要+路径），模型按需 read
- 首批三个技能：release-plugin（发布插件 7 步）/ debug-llama-server（引擎排障）/
  verify-artifact（产物验收清单）
- 依据：Keyhole 白皮书——Skills 是"只在相关时加载的过程性知识"，AGENTS.md 4K 之外的容量出口

**4. 危险操作分级（permission tiering）**
- block 级（不可逆）：rm -rf / Remove-Item -Recurse -Force / del /s / git reset --hard /
  git push --force / 格式化 / shutil.rmtree → 注入"执行前必须说明+给更安全方案"
- warn 级：rm 单文件 / git checkout -- / 覆盖写 / 引擎关键参数 → 提示核对与备份
- 不阻断（拦截仍归 dsh approval policy），提供模型侧意识 + 可追溯警告

### Tests
- 38/38（新增：Skills 3 例、危险操作 3 例、JSON 重试随 trace 验证）

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
