# 路线图（活文档）

> **怎么读这份文件**（2026-11-21 重构，按人的阅读顺序）：
> **① 当前这张卡**（正在做/下一张）→ **② 未来要做哪些卡**（脉络与依赖）→ **③ 已完成哪些卡** → **④ 明确不做**。
> 机器真相在 [ROADMAP_GRAPH.md](ROADMAP_GRAPH.md)，语义字段在 [CAPABILITY_LADDER.yaml](CAPABILITY_LADDER.yaml)；
> 本文件是人读视图，§1-§3 自动块由 `tools/roadmap_check.py --refresh` 生成，勿手改。
> 更新于 **2026-11-21**（v2.26.6）；入口 [README](README.md) · 细节 [docs/](docs/README.md) · 决策依据 [decisions/](decisions/README.md)。

---

## 1. 当前这张卡

<!-- HUMAN_CURRENT_BEGIN v2：由 roadmap_check.py 自动生成，勿手改 -->
### ▶ 当前这张卡：`S12` 补丁应用闭环（禁写脚本不落地）

- **做什么**：检测"写了修复脚本但没真正应用"的模式：补丁脚本(_apply_*.py/_fix_*.py)写入后必须有对应的apply证据（目标文件mtime变化+语法通过），否则守卫提示"脚本已写但未应用"
- **为什么**：A1_6一张卡留下5个补丁脚本全没应用，浪费几十分钟——"写了脚本"≠"应用了脚本"是新变体的说要做不做
- **依赖 → 解锁**：A1 → —
- **对 agent 的好处**：堵住"用写脚本代替改文件"的绕路，把时间花在真正落盘
- **坑/边界**：别误伤合法的临时分析脚本；apply证据要用环境事实（目标mtime+内容），不认模型声明
- **何时停**：无法可靠关联补丁脚本与目标文件
- **机器判据**：0/3 通过（`--card S12` 看详情；⚠️ 判据尚未全部实现，领卡即开工）

> **为什么是这张**：当前有 3 张 ready 卡，`find_next` 按 (risk, tier, -roi, id) 排序——
>
> | 候选 | risk | tier | 判据 | 说明 |
> |---|---|---|---|---|
> | `M10`  | low | 2 | 4/4 | tier=2，排在后面 |
> | `S12` **← 选中** | low | 缺失→按0排 | 0/3 | tier 缺失被当作 0，故排在前面 |
> | `S13`  | low | 缺失→按0排 | 0/3 | tier 缺失被当作 0，故排在前面 |
>
> ⚠️ 这张是**算法机械排序**结果，不是人工推荐的"最该做"。若判据全 FAIL，说明卡只写了状态没做实现。
<!-- HUMAN_CURRENT_END -->

## 2. 未来要做哪些卡（脉络）

<!-- HUMAN_FUTURE_BEGIN v2：由 roadmap_check.py 自动生成，勿手改 -->
### 未来要做哪些卡（23 张，按依赖脉络分组）
> 阅读顺序：现在能做 → 后续排队 → 需人工拍板。每张卡的 `依赖→解锁` 显示它在脉络中的位置。

#### 现在能做 / 进行中（4）

| 卡片 | 状态 | 依赖 → 解锁 | tier |
|---|---|---|---|
| `M10` 会话生命周期治理（刹车） | 🟢 ready | A1 → — | 2 |
| `S12` 补丁应用闭环（禁写脚本不落地） | 🟢 ready | A1 → — | - |
| `S13` verifyRan收紧（read≠验证） | 🟢 ready | A1 → — | - |
| `S17` 函数外置模式推广（自修改地基） | 🔵 doing | — → — | 2 |

#### 后续排队（backlog，按 tier 分层）（12）

| 卡片 | 状态 | 依赖 → 解锁 | tier |
|---|---|---|---|
| `M2` 会话树实时化 | ⚪ backlog | GWT_FEP → — | 2 |
| `M3` 用户意图 BDI 三槽 | ⚪ backlog | GWT_FEP → M9、L1 | 2 |
| `M9` 意图分类器 | ⚪ backlog | M3 → L1 | 2 |
| `L1` FEP 深化 → 世界模型 | ⚪ backlog | M1、M3、M9 → — | 4 |
| `L2` 标准化 eval | ⚪ backlog | — → L1 | 4 |
| `L6` 专属误差预测器 | ⚪ backlog | M8 → — | 4 |
| `L7` FAKEOK 抑制（探索） | ⚪ backlog | — → — | 4 |
| `L8` 多标签心智编码器 | ⚪ backlog | GWT_FEP → — | 4 |
| `A2` 会指路（自动勾选，只写权威源） | ⚪ backlog | A1 → — | - |
| `A3` 会迈步（预批低风险队列取任务） | ⚪ backlog | A2 → — | - |
| `A4` 会转弯（旁路 meta_decision） | ⚪ backlog | A3_5 → — | - |
| `A5` 自己走（常驻闭环） | ⚪ backlog | A1、A2、A3、A3_5、A4 → — | - |

