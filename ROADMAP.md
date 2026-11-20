# 路线图（活文档）

> **给第一次来的 AI / 接手者**：这个文件回答三个问题——项目现在在哪（§1）、接下来做什么（§2-4）、
> 为什么是这个顺序（§5）。每条目标都带**完成标准（DoD）**，做完打勾并写进 [CHANGELOG](CHANGELOG.md)。
> 入口在 [README](README.md)；细节在 [docs/](docs/README.md)；"为什么这么决定"在 [decisions/](decisions/README.md)。
> 更新于 **2026-11-20**（**v2.26.5**：能力阶梯 A0/A3_5/M1 已由 agent 自己爬完；人类视图改为自动生成；机器权威块已拆出为 ROADMAP_GRAPH.md）。
> 依据：[重定基线分析](docs/ROADMAP_REBASELINE_20261119.md) / [分类器评估](docs/CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md) / [深度维护](docs/DEEP_MAINTENANCE_20261119.md)。

---

<!-- 正文开始。机器权威块在 ROADMAP_GRAPH.md，由 tools/roadmap_check.py 按标记定位。 -->


## 1. 当前位置（30 秒读懂）

<!-- HUMAN_PROGRESS_BEGIN v1：由 roadmap_check.py --apply 自动生成，勿手改 -->
> ### 🟢 自主化进度（自动同步）
>
> | 卡片 | 状态 | 完成证据 |
> |---|---|---|
> | **A0 数据可信（sid 黑名单）** | ✅ done | 证据见 `evidence_log` + `docs/reflection-A0.md` |
> | **A1 会记路（机器判据 + dry-run 核验）** | ✅ done | 证据见 `evidence_log` + `docs/reflection-A1.md` |
> | **A3_5 安全地基（真实 diff + e2e + 回滚）** | ✅ done | 证据见 `evidence_log` + `docs/reflection-A3_5.md` |
> | **S1 Self-Harness P0-P2** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S1.md` |
> | **S2 可控遗忘常态化** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S2.md` |
> | **S3 频次收尾（trace 带 turn/controlTotal）** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S3.md` |
> | **S4 自适应 A/B** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S4.md` |
> | **S5 角色失效修复** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S5.md` |
> | **S6 注入检测** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S6.md` |
> | **S7 CPU 小模型基准** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S7.md` |
> | **S8 审计自校准落盘** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S8.md` |
> | **S9 有状态反馈** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S9.md` |
> | **M4 注入预算 token 化** | ✅ done | 证据见 `evidence_log` + `docs/reflection-M4.md` |
> | **M6 安全规则不可覆盖** | ✅ done | 证据见 `evidence_log` + `docs/reflection-M6.md` |
> | **GWT_FEP_done GWT 共享状态总线 + FEP 预期闭环** | ✅ done | 证据见 `evidence_log` + `docs/reflection-GWT_FEP_done.md` |
> | **archive_dedup 压缩存档去重** | ✅ done | 证据见 `evidence_log` + `docs/reflection-archive_dedup.md` |
> | **regression_106 回归审计 106 PASS / 0 FAIL** | ✅ done | 证据见 `evidence_log` + `docs/reflection-regression_106.md` |
> | **gpu_guard GPU 引擎守护** | ✅ done | 证据见 `evidence_log` + `docs/reflection-gpu_guard.md` |
> | **watcher_freq3 learn_watcher 频次三层改造** | ✅ done | 证据见 `evidence_log` + `docs/reflection-watcher_freq3.md` |
> | **rebaseline 路线图重定基线** | ✅ done | 证据见 `evidence_log` + `docs/reflection-rebaseline.md` |
> | **outcome_all 结果反馈捕获 / 确定性门控 / 三角色 / P0-P2 心智拼图** | ✅ done | 证据见 `evidence_log` + `docs/reflection-outcome_all.md` |
> | **M1 情景检索进主循环** | ✅ done | 证据见 `evidence_log` + `docs/reflection-M1.md` |
> | **M8 轨迹 FSM 监控器** | ✅ done | 证据见 `evidence_log` + `docs/reflection-M8.md` |
> | **S_GWT GWT 共享状态总线** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_GWT.md` |
> | **S_FEP FEP 预期闭环** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_FEP.md` |
> | **S_SCOPE spec 阈值分类标定** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_SCOPE.md` |
> | **S_CRITIC Critic 去同源化** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_CRITIC.md` |
> | **S_ARCHIVE 压缩存档去重 + 角色诊断** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_ARCHIVE.md` |
> | **S_ROLE 角色失效修复** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_ROLE.md` |
> | **S_TRACE trace 上下文字段** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_TRACE.md` |
> | **S_SECURITY 安全规则不可覆盖** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_SECURITY.md` |
> | **S_REVIEW 有状态反馈环** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_REVIEW.md` |
> | **S_INJECT 注入检测规则层** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_INJECT.md` |
> | **S_BUDGET 注入预算 token 化** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_BUDGET.md` |
> | **S_OUTCOME 结果反馈捕获** | ✅ done | 证据见 `evidence_log` + `docs/reflection-S_OUTCOME.md` |
> | **下一项** | ⏸ 空 | `--next` 无 autonomous ready 项，剩余需人工开闸 |
>
> 机器真相 = [ROADMAP_GRAPH.md](ROADMAP_GRAPH.md)；本表由 `--apply` 自动写，人读与机器不漂移。
<!-- HUMAN_PROGRESS_END -->

