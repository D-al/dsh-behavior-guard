# 路线图（活文档）

> **给第一次来的 AI / 接手者**：这个文件回答三个问题——项目现在在哪（§1）、接下来做什么（§2-4）、
> 为什么是这个顺序（§5）。每条目标都带**完成标准（DoD）**，做完打勾并写进 [CHANGELOG](CHANGELOG.md)。
> 入口在 [README](README.md)；细节在 [docs/](docs/README.md)；"为什么这么决定"在 [decisions/](decisions/README.md)。
> 更新于 2026-11-19（v2.14.0：频次重设 + Now/Next/Later 重排）。

---

## 1. 当前位置（30 秒读懂）

**项目是什么**：给 dsh（DeepSeek Harness）的一个 cordis 插件，通过**模型外部**的确定性脚手架
（规则注入 + 门控 + 旁路学习），让一个 8G 显存上的 35B MoE 模型表现得像可靠 agent。**模型权重一个字节没动。**

**做到哪了**：地基全部完成，处于「**骨架已立、血肉待长**」——数据底座（trace 5500+ / outcome 63+ /
CritBank 真实命中）、共享状态总线（GWT）、预期闭环（FEP）、权限代劳都已在线。
现在的瓶颈不是"缺结构"，是"**积累的数据还没变成能力**"。

**为什么是这个顺序**（[ADR-0017](decisions/0017-gwt-first-then-fep.md)）：
结构性地基越晚做越贵 → 先做；数据型目标时间站在我们这边 → 中间做；需要世界模型/外部基准的 → 最后做。
一句话：**先建总线，再往上接器官。**

**怎么判断一条新工作该放哪**：问它属于下面哪一波（§5），是否依赖未完成项。一波没验收，不开始下一波。

**知识资产沉淀规则（2026-11-19 用户明确要求）**：
每次**规划 / 调研 / 方案磋商**的结论都必须落进本文件（或专属 docs/ 评估文档 + 这里留链接），
不能只留在对话里。**被证伪的方向同样要记**（"明确不做" §8 + 对应评估文档）——
避免未来重复踩坑，也让没参与讨论的 AI 能接上决策脉络。
已沉淀的方案：Self-Harness（短期）、频次重设、压缩/角色诊断、两轮异构模型评估（§2 注释）。

---

## 2. 性价比速查（先做哪个？）

> **性价比 = 收益 / 成本**；`解锁` 指完成它后哪些目标变便宜。按此表从上到下领活。
> 这是**决策辅助**，不是硬顺序——硬依赖见 §5，一波没验收不开始下一波。

| 排序 | 目标 | 收益 | 成本 | 解锁 | 建议 |
|---|---|---|---|---|---|
| ✅ | **S3 频次收尾** | 中 | **极低**（2 个 trace 字段）| — | ✅ v2.17 已完成 |
| ✅ | **M6 安全规则测试** | 中 | **极低**（文档+1 测试）| — | ✅ v2.17 已完成 |
| ✅ | **S2 可控遗忘** | 高 | 低（已有脚本骨架）| S1 投毒防御 | ✅ v2.17 已完成 |
| 4 | **S6 工具结果注入检测** | 高 | 低（86M 分类器，CPU <10ms）| 外周神经第一块 | **新 P0，性价比最高** |
| 5 | **S7 CPU 小模型基准** | 中 | 低（纯测量）| 所有外设决策的前置 | **先测再决定** |
| 6 | **S5 角色失效修复** | 高 | 中（需端到端复现）| — | ✅ **v2.15 已完成** |
| 7 | **M4 注入预算 token 化** | 高 | 中（改注入路径+验证）| 全场景抗稀释 | S3 后做 |
| 8 | **S1 技能自进化** | **极高**（+18.7pp 外部证据）| **高**（Self-Harness P0-P3）| M1 检索对象 | 重点投入，但先 P0 验证 |
| 9 | **M1 情景检索** | 高 | 中 | — | 依赖 S1 evidence |
| 10 | **M3 BDI 三槽** | 中 | 中 | L1 世界模型 | 中期后半 |
| 11 | **S4 自适应端到端** | 中 | 中（要跑 6 次长任务）| — | 可与 S1 并行验证 |
| 12 | **M2 会话树实时化** | 中 | 中高（改 parent 指针）| 真 rewind | 中期后半 |
| 13 | **M5 工具面改造** | 中高 | 高（重构+用户拍板）| 上下文瘦身 | ⛔ 等用户拍板 |
| 14 | **M7 小模型格式修复器** | 中 | 中（需 S7 基准先过）| 省 JSON 重试的 35B 调用 | 依赖 S7 |
| 15 | **L2 标准化 eval** | 高（外部效度）| 高（迁移基准）| 可比社区 | 长期优先 |
| 16 | **L1 FEP→世界模型** | 高 | **极高**（需 M1+M3）| — | 最后 |
| 17 | **L5 小模型 Critic 预警** | 中 | 高（需 S7 + A/B 召回率≥80%）| 减 35B 调用 | 收紧前置条件 |
| 18 | **L3 脑分区空白** | 低（探索性）| 高 | — | 有证据再做 |
| 19 | **L4 独立轨道** | 中 | 高（引擎/上游）| 免维护 patch | 不插队 |

