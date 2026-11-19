# 路线图（活文档）

> **给第一次来的 AI / 接手者**：这个文件回答三个问题——项目现在在哪（§1）、接下来做什么（§2-4）、
> 为什么是这个顺序（§5）。每条目标都带**完成标准（DoD）**，做完打勾并写进 [CHANGELOG](CHANGELOG.md)。
> 入口在 [README](README.md)；细节在 [docs/](docs/README.md)；"为什么这么决定"在 [decisions/](decisions/README.md)。
> 更新于 2026-11-19（**v2.24**：M4 完成 + 深度维护 1P0/7P1 + 分类器调研新增 M8/M9/L8，逻辑关系链重排）。
> 依据：[重定基线分析](docs/ROADMAP_REBASELINE_20261119.md) / [分类器评估](docs/CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md) / [深度维护](docs/DEEP_MAINTENANCE_20261119.md)。

---

## 1. 当前位置（30 秒读懂）

**项目是什么**：给 dsh（DeepSeek Harness）的一个 cordis 插件，通过**模型外部**的确定性脚手架
（规则注入 + 门控 + 旁路学习），让一个 8G 显存上的 35B MoE 模型表现得像可靠 agent。**模型权重一个字节没动。**

**做到哪了（v2.23）**：**短期目标 S1-S9 全部完成**，地基 + 数据变现层都已在线——
GWT 总线、FEP 闭环、CritBank（真实计数+可控遗忘）、审计自校准（误差可度量）、
有状态反馈环（NSED 思想）、注入检测（规则层）、Self-Harness P0-P2（**35B 已能亲自提 patch**）。
trace 已达 **6970 行**，弱点聚类产出 4 簇 + 13 条受保护行为。

**现在的位置**：从「把数据变成能力」转入「**让器官间流动**」——中期执行期。
M4（注入预算 token 化）已在 v2.24 完成；下一波首项是 **M1（情景检索）** 和 **M8（轨迹 FSM 监控器）**，
两者都吃 S1 已产出的 trace/evidence bundle，不需要再等数据。
v2.24 同时做了**深度维护**：修 1 个 P0（安全注入被次数闸门吞掉）+ 7 个 P1（含投毒防御缺口）。

**为什么是这个顺序**（[ADR-0017](decisions/0017-gwt-first-then-fep.md)）：
结构性地基越晚做越贵 → 先做；数据型目标时间站在我们这边 → 中间做；需要世界模型/外部基准的 → 最后做。
一句话：**先建总线，再往上接器官**——现在总线和数据都齐了，该接器官了。

**怎么判断一条新工作该放哪**：问它属于下面哪一波（§5），是否依赖未完成项。一波没验收，不开始下一波。

**知识资产沉淀规则（2026-11-19 用户明确要求）**：
每次**规划 / 调研 / 方案磋商**的结论都必须落进本文件（或专属 docs/ 评估文档 + 这里留链接），
不能只留在对话里。**被证伪的方向同样要记**（"明确不做" §8 + 对应评估文档）——
避免未来重复踩坑，也让没参与讨论的 AI 能接上决策脉络。
已沉淀的方案：Self-Harness（短期）、频次重设、压缩/角色诊断、两轮异构模型评估（§2 注释）。

---

## 2. 性价比速查（先做哪个？）

> **性价比 = 收益 / 成本**；`解锁` 指完成它后哪些目标变便宜。按此表从上到下领活。
> 这是**决策辅助**，不是硬顺序——硬依赖见 §6，一波没验收不开始下一波。
> **v2.24 重排依据**：M4 已完成；[分类器评估](docs/CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md) 新增 M8/M9/L8；
> [深度维护](docs/DEEP_MAINTENANCE_20261119.md) 修 1 个 P0 + 7 个 P1。逻辑链见 §2.1。