#### 需人工拍板（manual-blocked）（7）

| 卡片 | 状态 | 依赖 → 解锁 | tier |
|---|---|---|---|
| `L3` 脑功能分区空白区 | 🔴 需拍板 | — → — | 4 |
| `L4` 独立轨道（上游 PR） | 🔴 需拍板 | — → — | 4 |
| `L5` 小模型 Critic 预警（降级） | 🔴 需拍板 | — → — | 4 |
| `M5` 工具面结构改造 | 🔴 需拍板 | — → — | 3 |
| `M7` 格式修复器（降级） | 🔴 需拍板 | — → — | 3 |
| `S10` 推理活性判据纠偏（取消单帧采样） | 🔴 需拍板 | A1 → — | - |
| `S6_model` S6 模型层升级 | 🔴 需拍板 | S6_rule → — | 3 |

> 完整卡片详情（what/why/坑/反思）见 `--card <ID>`；波次依赖逻辑见下方"脉络说明"（手工段）。
<!-- HUMAN_FUTURE_END -->

### 脉络说明（手工段，稳定不变）

短/中/长期是**执行节奏**（随进度重排）；下面四波是**依赖逻辑**（稳定不变）。判断新工作先问属于哪波：

| 波次 | 主题 | 依赖逻辑 | 状态 |
|---|---|---|---|
| **0 地基期** | 数据底座 + 共享总线 | 没 outcome 无从比对、没 GWT 只能手动搬运状态——所有后续机制的前提 | ✅ 完成（v2.8~v2.12）|
| **1 回填期** | 把数据变成能力 | FEP 偏差 + outcome 已攒够，喂技能进化与遗忘 | ✅ 完成（v2.22：S1-S9 全部）|
| **2 连接期** | 器官间流动 | GWT + evidence bundle 均已立，情景检索/会话树可进主循环 | 🟡 当前波次（M4/M1/M8 已 done，下一步见 §1）|
| **3 进化期** | 从经验变聪明 | **投毒防御必须先于写回闭环**——SkillJack：80% 攻击删源后仍存活 | 🔴 长期 L1-L7（P0 白名单已立，P3 未启动）|

**双向迭代**：依赖链不只向上——第 4 层审计需求曾反向复用第 1 层 spec 日志信号；
FEP 注入曾挤掉 D5 审计额度，反向促成"学习信号不占运行时注入通道"（[ADR-0017](decisions/0017-gwt-first-then-fep.md)）。
依据：[ADR-0017](decisions/0017-gwt-first-then-fep.md) · [重定基线分析](docs/ROADMAP_REBASELINE_20261119.md) · [能力阶梯执行器](tools/roadmap_check.py)。

## 3. 已完成哪些卡

<!-- HUMAN_DONE_BEGIN v2：由 roadmap_check.py 自动生成，勿手改 -->
### 已完成哪些卡（30 张）
> 唯一清单——历史归档、短期盘点不再重复列这些卡。

- ✅ `A0` 数据可信（sid 黑名单）
- ✅ `A1` 会记路（机器判据 + dry-run 核验）
- ✅ `A3_5` 安全地基（真实 diff + e2e + 回滚）
- ✅ `A1_5` 判据元验证（防假绿）
- ✅ `A1_6` 守卫 L1 补将来时承诺检测
- ✅ `A1_7` 评审机制可观测性
- ✅ `S15` 选择性验证深度（ Selective Verification）
- ✅ `S16` 工具描述瘦身与示例
- ✅ `S1` Self-Harness P0-P2
- ✅ `S2` 可控遗忘常态化
- ✅ `S3` 频次收尾（trace 带 turn/controlTotal）
- ✅ `S4` 自适应 A/B
- ✅ `S5` 角色失效修复
- ✅ `S6` 注入检测
- ✅ `S7` CPU 小模型基准
- ✅ `S8` 审计自校准落盘
- ✅ `S9` 有状态反馈
- ✅ `M4` 注入预算 token 化
- ✅ `M6` 安全规则不可覆盖
- ✅ `GWT_FEP_done` GWT 共享状态总线 + FEP 预期闭环
- ✅ `archive_dedup` 压缩存档去重
- ✅ `regression_106` 回归审计 106 PASS / 0 FAIL
- ✅ `gpu_guard` GPU 引擎守护
- ✅ `watcher_freq3` learn_watcher 频次三层改造
- ✅ `rebaseline` 路线图重定基线
- ✅ `outcome_all` 结果反馈捕获 / 确定性门控 / 三角色 / P0-P2 心智拼图
- ✅ `M1` 情景检索进主循环
- ✅ `M8` 轨迹 FSM 监控器
- ✅ `S11` 写后校验覆盖全部写工具
- ✅ `S14` 编辑协议升级（降低复现负担）