> **两轮异构评估（2026-11-19）**：
> ① [判断类证伪](docs/HETEROGENEOUS_MODELS_EVALUATION.md)：小模型当审计/纠正/验收 = 弱 judge 放行强 actor 错误，不做。
> ② [外设类成立](docs/PERIPHERAL_MODELS_EVALUATION.md)：小模型做感知/分类/反射（注入检测 86M<10ms、路由 0.5B 83%）有生产实证——
> 但要 router-first、**不要 cascade**（交互场景 tiering 对延迟几乎无用）。新增 S6/S7 为近期重点。

**读法**：收益=能力/质量提升幅度；成本=代码改动+验证时长；`⛔`=被外部决策阻塞；`✅`=已完成。

---

## 3. 🟢 短期（Now，1-2 周）：把积累的数据变成能力

> 共同特征：数据已经够了（outcome 63+ / trace 5500+ / 技能草稿已产出），只差接成闭环。
> 全部**权重零改 + 纯文本/规则**，不改引擎。

| # | 目标 | 性价比 | 为什么现在做 | 完成标准（DoD） | 状态 |
|---|---|---|---|---|---|
| S1 | **技能自进化闭环** | 极高/高 | 数据已 ≥20 条，草稿已产出；这是短期①的核心 | outcome+FEP 偏差喂 `skill_draft`；草稿命中同类任务成功率上升；`promote_skills` 仍人工审批（ADR-0015）；投毒防御先于自动写回 | [ ] |
| S2 | **可控遗忘常态化** | 高/低 | CritBank 目前 0 计数，假记忆会自我强化 | 真实 helpful/harmful 计数非零；`crit_decay.py --apply` 月度跑；无过时经验被引用（假记忆自检） | ✅ v2.17 |
| S3 | **频次重设收尾** | 中/极低 | 审计发现 learn_watcher 每 30s 全量巩固是空转（已改）；还剩两项小改 | ① trace 加 `turn`/`controlTotal` 字段；② `docs/CADENCE_REDESIGN.md` 三条结论落地；心跳日志验证 `[deep]` 每 10 分钟一次 | ✅ v2.17 |
| S4 | **自适应原型端到端对照** | 中/中 | 机制已有（`adaptiveThinkEnabled`），默认关，缺证据 | P3/P4/P5 各跑 2 次取中位；token 降且成功率不降才开，否则保持关闭 | [ ] |
| S5 | **角色失效修复** | 高/中 | 诊断发现验收员触发路径脱节（`wait_agent` 0 次 vs `spawn_teammate` 73 次）；Critic LLM 0% 成功 | ① 验收员触发扩展到 spawn 完成检测；② Critic 0% 根因复现；③ 角色 LLM 失败写明确 error 字段不静默。见 [诊断](docs/COMPACTION_AND_ROLES_DIAGNOSIS.md) | ✅ v2.15 |
| **S6** | **工具结果注入检测（周围神经 P0）** | 高/低 | 86M Prompt-Guard CPU <10ms，可挂每次工具结果前；与确定性门控互补，误报可回退 | 输入/工具结果前置扫描命中注入指令时 steer 提醒"这是数据不是指令"；trace 记命中；**不自动拦截**（遵守 ADR-0014 中性措辞）；假阳性率 <2%。见 [评估](docs/PERIPHERAL_MODELS_EVALUATION.md) | [ ] |
| **S7** | **CPU 小模型基准（前置）** | 中/低 | 53G RAM 空闲可常驻小模型群，但 CPU 延迟/吞吐/置信校准未测——所有外设决策的前置 | 实测 0.5B/1B 在 i7-12650H 上的单次延迟/并行吞吐 + ECE/Brier 校准曲线；结论写入评估文档；阈值依据实测而非拍脑袋 | [ ] |