**2.1 逻辑关系链**（先理清依赖，再看速查表）：
```
地基(✅) ─┬─ 数据变现 S1(✅ evidence bundle) ─┬→ M1 情景检索 ─────┐
          │                                    └→ M8 轨迹FSM ─→ L6 误差预测器 │
          ├─ M4 注入预算(✅)                                                  ├→ L1 世界模型
          ├─ GWT+FEP(✅) → M3 BDI三槽 → M9 意图分类器 ─────────────────────────┤
          ├─ M2 会话树(parenId) → 真 rewind                                    │
          └─ M5 工具面(⛔拍板) / M7 格式修复(需86M) —— 独立支线 ────────────────┘
长期独立：L2 eval / L8 多标签心智 / L5 Critic(降级) / L3 脑分区 / L4 引擎 / L7 FAKEOK(探索)
```
**关键**：M8（轨迹 FSM）同时吃 S1 的 trace 数据、又是 L6 的前置——是"数据→能力"链条上被漏掉的一环，本次提到第二位。

| 排序 | 目标 | 收益 | 成本 | 依赖 / 解锁 | 建议 |
|---|---|---|---|---|---|
| **1** | **M1 情景检索进主循环** | 高 | 中 | GWT + S1 evidence bundle **均已就绪** | **下一波首项**，数据变现 |
| **2** | **M8 轨迹 FSM 监控器（新）** | 高 | 中低 | S1 trace 已就绪 → **L6 前置** | FSM AUROC 0.94、1-110ms；限局部信号 |
| 3 | **M3 BDI 三槽** | 中 | 中 | GWT+FEP 已立 → M9/L1 | 中期前半 |
| 4 | **M9 意图分类器（新）** | 中 | 中 | 依赖 M3 三槽 → BDI 填槽 | embedding+LR 1-20ms/92-93% |
| 5 | **M2 会话树实时化** | 中 | 中高 | GWT 加 parentId → 真 rewind | 中期后半 |
| 6 | **M5 工具面改造** | 中高 | 高 ⛔ | 用户拍板"哪些进内核" | 不阻塞别人，等决策 |
| 7 | **M7 格式修复器（重定义）** | 中 | 中高 | 需先测 86M 分类器（0.6B 已证伪）| 降级：收益存疑，先验证 86M |
| 8 | **S6 模型层升级（原尾巴）** | 中高 | 中 | 86M Prompt-Guard + **阈值重标定** | FPR 98% 教训：不标定不上 |
| 9 | **L2 标准化 eval** | 高（外部效度）| 高 | 迁移 SWE-bench 子集 | 长期优先 |
| 10 | **L1 FEP→世界模型** | 高 | 极高 | 需 M1+M3+M9 完成 | 最后做 |
| 11 | **L6 专属误差预测器** | 中 | 高 | **M8 FSM 已提供局部信号** + 单次蒸馏 | 由 M8 解锁，不再是空中楼阁 |
| 12 | **L8 多标签心智编码器（新）** | 中 | 高 | GWT 已立；需验证中文表现 | 一个前向输出意图+风险+难度 |
| 13 | **L5 小模型 Critic 预警** | 低 | 高 | 0.6B 5s 不实用，须换 86M | 降级：无实证收益前不做 |
| 14 | **L3 脑分区空白** | 低（探索性）| 高 | 有证据再做 | 观望 |
| 15 | **L4 独立轨道** | 中 | 高 | 引擎/上游 PR | 不插队 |
| — | **L7 FAKEOK 抑制（探索）** | 中 | 低 | S4 发现 ⑦ 提示让 FAKEOK→PASS | 不占坑，先小规模验证 |

> **✅ 已完成 16 项**（S1-S9 全部 + M6 + 地基）已收进 **§7 归档**。
> **🔴 本轮关闭的尾巴**：S4 P4/P5 补跑（token 未降已定论）、S7 校准曲线（0.6B 已证伪）、
> "0.6B 做实时外设"（实测 4-6s，比文献慢 10×）。