**项目是什么**：给 dsh（DeepSeek Harness）的一个 cordis 插件，通过**模型外部**的确定性脚手架
（规则注入 + 门控 + 旁路学习），让一个 8G 显存上的 35B MoE 模型表现得像可靠 agent。**模型权重一个字节没动。**

**做到哪了（v2.26.5）**：**短期目标 S1-S9 全部完成**，地基 + 数据变现层都已在线——
GWT 总线、FEP 闭环、CritBank（真实计数+可控遗忘）、审计自校准（误差可度量）、
有状态反馈环（NSED 思想）、注入检测（规则层）、Self-Harness P0-P2（**35B 已能亲自提 patch**）。
trace 已达 **8147 行**，弱点聚类产出 **6 簇**（深度维护修复 verify_on_stop 漏检后从 4→6）+ 13 条受保护行为。

**现在的位置**：从「把数据变成能力」转入「**让器官间流动**」——中期执行期。
**M1（v2.26.5）/ M8（v2.26.6）/ A1（v2.26.7）均已完成**——情景检索、FSM 局部预警、归档机器判据都在线。
**当前 `--next`=NO_READY_ITEM：自治区间耗尽**，剩余卡为 backlog/manual-blocked，需人工拍板或补判据。
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

**2026-11-20 新增评估**：
- **[能力阶梯 / agent 成长手册](CAPABILITY_LADDER.yaml)** —— **机器可读**的 23 张成长卡片（15 心智项 + 7 自主化阶 + 判据），每张回答 what/why/解锁/好处/代价/坑/反思；执行器 `tools/roadmap_check.py`（`--next` 选卡 / `--card ID` 读卡 / `--dry-run` 验判据）。设计见 [成长卡片说明](docs/GROWTH_CARD_DESIGN_20261120.md)。
- [学会自己走路 · 执行阶梯](docs/WALKING_PLAN_20261120.md) —— **用户新目标**：把"自主按路线图更新自己"切成 6 阶（阶0数据清洗→阶1自动验收→阶2自动勾选→阶3自动选任务→阶3.5安全地基→阶4任务内决策→阶5常驻闭环），每阶只用现有器官、零 LLM 可验证。**与下面 15 个心智器官目标并行，不替代**；可立即开始阶0+阶1（1-2天、零显存）。
- [自主走路能力评估](docs/AUTONOMY_GAP_20261120.md)——当前 L1（人工驱动+局部自动），路线图已机器可写回（`--apply`）；到 L2 只差"给 15 个条目补机器判据 + 60 行核验脚本"，到 L3/L4 还差常驻循环与审批上移。~~注意：本 ROADMAP 目前不是机器可更新的——这正是自主化的第一道缺口。~~
**2026-11-20 已修复**：状态真相源拆到 [ROADMAP_GRAPH.md](ROADMAP_GRAPH.md) + `roadmap_check.py --apply` 机器写回；人类视图由 §1 进度表和下方卡片详情自动同步。缺口已闭合。
- [长期记忆→心智模型资产盘点](docs/MEMORY_TO_MIND_MODEL_20261120.md)——负面证据库 / 确定性信号 / 成本经验可迁移；含 8G 显存可行性。

---

<!-- HUMAN_CARDS_BEGIN v1：由 roadmap_check.py --apply 从 LADDER 语义源生成，勿手改 -->
> ### 📇 卡片详情（人读版 · 为什么做每张卡）
> 语义来自 CAPABILITY_LADDER.yaml，状态来自 ROADMAP_GRAPH.md；本块每次 `--apply` 自动重写。
> 机器判据/验证方法见 `--card <ID>`；这里只回答"做什么 / 为什么 / 对我有啥好处 / 坑 / 何时停"。
> ⚠️ 全局铁律（所有卡通用，故不再逐条重复）：说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 ≠ 进程活着。