<!-- HUMAN_DONE_END -->

历史归档（按版本的详细验证记录）见 [CHANGELOG](CHANGELOG.md)；
被证伪方向与评估结论见 §4 及 [docs/](docs/README.md)。

## 4. 明确不做（防止新人重造轮子 / 走回头路）

| 不做 | 理由 |
|---|---|
| 多模态 / CUA | 与纯文本 8GB 环境不匹配，社区主战场但非我们场景 |
| 通用 agent 框架 / 向量检索代码 | [Harness Engineering 2609.00006](https://arxiv.org/abs/2609.00006)：11 个主流 harness 全用确定性循环，无人用 |
| 训练 / 微调模型（含 RL 优化 harness）| 与"权重零改"路线冲突；agent-lightning 等 RL 路线只作技术雷达 |
| 堆更多 judge | [Apple: 9 judge≈2 票](docs/MIND_GAPS_RESEARCH.md)；信号源多样性 >> judge 数量 |
| 强制二选一 / 质疑式干预 | 现场"写完又重做"+ 自我纠错需外部信号（ICLR2024）；原 76.6% 数据系幻觉已作废（[ADR-0014](decisions/0014-reject-forced-choice-injection.md)）|
| FEP 偏差走运行时注入通道 | 实测挤掉 D5 审计额度（ADR-0017）——学习信号只进 trace/学习队列 |
| 改 Electron 启动参数降 3D | `--disable-gpu` 等已证伪反效果（[Electron #50469](https://github.com/electron/electron/issues/50469)）；见 [GPU 守护](docs/GPU_ENGINE_GUARD.md) |
| 无差别提高自动化频次 | 频次审计证明大部分参数经实测校准合理；只按证据调（[CADENCE_REDESIGN](docs/CADENCE_REDESIGN.md)）|
| **小模型（0.8B 级）做审计/纠正/验收** | JudgeBench 小 judge 一致率仅 45-60%（近抛硬币）；"强 judge 才鲁棒"要求 judge ≥ actor；弱 verifier 放行强 actor 错误比不审查更糟。**验收员本就是 Python 规则，零 LLM**（[评估](docs/HETEROGENEOUS_MODELS_EVALUATION.md)）|
| **0.6B/1B 级 LLM 做实时外设** | S7 实测：Qwen3-0.6B Q8_0 纯 CPU 分类 4.2s / 格式 6.0s（比文献边缘设备 392ms 慢 10×），且 thinking 吃光 content 需 max_tokens≥512。实时注入检测须用 86M 级 BERT 分类器，不是 LLM（[基准](docs/S7_SMALL_MODEL_BENCH_RESULT.md)）|
| **开启 adaptiveThinkEnabled 默认值** | S4 P3 A/B：token 4172→4168 未降（DoD 要求"token 降且成功率不降"）；单次 FAIL→PASS 有噪声，不足以证明机制有效。保持默认关闭（[结果](docs/S4_ADAPTIVE_AB_RESULT.md)）|
| **递归自喂式蒸馏** | Nature 2024：第 9 代退化为"野兔清单"；只做单次 n=1 且保留 UNCERTAIN 样本（[评估](docs/FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md)）|

---

---

> **知识资产沉淀规则（2026-11-19 用户明确要求）**：每次规划/调研/方案磋商的结论必须落进本文件（或专属 docs/ 评估文档 + 这里留链接），不能只留在对话里。
> **被证伪的方向同样要记**（§4 + 对应评估文档）——避免重复踩坑，让没参与讨论的 AI 接上决策脉络。