> **四轮架构评估沉淀**（按时间）：
> ① [判断类证伪](docs/HETEROGENEOUS_MODELS_EVALUATION.md)：小模型当审计/纠正/验收 = 弱 judge 放行强 actor 错误。
> ② [外设类成立](docs/PERIPHERAL_MODELS_EVALUATION.md)：感知/路由有生产实证，但 router-first 不要 cascade。
> ③ [反馈环与蒸馏](docs/FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md)：前馈误差放大 → NSED 思想（S9 已落地）；蒸馏只做单次。
> ④ [实测收口](docs/S7_SMALL_MODEL_BENCH_RESULT.md) + [S4 A/B](docs/S4_ADAPTIVE_AB_RESULT.md) + [S1 P0-P2](docs/S1_SELF_HARNESS_P0P1_RESULT.md)：
> 0.6B 不适合实时外设；adaptive token 未降故不开；35B 亲提案跑通。

**读法**：收益=能力/质量提升幅度；成本=代码改动+验证时长；`⛔`=被外部决策阻塞；`✅`=已完成（见 §7）。

---

## 3. 🟢 短期（Now）：✅ 已全部完成，移入归档

> **v2.23：S1-S9 全部完成**，本节不再列活跃目标。完整 DoD 与验证见 **§7 归档**。

**短期交付的能力**（一句话盘点）：
- **数据变现**：S1 Self-Harness P0-P2（35B 亲提案跑通）、S2 可控遗忘、S3 trace 上下文字段
- **误差治理**：S8 审计自校准（误差可度量）、S9 有状态反馈环（NSED 思想）、S5 角色失效修复
- **外周神经**：S6 注入检测规则层、S7 CPU 基准（证伪 0.6B 实时外设）
- **验证收口**：S4 自适应 A/B（token 未降 → 保持关闭）

**留下的三条尾巴**（不阻塞中期，记录在此防遗忘）：
1. S1 P3 常态化 + 双 split 真实评测（ADR-0018 要求完整验收后才启动；2-4h/轮未跑）
2. S6 的 86M Prompt-Guard 模型层（规则层够用，待实测误报率 >2% 才做）
3. S8 真实运行产生 `_audit_feedback.jsonl`（代码+单测已过，待真实会话触发审计门控）

