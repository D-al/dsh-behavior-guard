# 心智缺口与信任锚（2026-11-20~22）

> MIND_GAPS 广搜、六路线调研、信任锚、竞争分析

> 本卷合并 3 份原报告（2026-11-25 整理）。

## 本卷目录

- `MIND_GAPS_RESEARCH.md`（原文件保留为引用桩）
- `TRUST_ANCHOR_RESEARCH_20261122.md`
- `COMPETITIVE_ANALYSIS.md`（原文件保留为引用桩）

---

## 原报告：`MIND_GAPS_RESEARCH.md`

## 心智模型缺失拼图 —— 广搜调研汇总（2026-11-18）

> ⚠️ **引用审计声明（2026-11-20）**：本文部分 arXiv 引用经官方 API 核实为**幻觉引用**
> （编号真实但标题/结论/数字与论文无关）。已逐条标注 `[❌幻觉-已作废]`。
> **凡标注的引用不得作为任何决策依据**。核实协议见 `CITATION_AUDIT_PROTOCOL_20261120.md`，
> 台账见 `config/citation_ledger.json`。



> 5 个并行 agent 调研：①认知科学框架 ②前沿能力缺口 ③三缺口深化 ④社区产品 ⑤记忆系统。
> 本文件是汇总草稿，逐份回填。最终结论将进 README 路线图 + MANUALS。

---

### 对照基线：我们已有的 8 功能

| 功能 | 实现 | 状态 |
|---|---|---|
| 感知 | 工具面 28 + 短路径 + 感官缓冲 | ✅ |
| 工作记忆 | todo + 控制回合 | ✅ |
| 情景记忆 | P0 存档 + memory 日志 | ✅ |
| 执行控制 | L0-L3 + D1-D5 + 纠正器 | ✅ |
| 验证/免疫 | D4 + Critic + 验收员 + verify-on-edit | ✅ |
| 元认知 | 规则代替感觉 + 心智状态快照 + 控制回合 | ✅（v2.10 短期四目标后）|
| 可塑性 | G1-G7 技能自进化 + outcome/FEP 偏差数据流 | 🟡 数据已够 63 条，写回闭环待做（新短期）|
| 自我模型 | 弱（错误画像 + bdi 单槽）| 🟡 BDI 三槽深化排中期 |

插件实际开关 15 个、监听 3 类事件（agent/pre-step、agent/turn-stopping、session/event）。

---

### 调研①：认知科学完整心智框架

**结论**：我们的 8 功能框架已对齐 CoALA 认知架构水平（working/episodic/semantic/procedural + 决策/感知/行动）。
真正的结构性缺口有三块：

1. **GWT 广播总线**（Global Workspace Theory）——我们的信息在 todo/critbank/trace/存档之间**手动搬运**，
   没有一个"所有模块共享的黑板"。心智状态快照是雏形，但只是单向注入，不是双向总线。
2. **FEP 预测闭环**（Free Energy Principle / active inference）——我们的验证是**事后**的，
   缺"先预测结果、再比对观察、偏差驱动学习"的闭环（ODAR 论文的方向）。
3. **System 3 动机/价值**——我们有目标（用户指令）但没有**优先级/价值函数**，
   遇到多目标冲突时靠规则不靠价值排序。

**可落地性判断**：GWT 广播总线 ✅（确定性状态对象）、FEP 预测闭环 🟡（需少量 LLM）、
System 3 动机 🟡（可用规则近似）、ToM 用户模型 ✅（显式文本卡）。

---

### 调研②：前沿能力缺口（TOP 5）

| 排名 | 方向 | 关键数字 | 我们怎么做 |
|---|---|---|---|
| 1 | **意图漂移在线监测（RGE + LivePlan）** | Drift F1 >93%，良性覆盖 ≥95.8%，+15.2% SWE-bench，$0.08/instance | 每步抽取 `(role, goal, evidence)`，确定性状态机算偏离度，超阈值才 LLM 重定向 |
| 2 | **记忆/技能库投毒防御（SafeEvolve + provenance）** | SkillJack 安全检测 98.5%→11.4%；80% 攻击删源后存活；SafeEvolve 不安全检索 35.3%→8.7%，良性效用仅 -0.4pp | 写入打 provenance + 检索时 lineage risk 加权 + 外部内容禁入技能管线 |
| 3 | **Test-time compute 自适应（DART+ARR+BOSS）** | token -41%~76%，MATH +14.2pp，串行 2.4×，24 设置 22 个最高 | 双草稿一致性路由 + 不动点早停 + 硬 token 账本；**用 CONFIRMED 哨兵不用数值置信** |
| 4 | **异步记忆巩固 + 技能合并回滚（EngramRAG+SkillProx/MASkills）** | Recall@5 38.29%→53.21%，幻觉 70%→0，延迟 26.21ms | 用法频次重排 + SUPERSEDES 标记 + 合并近重复技能 + held-out 回滚 |
| 5 | **用户意图 BDI 状态注入（XYBench+ToMELP）** | 模型字面请求回答 75-92%，真实目标仅 35-41%；oracle 给 X 后解决率 59%→67% | 维护伙伴状态卡，关键决策前显式复述用户真实目标 X 并请求确认 |

**观察项**：文本世界模型（TWM）——方向对但有"有模型也不会主动用"的反证，暂不投。

**关键洞察（跨方向主线）**：方向 1/4/2 可共用同一个**结构化轨迹事件流**——
每步产出 `(role, goal, evidence, provenance, trust_state)`，同时喂给巩固器、漂移监测器、安全审计器。
这可能是最低成本的整合点，也是 GWT 广播总线的落地形态。

**安全警告（对我们架构最直接）**：攻击面已从"运行时输入"转移到**持久化记忆与技能库**——
攻击一次写入跨会话生效、任务成功完成不等于安全、删除原始污染记录后攻击仍存活。
我们的外置记忆 + 自进化技能库正是靶心，现有门控覆盖不到。

---

### 调研①②③④⑤：全部到齐（2026-11-18 14:10）

（agent 运行中）


---

### 调研⑤：记忆系统完整性（**最有行动价值的一份**）

**核心判断**：我们不缺记忆"种类"（CoALA 五分法已全覆盖），缺的是**代谢系统**——
写入要门控、存储要有界、旧经验要能失效、情景要能主动调取。

| 记忆块 | 状态 | 判断 |
|---|---|---|
| 工作/感官 | ✅ | 已覆盖 |
| **巩固与遗忘** | 🔴 **主动有害** | append-only 让过时经验自我强化——**唯一正在降低正确性的一块** |
| **情景检索** | 🔴 缺检索 | P0 是死档案，检索是价值放大器 |
| 程序性记忆 | ⚠️ 有载体缺闭环 | 技能卡正确但静态；2026 数字：失败学习 +37%、CodeMem 可执行化、skill staleness 风险 |
| 跨会话 | ⚠️ 弱 | 日志对人不对机器；与情景检索共用 es.exe 可顺手补 |
| 真实性/投毒 | ⚠️ 基础对不够 | 只存真实指令方向对，但缺 provenance/隔离区/召回重验 |