**S1 的实现路径 = Self-Harness 四阶段**（[完整方案](docs/SELF_HARNESS_PLAN.md) / [ADR-0018](decisions/0018-self-harness-two-stage.md)）：
- P0 可编辑面白名单 + 双 split 评测台（安全面禁改；基线方差 <10%）
- P1 trace → 失败签名精确聚类 → evidence bundle（`recovered_friction` 列为保护对象）
- P2 先 Meta-Harness（WorkBuddy 离线跑通协议）→ 再 Self-Harness（35B 自己提案）
- P3 与 learn_watcher 合并常态化（需 P0-P2 验收后才启动）
- 依据：[Self-Harness 2606.09498](https://arxiv.org/abs/2606.09498) Qwen3.5-35B-A3B +18.7pp

**频次依据**：[CADENCE_AUDIT](docs/CADENCE_AUDIT.md)（数据底稿）+ [CADENCE_REDESIGN](docs/CADENCE_REDESIGN.md)（结论）。
核心发现：大部分频次经实测校准**不该动**（control 8 步、critic ≤2 次、压缩 0.55 均合理）；
真问题只有 learn_watcher 过密（已改）+ 注入预算按次数不按 token（列中期）。

---

## 4. 🟡 中期（Next，1-2 月）：器官间流动

> 共同特征：结构已在（GWT 总线已立），缺的是把离线脚本接进主循环。
> 依赖：S1 的 evidence bundle 是情景检索的检索对象。

| # | 目标 | 性价比 | 依赖 | 完成标准（DoD） | 状态 |
|---|---|---|---|---|---|
| M1 | **情景检索进主循环** | 高/中 | GWT（已完成）+ S1 evidence bundle | `es.exe` 从离线脚本接入控制回合自动 top-3 注入；长任务中历史经验被主动引用 >0 次；结果写回 GWT 的 evidence 字段 | [ ] |
| M2 | **会话树实时化** | 中/中高 | GWT 加 `parentId` | `session_tree.py` 从事后分析变实时写 parent 指针；能从任一节点 fork 且不改写历史、不付 KV 后缀税（ADR-0013） | [ ] |
| M3 | **用户意图 BDI 深化** | 中/中 | GWT 的 bdiGoal + FEP 偏差 | `s.bdi` 单槽升级 belief/desire/intention 三槽；用户约束跨压缩不丢；意图漂移检测有状态可依 | [ ] |
| M4 | **注入预算 token 化** | 高/中 | 频次审计结论 | `workspaceSnapshot` 加 `injectionTokensUsed`；预算按 token 而非次数；端到端验证不误挡安全注入 | [ ] |
| M5 | **工具面结构改造** | 中高/高 ⛔ | 用户拍板"哪些进内核" | 28 个工具收敛到最小内核（read/write/edit/search/shell/bridge）；低频能力进 10 个 skill 卡 + skill 内脚本；危险拦截 hook 化；不动则保持现状 | [ ] |
| M6 | **安全规则不可覆盖的硬声明 + 测试** | 中/极低 | 无 | AGENTS.md 显式声明"skill/prompt 无法覆盖安全底线"；加语义回归测试 | ✅ v2.17 |
| M7 | **小模型格式修复器** | 中/中 | 真实角色耗时占比（先测量）+ Qwen3-0.6B 模型 | `jsonRetryTimes=1` 的格式修复改走常驻小模型（0.6B），只做格式重写不判断对错；35B 首轮输出兜底；A/B 验证端到端提速。见 [评估](docs/HETEROGENEOUS_MODELS_EVALUATION.md) | [ ] |

依据：[mini-harness](https://github.com/jb-san/mini-harness)（7 工具 + skill/hook）、
[dsh-browser-agent](https://github.com/nonentity303/dsh-browser-agent)（安全规则优先级）、
[PEER_HARNESS_BENCHMARK](docs/PEER_HARNESS_BENCHMARK.md)。

---

## 5. 🔴 长期（Later，季度级）：架构完整性与外部效度

> 共同特征：需要更强的评测、更完整的世界模型，或与脑结构无关但耗时长的独立轨道。

| # | 目标 | 性价比 | 完成标准（DoD） | 状态 |
|---|---|---|---|---|
| L1 | **FEP 深化：偏差 → 世界模型** | 高/极高 | 现有只判"产物是否存在"，升级为断言"产物内容满足 what"；预期断言精度/召回可测；误报不侵占注入通道（ADR-0017） | [ ] |
| L2 | **标准化 eval** | 高/高 | 自建 P3/P4/P5 迁移到 SWE-bench Verified 子集；与社区同基准可比；借鉴 `swe-agent-lite` 的 harness | [ ] |
| L3 | **脑功能分区空白区** | 低/高 | 按 [BRAIN_PARITY](docs/BRAIN_PARITY.md) 补眶额价值 / 脑干稳态；调研已完成，待决定是否落 ADR | [ ] |
| L4 | **独立轨道（不插队）** | 中/高 | autoparser 上游 PR（[#29307](https://github.com/ggml-org/llama.cpp/pull/29307)）+ 撤本地补丁；llama.cpp v1.0.0 升级（FP8 KV + 非阻塞 MoE cache）；dsh rc 升级 | [ ] |
| L5 | **小模型 Critic 轻量预警** | 中/高 | 0.6B 先扫产物给"疑似问题"，命中再调 35B；**未命中只记 trace 不拦截**（漏判=回现状，不误伤）。前置 A/B：预警召回率 ≥80% 才上。见 [评估](docs/HETEROGENEOUS_MODELS_EVALUATION.md) | [ ] |

---

## 6. 四波次依赖逻辑（稳定不变，判断新工作先问属于哪波）

> 短/中/长期是**执行节奏**（会随进度重排）；这四波是**依赖逻辑**（稳定不变）。

| 波次 | 主题 | 依赖逻辑 | 状态 |
|---|---|---|---|
| **0 地基期** | 数据底座 + 共享总线 | 没 outcome 无从比对、没 GWT 只能手动搬运状态——所有后续机制的前提 | ✅ 完成（v2.8~v2.12）|
| **1 回填期** | 把数据变成能力 | FEP 偏差 + outcome 已攒够，现在能喂技能进化与遗忘 | 🟢 短期 S1-S5（S5 已完成） |
| **2 连接期** | 器官间流动 | GWT 已立，情景检索/会话树可进主循环；BDI 有状态卡可依 | 🟡 中期 M1-M6 |
| **3 进化期** | 从经验变聪明 | **投毒防御必须先于写回闭环**——SkillJack：80% 攻击删源后仍存活 | 🔴 长期 L1-L4 |

**双向迭代**：依赖链不只向上——第 4 层审计需求曾反向复用第 1 层 spec 日志信号；
FEP 注入曾挤掉 D5 审计额度，反向促成"学习信号不占运行时注入通道"（ADR-0017）。
判断新工作时多问：属于哪波？是否要回头改下层？

---

## 7. ✅ 已完成（归档，不再占用短中长期位置）

| 目标 | 版本 | 验证 |
|---|---|---|
| spec 阈值分类标定 | v2.10.0 | `test_short_term_goals.mjs` 2/2 |
| Critic 去同源化（异质采样 + AC3）| v2.10.0 | 同上 4/4 |
| test-time 自适应原型（机制，非端到端）| v2.10.0 | 同上 2/2 |
| 真实会话回归 | v2.10.0 | 桥接派真实任务，verify-on-stop 验证链成立 |
| 权限弹窗代劳（full-access 预设 + answerer）| v2.10.1 | 新会话 0 次 `approval/asked` |
| **GWT 共享状态总线**（胼胝体）| v2.11.0 | `test_gwt_fep.mjs` 9/9 |
| **FEP 预期闭环**（小脑）| v2.11.0 | 同上 7/7；真实 trace 出现 `fep_cycle` |
| 深度维护审计（8 P0 + 9 P1 修复）| v2.12.0 | 106 PASS / 0 FAIL |
| Self-Harness 纳入路线图 + GPU 引擎守护 + 同族对标 | v2.13.0 | 106 PASS / 0 FAIL；GPU 自检过 |
| learn_watcher 频次三层改造 | v2.14.0 | 语法 OK；心跳 `[deep]` 每 10 分钟 |
| 压缩存档去重 + 角色失效诊断 + 过程折叠 | v2.15.0 | `test_archive_dedup.mjs` 9/9 |
| S5 角色失效修复（静默失败 / Critic 0% / 验收员触发）| v2.16.0 | `test_role_fixes.mjs` 6/6 |
| **S3 频次收尾**（trace 带 turn/controlTotal）| v2.17.0 | `test_trace_context.mjs` 5/5 |
| **M6 安全规则不可覆盖**（声明 + 测试）| v2.17.0 | `test_security_boundary.mjs` 8/8 |
| **S2 可控遗忘常态化**（真实计数 + 月度 decay + 假记忆自检）| v2.17.0 | `test_controllable_forgetting.py` 11/11 |
| 结果反馈捕获 / 确定性门控 / 三角色 / P0-P2 心智拼图 | v2.0~v2.9 | 见 CHANGELOG 全文 |

完整历史见 [CHANGELOG](CHANGELOG.md) 与 [时间线](docs/history/TIMELINE.md)——**历史只追加，不重写**。

---

## 8. 明确不做（防止新人重造轮子 / 走回头路）

| 不做 | 理由 |
|---|---|
| 多模态 / CUA | 与纯文本 8GB 环境不匹配，社区主战场但非我们场景 |
| 通用 agent 框架 / 向量检索代码 | [Harness Engineering 2609.00006](https://arxiv.org/abs/2609.00006)：11 个主流 harness 全用确定性循环，无人用 |
| 训练 / 微调模型（含 RL 优化 harness）| 与"权重零改"路线冲突；agent-lightning 等 RL 路线只作技术雷达 |
| 堆更多 judge | [Apple: 9 judge≈2 票](docs/MIND_GAPS_RESEARCH.md)；信号源多样性 >> judge 数量 |
| 强制二选一 / 质疑式干预 | "Are you sure"≈"You are wrong"，会让 76.6% 正确答案被推翻（[ADR-0014](decisions/0014-reject-forced-choice-injection.md)）|
| FEP 偏差走运行时注入通道 | 实测挤掉 D5 审计额度（ADR-0017）——学习信号只进 trace/学习队列 |
| 改 Electron 启动参数降 3D | `--disable-gpu` 等已证伪反效果（[Electron #50469](https://github.com/electron/electron/issues/50469)）；见 [GPU 守护](docs/GPU_ENGINE_GUARD.md) |
| 无差别提高自动化频次 | 频次审计证明大部分参数经实测校准合理；只按证据调（[CADENCE_REDESIGN](docs/CADENCE_REDESIGN.md)）|
| **小模型（0.8B 级）做审计/纠正/验收** | JudgeBench 小 judge 一致率仅 45-60%（近抛硬币）；"强 judge 才鲁棒"要求 judge ≥ actor；弱 verifier 放行强 actor 错误比不审查更糟。**验收员本就是 Python 规则，零 LLM**（[评估](docs/HETEROGENEOUS_MODELS_EVALUATION.md)）|