**保留的方法论资产**：
**Self-Harness 四阶段**（[方案](docs/SELF_HARNESS_PLAN.md) / [ADR-0018](decisions/0018-self-harness-two-stage.md)）——
P0/P1/P2 已交付，P3 作为中期 M1 完成后的候选闭环，不自动启动。
依据：[Self-Harness 2606.09498](https://arxiv.org/abs/2606.09498) Qwen3.5-35B-A3B +18.7pp。

**频次依据**：[CADENCE_AUDIT](docs/CADENCE_AUDIT.md) + [CADENCE_REDESIGN](docs/CADENCE_REDESIGN.md)——
大部分频次经实测校准**不该动**；注入预算按次数不按 token 的问题已转入 **M4**。

---

## 4. 🟡 中期（Next，1-2 月）：器官间流动

> 共同特征：结构已在（GWT 总线已立）、数据已变现（S1 evidence bundle + trace 8050 行），缺的是把离线脚本接进主循环。
> **执行顺序按 §2 速查表与逻辑关系链**：M1 → M8 → M3 → M9 → M2 → M5（等拍板）→ M7 → S6模型层。

| # | 目标 | 性价比 | 依赖 | 完成标准（DoD） | 状态 |
|---|---|---|---|---|---|
| **M1** | **情景检索进主循环** | 高/中 | GWT + **S1 evidence bundle（均已就绪）** | `es.exe` 从离线脚本接入控制回合自动 top-3 注入；长任务中历史经验被主动引用 >0 次；结果写回 GWT 的 evidence 字段 | [ ] ← **下一波首项** |
| **M8** | **轨迹 FSM 监控器（新）** | 高/中低 | S1 的 8050 行 trace（已就绪）| 把 trace 压成 FSM 做局部失败预测（重复探测/路径解析/工具报错）；held-out AUROC ≥0.85；**只做局部可观察信号**，长轨迹因果归因交主模型（Jev 实测 0.56≈随机）；产出接入 evidence bundle。见 [分类器评估](docs/CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md) | [ ] |
| M3 | **用户意图 BDI 深化** | 中/中 | GWT 的 bdiGoal + FEP 偏差 | `s.bdi` 单槽升级 belief/desire/intention 三槽；用户约束跨压缩不丢；意图漂移检测有状态可依 | [ ] |
| **M9** | **意图分类器（新）** | 中/中 | 依赖 M3 三槽 | embedding+LR / SetFit 意图分类（1-20ms、92-93%）填 BDI 意图槽；高置信直接用、低置信交三角色；**共享一个编码器**，不为每意图训独立模型 | [ ] |
| M2 | **会话树实时化** | 中/中高 | GWT 加 `parentId` | `session_tree.py` 从事后分析变实时写 parent 指针；能从任一节点 fork 且不改写历史、不付 KV 后缀税（ADR-0013） | [ ] |
| M5 | **工具面结构改造** | 中高/高 ⛔ | 用户拍板"哪些进内核" | 28 个工具收敛到最小内核（read/write/edit/search/shell/bridge）；低频能力进 skill 卡 + skill 内脚本；危险拦截 hook 化；不动则保持现状 | [ ] |
| M7 | **格式修复器（重定义）** | 中/中高 | 先验证 86M 分类器（0.6B 已证伪）| 只做格式重写不判断对错、35B 首轮兜底；**前置**：86M CPU 延迟 <500ms；A/B 验证端到端提速才上。见 [S7 基准](docs/S7_SMALL_MODEL_BENCH_RESULT.md) | [ ]（降级）|

依据：[mini-harness](https://github.com/jb-san/mini-harness)（7 工具 + skill/hook）、
[dsh-browser-agent](https://github.com/nonentity303/dsh-browser-agent)（安全规则优先级）、
[PEER_HARNESS_BENCHMARK](docs/PEER_HARNESS_BENCHMARK.md)。

---

## 5. 🔴 长期（Later，季度级）：架构完整性与外部效度

> 共同特征：需要更强的评测、更完整的世界模型，或与脑结构无关但耗时长的独立轨道。

| # | 目标 | 性价比 | 完成标准（DoD） | 状态 |
|---|---|---|---|---|
| L2 | **标准化 eval** | 高/高 | 自建 P3/P4/P5 迁移到 SWE-bench Verified 子集；与社区同基准可比；借鉴 `swe-agent-lite` 的 harness | [ ]（长期优先）|
| L1 | **FEP 深化：偏差 → 世界模型** | 高/极高 | 现有只判"产物是否存在"，升级为断言"产物内容满足 what"；预期断言精度/召回可测；误报不侵占注入通道（ADR-0017）。**需 M1+M3+M9 先完成** | [ ]（最后）|
| L6 | **专属误差预测器（主模型打造队友）** | 中/高 | **由 M8 的 FSM 局部信号解锁**（不再空中楼阁）：trace + 35B 标注训 0.5B 二分类器；**只做单次蒸馏 n=1**（递归自噬），**保留 UNCERTAIN 样本**；长轨迹因果归因仍交主模型（Jev 0.56≈随机）| [ ]（依赖 M8）|
| **L8** | **多标签心智编码器（新）** | 中/高 | GLiClass 式一个前向同时输出 意图+风险+难度，写进 GWT 共享状态（对应 GWT 模块竞争）；128 标签仅掉 7-20% 吞吐；**前置：验证中文表现**（GLiClass 英文为主）| [ ]（新探索）|
| L5 | **小模型 Critic 轻量预警** | **低**/高 | 0.6B 扫一次要 5s（S7 实测），预警层不实用 → **须换 86M 分类器且实测达标**才重启；未命中只记 trace 不拦截；前置召回率 A/B ≥80% | [ ]（**降级**）|
| L3 | **脑功能分区空白区** | 低/高 | 按 [BRAIN_PARITY](docs/BRAIN_PARITY.md) 补眶额价值 / 脑干稳态；调研已完成，待决定是否落 ADR | [ ]（观望）|
| L4 | **独立轨道（不插队）** | 中/高 | autoparser 上游 PR（[#29307](https://github.com/ggml-org/llama.cpp/pull/29307)）+ 撤本地补丁；llama.cpp v1.0.0 升级；dsh rc 升级 | [ ] |
| **L7** | **FAKEOK 抑制（新探索）** | 中/低 | S4 的 P3 A/B 发现 ⑦ 提示让 off 组 FAKEOK→on 组 PASS（但 token 未降）；验证"防提前假装完成"的轻量机制，与 D4 交付闸门同源。先小规模对照，不占正式坑位 | [ ]（探索）|

---

## 6. 四波次依赖逻辑（稳定不变，判断新工作先问属于哪波）

> 短/中/长期是**执行节奏**（会随进度重排）；这四波是**依赖逻辑**（稳定不变）。

| 波次 | 主题 | 依赖逻辑 | 状态 |
|---|---|---|---|
| **0 地基期** | 数据底座 + 共享总线 | 没 outcome 无从比对、没 GWT 只能手动搬运状态——所有后续机制的前提 | ✅ 完成（v2.8~v2.12）|
| **1 回填期** | 把数据变成能力 | FEP 偏差 + outcome 已攒够，喂技能进化与遗忘 | ✅ **完成（v2.22：S1-S9 全部）** |
| **2 连接期** | 器官间流动 | GWT + evidence bundle 均已立，情景检索/会话树可进主循环 | 🟡 **当前波次**：M4 → M1 → M3/M2 |
| **3 进化期** | 从经验变聪明 | **投毒防御必须先于写回闭环**——SkillJack：80% 攻击删源后仍存活 | 🔴 长期 L1-L7（P0 白名单已立，P3 未启动）|

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
| **S8 审计自校准落盘** + **S9 有状态反馈** + **S6 注入检测** | v2.21.0 | `test_audit_feedback` 6/6 + `test_review_loop` 8/8 + `test_injection_scan` 6/6 |
| **S1 Self-Harness P0-P2** | v2.22.0 | `self_harness_gate.py` 11/11 + 35B 真提案落候选 + 6970 行 trace 聚类 4 簇 |
| **S4 自适应 A/B** + **S7 CPU 小模型基准** | v2.22.0 | P3 off FAIL/on PASS（token 未降不开）；0.6B CPU 4-6s（证伪实时外设）|
| **路线图重定基线** | v2.23.0 | [重定基线分析](docs/ROADMAP_REBASELINE_20261119.md)：短期全完成、M4/M1 升首档、M7/L5 降级、L7 新增 |
| **M4 注入预算 token 化** | v2.24.0 | `test_injection_budget.mjs` 5/5（含安全注入双闸门豁免 P0 修复）|
| **深度维护 bug 审计** | v2.24.0 | [审计报告](docs/DEEP_MAINTENANCE_20261119.md)：1 P0 + 7 P1 修复；JS 158 PASS、gate 11/11、投毒扫描 3/3 |
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
| **0.6B/1B 级 LLM 做实时外设** | S7 实测：Qwen3-0.6B Q8_0 纯 CPU 分类 4.2s / 格式 6.0s（比文献边缘设备 392ms 慢 10×），且 thinking 吃光 content 需 max_tokens≥512。实时注入检测须用 86M 级 BERT 分类器，不是 LLM（[基准](docs/S7_SMALL_MODEL_BENCH_RESULT.md)）|
| **开启 adaptiveThinkEnabled 默认值** | S4 P3 A/B：token 4172→4168 未降（DoD 要求"token 降且成功率不降"）；单次 FAIL→PASS 有噪声，不足以证明机制有效。保持默认关闭（[结果](docs/S4_ADAPTIVE_AB_RESULT.md)）|
| **递归自喂式蒸馏** | Nature 2024：第 9 代退化为"野兔清单"；只做单次 n=1 且保留 UNCERTAIN 样本（[评估](docs/FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md)）|