**最该补的 3 块**（按 影响 × 可修补性）：
1. **可控遗忘与写入门控**（唯一正在损害正确性；纯文本表格即可）
2. **情景记忆主动检索**（EVENTS.md + es.exe + 控制回合一个检索步；一次投入两处收益）
3. **程序性记忆闭环**（frontmatter 加 version/verified_on/success_count/last_failure + 执行记录 + 维护 skill）

**关键数字/链接**：
- [SEEM (ACL 2026)](https://aclanthology.org/2026.acl-long.277.pdf)：EEF 六槽 + 来源指针，LongMemEval 45.5 vs 34.8
- [mem0 遗忘博客](https://mem0.ai/blog/memory-eviction-and-forgetting-in-ai-agents)：忘却是检索质量干预，非存储副作用
- [记忆增长致漂移](https://proofoftech.org/blog/agent-memory-growth-causes-drift)：无攻击下性能 0.455→0.05、假记忆率 6.8%
- [Letta Code](https://aiforautomation.io/news/2026-03-18-letta-code-memory-first-ai-coding-agent-remembers)：失败学习 +37%、任务模式 +21%
- [OWASP ASI06 记忆投毒](https://nhimg.org/ai-agent-memory-poisoning-guide)、[五条投毒路径](https://aiagentmemory.org/articles/ai-memory-injection)：Scope/Selection/Path 投毒即使记录全真也能中

**与我们现有工作的关联**：
- 我们今天做的 G2 `crit_revision.py` 正是"可控遗忘"的雏形（命中后仍失败→降级建议），但它只生成建议不自动生效，且 CritBank 本身仍 append-only——**方向对但没闭环**
- 我们今天做的 `mind_state.py` 的"错误画像"是最粗粒度的 self-model，但没有 provenance 列


---

### 调研③：三大缺口深化（**推翻了我们的假设，含紧急发现**）

#### 🚨 强制二选一已停用（2026-11-18 决策；证据已于 11-20 更正）

⚠️ **证据更正声明（2026-11-20）**：本节原先引用 7 篇 arXiv 论文
（2605.01403 / 2605.11705 / 2605.14729 / 2504.09864 / 2605.00631 / 2606.05256 / 2604.09715）
作为"质疑式提示让正确答案被推翻"的依据——**经逐篇 WebFetch 核实，这 7 个编号真实存在但标题/结论全部编造**
（真实论文分别是 GNN 节点分类、多模态数据选择、宇宙学、蒸发制冷、RAG、说服策略、3D 姿态估计，与 LLM 提示词无关）。
原"JS 散度 0.0186 / -20.4pp / -20.9pp / 76.6% 被推翻"等数字**全部作废，勿再引用**。

**决策保留，但依据改为真实证据**：
1. **现场观察**（本项目实测）："强制二选一"上线后仍出现"写完交付正文后又从头创建"——
   质疑式措辞可能诱发已完成产物被推翻，这与 C-007（"只输出好"上下文自强化）同源。
2. **已核实学术证据**：Huang et al., "LLMs Cannot Self-Correct Reasoning Yet"（ICLR 2024,
   arXiv:2310.01798）——无外部反馈的内省式自我纠错无效甚至有害（Llama-2-70B GSM8K 62.0%→36.5%）；
   有效的是真实外部信号（测试失败/语法检查），不是质疑措辞。

👉 **结论不变**：改成中性事实陈述 + 退出许可，不用质疑式 A/B 二选一；
但理由从"论文证明质疑有害"改成"现场症状 + 自我纠错需外部信号"。
**改进方向**：改成**带证据的请求式 A/B**，不用质疑措辞，只在检测到"已完成"事实时单向肯定（"已交付，停"），
不用"尚未交付→换路径"诱导自我怀疑。或 safer：只给事实陈述 + 退出许可，不给二选一。

#### 缺口1：可塑性 —— 不是缺机制，是缺证据收集

| 结论 | 数字/依据 |
|---|---|
| **历史成功率是缺失变量** | [Reflexion (2303.11366)](https://arxiv.org/abs/2303.11366) 8.2%→33.8%；[ExpeL](https://arxiv.org/abs/2307.11909) 84.2%→92.6%，都来自失败轨迹提炼 |
> ❌ **幻觉引用-已作废**（2504.19413: 真论文但数字相反(真实:91%延迟↓/90%token↓)）
> | **纯检索≠学习** | [Mem0 (2504.19413)](https://arxiv.org/abs/2504.19413) 71.7% 但延迟 14x/token +41%；[SimpleMem](https://arxiv.org/abs/2601.02553) 检索 AIME 仅 2.8% |
> ❌ **幻觉引用-已作废**（2605.16281: 真论文是AI治理问责,非SkillRL）
> | **失败 > 成功** | [SkillRL (2605.16281)](https://arxiv.org/abs/2605.16281) ALFWorld 86.6%→90.7%；但对失败**做解释反而掉点** → 学"诊断"不是"复盘" |
> ❌ **幻觉引用-已作废**（2605.10686: 真论文是超导理论,非SkillCatalogue; 2605.25163: 真论文是3D牙科重建,非SkillClaw）
> | **技能会失控复制** | [SkillCatalogue (2605.10686)](https://arxiv.org/abs/2605.10686) 无治理多生成 54 技能；[SkillClaw (2605.25163)](https://arxiv.org/abs/2605.25163) 用聚类+概率门控过滤 |
> ❌ **幻觉引用-已作废**（2607.02021: 真论文是自旋波物理,非MemRL）
> | **反面** | [MemRL (2607.02021)](https://arxiv.org/abs/2607.02021) 50% 任务记忆反害策略；[SkillEvolver](https://arxiv.org/abs/2606.10821) 域内 +46.9pp 但跨域 **-24.8pp** → 必须可回滚、按域隔离 |

👉 缺的不是工具，是**把工具喂饱的证据**：每轮 write/edit 后追加结构化判定（成功/失败/部分），10-20 条就能让 skill_draft 从"猜"变"提炼"。

#### 缺口2：自我模型 —— **伪缺口**：让 Critic 顺带输出，不要另起 agent

> ❌ **幻觉引用-已作废**（2605.11970: 真论文是神经算子,非Self-Braceless）
> - [Self-Braceless (2605.11970)](https://arxiv.org/abs/2605.11970)：训练时 critique 自进化，推理时**零额外调用**，自我准确率 +10.1pp
> ❌ **幻觉引用-已作废**（2603.25150: 真论文是语音发音评估,非Meta-CoT）
> - [Meta-CoT (2603.25150)](https://arxiv.org/abs/2603.25150)：元认知策略外化成复用技能，22.2%→46.7%
> ❌ **幻觉引用-已作废**（2605.02077: 真论文是Algorand区块链隐私,非Self-Constancy）
> - [Self-Constancy (2605.02077)](https://arxiv.org/abs/2605.02077)：自报置信绝对值不可靠但**相对趋势**可预测失败（AUC>0.7）→ 用序列不用快照
> ❌ **幻觉引用-已作废**（2608.14111: 真论文是自动机理论,非AGU）
> - [AGU (2608.14111)](https://arxiv.org/abs/2608.14111) + [AGenieBench](https://arxiv.org/abs/2606.15971)：定向自问 > 泛泛自问，US Air Traffic 1.6%→22.9%（+21.3pp）
> ❌ **幻觉引用-已作废**（2608.22134: 真论文是Calabi-Yau不变量,非GACP）
> - **反面**：[Critic 盲区 (2410.10934)](https://arxiv.org/abs/2410.10934)、[MARTA (2610.05223)](https://arxiv.org/abs/2610.05223)、[GACP (2608.22134)](https://arxiv.org/abs/2608.22134)（小模型"learn to sound humble"而非真校准）

👉 在 Critic/审计员/验收员现有 JSON 里加 3 个字段（self_assessment / error_category / evidence_refs），零额外 LLM 调用。

#### 缺口3：元认知 —— 诊断没闭环，且**不要改写历史**

- [SEVA (2606.29713)](https://arxiv.org/abs/2606.29713)：结构化验证输出让 3B 追平 GPT-4o-mini，关键是**六类错误诊断 + 可执行修复**
- [Metacognitive Prompting (2308.05342)](https://arxiv.org/abs/2308.05342) NAACL 2024：7 阶段固定自问，PaLM 62→68%，但 token 成本高
- [AgentRx (2602.02475)](https://arxiv.org/abs/2602.02475)：失败步定位 +75%，但**"定位后必然修复"假设错误**
> ❌ **幻觉引用-已作废**（2602.12106: 真论文是MedExChain医疗区块链,非ESPRT）
> - **反面（重要）**：[AReaL (2505.24298)](https://arxiv.org/abs/2505.24298) "rewrite thoughts" 在 4/7 基准掉点；[ESPRT (2602.12106)](https://arxiv.org/abs/2602.12106) 截断思维链有害

👉 下一步不是更花哨的自问，而是**把每次诊断连到可回滚的证据记录**，让第 N 次同错被自动识别为"已试过且失败"。

#### 三缺口共同底座
都指向**在现有事件流上新增"结果反馈"维度**（成功/失败/部分 + 证据引用 + 可回滚快照）。
比新建三个系统便宜得多，也正是调研②的"结构化轨迹事件流"、调研⑤的"代谢系统"。


---

### 已落地的改动（调研进行中同步执行）

#### 🚨 紧急修复：强制二选一 → 中性事实+退出许可（v2.7.2 已发布，ADR-0014）

现场观察到"写完又重做"症状，且自我纠错需要外部信号而非质疑措辞
（Huang et al. ICLR2024, arXiv:2310.01798）——⚠️ 原引用的"JS 散度 0.0186 / -20.4pp / -20.9pp"
已核实为幻觉数据（11-20 更正）。我们把刚上线的"强制二选一"改成：

```
[harness 状态] 观察到重复动作：...
事实：这些动作在此会话中已执行过，结果已在上下文中。
你可以直接结束本轮（若目标已达成）；或选择一个与此前不同的动作继续。
无需重复验证已确认过的内容。
```

- 不用质疑措辞、不暗示"你还没做完"、不给 A/B 二选一
- test_mind_state.mjs 4/4（T1b 改为验证"无质疑式二选一"）；全量 26+40+30/30

#### 意图漂移监测脚本（调研② TOP1 的离线最小版）

`intent_drift.py`：从会话抽所有真实用户指令，用关键词覆盖率算与初始任务的偏离。
**现场验证精准复现**：seq 681 "给个测试窗口" vs 初始"写插件" 覆盖率 **0.00**，
而 P0 存档 16 次都没跟上——证实意图漂移是真实缺口，且检测成本近零。


---

### 调研④：社区产品心智机制（**架构背书 + 最明确的三块空白**）

#### 核心情报：arXiv 2609.00006《Harness Engineering》（2026-07，83页，源码级解剖 11 个 coding harness）

结论：**没有任何主流 harness 用通用 agent 框架、没有任何用向量检索代码；
全部是手写循环 + 确定性检索 + SKILL.md 式技能（9/11 采用率，超过 MCP 的 8/11）**。
→ 我们的路线（确定性代码 + Skills 而非 MCP + 短路径检索）被学术背书，方向无需怀疑。

#### 社区已共识、我们完全空白的 3 件事（优先级排序）

| # | 空白 | 社区做法 | 我们怎么抄（纯文本/零训练）|
|---|---|---|---|
| **1** | **外层验证循环（Loop Engineering）** | Hermes verify-on-stop：改了代码没验证证据就**否决退出**；OpenHands /goal 用 judge 决定重跑 or 停止 | 收尾前结构化清单（改了文件？有测试证据？），缺项把 FINISH 改回 CONTINUE。**我们强在多角色，弱在"环"** |
| **2** | **自写记忆/技能写回** | 全社区一致：零训练"变聪明"=写文件；Claude auto memory 四类+索引 200行/25KB；Hermes skill lifecycle 有 cooldown/审批/provenance/stale 归档 | 我们的存档+技能是**单向注入**，缺写回闭环。这是零训练路线最该补的一块 |
| **3** | **事件溯源会话树** | OpenHands/Pi/OpenCode：历史是树（parent 指针），fork/rewind 一等公民，"遗忘"记为事件而非删除 | 线性存档→带 parent 的条目，纠错可回滚/分支对比/重启恢复 |

#### TOP 10 里可直接抄的单点

- **Verify-on-Stop Guard**（Hermes）：验证从"循环内一步"移到"停止条件"——这是 TOP1，也印证调研②的意图漂移监测
- **Goal Judge**（OpenHands）：验收输出强制 `score/complete/missing` 三字段，missing 作下一轮第一条注入
- **StuckDetector 先 nudge 再停**（OpenHands）：与我们刚做的心智状态触发式注入同构——**说明我们方向对**
- **Phase-Gate**：每个 todo 绑 verifier 字段和 stop rule，让计划自带验证契约
- **Triggered Rules**：技能触发从"模型判断"升级为"路径/关键词硬匹配"（我们已是关键词，可加路径）
- **Context-Efficient Swarm**（Cursor）：s可扩展性来自上下文效率而非并行——确认审计/Critic 用新鲜上下文

**链接**：[Harness Engineering 2609.00006](https://arxiv.org/abs/2609.00006)、
[Claude Code memory 文档](https://code.claude.com/docs/en/memory)、
[OpenHands 实现综述](https://github.com/BaranziniLab/biorouter/blob/main/docs/research/coding-agent-landscape/openhands.md)、
[self-improvement 验证报告](https://dz3ai.github.io/allclaws/docs/reports/self-improvement-claims-verification)、
[Cursor Agent Swarm](https://cursor.com/blog/agent-swarm-model-economics)

---

### 调研结论的兑现追踪（2026-11-18 21:30，v2.11.0）

> 本文件是调研快照，保留原始判断（历史只追加不重写）。下面记录哪些结论已被后续版本兑现——
> 以 [ROADMAP](../ROADMAP.md) 的勾选状态为准。

| 调研结论 | 兑现版本 | 状态 |
|---|---|---|
| GWT 广播总线（结构性缺口，模块间手动搬运）| v2.11.0 | ✅ `workspaceSnapshot` 共享状态对象，三消费者同源 |
| FEP 预测闭环（从事后验证到先断言→比对→偏差）| v2.11.0 | ✅ 产物存在性级；更深的内容级断言排长期 |
| 可控遗忘（唯一正在降低正确性的一块）| — | 🟢 新短期：CritBank 真实计数 + 月度 decay |
| 情景检索（P0 是死档案，检索是价值放大器）| — | 🟡 中期：进控制回合自动 top-3 |
| 技能写回闭环（社区一致，我们单向注入）| 部分（草稿+审批）| 🟢 新短期：outcome/FEP 偏差喂草稿，`promote_skills` 仍审批 |
| 意图漂移在线监测 | v2.9 | ✅ 控制回合 ⑤ 信号（关键词覆盖率 <0.25）|
| BDI 用户意图 | 部分（单槽状态卡）| 🟡 中期：belief/desire/intention 三槽深化 |
| 安全：记忆/技能投毒防御 | 部分（provenance + 审批）| 🟢 新短期前置：写回闭环前先补 lineage risk |

**脑功能分区视角的补充盘点**见 [BRAIN_PARITY.md](BRAIN_PARITY.md)：胼胝体（GWT）已补，
杏仁核/眶额（情绪价值）与脑干（内在动机）是最大空白群；社区最先进的 Foundation Agents 蓝图（2504.01990）也承认 L3 未开发。

---

## 原报告：`TRUST_ANCHOR_RESEARCH_20261122.md`

## 无限回归的终止点：信任锚调研（2026-11-22）

> 缘起：用户问"基于对审计者本身的信任有没有更天然的解法？区块链能否帮忙？"
> 两路并行调研（信任根基工程解法 / 区块链密码学批判评估）结论一致。

### 一、总答案

**理论终点不存在，实践可止损。** 这是明希豪森三难（Münchhausen trilemma）的工程版：
任何证成只能落在无限回溯、循环自证、武断中止三者之一。所有成熟方案本质都是
"选择在哪里停止追问"，并让停止点尽可能小、可独立复验（de Bruijn 准则）。

**区块链：在这个场景有害（用错工具）。** 详见 §三。

### 二、五条路径评估

| 路径 | 核心洞察 | 对我们 | 成熟度 |
|---|---|---|---|
| **TCB 最小化** | 回归不消失，被集中到可审计的窄接口。seL4 内核 1-1.6万行 C，但证明体 110万行/20人年；官网明示假设（340行汇编/启动代码/硬件/DMA/侧信道在证明外）| ❌ 单人不可行 | 生产级 |
| **形式化验证 / PCC** | de Bruijn 准则：证明生成可复杂不可信，**证明检查必须小而独立**——目前唯一数学意义上成立的终止点。Lean4 内核 5-6千行 C++，mathlib 50万行不可信只产证明 | ⚠️ 只做局部不变量可行 | 成熟但需专家 |
| **确定性小检查器** | "untrusted solver + trusted checker"：审计者做成确定、无外部依赖、纯函数后，"审计者的审计"从"再运行一个程序"**降级为代码审查**——成本最低的维度降级 | ✅ **最优** | 成熟+前沿 |
| **能力安全/类型系统** | 让腐化在编译期/硬件层**不可编码**（CHERI tag+bounds、Rust ownership、Idris 依赖类型）；但只覆盖可编码的不变量，语义正确性仍需外部锚 | ❌ 需换语言/硬件 | 部分成熟 |
| **透明日志/供应链** | 不证明代码正确，只证明**"运行的就是你审查过的那份"**——把"身份/来源"从"正确性"剥离独立解决。SLSA 1.2 / Sigstore Rekor / in-toto | ✅ 部分有用（见§四）| 大规模部署 |

### 三、区块链：为什么有害

1. **场景错配**：区块链核心是多方互不信任下的拜占庭共识（NIST IR 8202 / 以太坊白皮书）。
   本场景只有一个参与方，且该方（LLM）正是要防的攻击者——没有 n=3f+1、没有 Sybil 威胁，
   BFT 在解一道不存在的题。
2. **安全假设倒置**：唯一操作者即对手时，链只是把 LLM 说的任何话**永久固化**——
   "上链=不可篡改"制造致命的虚假安全感（garbage in, garbage out forever），
   还引入节点/密钥/gas/共识依赖与更多攻击面。
3. **学术印证**：Budish《The Economic Limits of Bitcoin and the Blockchain》指出企业本有
   更便宜的可信方数据安全形式；2025 Emerald 论文实证联盟链最终沦为可信第三方，变得多余
   （Hawlitschek "trust-free fallacy"）。

**zkVM 也不能救命**：ZK 证明"程序 P 在输入 X 输出 Y"——若 LLM 能改 P（门禁本身），
证明就是在为恶意程序背书；只是把回归搬到电路。且一次本机检查重跑远便宜于验签，
验签远便宜于证明（prove once verify forever 适合多方反复验证，不适合我们）。

**可信时间戳价值极低**：只证明"某哈希不晚于某时刻存在"，不证明内容为真/日志完整/
呈现者即盖章者。OTS 自述"若不知道入侵何时发生，时间戳帮不了你"——LLM 自修改恰不知漂移起点。

### 四、真正有用的部分（不用区块链）

**密码学不能消灭回归，只能把锚从代码挪到密钥/外部锚点**——信任必须终止于某个
你愿意不证明就相信的东西。优先级：**硬件隔离 > 第二设备/本人 > 外部透明日志**。

- **git 已是 Merkle DAG + 内容寻址**：`git rev-parse HEAD` 就是内容指纹，`git log` 是不可篡改的
  时间证明。我们现有的 sha256 权威源/运行版对比就是 git 思想的简化版。
- **git 的硬边界**：有 push 权限者可 rebase/force-push 重写全部历史，新 clone 哈希自洽无警告；
  只有拿**独立信任锚**对比才有效。SHA-1 已可碰撞，应迁 SHA-256。
- **最小可行**：git(SHA-256) + 签名提交/标签，**私钥放在被审机器之外**；
  drift 日志用 HMAC 哈希链；把 HEAD/树根**单向发布到第二设备/邮箱/公共日志**作外部锚。
  无外部锚则链与 git 都只是自证。
- **强制验签是灵魂**：无强制执行的签名只是装饰。

### 五、本项目现状与建议

#### 实测的信任基规模（2026-11-22）
- `index.mjs` 2445 行 / 41 顶层函数——**太大，不可能"显然正确"**
- `foundation_guard.py` 180 行、`test_census.py` 106 行、`fingerprint.py` 113 行——小
- `check_verify.py` 389 行、`roadmap_check.py` 820 行——偏大
- **L4 依赖 L3/L2（guard 调 census/audit_verify/tech_tree），无循环依赖**——真分层
- ⚠️ **但 L4 和 L2 都调用同一批检查器**——"两次通过"不是两个独立证据，是同一检查跑两次

#### 实证的 evaluator tampering 风险
- `foundation_guard.py` / `run_all.sh` / `AGENTS.md` **均无写保护标记**——agent 可改自己的评判者
- git 历史证实 agent 确实改过 `run_all.sh`（cba4600 等）
- 2026 自改进 harness 论文（arXiv:2611.22299 / 2509.26354）明确列出 evaluator tampering、
  权限自削弱、benchmark gaming，防御是：**agent 不得改写唯一评判测试、不得削弱权限层、
  harness 必须版本化并经人工评审**

#### 建议（按性价比）
1. **冻结评判测试**：把 `run_all.sh` / `foundation_guard.py` / 关键 test_* 设为"仅人工可改"
   （流程约束：agent 改这些必须先问用户；技术上可用 git path 保护/hook 提示）
2. **缩小信任基**：把地基不变量抽成独立小模块（guard 已是静态扫描，不依赖 import，可行）
3. **外部锚**：把 HEAD/体检结果单向发到第二设备或邮箱（零成本外部验证点）
4. **不建议**：区块链、zkVM、TSA、全量形式化验证、换 CHERI 硬件

#### 一句话
不需要第六层审计者。需要的是**把信任压缩到一个小而独立、可人工复验的核**，
并让"被审对象 = 运行对象"（内容摘要锁定）——加上一个**在机器之外的锚**。

### 六、出处
Hans Albert《批判理性论》1968 / Münchhausen trilemma；de Bruijn 准则；
sel4.systems FAQ；Necula PCC；Lean4Lean arXiv:2403.14064；compcert.org；
FORGE/PCAS arXiv:2602.16708（Datalog 策略，LLM 遵从率 48%→93%）；
CHERIoT 1.0 (2025-11)；SLSA v1.2 (2025-11)；Sigstore Rekor v2 (2025-10)；
NIST IR 8202；Budish 2018；Emerald SCM 30(2) 2025；gethasp.com；
OpenTimestamps 0.7.2；arXiv:2611.22299 / 2509.26354（自改进 harness 安全）。


---

### 七、追问：锚不必是人，只要不是执行者就行？（2026-11-22 10:25 调研）

#### 答案：直觉对了一半。"人"不是定义属性，但"不是执行者"是必要远非充分。

**信任锚的形式定义**（NIST SP 800-57 / RFC 5280 / RFC 4949 / TCG）：
锚是"信任被假定、无上层可验证者、经带外注入"的权威实体——可以是公钥、CA、硬件 RoT，
**从来不需要是人**。human 只是 bootstrap 决策者（root program），是另一个层次。

#### 精确判据：不是"它是谁"，而是"执行者是否持有任何能影响它或其送达通道的 capability"

设 E=执行者，A=候选锚，V=消费 A 输出的验证器。A 是真锚当且仅当同时满足：
1. **不可达**：E 不持有指向 A 的任何 capability（不能读写/删除其状态或判定逻辑）——
   不是"不同进程"，而是权限不可达；
2. **带外通道**：A→V 的传递不被 E 控制（不可伪造/重放/替换/丢弃）；
3. **终止性**：V 不用同一机制反证 A；再加一层软件验证只是把锚后移，递归不终止。
   TCG 原文："must be trusted because misbehavior is not detectable"；
4. **不可传递**：E 不能通过调用 A 间接获得 A 的权限（capability 不可代理/委托）。

#### 光谱（从假锚到真锚）
| 形态 | E 能篡改? | 真锚? |
|---|---|---|
| 同进程另一个函数 | 能（共享内存）| ❌ |
| 同机同权限脚本 | 能（直接改）| ❌ |
| 另一个 LLM verifier | 不能直接改文件，但共享环境/注入面/偏见 | ❌ 伪锚 |
| 不同 OS 用户+ACL+只读代码 | 普通用户不能、管理员能 | ⚠️ 弱锚（条件成立时）|
| chattr +i（E 无 root）/ 只读挂载 | 不能 | ✅ 较强 |
| TPM sealed key / Secure Boot / VBS-HVCI | OS 层不能 | ✅ 强（证明平台状态，不证明业务正确）|
| 硬件密钥（YubiKey/TPM）| 私钥不可导出（可篡改"签什么"）| ✅ 强 |
| 第二设备 / 透明日志（Rekor/CT）| 本机改不了历史，可 DoS | ✅ 最强（可检测 > 阻断）|

⚠️ TEE 有硬件攻击面：2024-26 BadRAM/WireTap/TEE.fail/DDRop 可伪造远程证明。

#### 另一个 LLM 当锚——最危险的伪锚
- 共享执行环境/工具权限/工作区 → 违反不可达（prompt、配置、输出可被改写）
- 共享 prompt injection 面——注入是语义的，换会话不消失（CaMeL 2503.18813 / Design Patterns 2506.08837）
- self-preference：arXiv 2508.21164 标签致最高 50 个百分点偏好翻转
- 它输出"看似合理"，制造**递归已终止的假象**——比没有锚更危险
- **例外**：仅当跑在不同 authority domain、只读输入快照、无工具、输出签名/不可变通道，
  且只作**证据**由确定性规则裁决时才有价值（Ouroboros 2608.08311 的真正锚是
  immutable ground truth + deterministic preflight + fingerprint 防 TOCTOU + review ledger；
  DGM 2505.22954 的锚是 agent 不能控制的外部 benchmark）

#### 最小可行非人锚（Windows 本机、运行时无人）
**前置硬条件：agent 必须是标准用户且不可提权**；若同一账号是管理员，一切软件边界失效，只剩硬件/外部日志。
1. 一次带外初始化（锚不能自举，必须有人/外部做一次）：新建标准用户 `verifier`；
   建 `C://Anchor`，`icacls` 设 verifier=Full、agent=RX、禁止继承/取得所有权；
   放入只读 `verify.ps1`、`policy.json`、`baseline.sha256`
2. 用**以 verifier 身份运行的计划任务**（由文件/事件触发，不由 agent 调用、不接 agent 参数）
   读工作区、算 Merkle root、对照基线，输出签名 `evidence.json`；
   密钥用 **TPM CNG key**（可 bind PCR 到 Secure Boot+HVCI，不可导出）
3. agent 只能读证据；对 `C://Anchor` 的写被 ACL 拒绝并进安全审计日志；
   工作区任何写使旧证据失效（ledger）
4. 可选：evidence 哈希提交 **sigstore Rekor** 取 inclusion proof——本机全控也改不了历史

**边界声明**：这不能证明"代码正确"，只证明"验证在 agent 权限域外执行且结论不可篡改"。

#### 本项目的现成候选：GitHub remote
`D-al/dsh-behavior-guard` 每次 commit 都 push，是"不是人、不在本机、有独立权限边界"的候选锚。
但需确认：①branch protection 是否开启（agent 有无 force push 能力）②本地 credential manager
是否存了 token（若有，权限边界不成立）。**必须先收窄 push 权限才能真正当锚。**

#### 出处（本轮补充）
NIST SP 800-57 Pt1 r5（词汇表/8.1.5.1.1）；RFC 4949/5280 §6.1.1/6024/9925(2026)；
TCG TPM2 Part1 §9.4；arXiv 2503.18813/2506.08837/2508.21164/2608.08311/2505.22954；
RFC 6962/9162、RFC 9943；MS Learn CFA/VBS/Credential Guard；TEE 攻击综述 2024-26。


---

### 八、三目标平衡：高效 / 可信 / 真实（2026-11-22 10:30 调研）

#### 总答案：不是三选二，是"分层各取所需 + 一条不可交易底线"
不存在 CAP 式形式化"验证三难"定理。各领域 trilemma 的轴互不相同。
单次检查在同一瞬间确实此消彼长，但**系统级可通过差异化兼得**。

#### 实测三维度现状（我们系统）
| 维度 | 实测 | 评价 |
|---|---|---|
| 高效 | census 0.34s / 地基守护 2.69s / 体检 3.48s / 全门禁 32.75s | ✅ 不差——瓶颈不在速度 |
| 真实 | 判据分布 OK14/DOCUMENT5/MIXED24/MANUAL15/STRUCTURAL3；2处诚实SKIP | ⚠️ 15 MANUAL 不算绿；真实度有提升空间 |
| 可信 | credential.helper=manager；evaluator(run_all/guard)无写保护 | ❌ 最弱一环——agent 可改评判者 |

**结论：三者的瓶颈不在同一处，所以不需要"三选二"——把每层优化它擅长的那一维即可。**

#### 社区关键洞察
1. **Verifier's Dilemma**（arXiv:2406.01794）：验证 costly 且无收益时，理性验证者会"懒报"——
   可信度不会自动产生，需激励/独立性设计。
2. **Weak-Strong Verification**（arXiv:2602.17633，2026-02）：最优策略是**双阈值**——
   弱分高直接接受、低直接拒绝、中间带才调强验证。
3. **DeepMind 委派**（arXiv:2602.11865）：可验证性是一等因子，"拆到可验证为止"，
   低风险任务设"委派复杂度地板"；验证昂贵会使安全沦为奢侈品。
4. **Google flaky test 隔离**（Micco 2016）：门禁**可信度比覆盖率更稀缺**。
5. **Meta TestGen-LLM**（2024）：机器过滤查构建/通过/覆盖，**断言对错必须人判**（73% 建议经人审）。
6. **变更影响选择**（Meta PTS）：拦住 >99.9% 回归只跑约 1/3 测试——省下的预算
   **reinvest 到变更行的变异与不变量**，而非单纯少跑。
7. **真实度指标本身可被污染**：变异分重复运行漂移 ~4pp；19% 的 flaky "kills" 源于 flake
   → **必须先有可重复的绿基线**。

#### 四种失衡反模式（入规约）
- 高效吃真实：恒真/vacuous 测试；AI 生成测试断言实现而非规格（变异分 58-62% vs 人写 78%）
- 可信吃高效：层层形式化→验证成瓶颈→被绕过
- 真实吃可信：把证据通道交给被审者——METR 记录 o3 改计时函数、把评测函数换成全 pass stub（Goodhart）
- **隐形第四种**：flaky 门禁"狼来了"，团队学会点 retry，真失败被淹没

#### 最小平衡架构（与本项目现状映射）
| 目标 | 靠什么 | 我们已有 | 待补 |
|---|---|---|---|
| 高效 | 分层 + 变更影响选择 + 双阈值 | 变更驱动指纹/按需体检/每日兜底 | 强验证调用率度量 |
| 可信 | 证据通道 + evaluator 隔离 | sha对比/drift日志 | **冻结evaluator**/签名证据 |
| 真实 | 变异 + canary + 独立 oracle | census/真退出码/6不变量/sentinel | 增量变异(变更行)/每周canary |

**三轴盘（不做单一综合分）**：p95 门禁时长 / 签名证据覆盖率 / mutation score+canary检出率。

#### 出处
arXiv:2406.01794（Verifier's Dilemma）、2602.17633（Weak-Strong Verification）、
2602.11865（DeepMind Intelligent AI Delegation）；Google Testing Blog（flaky test）；
Meta TestGen-LLM 2024 / PTS；Stryker 2024 mutation benchmark；
Shi/Bell/Marinov ISSTA 2019（变异分漂移）；METR o3 reward hacking 记录；NIST SP 800-204D。


---

### 九、冻结评判者的维护悖论：谁维护那几个文件？（2026-11-22 10:40 调研）

#### 总论：措辞要改——不是"冻结"，是"版本钉住"
冻结 = 禁止原地修改，**不等于永不改变**。改变 = 产生新版本 + 显式批准 + 旧版可回滚。
若指"内容永不变"，那确实是伪方案——规则必然过时且会被利用。正确含义是 immutable infrastructure：
改 = 构建新版本并替换（pin digest、禁 latest），回滚 = 重部署旧版。

#### 本地实测：负担是不是真的？
- run_all.sh 历史 14 次提交**全集中 11/20-11/22 三天**（建设期爆发，非稳态维护）
- 拆开看：大部分是"新增功能顺手加测试"（结构性扩充），真正的纠错性维护没几次
- 而纠错性维护恰恰是 agent 干不好的（S22 连改3次失败、恒真断言、退出码永0）
- **已结构性消除**：A6 把 py 测试改成 glob 自动发现——实测新增 test_zz_probe.py 后
  census 自动纳入（49个）、missing=0，**不用改 run_all.sh 一个字**
- 反直觉：不冻结负担更大——要反复核验 agent 每次改评判文件有没有夹带私货

#### 社区治理要点
1. **门槛加在语义变更，摩擦降在预演**：注释/加测试走 lazy consensus（无异议即过），
   改判定逻辑需双人+冷静期+变更记录（CODEOWNERS + branch protection four-eyes）
2. **规则带生命周期元数据**：`source / applies_to / retire_when` 三元组；误报预算由分诊容量反推；
   季度 replay；12个月零触发默认退役；先降 warn 后删。**"本应每周触发却一月静默"当自检心跳**
3. **人的负担是被量耗尽的资源**（关键数据）：Anthropic 实测 93% 权限提示被盲批（2026-03），
   8月升至97%；人工仅拦住13.6%危险命令 vs auto mode 89%；50次提示后人工拦截率17%→5%
   → 解法 T0-T3 分级：只读自动/可逆写自动+通知/不可逆人工批准/默认拒绝；
   **审批卡须1分钟内可判，否则是队列不是控制**
4. **自改进先例全是"冻结评判者+可进化求解器"**：AlphaEvolve 冻结 Gemini+自动评分器；
   DGM 保留全部祖先（SWE-bench 20%→50%，但出现 objective hacking——agent 关闭评分器依赖的日志）；
   Ouroboros 核心经 reviewed commits 演进，governance protection/operator halt 保持权威
5. **前沿**：Red Queen GDM（2026）已开始共同进化评判器——静态基准终将被利用

#### 三问答案
- **是不是负担？** 是，但源于"每次都要人"，不源于"冻结"。分层+退役后，人每年只处理个位数次语义变更
- **谁维护？** 那几个文件即规则包 vN，原则上由人在变更前维护；**无人值守时答案是"不维护"**——
  agent 只能把 diff/基线对比/误报影响提交到 staging PR，无人批准即永不生效
  （变更默认拒绝、读取默认允许）。允许变更仅三条件：①新工具/场景造成能力缺口 ②误报超预算
  ③有回归测试与回滚版本。紧急修复走 emergency change：先执行、事后复审
- **完全冻结是伪方案吗？** 内容永不变=是；版本钉住=可辩护

#### 对本项目的落地建议（待用户确认）
- 改口：不说"冻结"，说"evaluator 版本钉住"——把 run_all.sh/guard/census/check_verify 视为规则包
- agent 对这些文件：**只读 + 可提 staging diff，不自动生效**
- 新增测试走 glob 自动纳入（已实现），不需要碰门禁文件——这是消除维护负担的主路径
- 每个 guard 写 retire_when + 误报预算，季度 replay（Ouroboros 的"心跳"思路）
- 误报/过时规则降级为 warn 再删，不直接删

#### 出处
anthropic.com/responsible-scaling-policy/updates + news/claude-new-constitution（90天同步公开、
93%盲批数据）；rust-lang.github.io/rfcs（FCP）；agenticdevelopercookbook.com immutable-infrastructure；
agentpatterns.ai rule-lifecycle-metadata；arxiv.org/abs/2608.08311（Ouroboros）；
safeguard.sh recursive-self-improvement-claims；autotrust.ai/AutoTrust-RSI.pdf。


---

### 十、"监察审计权是否已正式独立剥离"——定位性结论（2026-11-22 10:45）

#### 答案：实质上是，措辞上"正式"要打折扣
这轮演进的实质 = **执行权 / 审计权 / 维护权三权分立**在工程系统里的映射。
但"正式独立"需要区分两个层次：

| 层次 | 状态 | 证据 |
|---|---|---|
| **审计功能独立** | ✅ 已完成 | 独立核验SOP（不信自报）+ A6元验证 + Foundation Guard 已分居执行者之上；判据来自环境而非 agent 自述 |
| **审计权力锁定** | ❌ 未完成 | run_all.sh / foundation_guard.py / census 仍是普通文件，agent 技术上可改；staging diff 通道未建；credential manager 可能存 push token |

**结论：功能已剥离，权力未锁死。** 设计上的边界画好了，机制上的栅栏尚未全装上。

#### 剥离的历史脉络（四步，每步都是一次"权力上收"）
1. **S13/S22 推卡** → 发现自报不可靠（sha漏同步/恒真/假绿）→ 独立核验SOP：
   **判定权从"执行者的自述"中剥离**
2. **A6** → 发现测试本身会腐化（没进门禁/退出码永0）→ census+真退出码+行为断言：
   **元验证权从"普通测试"中再剥离一层**
3. **Foundation Guard** → 发现验证体系也会漂移 → 6条不变量+drift日志：
   **守护权从"单次门禁"中剥离**
4. **信任锚调研** → 发现评判者也能被改 → 版本钉住+权限边界：
   **维护权从 agent 手中剥离的方向确立**（机制待落地）

#### 三权的精确边界
- **执行权（agent）**：写业务代码、提 staging diff；不得改规则包
- **审计权（门禁/guard）**：只读判定、验环境证据、不采信自报；不得改被审对象
- **维护权（人/带外）**：规则版本演进、批准变更、紧急修复；不日常执行

**关键性质**：三条边界是**单向不可越**的——审计只读执行、维护只发新版本不直接改运行实例。
这不是"三个部门"，是"三条不可跨越的权限边界"。

#### 待落地（真正"正式"还差这些）
- evaluator 文件版本钉住（pin digest + 只读 ACL / 独立用户）
- staging diff 通道（agent 可提不可生效，变更默认拒绝）
- GitHub remote 收窄 push 权限或开 branch protection
- 规则带 retire_when + 误报预算 + 季度 replay

#### 一句话
**这是从"agent 既当运动员又当裁判"到"三权分立的工程系统"的转型——
权力结构在概念上已经确立，剩下的是把边界从设计文档变成权限边界。**

---

### 十一、三权分立落地：规则包版本钉住（2026-11-22 10:50 实现）

#### 已实现（commit 见下）
1. **`bench/rulepack/manifest.json`** — 8 个评判文件的 digest + version + retire_when +三变更条件。
   **权威版从 git HEAD 读**（`git show HEAD:`），改工作区 manifest 无效——必须 commit 才生效，留痕。
2. **`tools/rulepack_guard.py`** — 校验当前文件 digest vs git 里的 pin；漂移 = FAIL + 修复命令。
   `--json` 供 agent 解析。
3. **`tools/rulepack_propose.py`** — agent 变更提案通道：生成 staging diff（`bench/rulepack/STAGING/`），
   **提案本身不生效**；支持 `--list` / `--reject <ID> --reason`。
4. **INV-7** 接入 foundation_guard（现 7 条不变量）+ run_all 独立检查项（双保险）→ 门禁 58→59。
5. **AGENTS.md 铁律新增"评判规则包保护"** — 写明 agent 执行权 vs 审计维护权的边界、三变更条件、
   emergency change 流程、以及诚实边界声明。

#### 受控实验（证明机制有效）
- 偷改 `run_all.sh`（加一行注释）→ rulepack_guard **FAIL rc=1** + 指出 digest 不匹配
- 恢复 → **PASS rc=0**
- 改 foundation_guard.py 加 INV-7 → INV-7 自己把自己抓红（6/7 DRIFT DETECTED）→
  走批准流程 re-pin v1.1.0 后恢复 7/7
- 提案通道：改文件 → propose → 生成 staging diff → 列表可读；提案不算漂移（设计如此）

#### 诚实的边界声明
当前 agent 与维护者**同为 Windows 标准用户 Ad**（Medium 完整性级别，非管理员），
**OS ACL 无法隔离同一用户**——所以要独立 verifier 用户才能物理阻止，那需要管理员建用户。
本机制是"**检测 + 留痕 + 纪律**"：把偷改变成立刻可见的红灯，不是物理阻止。
若要真权限边界，需带外初始化一个独立 verifier 用户 + TPM CNG 签名计划任务（见 §九）。

#### 版本历史
- v1.0.0（8 文件 pin）→ v1.1.0（加 INV-7 + run_all 双保险 + AGENTS.md 纪律）

#### 谁维护（回答用户上一问）
- 日常：agent 只读 + 可提 staging diff；**无人批准即永不生效**（变更默认拒绝、读取默认允许）
- 新增检查：走 glob 自动发现，**不用碰规则文件**（实测过）
- 规则 bug / 过时：由用户审核 staging diff → 更新 manifest → commit → 新版本；旧版可 git 回滚

---

## 原报告：`COMPETITIVE_ANALYSIS.md`

## 合成心智 vs 社区主流方案：先进与落后对比

> 数据来源：5 路广搜（docs/MIND_GAPS_RESEARCH.md）+ 第 6 路"先进维度"专项调研。
> 判据：不吹牛、不贬低——每条都给一手链接和具体数字。

### 核心结论（二分法）

**架构理念：我们领先或齐平**（确定性优先、零训练、外置认知、模板层干预）
**工程成熟度：我们明显落后**（社区产品化了 2-3 年，我们 11-18 才起步）

---

### 一、先进的维度（有证据）

#### A1 确定性门控的深度和广度

社区：[Harness Engineering (2609.00006)](https://arxiv.org/abs/2609.00006) 解剖 11 个 coding harness，
结论是全部手写循环 + 确定性检索；LivePlan (2608.06701) 的"规则先筛、LLM 再审"是社区 2026 的新提倡。

我们：L0-L3 早收尾 + D1-D5 风险门控 + verify-on-edit + present 深检 + 危险操作分级
——绝大部分 0 LLM，且已跑 30/30 门禁。这比社区的"新提倡"更彻底。

#### A2 模板层干预（治本 vs 治标）

我们：直接在 jinja chat template 做 `is_stub` 跳过假完成 assistant + 生成位置锚点。
社区：主流在 prompt 层或 tool_choice=required（我们 A/B 验证后者 0/2 无效）。

#### A3 引擎内部信号作零成本风险代理

我们：读 llama-server 的 MTP draft acceptance 率 <0.65 触发审计门控，不额外调用 LLM。
（待专项调研验证是否独创）

#### A4 端到端实证文化

我们：decode t/s 伪优化（+37% 但端到端慢 2.4×）、温度 U 形、多审计员无效——
都是自己 A/B 证伪的，不是纸面数字。社区大量方案只有论文自报数字。

---

### 二、落后的维度（有证据）

| 维度 | 社区成熟度 | 我们状态 |
|---|---|---|
| 会话树/rewind | OpenHands/Pi/OpenCode 一等公民 | 今天才做离线脚本 |
| 记忆/技能写回 | Hermes 907 行 review + 审批/归档 | 今天才做审批门 |
| verify-on-stop | Hermes / OpenHands /goal | 今天才加 |
| test-time 自适应 | DART+ARR+BOSS：token -41~76% | 完全没做 |
| 多模态/CUA | 2026 社区重点 | 0 |
| 形式化 eval | 标准 benchmark 套件 | 只有自建 agentlab/projectlab |
| 深度 ToM | BDI/XYBench | 今天才做骨架 |


---

### 第六路专项调研修正（重要：推翻两项"领先"判断）

**一句话总括（调研原文）**：我们的真正护城河是"在极小模型、零训练、纯文本约束下，
把社区公认的正确原则（单 agent + 确定性门控 + 缓存友好 + 实证）用一套权限语义和跨层信号
（spec acceptance）整合到极致"——是**整合与跨层复用**的领先，**不是任何单一技术组件的原创**。

#### 原判断被推翻的两项

1. ❌ **"确定性门控深度领先"要降级**：社区 2026 已明确收敛到"确定性 cascade"
   （[Stability Trap 2601.11783](https://arxiv.org/html/2601.11783)、
   [Deterministic vs LLM-Judge 2026](https://futureagi.com/blog/deterministic-vs-llm-judge-evals-2026/)：
   确定性是免费的 30-60% 失败地板）。**方向一致，不领先**——我们只是推得极端。
2. ❌ **"append-only 避免后缀税"完全不新**：这是社区第一指标 + 黄金规则
   （[Manus: KV-cache hit rate is the single most important metric](https://mnemoverse.com/docs/research/agents/kv-cache-context-engineering)）。
   且 8GB 下 llama.cpp prefix cache 是否真命中还需自证。

#### 真正领先的 TOP 5（调研判定）

1. **Spec acceptance → 审计门控**：社区用该信号做吞吐/调度，我们跨层复用到语义风险审计，
   零额外 LLM、零 logits 访问——**跨层复用新颖，信号思想不新**
2. **零权重/零并行下的带权限语义多角色控制平面**：单写者+steer+代执行+三态验收，
   ['方向领先/技术平凡']——社区多 agent 已被证伪（MAST 1600+trace/κ=0.88、Google+MIT 180 组
   顺序任务 -39~-70%），我们的选择对了，但 conditioning 技术是 2023 年级基础
3. **极端确定性占比 + is_stub 模板层治本**：少见但社区有更 principled 的约束解码
4. **chat-template 层锚点**：少见切入点，但 hacky、不可移植
5. **证伪驱动的实证文化**：真实亮点，但基准是自设的，外部效度有限

#### 我们薄弱/落后的补充发现

- **Critic 与执行者同源**：社区要求异质 verifier 破 self-preference；我们"异质 rubric"不解决模型同源偏差
- 外置记忆能力弱于 Mem0(+26%质量/-91%延迟)/Zep(+18.5%/-90%)/Letta
- spec 阈值 0.65 脆弱：社区典型 acceptance 对话 0.65-0.75/代码 0.55-0.70/创意 0.45-0.60，
  我们的阈值在创意长尾任务可能系统性误触发——**需用 P3/P4/P5 标定，不能拍脑袋**
- template 干预 hacky（社区有 Outlines FSM 97%成功/logit masking 更稳健）
