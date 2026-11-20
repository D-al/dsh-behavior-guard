# 资产地图：我们有什么、在哪、何时调用

> 用户 2026-11-20 问："对话中还有哪些是资产值得补充进项目？哪些放错地方没发挥价值？
> 如何充分整理并调度资产？"
>
> 判据：**资产 = 能被再次调用的东西**。只是"留着了"的是杂物。
> 本文是"合成心智"的**资产调度中枢**——让 agent 在运行时知道"我有什么、在哪、何时用"。

## 1. 资产分类（按对合成心智的价值）

| 类别 | 资产 | 位置 | 何时调用 | 现状 |
|---|---|---|---|---|
| **身份/家谱** | 五层起源、决策账本、三层链、主体分析、认识论、身份锚 | `lineage/` | "我是谁/为什么这么做"时 | ✅ 已建，README 可达 |
| **证据核实** | 引用台账（104条）、citation_guard、四层判据 | `config/citation_ledger.json`、`tools/citation_guard.py`、`docs/CITATION_AUDIT_*` | 写决策/引用论文时 | ✅ 已接 run_all |
| **证据生产工具** | arXiv API 核实、引用提取、读写漏斗、幻觉扫描 | `tools/evidence/`（2026-11-20 从临时目录收编）| 需要新证据/复核时 | ⚠️ 刚收编，未接入流程 |
| **确定性器官** | 守卫 L0-L3/D1-D5、verify-on-edit、控制回合、Critic rubric | `index.mjs`、`config/GUARD_MANIFEST.yaml`、`config/rubrics/` | 运行时自动 | ✅ 生效 |
| **教训库** | CritBank 9 条、skill 卡 7 个 | `config/critbank.json`、`skills/` | 命中门控时 | ✅ |
| **成长卡** | CAPABILITY_LADDER（25卡）、roadmap_check | `CAPABILITY_LADDER.yaml`、`tools/roadmap_check.py` | 选下一步/爬梯时 | ✅ |
| **本机实测基线** | 性能基线、显存账、温度曲线、读写漏斗 18.2% | 项目 MEMORY.md + `docs/history/tuning/` | 判断"加速是否有效"时 | ⚠️ 散落，部分只在记忆 |
| **现场 trace** | `_trace.jsonl`、`_audit_feedback.jsonl` | `bench/`（workspace）| 证据分层/审计时 | ⚠️ 在 workspace 不在项目 |

## 2. 对话中产生、但差点丢失的资产（本轮已救回）

这些是我们这几天对话的产物，写在 `D:/Brain/_cleanup_20261118/`（一个名字像"清理垃圾"的目录）：

| 资产 | 价值 | 处置 |
|---|---|---|
| `verify_arxiv_api.py` | **权威源直连核实**——比 WebFetch 逐篇更可靠，是认识论免疫系统的核心工具 | ✅ 收编 `tools/evidence/` |
| `extract_citations.py` | 全量引用提取，86篇的发现靠它 | ✅ 收编 |
| `rw_funnel.py` | "识字率"量化：read→write 转化 18.2%、6/8 会话读循环 | ✅ 收编 |
| `scan_citation_patterns.py` | 可疑引用模式扫描 | ✅ 收编 |
| `_arxiv_verified.json`（140KB）| 86 篇论文的原始核实数据（标题+摘要）| ⚠️ 仍在临时目录，建议移入 `data/evidence/` |
| `_title_compare.json`（48KB）| 项目声称 vs 真实标题的逐条对照 | ⚠️ 同上 |
| 大量 `_a1_e*.json` / `_m8_e*.json` / `_events_*.json` | 现场事件快照（盯梢用）| ❌ 一次性诊断数据，保持临时目录，不入库 |

**关键教训**：把"证据生产工具"放在名为"cleanup"的目录，等于把它们标记为可删。
**工具的位置决定它的命运**——这是"资产放错地方"的头号案例。

## 3. 放错地方、没发挥价值的资产（待处理）

### 3.1 只在对话/记忆里，不在项目里
- **用户偏好规则**：不 sleep 等子任务、方案必须沉淀进活文档——在 `~/.workbuddy/MEMORY.md`，
  项目里 agent 运行时看不到。建议：提炼成 `lineage/WORKING_CONTRACT.md` 的项目级版本。
- **"识字率"类比**：用户的核心洞察（读写=决策+准确执行），只写进了 FILE_RW_CAPABILITY_PLAN 的开头，
  没有成为独立的思维模型卡。建议：建 `skills/literacy.md` 技能卡，让 agent 遇到读写任务时能调用。
