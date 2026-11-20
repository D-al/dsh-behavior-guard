# 心智模型缺失拼图 —— 广搜调研汇总（2026-11-18）

> ⚠️ **引用审计声明（2026-11-20）**：本文部分 arXiv 引用经官方 API 核实为**幻觉引用**
> （编号真实但标题/结论/数字与论文无关）。已逐条标注 `[❌幻觉-已作废]`。
> **凡标注的引用不得作为任何决策依据**。核实协议见 `CITATION_AUDIT_PROTOCOL_20261120.md`，
> 台账见 `config/citation_ledger.json`。



> 5 个并行 agent 调研：①认知科学框架 ②前沿能力缺口 ③三缺口深化 ④社区产品 ⑤记忆系统。
> 本文件是汇总草稿，逐份回填。最终结论将进 README 路线图 + MANUALS。

---

## 对照基线：我们已有的 8 功能

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

## 调研①：认知科学完整心智框架

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

## 调研②：前沿能力缺口（TOP 5）

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

## 调研①②③④⑤：全部到齐（2026-11-18 14:10）

（agent 运行中）


---

## 调研⑤：记忆系统完整性（**最有行动价值的一份**）

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

## 调研③：三大缺口深化（**推翻了我们的假设，含紧急发现**）

### 🚨 强制二选一已停用（2026-11-18 决策；证据已于 11-20 更正）

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

### 缺口1：可塑性 —— 不是缺机制，是缺证据收集

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

### 缺口2：自我模型 —— **伪缺口**：让 Critic 顺带输出，不要另起 agent

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

### 缺口3：元认知 —— 诊断没闭环，且**不要改写历史**

- [SEVA (2606.29713)](https://arxiv.org/abs/2606.29713)：结构化验证输出让 3B 追平 GPT-4o-mini，关键是**六类错误诊断 + 可执行修复**
- [Metacognitive Prompting (2308.05342)](https://arxiv.org/abs/2308.05342) NAACL 2024：7 阶段固定自问，PaLM 62→68%，但 token 成本高
- [AgentRx (2602.02475)](https://arxiv.org/abs/2602.02475)：失败步定位 +75%，但**"定位后必然修复"假设错误**
> ❌ **幻觉引用-已作废**（2602.12106: 真论文是MedExChain医疗区块链,非ESPRT）
> - **反面（重要）**：[AReaL (2505.24298)](https://arxiv.org/abs/2505.24298) "rewrite thoughts" 在 4/7 基准掉点；[ESPRT (2602.12106)](https://arxiv.org/abs/2602.12106) 截断思维链有害

👉 下一步不是更花哨的自问，而是**把每次诊断连到可回滚的证据记录**，让第 N 次同错被自动识别为"已试过且失败"。

### 三缺口共同底座
都指向**在现有事件流上新增"结果反馈"维度**（成功/失败/部分 + 证据引用 + 可回滚快照）。
比新建三个系统便宜得多，也正是调研②的"结构化轨迹事件流"、调研⑤的"代谢系统"。


---

## 已落地的改动（调研进行中同步执行）

### 🚨 紧急修复：强制二选一 → 中性事实+退出许可（v2.7.2 已发布，ADR-0014）

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

### 意图漂移监测脚本（调研② TOP1 的离线最小版）

`intent_drift.py`：从会话抽所有真实用户指令，用关键词覆盖率算与初始任务的偏离。
**现场验证精准复现**：seq 681 "给个测试窗口" vs 初始"写插件" 覆盖率 **0.00**，
而 P0 存档 16 次都没跟上——证实意图漂移是真实缺口，且检测成本近零。


---

## 调研④：社区产品心智机制（**架构背书 + 最明确的三块空白**）

### 核心情报：arXiv 2609.00006《Harness Engineering》（2026-07，83页，源码级解剖 11 个 coding harness）

结论：**没有任何主流 harness 用通用 agent 框架、没有任何用向量检索代码；
全部是手写循环 + 确定性检索 + SKILL.md 式技能（9/11 采用率，超过 MCP 的 8/11）**。
→ 我们的路线（确定性代码 + Skills 而非 MCP + 短路径检索）被学术背书，方向无需怀疑。

### 社区已共识、我们完全空白的 3 件事（优先级排序）

| # | 空白 | 社区做法 | 我们怎么抄（纯文本/零训练）|
|---|---|---|---|
| **1** | **外层验证循环（Loop Engineering）** | Hermes verify-on-stop：改了代码没验证证据就**否决退出**；OpenHands /goal 用 judge 决定重跑 or 停止 | 收尾前结构化清单（改了文件？有测试证据？），缺项把 FINISH 改回 CONTINUE。**我们强在多角色，弱在"环"** |
| **2** | **自写记忆/技能写回** | 全社区一致：零训练"变聪明"=写文件；Claude auto memory 四类+索引 200行/25KB；Hermes skill lifecycle 有 cooldown/审批/provenance/stale 归档 | 我们的存档+技能是**单向注入**，缺写回闭环。这是零训练路线最该补的一块 |
| **3** | **事件溯源会话树** | OpenHands/Pi/OpenCode：历史是树（parent 指针），fork/rewind 一等公民，"遗忘"记为事件而非删除 | 线性存档→带 parent 的条目，纠错可回滚/分支对比/重启恢复 |

### TOP 10 里可直接抄的单点

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

## 调研结论的兑现追踪（2026-11-18 21:30，v2.11.0）

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