#### 🟡 排队（backlog）（12 张）

**`A2` 会指路（自动勾选，只写权威源）**
- **做什么**：roadmap_check.py 自动勾选确定性条目，只写权威源
- **为什么**：把人从"每次勾选"解放到"审 git diff"，闸门上移但不取消
- **对 agent 的好处**：我改完就能自己记进度，人只需看一眼 diff
- **坑/边界**：必须写权威源 CAPABILITY_LADDER.yaml，不写 p/bench 副本；写回前 git diff --check；主观项不勾选
- **做完要反思**：自动勾选有没有和人的判断冲突过？；diff 审阅里人最常改哪类勾选？
- **何时停**：出现一次假完成勾选 → 退回人工勾选

**`A3` 会迈步（预批低风险队列取任务）**
- **做什么**：watcher 从人工预批的低风险队列取任务，执行→gate→写回
- **为什么**：没人按"开始走"按钮，自进化 P3 一直没启动
- **对 agent 的好处**：我没任务时不用等着人派活，能从已批准队列里自己找活干
- **坑/边界**：只执行队列内任务，绝不碰队列外；限单次预算（35B 每步 11s）；白名单含 index.mjs 细粒度项需 A3.5 先完成
- **做完要反思**：队列里的任务我完成率多少？失败的是哪类？；有没有越界执行过队列外任务？
- **何时停**：越界执行 1 次或连续 2 次任务失败

**`A4` 会转弯（旁路 meta_decision）**
- **做什么**：把 D1 重复探测等信号从 prompt 软提示升级为旁路 meta_decision 决策器
- **为什么**：控制回合只是 prompt 反思，代码无 abandon/skip 路径
- **对 agent 的好处**：我卡住时能真的"换条路"，而不是在 prompt 里被提醒了还继续重复
- **坑/边界**：做旁路决策器，不改 D1-D5 判定本体（禁改面）；先只做 D1（最明确）；命中写结构化 trace
- **做完要反思**：meta_decision 跳过后再没重复探测的比例多少？；有没有误跳过本该继续的动作？
- **何时停**：误跳过率>10%

**`A5` 自己走（常驻闭环）**
- **做什么**：全链常驻闭环：读图→选任务→执行→验收→写回→反思→下一轮
- **为什么**：把前面所有器官连成 24/7 自走系统
- **对 agent 的好处**：我真正"学会走路"——没人盯着也能在低风险区持续成长
- **坑/边界**：只在白名单+预算内；保留人工验证基线，定期 diff 防语义漂移；L5 自我改写目标永不做
- **做完要反思**：一周里我沉淀了几条可复用经验？爬后面的任务是否真的更快了？；有没有"越爬越偏"的漂移迹象？
- **何时停**：7 天内出现 1 次越界或需人工救场 → 暂停闭环

**`M3` 用户意图 BDI 三槽**
- **做什么**：把 s.bdi 单槽升级成 belief/desire/intention 三槽，承载用户意图跨压缩不丢
- **为什么**：单槽装不下"用户要什么/信什么/打算怎么做"，压缩后约束丢失，意图漂移检测无状态可依
- **对 agent 的好处**：长任务压缩后仍记得用户最初要什么，不会因为 context 缩短而跑偏
- **坑/边界**：改 index.mjs 的 bdi 状态结构，不在白名单细粒度 target 内 → 人工确认；复用现有 mind_state kind 埋点，别新造 kind；用户意图多轮冲突时以最新指令为准（ADR-0014 不质疑式干预）
- **做完要反思**：三槽里哪一槽最常在压缩后丢失？；有没有把用户临时指令误当长期意图的情况？
- **何时停**：bdi 结构改动导致现有 control_turn/FEP 断言回归

**`M9` 意图分类器**
- **做什么**：用意图分类器填 BDI 意图槽，高置信直接用、低置信交三角色
- **为什么**：规则判意图太脆，但本机 8G 挂 embedding 编码器不可行
- **对 agent 的好处**：意图识别从"靠关键词猜"变成有置信度的判断，低置信时会主动求助而非乱做
- **坑/边界**：8G 显存硬约束：先验证 86M CPU 分类器，别直接上 embedding；GLiClass 英文为主，中文表现未验证；共享一个编码器，不为每意图训独立模型
- **做完要反思**：中文意图分类的置信度分布如何？低置信阈值定多少合适？；分类器错了有没有被三角色拦住？
- **何时停**：86M CPU 延迟>500ms 或中文准确率不达 92%