- **"约束最优"概念**：刚写进 DECISION_AGENCY，但 CAPABILITY_LADDER 的卡片里没有这个判据。
  建议：在成长卡模板加"是否约束最优"字段。

### 3.2 在项目里但 README 入口够不到
- `docs/history/` 的历史叙事（五层链的展开）——与 `lineage/ORIGIN.md` 有重叠，**读者不知道先看哪个**
- `tools/` 里 43 个分析脚本 + 4 个证据工具（2026-11-20 统计），多数只在需要时被想起；证据工具已有 [README](../tools/evidence/README.md)，其余仍无统一工具目录
- `config/rubrics/` 的四套 rubric——有代码引用但无文档说明各自何时用

### 3.3 junction 资产的"受控性错位"（2026-11-20 补充）
- `config/AGENTS.md` 通篇用 `p/bench/xxx`、`bench/critbank.json` 等短路径——它们**不是错误**，
  而是由 `setup/links.ps1` 建的 7 个 junction（ADR-0016），在**生产工作区 cwd** 建立，不在仓库根目录。
- **真问题**：这些资产（`D:/Brain/workspace/bench/` 下的 `agentlab.py`/`critbank.json`/`verify_agent.py`
  等项目实测工具）**在 workspace，不受本仓库版本控制、不随仓库分发**。
  即：换机器 clone 本仓库后，AGENTS.md 引用的教训库和验证工具**不自动存在**，必须另跑 links.ps1 + 复制 workspace。
- **影响**：CritBank/agentlab/verify_agent 是"确定性器官"的一部分，却游离在资产主干之外——
  这是"放错地方"的结构性案例（功能可达，但不可移植/不可审计）。
- **建议**：把 bench 里**真正是项目资产**的文件（critbank.json、agentlab.py、verify_agent.py、
  regression_check.py 等）纳入仓库 `bench/` 真身，junction 只作为访问别名；workspace 只留运行产物。

### 3.4 数据/状态文件的归属混乱
- `docs/_s14_status.json`（看板状态）——已 gitignore ✅
- 但大量 `_trace.jsonl` 等运行产物在 workspace，lineage 引用它们时路径跨目录
- 建议：明确 `data/`（运行产物，gitignore）vs `config/`（台账，入库）vs `lineage/`（家谱，入库）三分

## 4. 如何调度：三层调用机制

### 4.1 静态调度（README 入口表）✅ 已有
`README.md` 的"你是谁→从哪读起"表是资产的第一入口。已加 lineage 行。

### 4.2 动态调度（agent 运行时自查）— 建议新增
建 `ASSET_INDEX.json`（机器可读资产清单），字段：
```
{id, kind, path, when_to_use, authority, last_verified}
```
agent 在关键节点（写决策/引用/评审/选卡）查这个索引，而不是靠记忆"好像有个脚本"。
这与已有的 `GUARD_MANIFEST.yaml`（三副本清单）、`skills/` 卡是同族机制。

### 4.3 校验调度（防止资产失效）— 部分已有
- `citation_guard` 校验引用 ✅
- `consistency_guard` 校验三副本 ✅
- **缺**：证据生产工具的可用性校验（收编后应进 run_all 或 smokescreen）

## 5. 优先级建议（对合成心智价值最高）

| 优先 | 动作 | 理由 |
|---|---|---|
| P0 | 把 4 个证据工具接入流程（参数化路径 + 入口说明）| 认识论免疫系统的"器官"，不能只是摆设 |
| P0 | 把 `_arxiv_verified.json` 移入 `data/evidence/` 并在 ASSET_MAP 登记 | 86 篇核实的原始证据，丢了要重做 |
| P1 | 建 `ASSET_INDEX.json` 机器清单 | 让 agent 运行时能调度，而非靠人记 |
| P1 | 抽 `literacy.md` 技能卡 | 用户"识字率"洞察是可复用的读写决策框架 |
| P2 | 整理 docs/history vs lineage 的重叠 | 避免"两份家谱"的认知负担 |
| P2 | 项目级 WORKING_CONTRACT（不sleep/沉淀规则）| 让运行时 agent 继承这些纪律 |

## 6. 一句话总结

**我们的资产不缺，缺的是"调度"——工具在 cleanup 目录、洞察在对话里、数据在 workspace，
三者都没进入 agent 运行时能看见的地方。合成心智的下一步不是加新器官，
而是把已有器官接进神经系统（入口 + 索引 + 校验）。**
