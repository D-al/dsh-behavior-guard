## [2.6.0] - 2026-11-18 13:10

### Changed（README 重构为总分式 + 说明书集合）
- README 从"流水账 8 Part"改为**四部分总分式**：
  - **总**：一句话定位 + 三个认知 + Mermaid 时间线 + 过去/未来路线图 + 8 分支地图 + 一键开箱
  - **分**：8 个分支各按统一格式（问题→调研→措施→结果→新发现→依据）展开，
    每个分支末尾"依据"全部是可点击的 arXiv / GitHub / 会议链接
  - **负面资产**：F1-F10 失败清单（锚点可跳转）
  - **索引**：指向说明书与所有子文档
- 新增 `docs/MANUALS.md`（说明书集合）：一键开箱 / 生产参数 / 工具速查 /
  论文速查表（41 链接）/ 版本升级检查清单 / 故障排查
- 修正 U-Fold、ARC 的错误 arXiv 链接（改为按机构/会议标注）

## [2.5.3] - 2026-11-18 12:42

### Fixed（rc.3 破坏性变更：{{cwd}} 变量）
- **症状**：dsh 报 `unknown prompt variable "{{cwd}}" in section "deployment:persona-suffix";
  registered variables: provider, model` → 本轮运行失败
- **根因**：rc.3 收紧 prompt 变量白名单（只剩 provider/model），我们的 cordis.patch.yml
  persona suffix 里 `Your working directory is {{cwd}}.` 不再合法
- **修复**：改为静态文本 `Your working directory is the dsh workspace root (see AGENTS.md for path mapping).`
  ——AGENTS.md 第 57 行已有完整工作区路径，这行本就冗余
- **附带修复**：库里的 cordis.patch.yml 之前只有 59 行（仅 harness 挂载），
  现同步为运行副本完整版 505 行（含 persona/web/model provider）——真正实现一键开箱

## [2.5.2] - 2026-11-18 12:35

### Changed（dsh rc.3 升级实测）
- dsh 已升至 **0.2.2-rc.3**，全量验证通过（26+40+30/30、config_check、探针、服务健康）
- 记录 rc.3 两个真实变化：① pnpm 路径迁到 `primary-runtime/dependencies/pnpm`；
  ② virtual store 从 junction 路径变物理路径（pnpm update 报 ERR_PNPM_UNEXPECTED_VIRTUAL_STORE）
- `setup/install.ps1` 的 pnpm 路径已更新为 rc.3 新路径
- 实测：AGENTS/env/cordis/junction/插件/会话全部保留；web searxng provider 保留；
  bundles 少 `dsh-experimental-agent-team-profile`（AgentTeam 改具名，不影响本 harness）

## [2.5.1] - 2026-11-18 11:45

### Changed（A2 全栈配置一致性）
- `config_check.py` 从 env-vs-INI（23 键）扩展为**四层检查**：
  ① env vs INI ② cordis llama contextWindow vs env CTX（跳过 ollama 的 1000000）
  ③ AGENTS.md 引用的 skill 都存在（外置后防死链）④ skill keywords 非空/无重复（防检索失效）
- `regression_check.py` 加入该检查 → **门禁 29 → 30/30**
- 负向测试 3/3 PASS（伪造 cordis 不一致 / 缺失 skill / 缺 keywords 都能抓到）

## [2.5.0] - 2026-11-18 11:40

### Changed（A1 可移植性改造 + 前 3 项清理）

**A1 可移植性（从"能跑"→"可复制"）**
- `p/` junction 从带时间戳的 `WorkBuddyWorkSpace/<时间戳>` 改为稳定路径 `D:/Brain/workspace`
- 新增 `setup/links.ps1`：一键重建 7 个 junction（DryRun 实测 7/7 OK）
- AGENTS.md 路径约定同步（`p/bench/xxx = D:/Brain/workspace/bench/xxx`）
- 注：脚本本身早已在唯一真源（WorkBuddyWorkSpace/bench 本就是 junction 指向 Brain/workspace）

**前 3 项零风险清理**
- 归档 157 个 `_` 临时文件 + 8 个会话转储(45MB) → `bench/archive/`
- 清 `__pycache__`(1.4M) + 过期 installer.exe(276M) → `_cleanup_20261118/`（可恢复）
- `trace_report.py` 加"数据不足"提示（避免把机制未触发误判为故障）

### Tests
- 26 + 40 + 29/29；7 junction 可达；探针 11:37:06（晚于 AGENTS 修改 11:36:32）

## [2.4.1] - 2026-11-18 11:20

### Added（版本基线章节）
- README 新增「版本基线」：dsh app.asar(9-29) vs 官方 rc.3(11-13)、llama.cpp b12244 vs b12493、
  autoparser 补丁、生产参数、#29307/#29949/v1.0.0 跟进状态、dsh 升级四个坑
- 修正头部过期版本号（v2.2.1 → v2.4.0）

### 升级状态
- dsh 升级到 rc.3 **阻塞**：Electron 桌面版只能 GUI 更新（无 CLI / feed 取不到 / 缓存 installer 是
  旧的 0.2.0-rc.2）。已完成 profile 备份 `_backup-before-rc3-20261118-1112/`，等用户手动升级后跑全测。

# Changelog

所有迭代以本地时间记录（UTC+8）。

## [2.3.0] - 2026-11-18 09:30

### Added（Part 8 绿色项 G1-G7 全部落地）

| 项 | 实现 | 依据 |
|---|---|---|
| **G1 技能自进化** | `bench/skill_draft.py`：从 trace 的成功/失败轨迹生成 skill 草稿 → `_skill_drafts/`（**人工确认后入库**） | Trace2Skill 2603.25158 / SkillCAT 2606.13317 / SkillComposer 2606.06079 |
| **G2 记忆反向修订** | 插件记 `crit_hit` trace；`bench/crit_revision.py` 检测"命中教训后仍失败"→ 生成降级建议（**不自动改 critbank**） | ReHarness 2610.12668 |
| **G3 失败时间线** | `bench/trace_timeline.py`：t_err/t_lock/t_obs 三时间点 + lag 统计 | Failure as a Process (UCL+NJU) / AgentRx 2602.02475 |
| **G4 结构化验收** | `critic_v2.json` 加 evidence/confidence/error_class/fix；confidence=low → UNCERTAIN 回退（不硬拒） | SEVA 2606.29713 / AgentV-RL 2604.16004 |
| **G5 概率校准** | `bench/audit_calibrate.py`：按门控统计有效率 → 阈值调整建议（人工确认） | SAG / SU 2609.05274 |
| **G6 双向验证** | rubric v2 加第 5 维"反向覆盖"（产物→需求），正向维度 1 也强化 | AgentV-RL 2604.16004 |
| **G7 工具语义边界** | `bench/skills/tool-boundaries.md`（8 个 skill 了）；AGENTS.md 加一行索引（3959 token，4K 内） | BFCL 43%→2% / RAG-MCP 2505.03275 |

**关键纪律**：G1+G2 成对——只生成新技能不修订旧技能会让错误经验加速积累；
所有降级/入库都需要人工确认，脚本只生成建议不自动生效。

### Tests
- 26（turn-guard）+ 40（new_guards，新增 G4/G6 两项）+ 门禁 29/29

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