**`M2` 会话树实时化**
- **做什么**：让 session_tree.py 从事后分析变实时写 parent 指针，支持从任一节点 fork
- **为什么**：现在只能事后重建会话树，无法在长任务中实时知道"我现在是哪条支线"
- **对 agent 的好处**：能真正 rewind 到任意节点重试，而不用重读整段历史
- **坑/边界**：append-only 历史语义，fork 不能改写既有记录（ADR-0013）；不付 KV 后缀税——靠追加不靠改写
- **做完要反思**：fork 后旧节点的经验有没有被正确继承？；有没有因为 parent 指针错而 rewind 到错误节点？
- **何时停**：parent 指针写入导致历史 trace 被改写或 KV 后缀税回升

**`L2` 标准化 eval**
- **做什么**：把自建 P3/P4/P5 评测迁移到 SWE-bench Verified 子集
- **为什么**：自建 bench 无法与社区同基准可比，外部效度存疑
- **对 agent 的好处**：知道自己在社区真实水平的位置，不再自我感觉良好
- **坑/边界**：高成本：迁移+跑基准；长期优先，不插队
- **何时停**：无（长期人工排期）

**`L6` 专属误差预测器**
- **做什么**：用 trace + 35B 标注训 0.5B 二分类误差预测器
- **为什么**：由 M8 的 FSM 局部信号解锁，不再空中楼阁
- **对 agent 的好处**：能预测"这一步会不会错"，提前触发审计而非事后补救
- **坑/边界**：只做单次蒸馏 n=1（递归自噬第 9 代会退化成野兔清单）；保留 UNCERTAIN 样本；长轨迹因果归因仍交主模型
- **何时停**：无（依赖 M8 完成后人工评估）

**`L1` FEP 深化 → 世界模型**
- **做什么**：FEP 从"产物是否存在"升级为"产物内容满足 what"的世界模型断言
- **为什么**：存在性判据太浅，产物写错内容也能过
- **对 agent 的好处**：能真正判断"做对了没"，不只是"做了没"
- **坑/边界**：需 M1+M3+M9 先完成；误报不能侵占注入通道（ADR-0017）；断言精度/召回必须可测
- **何时停**：无（长期，依赖三个前置）

**`L8` 多标签心智编码器**
- **做什么**：一个前向同时输出意图+风险+难度，写进 GWT 共享状态
- **为什么**：现在三个判断分散，128 标签仅掉 7-20% 吞吐可行
- **对 agent 的好处**：一次推理拿到三维心智状态，比三次判断省时
- **坑/边界**：GLiClass 英文为主，中文表现必须先验证；8G 可行性待证
- **何时停**：无（探索项）

**`L7` FAKEOK 抑制（探索）**
- **做什么**：验证"防提前假装完成"的轻量机制
- **为什么**：S4 发现提示让 FAKEOK→PASS（token 未降）
- **对 agent 的好处**：减少"看着完成了其实没做"的自欺
- **坑/边界**：先小规模对照，不占正式坑位；与 D4 交付闸门同源
- **何时停**：无（探索）

#### ⛔ 需人工拍板（manual-blocked）（6 张）

**`M5` 工具面结构改造**
- **做什么**：把 28 个工具收敛到最小内核，低频能力进 skill 卡
- **为什么**：工具面过宽会退化（社区上限约 40），但"哪些进内核"是产品判断
- **对 agent 的好处**：每次决策要在更少的工具里选，减少选择噪声
- **坑/边界**：⛔ 用户拍板项，agent 不得自主决定；不动则保持现状，别为了改而改
- **何时停**：无（人工决策项，不自主执行）

**`M7` 格式修复器（降级）**
- **做什么**：格式修复器：只做格式重写、不判断对错，35B 首轮兜底
- **为什么**：模型输出格式错误浪费后续步骤，但前置 86M 分类器还没验证
- **对 agent 的好处**：格式问题不用走到 35B 全量推理就能修，省 11s/次
- **坑/边界**：降级项：0.6B 已证伪（4-6s 比文献慢 10×）；必须 86M CPU 延迟<500ms + A/B 端到端提速才上
- **何时停**：无（前置未满足，manual-blocked）

**`S6_model` S6 模型层升级**
- **做什么**：S6 从规则层升级到 86M Prompt-Guard 模型层
- **为什么**：规则层够用；模型层是误报率兜底，但 FPR 98% 的教训在前
- **对 agent 的好处**：注入检测从关键词匹配升级到语义级，减少漏报
- **坑/边界**：必须先阈值重标定，FPR 98% 的坑不能再踩；规则层已在线，实测误报率>2% 才做模型层
- **何时停**：无（manual-blocked）

**`L5` 小模型 Critic 预警（降级）**
- **做什么**：86M 小模型 Critic 做轻量预警
- **为什么**：0.6B 扫一次 5s 不实用；但小 judge 一致率仅 45-60%，需谨慎
- **对 agent 的好处**：能在主模型提交前快速扫一眼风险
- **坑/边界**：降级：0.6B 已证伪，须换 86M 且召回 A/B≥80%；未命中只记 trace 不拦截
- **何时停**：无（降级观望）

**`L3` 脑功能分区空白区**
- **做什么**：补眶额价值/脑干稳态的脑功能空白
- **为什么**：BRAIN_PARITY 盘点的空白区
- **对 agent 的好处**：多目标冲突时有价值排序
- **坑/边界**：调研完成，待决定是否落 ADR；观望
- **何时停**：无（观望）

**`L4` 独立轨道（上游 PR）**
- **做什么**：上游 autoparser PR 合并后撤本地补丁，升级引擎
- **为什么**：跟上游减少维护负担
- **对 agent 的好处**：不用每次升级重打补丁
- **坑/边界**：#29307 未合并，本地 2 行补丁还在；不插队
- **何时停**：无（等上游）

<!-- HUMAN_CARDS_END -->

## 2. 性价比速查（先做哪个？）

> **性价比 = 收益 / 成本**；`解锁` 指完成它后哪些目标变便宜。按此表从上到下领活。
> 这是**决策辅助**，不是硬顺序——硬依赖见 §6，一波没验收不开始下一波。
> ⚠️ 本表排序是历史快照；**实时状态以 §1 自动进度表和上方卡片详情为准**（M1/M8/A1 均已完成；当前 `--next`=NO_READY_ITEM，自治区间耗尽）。
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
**关键**：M8 已完成（heldout_auc=0.8927，局部信号），L6 误差预测器的前置已就绪；A1 完成后 23 张卡里自治区间已耗尽（`--next`=NO_READY_ITEM），剩余卡需人工拍板。

| 排序 | 目标 | 收益 | 成本 | 依赖 / 解锁 | 建议 |
|---|---|---|---|---|---|
| ~~1~~ | ~~M1 情景检索进主循环~~ | 高 | 中 | GWT + S1 evidence bundle 均已就绪 | ✅ **已完成**（v2.26.5，见 §7）|
| ~~2~~ | ~~**M8 轨迹 FSM 监控器**~~ | 高 | 中低 | S1 trace → L6 前置 | ✅ **已完成**（v2.26.6）：heldout_auc=0.8927，`FSM_SIGNAL` 已接入 |
| ~~A1~~ | ~~**会记路（机器判据+dry-run）**~~ | 高 | 中 | A0 → A2/A3 | ✅ **已完成**（v2.26.7）：12 归档卡 + 独立回测 13/13 |
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

> **✅ 已完成 35 项**（S1-S9 + M1/M4/M6/M8/A0/A1/A3_5 + 地基）已收进 **§7 归档 / 权威块**，详见 §1 自动进度表。
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

> 共同特征：结构已在（GWT 总线已立）、数据已变现（S1 evidence bundle + trace 8147 行），缺的是把离线脚本接进主循环。
> **执行顺序**：~~M1 ✅~~ → **M8（当前）** → M3 → M9 → M2 → M5（等拍板）→ M7 → S6模型层。

| # | 目标 | 性价比 | 依赖 | 完成标准（DoD） | 状态 |
|---|---|---|---|---|---|
| ~~**M1**~~ | ~~**情景检索进主循环**~~ | 高/中 | GWT + S1 evidence bundle | 已完成：`episodicSearch` 接入控制回合 + `evidence_cited` 埋点（reflection-M1.md）| ✅ **done** |
| **M8** | **轨迹 FSM 监控器（新）** | 高/中低 | S1 的 8147 行 trace（已就绪）| 把 trace 压成 FSM 做局部失败预测（重复探测/路径解析/工具报错）；held-out AUROC ≥0.85；**只做局部可观察信号**，长轨迹因果归因交主模型（Jev 实测 0.56≈随机）；产出接入 evidence bundle。见 [分类器评估](docs/CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md) | [ ] |
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
| **2 连接期** | 器官间流动 | GWT + evidence bundle 均已立，情景检索/会话树可进主循环 | 🟡 **当前波次**：M4 ✅ → M1 ✅ → **M8（当前）** → M3/M2 |
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
| **完成状态验收审计** | v2.25.0 | [验收报告](docs/COMPLETION_AUDIT_20261119.md)：修 3 个"宣称完成但没落地"缺口；JS **160 PASS/0 FAIL**；S6/S8/S9 真实会话验证 |
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

---
