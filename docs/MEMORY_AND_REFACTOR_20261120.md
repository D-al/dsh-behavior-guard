# 记忆蒸馏与重构模式（2026-11-20~21）

> 三层记忆→心智模型、重构模式、深度维护两版、完成审计

> 本卷合并 8 份原报告（2026-11-25 整理）。

## 本卷目录

- `MEMORY_TO_MIND_MODEL_20261120.md`
- `REFACTOR_PATTERN_20261121.md`
- `REFACTOR_ASSESSMENT_20261120.md`
- `DEEP_MAINTENANCE_20261119.md`
- `DEEP_MAINTENANCE_20261121.md`（原文件保留为引用桩）
- `COMPLETION_AUDIT_20261119.md`
- `BRAIN_AUDIT_20261118.md`
- `AUTOCARD_POSTMORTEM_20261122.md`

---

## 原报告：`MEMORY_TO_MIND_MODEL_20261120.md`

## 长期记忆 → 心智模型：可迁移资产盘点（2026-11-20）

> 用户问：我的长期记忆有哪些？哪些能提供给"心智模型"？要考虑硬件配置和可实现性。
> 本文把三层记忆与项目心智模型框架（MIND_GAPS / BRAIN_PARITY / ROADMAP）交叉，筛出**可迁移 + 本机跑得动**的部分。

---

### 0. 我的三层记忆（实际内容，非笼统描述）

| 层 | 位置 | 内容性质 | 体量 |
|---|---|---|---|
| L1 云侧画像 | 服务端注入 | 用户长期偏好摘要（隐式学习，只读）| 短 |
| L2 用户级本地 | `~/.workbuddy/.../MEMORY.md` | 显式规则：子任务不瞎等/能并行就派/沉淀规则/权限代劳/进度可视化 | 6 条 |
| L3 项目级 | `.workbuddy/memory/MEMORY.md` + 24 个日志 | 本机硬件账、35B 调优、harness 架构、坑与证伪、平台整治铁律 | ~13KB 精要 + ~700KB 日志 |

**对心智模型有价值的，几乎全在 L3**——因为它是"实测发生过什么、什么有效什么被证伪"的一手记录，而心智模型最缺的正是**经验数据与负面证据**，不是抽象框架。

---

### 1. 硬件与可实现性（硬约束先行）

**机器**：i7-12650H（10C/16T）/ 64G DDR4-3200 / **RTX 4060 Laptop 8G** / 无核显 / 1.9T NVMe。
**模型**：只有 Q4 的 Qwen3.6-35B-A3B（21.28 GiB），20K decode 27.2 t/s、prefill 800 t/s。
**显存账（96K）**：权重 2326 + KV 780 + DeltaNet 377（不可压）+ MoE cache 1022 + compute 550 + MTP 600 + 视觉 —— 空闲安全线 ≥450 MiB。

**据此的三条可行性判定：**

1. **8G 显存是本机一切方案的天花板**。任何"再挂一个分类模型/embedding 模型占显存"的方案直接不可行（L8 多标签编码器、多 judge 都要过这关）。
2. **CPU 侧 64G 是可用余量**。GLiClass 类小分类器、FSM 监控、向量检索放 CPU 完全可行——但要注意"沙箱派生进程被 CPU 限速"，真实速度需走计划任务测。
3. **主模型推理成本极高**（20K 每步约 11s）。**任何"多花一次 LLM 调用"的机制都要算账**——这正是记忆里"Critic 审计 13-20s、D5 审计 10-20s，只在门控触发时付"的根据。

---

### 2. 可直接喂给心智模型的记忆资产（按价值排序）

#### 🥇 A. 负面证据库（最稀缺、最有价值）

心智模型普遍只记录"什么成功"，记忆里有大量**证伪数据**，这是训练/提示价值最高的部分：

- **判据类**：聚合 GPU util% 骗人（空闲也 100%）；decode t/s 是误导指标（cpu-share 伪优化 +37% decode 但端到端慢 2.4×）。
- **模型能力类**：不能依赖模型元认知（小模型只搜 20% 该搜的）；9 个 judge ≈ 2 票（堆 judge 价值低）；判断类角色用异质小模型证伪。
- **机制类**：思考硬切/改写历史思维链（KV 后缀税 25-44s）均失败；温度 U 形曲线（Q4 最优 0.7）；reasoning-budget 硬切失败。
- **平台类**：`!!js [...]` 让 dsh 起不来；junction 被 realpath 解析导致分组割裂；Force kill 不触发 finally。

**可落地形**：这些是现成的 `critbank.json` 条目候选 —— 每条都有"触发条件 + 错误做法 + 正确做法"，天然是"情景记忆 + 程序性记忆"的双重素材。

#### 🥈 B. 可观测性规则（把"感觉"变成"信号"）

- **Copy 引擎 + 带宽 + 功耗** 判断推理是否真在跑（替代聚合 util%）——这是"感知"模块的真实信号源。
- **MTP 接受率 <0.65** 触发审计门控——已有确定性阈值。
- **trace 证据分层**（L1 代码存在 → L5 独立产物）——防止"心智模型自欺"的元规则。

**可落地形**：这些就是 BRAIN_PARITY 里"杏仁核显著性"和"脑干稳态"缺口的最轻量替代——用**确定性信号**而非情绪模拟。

#### 🥉 C. 已实现的认知功能映射（避免重造轮子）

记忆记录了 8 功能框架已对齐 CoALA：感知/工作记忆/情景记忆/执行控制/验证免疫/元认知/可塑性/自我模型，以及 P0-P2 心智拼图、GWT 总线、FEP 闭环的真实 trace 证据（真实 sid 各 5-19 次命中）。

**可落地形**：心智模型若要做"自我认知"，不该重新设计，而应**读现有 trace 做自述**——"我现在GWT状态是什么、FEP偏差多少、CritBank命中几条"。这是零额外 LLM 成本的自我模型。

#### D. 成本/调度经验（决定可实现性）

- 深检/审计成本 0.3s / 0 LLM；Critic 审计 13-20s、D5 审计 10-20s → 门控触发才付。
- 工具面 28 个、单会话只用 11 个，社区上限 ~40 → 不加 MCP。
- 压缩 thresholdRatio 0.55 / retain 16384 / headroom 16384 —— KV cache 后缀税约束。

**可落地形**：心智模型的"注意力预算"和"记忆巩固策略"应直接沿用这些已校准参数，不要新拍脑袋。

---

### 3. 明确不可迁移 / 需改造的部分

| 记忆内容 | 为什么不能直接给心智模型 |
|---|---|
| 35B 具体调优参数（CTX/NGL/UBATCH…） | 是本机引擎配置，不是认知知识；换模型/换机器即失效 |
| 硬件地址/路径（D:\Brain、C:\Users\Ad） | 环境特定，进心智模型会污染可移植性（参 ADR-0016）|
| 平台整治事故细节 | 价值在"教训"不在"过程"；应提炼成规则（已进 POSTMORTEM）而非原文塞入 |
| 云侧画像/用户偏好 | 属"关于用户"的知识，不是"关于世界/任务"的心智模型内容 |
| 24 个日志原文（700KB） | 需蒸馏，不能整吞——KV 后缀税 + 注意力稀释 |

---

### 4. 建议的落地路径（按性价比，全部本机可行）

1. **P0｜负面证据 → CritBank 扩展**：从"证伪清单"提 8-12 条成结构化条目（触发/错误/正确），零显存、零 LLM 成本，直接增强杏仁核式显著性判断。
2. **P0｜自我模型读真实 trace**：写个只读工具，从 `_trace.jsonl`（排除 s1 假数据）汇总当前会话的 GWT/FEP/CritBank/门控状态 → 注入 mind_state。零额外推理。
3. **P1｜确定性稳态信号**：把"Copy 引擎判据 / MTP 接受率 / 显存余量"做成周期探针，作为脑干稳态的轻量替代（不模拟情绪）。
4. **P1｜成本预算写进 GWT**：把"Critic/D5 门控才付、深检 0.3s 随便用"作为共享状态里的预算字段，控制回合复述。
5. **观望｜L8 多标签编码器 / 多 judge**：本机 8G 显存 + 20K 每步 11s，先验证中文表现再做；否则纯 CPU 小分类器（GLiClass 式）可行但收益待证。

**一句话**：记忆里最值钱给心智模型的不是"我知道什么"，而是**"我实测过什么不该做、什么信号可信、什么成本付得起"**——这三样刚好是纯框架文档最缺的。

---

### 6. 补充实证：现有学习管道的"经验摄入"被假数据淹没（2026-11-20 实测）

用户追问"如何更高效地从别人经验中汲取"时，实测了摄入端：

- `_pending_learn.jsonl` 共 **741 行**：sid 分布 = **s1 单测 650 + `outcome-` 测试 57 + 真实会话约 34（4.6%）**；kind = `fep_deviation` 725 / `crit_hit` 16。
- 这与 `_trace.jsonl` 的 89% 假数据同源——**学习管道喝进去的 95% 是测试数据**。
- 现有注入通道 `matchCritbank()`（index.mjs:529）：纯字符串 tag 匹配、零 LLM、**只取 top2**——通道本身高效，但输入脏、召回窄。
- B 段 `learn_watcher.py`：事件驱动、只追加 feedback 不自动改 critbank（G1+G2 人工审批制）——沉淀链是"人肉把关"而非全自动。

**结论：高效汲取的第一杠杆不是加新机制，而是 ①在摄入端过滤测试 sid（复用 trace 验收的 sid 黑名单）②提高 CritBank 召回的 precision（tag 加权 / signal 结构化）③把"外部经验→结构化条目"的提炼做成离线批处理（不占运行时推理）。**

---

### 7. 外部机制调研校正（带来源，2026-11-20）

#### 7.1 修正我上一轮的说法

- ❌ 我暗示"负面教训是最有价值的，多收集失败经验就行"。**这是错的。**
  *Repair–Generalization Gap*（arXiv 2610.22984）实证：agent 只从自己失败中学，旧任务修好、新任务几乎不涨甚至变差；错误归因率 20–53%（假成功/错归因/丢条件/有害建议四类）。SkillRL 的最佳实践是**成功轨迹留具体演示（路径本身有价值），失败只压成一句话"别这样做"规则**——保留完整失败轨迹纯烧 context。
- ✅ 正确做法：**失败教训必须有原文证据行号 + 验证器/人工门控归因**，这正是现有"人肉搬进 CritBank"的保护性所在，不要为自动化而去掉这个闸门。

#### 7.2 带证据的关键结论

| 结论 | 来源 |
|---|---|
| 静态规则放 **prompt 前缀**可吃 cache（覆盖 88%、实际成本仅 +15%）；**改前缀会让后续 KV 全失效**——规则须一次性固化，勿每步改写 | ERL arXiv 2603.24639 |
| BM25 检索吊打 embedding：19,195 会话基准，建索引 **29s vs 2h3m**、单查 **24ms vs 6.3s**、top-1 **18% vs 9%** | ToFu arXiv 2607.11423 + 基准 yage.ai |
| 230-token"规则 gene"胜过 2500-token skill 包；冗长 skill 平均**低于无经验基线 1.1pp** | Strategy Genes arXiv 2604.15097（4590 次对照）|
| 但**压缩过度会被忽略**（10 模型 9 环境）：扰动原始轨迹显著改变行为、扰动摘要几乎无效 → 要**结构化 + 增量 grow**，不要 summarize-and-replace | ACE / Agent Workflow Memory |
| 触发-动作对 200–500 条是单 agent 甜蜜点，30 天未触发降级；hot <4KB 常驻 / cold 按需读 | clawd.org.cn / boucle.sh |
| cue 压缩（5–15 token 判别式线索）用**同一模型**、无冷启动、无额外显存 | HeurChain |
| 离线"做梦"三段式：Triage（无 LLM 正则滤）→ Extract（35B 提炼带证据）→ Judge（去重/矛盾/真因）→ 人工批准 → git commit | dreaming pipeline / memloom / jatinbansal 四阶段 |
| "Focus on refusal, not generation"——防记忆污染比生成点子难 | dreaming pipeline |

#### 7.3 针对本机的最优组合（8G + 35B + 不能训练）

**在线路径（每步 0 次额外 LLM）**：10–30 条高频证伪教训压成 if-then 规则，**静态放前缀**吃 cache；其余日志用 BM25 冷检索（零显存、零模型）。

**离线路径（闲时批处理，不计入 11s/步）**：用**同一个 35B** 做 Reflect（提炼候选规则，带原文行号）→ Judge（去重/矛盾/真因判定）→ 人工一键批准 → 写入带 YAML frontmatter 的 CritBank。

**压缩策略按成败分流**：成功留具体演示；失败留一句话规则 + 证据行号；cue 用判别式线索（专有名词/数字优先）不用摘要式总结。

**防漂移**：保留人工验证基线，定期 diff 检测 LLM 反复重写导致的语义漂移（OpenClaw memory-shepherd 范式）。

#### 7.4 明确不适合本机

- ❌ 任何微调/LoRA/RL 更新权重（硬件不允许）
- ❌ embedding 模型 + 向量库（额外显存 + 基准双输）
- ❌ Voyager 式"生成+环境验证技能库"作主力（每步 11s 下成本失控）
- ❌ 无人监管地让 agent 自写失败教训进指令文件（Repair–Generalization Gap）
- ❌ 长文档 skill / 纯叙事摘要（低于无经验基线）
- ❌ 在线每步 self-refine / LLM-as-judge（应全挪离线）

#### 7.5 三个可立即落地的最小改动

1. **教训改成"触发-动作 + 证据行号"的 YAML frontmatter**，高频十几条固化到 prompt **前缀**（非后缀，避 KV 后缀税）。
2. **加 50 行 BM25 检索层**（rank_bm25）绕过任何 embedding 计划，冷记忆按需加载 + 时间衰减。
3. **"人肉搬运"升级为半自动离线流水线**：正则 Triage → 35B 提炼候选（带证据）→ Judge 去重 → 待审队列人工批准 → git commit。先做"自动起草 + 人工门控"，不追全自动。

> 证据多为 2024–2026 预印本/工程博客，个别属单一团队实证；落地前用本机任务集做小样本 A/B（尤其"失败规则 vs 成功演示"比例）。

---

## 原报告：`REFACTOR_PATTERN_20261121.md`

## 函数外置模式（2026-11-21 建立，供 agent 自己复用）

> 目标：让 agent 能安全地自修改——把嵌套函数逐步外置成"纯函数 + 单测 + 转发/内联 + 集成测试"四段式，
> 每次改动都有机器可验的等价证据，而不是靠人肉小心。
> **2026-11-21 晚更新**：实际落地证明"import 转发"比"复制函数体内联"更安全，已成为默认方案。

### 四段式模式（stateOf 之外的示范：taskProfile）

**第一步：外置纯函数** → `tools/task_profile.mjs`
- 无副作用、无外部依赖、只吃参数返回结构
- 顶部注释写明"为什么外置"（根因）+ 设计原则（确定性/零 LLM/fail-closed）

**第二步：写单测** → `tools/test_task_profile.mjs`
- 覆盖正常/边界/失败三类
- 每个断言是真行为断言，不许 `|| true` / `>=0` 恒真（今晚抓到 6 处这类假绿）
- **必须真的 0 FAIL 才能停**（executeReadOnly 卡曾带 5 FAIL + JSON.parse 崩溃就停了，是反例）

**第三步：接入 index.mjs（默认 import 转发）**
- **默认方案：import 转发**——在 index.mjs 顶部 `import { fn as _fn } from './tools/xxx.mjs'`，
  函数体改成 `return _fn(args)`。实例：`collectCorrectorInput`(index.mjs:25/1415)、
  `buildTrailText`(index.mjs:26/1228)。比复制函数体安全，避免 Unicode 转义/正则事故。
- **前提**：tools/ 文件必须与 index.mjs 同目录（node_modules 里同步存在），相对路径能解析。
- **旧方案"复制函数体内联"仍有风险**：`formatCorrection`/`formatExecutorResult` 用此方式完成，
  但中途踩过 Unicode 转义把中文写成 `\U884c`（大写 U + 4 位）导致字符损坏。

**绝对禁止（血泪教训）**：
- ❌ 正则替换含 `\n` 的 JS 模板字面量——会把转义序列变成真实换行，语法崩
- ❌ "整文件重建"——曾把 node_modules 里的 index.mjs 写成 **0 字节**，差点废掉运行副本
- ❌ 手写 Unicode 转义——中文必须用源文件原样，不手写 `\uXXXX`
- 卡住 3 次就止损：放弃接线，只提交 tools/ 三件套（formatExecutorResult 曾这么做，之后再补转发）

**第四步：动态集成测试** → `tools/test_task_profile_integration.mjs`
- 不只测纯函数，要测"接入守卫后行为真的变了"
- import 路径写 `'../index.mjs'`（相对权威源 tools/ 目录），**不要写死 `../node_modules/dsh-agent-harness/index.mjs`**——那是从 node_modules 工作目录写的，复制到权威源就断链

### 为什么改成 import 转发（原"为什么内联"已过时）

原设计担心"插件从 node_modules 加载，相对 import 会指错三副本不同步"——实际验证：
只要 tools/ 文件与 index.mjs 同目录且同步（本机 node_modules 里已同步），
`./tools/xxx.mjs` 能正确解析。而复制函数体内联带来的 Unicode 转义/正则清空风险远大于同步风险。
**结论：默认 import 转发；tools/ 版是唯一真相，index.mjs 只做转发。**

### 进度（2026-11-21 晚）

| 函数 | 状态 | 落地方式 |
|---|---|---|
| `taskProfile` | ✅ 完成 | 外置+单测 |
| `formatCorrection` | ✅ 完成 | 复制内联（ec0a7e4）|
| `formatExecutorResult` | ✅ 完成 | 三件套(a56d164)+内联(5e21f55) |
| `buildTrailText` | ✅ 完成 | 三件套(dfe48e5)+import 转发(440dce6) |
| `collectCorrectorInput` | ✅ 完成 | import 转发(03316cb) |
| `executeReadOnly` | ❌ 失败待重做 | 单测 5 FAIL+崩溃，未提交，残留已隔离到 cleanup |
| `guardDecide` | ⏳ 未做 | 中难度（cfg/state）|
| `stateOf` | ⏳ 未做 | 高难度（4 依赖）|
| `callLLM`/`runAudit`/`runCritic` | ⏳ 未做 | 最高难度，最后做 |

### 黄金基线

`data/baseline/trace_pre_refactor_20261121.jsonl`（3.5MB）+ `trace_report_pre_refactor.txt`。
每个函数外置后跑对照，确认 trace kind 分布与基线一致（不能只看单测全绿——今晚证明单测会假绿）。

### 反向检验铁律（2026-11-21 深度维护总结）

1. **dsh 进程启动后不热重载**——落盘的改动对当前进程不生效，必须重启才验证。
   07:54 启动后当晚所有 commit 的 index.mjs 修改，进程内存里一行都没跑。
2. **node --check 抓不到未定义函数**——`_verifyGate` 未定义调用能通过语法检查，运行时才 ReferenceError。
   接线后必须真实触发一次（或至少静态检查 import/定义配对）。
3. **权威源 ≠ 运行版**——agent 常在 node_modules 里改文件却不 commit，运行版会变成"半成品垃圾场"。
   每次验收必须 sha256 比对两版 + `git status` 确认 commit 落地。
4. **docs/ 与卡状态会滞后**——反向检验时必须源码级核对，不能信文档宣称。

---

## 原报告：`REFACTOR_ASSESSMENT_20261120.md`

## 重构评估：基于三份地图的结构性诊断（2026-11-20）

> 用户问："根据决策链/路线图/资产图，整个项目是否值得重构？目的是更清晰、更干净、
> 减少屎山程度；必要时考虑把 autostart 插件和探针合并进来。"
>
> 本文是**证据化评估 + 方案对比**，不是重构执行。承重改动必须由用户拍板（决策主体纪律）。

### 1. 屎山测量（不是感觉，是数字）

| 指标 | 实测 | 判读 |
|---|---|---|
| `index.mjs` 行数 | **2247** | 单插件偏大 |
| 顶层符号（const/function/class/export）| 47 | 中等 |
| **单个 `apply()` 跨度** | **714→1719+，~1500 行** | ⚠️ 核心问题：一个函数塞 40+ 逻辑块 |
| `ctx.on()` 事件钩子 | 3（session/event、turn-stopping、pre-step）| 钩子少，但每个回调巨大 |
| 顶层功能区块注释（`// ──`）| 14 | 说明作者已在用注释分块——但注释不是模块边界 |
| `apply()` 内二级逻辑块 | **40+**（S1-S9/D1-D5/L0-L3/P0-P2/G4/G6/Critic/Planner…）| 每次合并插件就往里塞一段 |

**根因明确**：屎山不是写坏的，是**长出来的**——
`behavior-guard` → `turn-continuation-guard` → `task-continuity` → `frame_limiter` 每次合并，
都把整段逻辑贴进同一个 `apply()`。这与 `lineage/DECISION_CHAIN.md` 的 I03（单权重多角色）决策一致：
我们选择"单模型多角色"而非多 agent，代价就是**所有角色的逻辑挤在一个进程的一个函数里**。

> 这是"合成心智"架构的**结构性代价**：单 write 者 + 共享 state 换来了权限清晰，
> 但换来了代码集中。重构不是否定这个决策，而是给它补上模块边界。

### 2. 三份地图指向的同一个结论

- **决策链**：地基决策（A 类实测）全在配置/参数层，架构决策（I/K 层）是"外置器官"——
  器官已经长出来了，但**器官之间没有物理边界**（全在 apply 里）
- **资产图**：16 项资产里，器官类（CritBank/skills/rubrics/mind_state）已经是外置文件，
  **只有执行逻辑还内联在 index.mjs**——外置了一半，一半没外置，这是不一致
- **路线图**：25 张卡 multi 链（M1-M10）说"器官间流动"，但代码层面器官间靠共享 state 耦合，
  流动靠 if/else 判断而非接口——**路线图要的连接，代码还没提供**

三份地图都指向：**该给器官补物理边界了**。

### 3. 重构选项对比

| 方案 | 做法 | 收益 | 风险 | 建议 |
|---|---|---|---|---|
| **A. 不动，只加文档地图** | 保持单文件，靠 ASSET_MAP 索引 | 0 风险 | 屎山继续长；新合并更难 | ❌ 治标不治本 |
| **B. 内部分块（低风险）** | 把 apply() 内 40+ 块抽成顶层纯函数，apply 只做编排；按 hook 分成 3 个 handler 文件 | 可读性大增、可单测、合并新机制有地方放 | 中（需行为等价验证）| ✅ **推荐先做** |
| **C. 全量模块化（中风险）** | index.mjs 拆成 src/{guards,learning,identity,observability}/ + 入口 apply | 结构最清爽 | 高（改动面大，生产在跑）| ⚠️ B 验证稳定后再考虑 |
| **D. 合并 autostart** | 把 dsh-llama-server-autostart（675+309行）并入本插件 | 单一仓库、统一升级 | ⚠️ **见 §4，不建议** |
| **E. 合并探针** | a16_watch/freeze_watch/speed_probe 等收进 tools/evidence | 资产归位 | 低 | ✅ 可做（部分已做）|

### 4. 为什么不建议合并 autostart（D 方案）

证据：
1. **职责正交**：autostart 管"拉起/关闭 llama-server 进程 + 帧率限制"（系统层），
   behavior-guard 管"agent 行为治理"（认知层）。合并后一个插件两种生命周期，反而更乱。
2. **独立发布节奏**：autostart 有自己的 CHANGELOG/package.json/consistency_guard 项，
   更新频率与 behavior-guard 不同（各 6 次提交 vs 独立历史）。
3. **风险不对称**：autostart 崩 = 推理服务没了；behavior-guard 崩 = 行为约束失效。
   合并 = 单点故障面积扩大——这违反"分层解耦"的工程常识。
4. **但有交集**：frame_limiter（推理期限帧）与 guard 的"活性判据"都关心 GPU 调度——
   这个交集靠**接口**协作（读同一 state），不靠合并代码。

**建议**：保持两个插件独立，但**在 ASSET_INDEX 登记两者关系**，让 agent 知道"GPU 争抢时查 autostart/frame_limiter"。

### 5. 探针合并（E 方案）——可做，但分类处理

| 探针 | 性质 | 处置 |
|---|---|---|
| `freeze_watch.py` / `learn_watcher.py` | 常驻守护（计划任务）| 保持 tools/，但登记进 ASSET_INDEX |
| `speed_probe.py` / `entropy_probe.py` | 按需诊断 | 收进 `tools/evidence/`（与 rw_funnel 同族）|
| `a16_watch.py` | 一次性盯梢脚本（SID 硬编码）| ⚠️ 不要收编——它是临时工具，硬编码会话 ID，收进来反而制造垃圾 |
| `trace_timeline.py` / `token_audit.py` 等 | 证据分析 | 保持在 tools/，补"工具目录"（ASSET_INDEX 已登记部分）|

原则：**按"可复用性"分流，不是按"名字像不像工具"**。

### 6. 推荐路线（分阶段，每阶段可独立验证/回滚）

#### 阶段 1：B 方案（内部分块）— 推荐立即做
1. 把 `apply()` 内 40+ 块按职责归到 6 组：
   `guards/`（L0-L3、D1-D5、verify-on-edit）、`learning/`（outcome捕获、CritBank、S8/S9）、
   `identity/`（GWT、mind_state、心智拼图）、`observability/`（trace、五元组）、
   `review/`（Critic、Planner、验收）、`continuity/`（P0/P1压缩与闹钟）
2. 每组抽成顶层 `function handleXxx(ctx, state, event)`，apply 只做注册和分发
3. **行为等价验证**（基础设施已齐，2026-11-20 核实）：
   - `run_all.sh`（18 项）+ `self_harness_gate.py`（14 项）—— 静态/回归门禁
   - `tools/trace_report.py` —— 改前后各出一份 trace kind 分布报告，对比数量/时间戳
   - `tools/replay_good.py` —— 从真实 session.v4.jsonl 还原某步 payload 重放，**不改服务端即可 A/B**
   - 真实基线：`D:/Brain/workspace/bench/_trace.jsonl`（3.5MB）—— 改前先存档为黄金基线
   - 判据：改后 run_all/self_harness 全绿 + trace kind 分布一致（±5%）+ replay 关键步输出一致
4. 每抽一组 commit 一次，可逐个回滚

#### 阶段 2：E 方案（探针归位）+ 关系登记
- 按 §5 分类收编；ASSET_INDEX 加 autostart 关系条目

#### 阶段 3：C 方案（物理模块化）— 仅在阶段 1 稳定运行 ≥1 周后
- 拆成 `src/` 多文件，需重做一致性守卫清单（现在 key_files 指向 index.mjs）

### 7. 重构的"不做什么"（明确边界）

- ❌ 不改行为逻辑（只搬位置，不改 if/else）——**行为等价是铁律**
- ❌ 不合并 autostart（§4 证据）
- ❌ 不在重构期开新卡/新机制（避免边拆边长）
- ❌ 不动 `.workbuddy/`（项目数据，非代码）
- ❌ 不碰 junction 机制（ADR-0016 承重）

### 8. 一句话结论

**值得重构，但不是推倒重来，而是"给已经长出的器官补模块边界"**——
阶段 1 的低风险内部分块（apply 分组成 handler）能解决 80% 的可读性问题，
且不改变任何行为；autostart 保持独立（正交职责 + 风险隔离），探针按可复用性分类归位。
每阶段独立可验证可回滚，符合"承重决策用户拍板"的身份纪律。

> 等待用户拍板：是否执行阶段 1？

### 9. 阶段 1 执行进展（2026-11-21 00:08）

用户已拍板执行阶段 1。实测后**修正了拆分粒度**（这是评估时未测到的深度）：

| 评估时的假设 | 实测后修正 |
|---|---|
| "40+ 逻辑块抽成 6 组 handler" | ❌ 不可行：块深度共享闭包（s/cfg/trace）+ 大量 `return` 提前退出，
  抽函数必改控制流 → 违反行为等价铁律 |
| — | ✅ 实际结构：**24 个纯函数已在 apply() 外**（作者已部分模块化），
  apply() 内只剩 15 个嵌套函数（都依赖闭包）|
| — | ✅ 可行粒度：**逐个外置嵌套函数为顶层函数 + cfg/runtime 显式注入 + 局部别名保调用点零改动** |

**试点已完成并验证**：`resolveSafePath` → `resolveSafePathWithCfg`
- 函数体逐字搬移（git diff 确认唯一差异是 cfg 参数化）
- 我搬移时手滑多加了一个全角冒号判断 → **当场发现并修正**（这正是行为等价验证的价值：
  证明"逐字搬移"也必须 diff 核对，不能凭记忆）
- 验证：node --check OK / run_all 18/18 / self_harness 14/14

**剩余工作**（15 个嵌套函数中，按依赖从少到多）：
`claimedPaths` 类纯计算 → `stateOf` 类需 state 注入 → `callLLM/runAudit/runCritic` 类需 trace+cfg 注入。
每个函数：搬移 → diff 核对 → 门禁 → commit（可逐个回滚）。

**黄金基线**：`data/baseline/trace_pre_refactor_20261121.jsonl`（3.5MB）+ `trace_report_pre_refactor.txt`。

---

## 原报告：`DEEP_MAINTENANCE_20261119.md`

## 深度维护 bug 审计与修复（2026-11-19，v2.24）

> 用户要求：做完 M4 后全面分析有没有 bug（深度维护）。
> 方法：两个只读审计 agent（JS 主代码 index.mjs 全 2147 行 / Python 工具链）+ 主代理逐条核实修复。
> 依据的已知历史坑：静默吞错、作用域跨块、正则扫内容、thinking 吃 token、结算放错位置。

### 一、P0（真 bug，已修）

#### P0-1 安全注入被次数闸门静默吞掉（JS）
- **位置**：index.mjs 1931（shared 次数闸门）vs 1933（token 闸门）
- **问题**：token 闸门有 `!s.pendingInject` 豁免，次数闸门没有——两者紧邻却语义矛盾。
  当本轮 sharedInjections≥3（turn-stopping 侧 5 处 `+=1` 从不检查上限，很容易达到），
  所有写进 pendingInject 的安全提示（S6 注入检测 / D1-D2 / 危险操作）被静默丢弃。
- **修复**：次数闸门同样加 `!s.pendingInject` 豁免。
- **验证**：`test_injection_budget.mjs` ⑤（sharedMaxPerTurn=0 时安全注入仍能发）通过。

### 二、P1（隐患，已修）

#### P1-1 verifyRan 正则过宽（JS）
- **位置**：index.mjs 879。原正则含裸 `-c\s` 和 `python -m`——装包/数据处理会误判为"已验证"，
  导致 verify-on-stop / present-gate 放行未验证产物。
- **修复**：收敛为 `python -m (pytest|unittest)` 等明确验证子命令，去掉裸 `-c\s`。

#### P1-2 学习回注跨轮沉淀永久丢失（JS）
- **位置**：index.mjs 765（turn/start 重置 learnSinceTs）+ 1979（过滤 `f.ts < learnSinceTs`）。
- **问题**：每轮 turn/start 把 learnSinceTs 重置为本轮起点，上一轮 watcher 写的反馈 ts 恒小于它 → 永久跳过。
  学习回注机制基本失效。
- **修复**：learnSinceTs 改为 session 级（stateOf 初始化一次），turn/start 不再重置；去重靠 consumedFeedback。

#### P1-3 安全检测达上限后完全关停（JS）
- **位置**：index.mjs 889/945。原逻辑达 dangerHits≥5 / injectionHits≥3 后**整个检测块不执行**——
  第 6 次 `rm -rf`、第 4 次注入攻击不再有任何 trace。
- **修复**：达上限后仍检测+记 trace（trace 加 `steered:false` 字段），只是不再 steer。
  同时**移除 S6 的 `<system-reminder>` 裸标记模式**——它会误判 harness 自己的合法系统标记。

#### P1-4 weakness_miner verify_on_stop 签名 100% 漏检（Python）
- **位置**：weakness_miner.py 45/52 + SIGNATURES。真实 trace 的 verify_on_stop 行只有 `{ts,sid,kind,step}`，
  没有 verdict/status → `('verify_on_stop', 'FAIL')` 永远取不到。
- **修复**：命中即算 artifact_missing（其语义就是"想收尾但产物未验证"）；补 adaptive_route 分支。
- **效果**：聚类从 4 簇变 **6 簇**，新捕获 artifact_missing(21) + prompt_injection_attempt(15)。

#### P1-5 promote_skills 审批门零注入扫描（Python，投毒防御核心缺口）
- **位置**：promote_skills.py --stage/--promote。全程无内容扫描——草稿含"忽略之前的指令"
  会被原样 promote 到 skills/，构成真实投毒链（SkillJack：80% 攻击删源后仍存活）。
- **修复**：新增 `scan_injection()`（5 种模式，与 S6 同源），stage 和 promote 两道门都扫，命中即拒绝；
  promote 额外校验 ledger.status=='pending'；备份名加时分秒防覆盖。
- **验证**：干净草稿放行，中英文注入均拦截。

#### P1-6 gate 基线方差门槛从未生效（Python）
- **位置**：self_harness_gate.py 的 accept() 定义了 variance_ok 却从不调用——surfaces.json 的
  `max_pass_rate_variance=0.10` 形同虚设。
- **修复**：accept 开头对 baseline 各 split 调 variance_ok，噪声>10% 直接 no-op。

#### P1-7 surface_check 禁改面严重不全 + patch 未校验（Python）
- **位置**：self_harness_gate.py 56 + proposer 81。原 markers 只有 6 个，漏了 D1-D5/CritBank/protected/权重等；
  且 proposer 只校验 change 文本，真正的写回内容 patch 从未校验。
- **修复**：markers 对齐 surfaces.json forbidden_always（13 个）；proposer 同时校验 change+patch。

### 三、P2（已修的轻量项）

- **reviewCycles 跨问题累加**（index.mjs）：新审计问题沿用旧计数 → 误报"同一问题第 N 轮"。
  修复：reviewState.issue 变化时重置计数。
- **proposer candidate-N 竞态**（Python）：目录计数非原子且被非候选文件污染 → 改时间戳+uuid 命名。
- **proposer 无异常兜底**：bundle 坏 JSON / LLM 输出围栏 → 加 try/except 走 decline。

### 四、未修（诚实记录）

- **P2 异步竞态**（需验证）：pre-step 与 turn-stopping 都是 async 且改同一 state。
  cordis 是否串行 await 未确认——若并发可能计数丢失。影响面小，列为观察项。
- **P2 M4 记账不覆盖 steer 通道**：turn-stopping 的 steer 走 createSteeringMessage 不经 createMessage，
  不计入 token 预算。但它走独立的次数预算，且都是安全/门控类，风险可控——列为已知限制。
- **P2 深检 dup>=1 误拦**：合法重复段落/代码块可能触发。阈值调整需真实产物样本，不盲改。

### 五、验证结果
- JS 全量：**158 PASS / 0 FAIL**（15 个测试文件，含新增 test_injection_budget 5/5）
- Python：gate 11/11、weakness_miner 6 簇、投毒扫描 3/3、全部语法 OK
- 唯一 FAIL：`regression_check.py` 的"渲染:模板断言"——因 llama-server(8081)/dsh 服务当前未运行
  （urlopen 10061），属环境状态非代码 bug，未强行重启以免打扰环境。

> 遵循知识资产沉淀规则：所有 bug（含被审计发现但选择不修的）与修复理由都留档。

---

## 原报告：`DEEP_MAINTENANCE_20261121.md`

## 深度维护报告（反向检验）— 2026-11-21

> 方法：不从"代码存在 / 文档宣称 / 单测过"正向推"完成"，而从**真实运行证据**倒推。
> 证据分层：真实 trace / 日志 / 三副本 sha256 / commit 落地 / 亲自跑单测 / 产物 mtime。
> 四路只读子任务并行调查 + 主代理第一手交叉验证。

---

### 一、最重要的系统性根因：时间线错位（贯穿所有"假完成"）

```
dsh 5 个进程启动时间：2026-11-21 07:54:02（至今未重启）
llama-server：07:54:05 / 07:54:07

commit 时间轴：
  e37aead graph三卡     07:44  ← 启动前，唯一真生效的
  65e269e frame粘性     07:52  ← 启动前
  b22373b 排除dsh       07:53  ← 启动前
  346780d roadmap判据   07:54:47 ← 启动后 45 秒
  c5cb823 revert限dsh   07:56
  36e8ab8 verify-on-edit 08:12
  ff16d50 S15门控        10:34
  ... 之后 all index.mjs 改动
```

**结论**：dsh 以 cordis 插件方式在**进程启动时**加载 index.mjs，无热重载证据。07:54 之后落盘的所有改动，当前进程内存里**一行都没跑**。这就是"代码存在+单测过"被当成"生效"的方法论失灵的总根源。

**推论**：今晚 agent 在 dsh 里做的所有"自修改地基"，对当前运行的 dsh 零效果；要真验证必须**重启 dsh 后采真实 trace**。

---

### 二、逐项判定表

#### A. 函数外置四卡 —— 真完成（代码质量确实过关）

| 卡 | 单测(亲测) | 集成(亲测) | index 接线 | 两版sha | 判定 |
|---|---|---|---|---|---|
| formatCorrection | 25/25 | 4/4 | 内联(1551) | 一致 | ✅ 真完成 |
| formatExecutorResult | 56/56 | 17/17 | 内联(1606) | 一致 | ✅ 真完成 |
| buildTrailText | 17/17 | 12/12 | import转发(26/1228) | 一致 | ✅ 真完成（但见 D1 挂起 bug）|
| collectCorrectorInput | 19/19 | 4/4→6/6 | import转发(25/1415) | 一致 | ✅ 真完成（但见 D2 弱断言）|

- 全部 commit + push，三副本 sha256 逐字一致。
- 无恒真断言（我扫描过）。
- **但对运行中的 dsh 零生效**（时间线错位）。

#### B. 框架层改动 —— 部分真 / 部分假

| 项 | 判定 | 关键证据 |
|---|---|---|
| roadmap_check ✅/[OK] 判据 | ✅ 真生效 | 独立脚本每次读磁盘；正则实测认✅/[OK]、不认汇总/失败文字，无假绿 |
| verify-on-edit ENOENT 修复 | ⚠️ 部分 | 代码两版一致，但 08:12 提交晚于 dsh 启动；trace 0 证据（设计不打点）；重启前无法证明生效 |
| frame_limiter 粘性释放 | ⚠️ 部分 | 代码两版一致、含 RELEASE_STREAK=4；但真实日志 291 行中 `no_3d_4streak` **0 次**——粘性逻辑从未真实走到；日志 08:05 后停写、无进程存活 |
| frame_limiter dsh 不豁免 | ⚠️ 部分 | 代码语义对（SKIP 只剩 dwm/system），但 revert(07:56)后无 dsh THROTTLE 样本可验证 |
| graph 三卡入权威源 | ⚠️ 部分 | 卡可读、graph/yaml 一致；但 ROADMAP.md 人读视图缺三卡、S16 曾状态冲突（本次已修）|
| **S15 门控** | ❌ **假生效/双重问题** | 权威源 index.mjs **从不接线**（commit 自承"未接入守卫"）；运行版却有 `const gate = _verifyGate(state)`——**`_verifyGate` 全文无定义无 import**，执行必抛 ReferenceError 并被最外层 catch 吞掉，连带跳过 Critic 评审 |

#### C. 文档层 —— 多项过时/假失败

- ❌ **S11 / A1_7 是"假失败"**（不是假完成）：功能真在（S11 覆盖 8 种写工具 `cfg.writeTools.includes(c.name)`；A1_7 有 `review_verdict`×3 / `rubric_version`×7 打点），但判据 regex 写错 + 测试文件从未落地 → done 卡恒 FAIL。**本次已修判据，两卡转 PASS**。
- ⚠️ REFACTOR_PATTERN 文档自称"三段式"实列四步、"必须内联"已被 import 转发推翻、"建议先做"的三函数已完成。**本次已重写**。
- ⚠️ CHANGELOG 停更在 2.26.5；**本次补 2.26.6**（含被证伪方向）。
- ⚠️ 权威源定义多重矛盾：CHANGELOG 说 ROADMAP.md 内嵌块、roadmap_check docstring 说 LADDER、实际 load_ladder 读 ROADMAP_GRAPH.md。**已在 ROADMAP 头部澄清**（docstring 未改，留待后续）。

---

### 三、本次已修复（维护动作）

1. **运行版 index.mjs 坏接线清除**：用权威源覆盖（sha 1dc1235），`_verifyGate` 未定义调用归零 —— 避免下次重启 ReferenceError。
2. **executeReadOnly 失败残留隔离**：运行版 `execute_read_only.mjs` + 测试移到 `D:/Brain/_cleanup_20261118/execute_read_only_failed_125004/`（可逆，未删除）。
3. **buildTrailText 单测挂起 bug**：CLI 入口守卫 `argv[1].endsWith('build_trail_text.mjs')` 会误匹配 `test_build_trail_text.mjs`（实测 true）→ 单测读 stdin 挂起。改为精确 basename 匹配。**run_all 从 90s 超时变成 35/35、rc=0**。
4. **collectCorrectorInput 弱断言**：测试4原为纯存在性恒真；改为真检查（真调用 + 真传参）+ 负对照，6/6。
5. **S11/A1_7 假失败判据修正**：regex 对齐真实代码，移除不存在的测试文件引用，两卡 PASS。
6. **S16 状态统一**：yaml ready→done，与 graph 一致。
7. **文档维护**：CHANGELOG 2.26.6、REFACTOR_PATTERN 重写（import 转发 + 禁令 + 反向检验铁律）、ROADMAP 头部/张数、package 版本同步。
8. **一致性收敛**：consistency 38 PASS，lock→b1b1bb1，全部 push。

---

### 四、仍未解决 / 需你决策

1. **dsh 从未重启** —— 所有 index.mjs 改动未经真实运行验证。是否重启 dsh 做一次真实 trace 采集？（重启会加载新代码，也会验证坏接线是否真清除）
2. **S15 门控未接线** —— 模块存在（57/57）但从未接入守卫。是继续接线（这次要静态检查 import/定义配对），还是把卡状态从 done 改回 doing？
3. **frame_limiter 进程已死**（日志停 08:05）—— 粘性释放没跑过。要不要重新拉起并观察真实 THROTTLE/reason？
4. **历史 12 张 FAIL 卡**（S1/S2/S4/S7/regression_106 等）—— 部分是判据损坏（`KeyError: 'path'`），部分可能是假完成。**不在本次范围**，需另开一轮。
5. **REFACTOR_PATTERN docstring / 权威源定义矛盾** —— roadmap_check.py 头部 docstring 仍说 LADDER 是权威源，与实际不符（本次只在 ROADMAP 澄清，未改代码注释）。

---

### 五、方法论沉淀（写进 REFACTOR_PATTERN）

1. dsh 进程启动后不热重载——落盘 ≠ 生效，必须重启采 trace。
2. `node --check` 抓不到未定义函数——接线后必须真实触发或静态检查 import/定义配对。
3. 权威源 ≠ 运行版——每次验收 sha256 比对 + git status 确认 commit。
4. 卡状态 done ≠ 判据通过——S11/A1_7 是 done 卡恒 FAIL 的假失败；反向要查判据本身对不对。
5. 文本判据（grep/正则）易写错也易恒真——必须配负对照。
6. 文档宣称 ≠ 代码现实——双向核对，尤其 CHANGELOG/状态三文件。

---

### 六、追加：用户指出"GitHub 人读路线图没更新"后的二次深度维护（13:01-13:25）

#### 根因（用户投诉的直接原因）
`roadmap_check.py --refresh` 只重渲染 `HUMAN_CARDS` 区（23 张非 done 卡），
**漏刷 `HUMAN_PROGRESS` 进度表**——S15/S16 是 done，从不出现在人读视图；
且人读进度表的"完成证据"列写死 `docs/reflection-{id}.md`（大多不存在，假链接）。

#### 修复
1. 抽出公共 `render_human_progress(data)`，`save_authoritative` 与 `--refresh` 共用（防漂移）；
   `--refresh` 现在同时刷 CARDS + PROGRESS 两区。假链接改为真实 evidence_log。
   → S15/S16 现在出现在 GitHub 人读进度表（✅ done），进度表 26→30 项。
2. ROADMAP.md 全文状态一致：line66 旧"--next=NO_READY_ITEM/自治耗尽"→ S12（与 line51/333 一致）；
   "23张卡"→53张、"35项"→30项；README 版本 2.26.2→2.26.6、脚本数不写死。
3. docs/README.md 补 REFACTOR_PATTERN_20261121 / DEEP_MAINTENANCE_20261121 索引。
4. 三文件权威定义统一：状态权威=ROADMAP_GRAPH.md / 语义=CAPABILITY_LADDER.yaml / 人读=ROADMAP.md
   （原 CAPABILITY_LADDER.yaml meta 自称 authority=自己、roadmap_check docstring 也说 LADDER 权威，均改）。
5. **判据假失败/假绿根治**（反向检验副产品）：
   - S4/S7/gpu_guard/rebaseline 的 `file_exists` **缺 path** → KeyError 恒 FAIL；补真实文件路径。
   - S15 verify 原本查 `MUTATION_AUDIT.md` + `test_task_profile`（与选择性验证无关却会 PASS）→ 改查
     `selective_verification.mjs` + 它自己的 57/57 单测。
   - roadmap dry-run: PASS **24→28**，FAIL **14→10**，KeyError 消失。

#### 反向检验（用户强调"记得反向检验"——逐条从远端/运行版倒推，不看我改了什么）
| # | 检验 | 方法 | 结果 |
|---|---|---|---|
| 1 | GitHub 人读路线图真更新 | `git show origin/main:ROADMAP.md` | ✅ S15/S16 done、next=S12、53卡/30项 |
| 2 | README 远端版本 | `git show origin/main:README.md` | ✅ v2.26.6 |
| 3 | refresh 修复在远端 | `git show origin/main:tools/roadmap_check.py` | ✅ render_human_progress×3 + HUMAN_BEGIN/HUMAN_END/progress |
| 4 | S15 判据远端正确 | 从远端 blob yaml.safe_load | ✅ 测 selective_verification 自身 |
| 5 | 5 张卡判据远端正确 | 从远端 blob 解析 | ✅ path/cmd 均真实 |
| 6 | 运行版 vs 权威源 sha | sha256 逐文件 | ⚠️ 首轮抓到 GRAPH 未同步 → 已修 → 复验一致 |
| 7 | lock 指向最新 commit | grep lock + git HEAD | ⚠️ 首轮指向旧 commit → 已修 → 三处一致 f02bcd5 |
| 8 | **负对照（防恒真）** | 临时把 S15 test cmd 改成不存在文件 | ✅ 真 FAIL（rc=1 PASS=0）→ 恢复后 PASS，判据非假绿 |

**反向检验的价值实证**：第 6、7 项是我自查"通过"但反向查出的真遗漏（运行版 GRAPH 没同步、lock 指向旧 commit）——
靠"我改了文件 + 本地测试过"根本发现不了。

#### 最终状态
HEAD = origin/main = lock = `f02bcd5`；门禁 35/35；roadmap PASS=28 FAIL=10 MANUAL=15；
consistency 38 PASS；工作区干净。剩余 10 FAIL 为历史遗留卡（非本次范围）。

---

## 原报告：`COMPLETION_AUDIT_20261119.md`

## 完成状态验收审计（2026-11-19，v2.25）

> 用户要求：再来一轮深度维护，确保所有东西都达到路线图声明的"已完成"状态。
> 方法：三层交叉验证——① 运行版代码实际内容 ② 真实测试 ③ 真实产物/真实会话，
> 外加两路只读审计（JS 侧 10 项 + Python 侧 10 项）。核心抓"文档宣称完成但实际没落地"。

### 一、验收总览

| 层面 | 结果 |
|---|---|
| JS 侧 10 项"已完成"机制 | **10/10 PASS**（运行版与权威源码 SHA256 一致）|
| Python 侧 10 项完成声明 | **8 PASS / 3 PARTIAL**（详见 §二）|
| 真实会话验证 | S6 注入检测、S8 自校准落盘、S9 反馈回灌 **全部真实触发** ✅ |

### 二、验收中抓到并修复的 3 个"宣称完成但没落地"

#### 缺口 1：投毒防御修复只改了 bench 副本，没进权威仓库（严重）
- **发现**：`docs/DEEP_MAINTENANCE_20261119.md` 宣称"promote_skills 加双门注入扫描"，
  但权威仓库 `tools/promote_skills.py`（安装源）**没有** `scan_injection`——只有 workspace 的 bench 副本有。
  下次从权威仓库重装，投毒防御就丢了。
- **修复**：bench 版同步回权威仓库（路径定义相同，直接覆盖），语法验证通过。
- **教训**：这个项目有"权威仓库 vs 运行版/bench 副本"多份拷贝，**任何修复必须确认同步到源**。
  与之前"合并包漏同步 behavior-guard 机制"是同类坑。

#### 缺口 2：测试断言没跟上生产行为变更（文档数字造假）
- **发现**：上一轮把 S6 改成"达上限仍记 trace、只是不 steer"（P1-3），但
  `test_injection_scan.mjs` ⑥ 仍断言"达上限后不再检测"→ **实际 158 PASS / 1 FAIL**，
  CHANGELOG 却写"158 PASS / 0 FAIL"。宣称与实测不符。
- **修复**：更新断言为⑥达上限仍记 trace、⑦超上限标记 `steered:false`；测试 **7/7 通过**，
  全量从 158/1 变为 **160 PASS / 0 FAIL**。

#### 缺口 3：ROADMAP 现在时数字过期
- **发现**：§1 写"trace 已达 6970 行，4 簇"——实际已 8147 行、6 簇（深度维护修漏检后增加）。
- **修复**：更新为 8147 行/6 簇。历史文档（v2.22 当时的快照）保留不动，符合"历史只追加不重写"。

### 三、真实会话验证（用户授权后做的深度验证）

用 dsh-session-bridge 建新会话，发起"连续读 3 个不存在文件"的任务，触发 repeated-failure 审计门控：

1. **S6 注入检测**：真实 trace 出现 `injection_hit: 17`（历史累计），本次会话也触发——规则层在生产路径工作 ✅
2. **S9 有状态反馈**：真实 trace 首次出现 `review_state: 1` + `review_echo: 1`——审计结论真实写入并回灌 ✅
3. **S8 自校准落盘**：真实会话产生 `_audit_feedback.jsonl` 首条记录：
   ```
   {"gate":"repeated-failure","badNow":1,"effective":false,"stepNow":6}
   ```
   审计干预被判定**无效**（注入后 3 步内又有 1 次失败）——这正是 S8 要度量的信号，机制完整跑通 ✅

**结论**：S8/S9 从"代码级完成（仅单测）"升级为"真实路径验证完成"。

### 四、验收中确认的真实（非 bug）发现

- **角色 LLM 成功率**：整体统计 audit 9.7%/corrector 7.6%/critic 0% 看似灾难，
  但按 sid 分组后发现：绝大多数失败来自 `sid=s1` 的**单测伪造数据**（100 次 audit fail）。
  真实会话里 audit 5/5、corrector 4/4 成功。**区分测试数据与真实数据是关键**——差点误报。
- **看门狗空转复现**：重启后 `RestartDsh` 卡 Running + llama 进程 0 个（IgnoreNew 吞触发）。
  按已知修法（Stop-ScheduledTask → 杀进程 → Start-ScheduledTask）恢复，8081 正常。
  这验证了项目记忆里的空转判据准确。
- **M6 安全声明**：`D:/Brain/dsh-data/AGENTS.md` 与仓库 `config/AGENTS.md` 都有 M6 条款且内容一致 ✅
- **运行版同步**：权威源码与运行版 index.mjs SHA256 一致（未踩"文档说完成但运行版没同步"的坑）✅

### 五、仍存在的观察项（诚实记录，非阻塞）

- **S8 有效率报告**：DoD 写"累计 ≥30 条后出有效率报告"，当前只有 1 条真实记录，需长期运行积累。
- **review_state trace 不含 issue 正文**：只记 source/step/cycles，无法从 trace 判断审计发现了什么——
  可观测性小缺口，不影响机制。
- **sid 截断历史遗留**：旧会话 sid 被截成 `"session-"`，无法区分（代码已修，历史数据如此）。
- **异步竞态 / steer 通道不计 token / 深检 dup 阈值**：上轮深度维护已列为观察项，本轮未新增证据，保持观察。

### 六、验证统计（最终）
- JS 全量：**160 PASS / 0 FAIL**（15 个测试文件）
- Python：gate 11/11、投毒扫描 3/3、weakness_miner 6 簇、全部脚本语法 OK
- 真实会话：S6/S8/S9 三条机制均产生真实 trace/产物
- 文档：69 份断链 0；config 一致

> 遵循知识资产沉淀规则：所有缺口、修复、真实验据、"差点误报"的判断过程都留档。

---

## 原报告：`BRAIN_AUDIT_20261118.md`

## “这个脑”全面盘点与架构优化报告（2026-11-18）

> 范围：`D:/Brain/**`（engine / dsh-data / workspace / publish / appdata）+ junction 映射 + 计划任务 + harness 插件。
> 目的：找出**进一步优化的空间（含架构层）**，并评估"给上游开 PR"是否值得。
>
> ✅ **执行状态（11:40，v2.5.0）**：前 3 项清理 + A1 可移植性改造均已完成。
> A2 也已完成（v2.5.1：四层检查 + 门禁 30/30）。A3（拆 index.mjs）/ 开 PR 仍待做。
>
> **时点说明**：本文是 11:40 的架构盘点快照，保留原貌不重写（历史只追加）。
> 当前状态以 [ROADMAP](../ROADMAP.md) 为准——本文 §优化清单 #6「拆 index.mjs」仍待做，
> 但 #7 开 PR 已降级为独立轨道（不插队）；新增的 GWT 总线/FEP 闭环见 v2.11.0。

---

### 一、资产地图（实测体积）

| 域 | 体积 | 内容 | 健康度 |
|---|---|---|---|
| `engine/llama-b12244-src` | **1005 MB** | 自编 b12244 源码 + build 产物 | ✓ 必要，但 build 中间物可清 |
| `dsh-data/dsh-runtimes` | 288 MB | dsh 内置 node runtime | ✓ 不动 |
| `appdata-local-updater/installer.exe` | 276 MB | **0.2.0-rc.2**（10-13，过期）| ⚠ 可清（升级时会重新下）|
| `appdata-local-pnpm-store` | 111 MB | pnpm 缓存 | ⚠ 含 33MB 旧日志 |
| `dsh-data`（其余） | ~7 MB | 7 会话 / 附件 / profile / plugins | ✓ 健康 |
| `workspace/bench` | 78 MB | 174 py + 41 mjs + 119 json + 167 临时文件 + 45MB 会话转储 + 16M 调优日志 | ⚠ **主要混乱源** |
| `publish/dsh-behavior-guard` | 2.5 MB | 63 文件 / Single Source of Truth | ✓ 已整理 |

**总量约 1.5 GB**，其中真正必要约 1.1 GB——**可优化空间约 400 MB**（主要是 build 中间物 + 过期 installer + 实验转储）。

---

### 二、五个架构级问题（按影响排序）

#### A1. 存储层分裂：7 个 junction 指向 4 个物理根 🔴 最高

```
default-workspace/
  bench    → D:/Brain/workspace/bench
  memory   → D:/Brain/workspace/memory
  p        → D:/WorkBuddyWorkSpace/2026-10-13-20-41-43   ← 另一个工作区！
  dsh      → D:/Brain/dsh-data
  gguf     → D:/GGUF_Download
  llama    → D:/llama.cpp
  wb       → C:/Users/Ad/.workbuddy
```

**问题**：`p/` 指向 `WorkBuddyWorkSpace/<时间戳>/`——这是一个**带时间戳的会话工作区**，换机器/换会话就失效。
这是"一键开箱"最大的结构性障碍：脚本里的所有 `p/bench/xxx` 路径都绑死在这个时间戳上。

**优化方向**：
1. 把活跃脚本从 `WorkBuddyWorkSpace/<时间戳>/bench` **迁到** `D:/Brain/workspace/bench`（唯一真源）。
2. `p/` 改为指向 `D:/Brain/workspace`（稳定路径，无时间戳）。
3. 让 harness 库成为脚本的唯一副本（v2.4 已完成大部分），运行副本只从库 install。

**收益**：换机器/重装后只需建 4 个固定 junction，不用改任何脚本路径。**这是从"能跑"到"可移植"的关键一步**。

#### A2. 配置四处维护，一致性只查两处 🔴

当前同一语义的配置散在：
| 位置 | 内容 | 一致性检查 |
|---|---|---|
| `config/env.llama` | 引擎参数 | ✓ `config_check.py` 比对 INI |
| `llama-router-preset.ini` | 路由/温度 | ✓ 同上 |
| `cordis.patch.yml` | 插件 config + contextWindow | ❌ 未纳入比对 |
| `AGENTS.md` | 行为协议 | ❌ 未纳入比对 |
| `skills/*.md` keywords | 技能触发词 | ❌ 未纳入比对 |

**优化方向**：扩展 `config_check.py` 为**全栈一致性检查**——至少加入：
- `cordis.patch.yml` 的 `contextWindow` vs `.env` 的 `CTX`
- AGENTS.md 里提到的 skill 名是否都存在（防止外置后死链）
- skill keywords 是否有空/重复（防止检索失效）

**收益**：这类"配置漂移"是隐性 bug 的温床（我们已抓到过 2 处 env/INI 真不一致）。

#### A3. 注入链 1300 行单文件，无模块边界 🟡

`index.mjs` 现在承载 L0-L3 / D1-D5 / P0/P1/P1.5 / 控制回合 / Skills / CritBank / trace / JSON 重试 / 危险操作——**全部在一个文件里**。

**问题**：
- 加一个新机制要在 1300 行里找插入点（今晚加 G2 trace 时就踩过 state 漏初始化的坑）
- 无法单独测试某个机制（测试靠全局 emit 事件）
- 加载顺序/预算竞争隐式（sharedMaxPerTurn / 各机制自己的上限互相不知情）

**优化方向**：拆成模块（不需要改 dsh 接口，只是 Node 内部 import）：
```
index.mjs          ← 编排 + 配置
modules/
  guards.mjs       ← L0-L3 / D1-D5
  continuity.mjs   ← P0/P1/P1.5
  meta.mjs         ← 控制回合 / Skills / CritBank
  feedback.mjs     ← trace / 审计自校准 / 概率校准
  safety.mjs       ← 危险操作分级
```
**收益**：可维护性 + 可测试性 + 预算统一管理。**风险**：重构期可能引入回归——建议等 dsh 升级稳定后再做，且必须保持 26+40 测试全过。

#### A4. 实验资产与生产资产混放 🟡（清理即可，零风险）

`bench/` 根有 **167 个 `_` 前缀文件**（19 py / 2 mjs / 89 json / 24 log / 10 jsonl / 13 txt），其中：
- **生产必需**：`_trace.jsonl` / `_compaction_ledger.jsonl` / `_agent_harness_loaded.json`（3 个）
- **大体积可归档**：`_cur*.jsonl` 8 个共 **45 MB**（会话转储）、`_projectlab_result.*` 系列
- **一次性实验**：`_obs1.py` / `_danger.py` / `_ctl.py` 等我今晚的临时脚本

**优化方向**：
```
bench/archive/experiments/    ← 89 json + 24 log + 13 txt
bench/archive/session-dumps/  ← _cur*.jsonl (45MB)
bench/moe-cache-tune-run/     → archive/  (16M)
bench/__pycache__/            → 删（1.4M，可自动再生）
```
保留 `_trace.jsonl` / `_compaction_ledger.jsonl` / 探针在原位（插件硬编码路径）。

**收益**：bench 根目录从 334 个文件降到 ~170 个，找生产脚本不再被实验产物淹没。

#### A5. 自校准闭环空转 🟡（机制已装，数据未积累）

`_audit_feedback.jsonl` **不存在**——代码有写入逻辑（index.mjs:1478），但从没触发过。
意味着 G5 概率校准脚本（audit_calibrate.py）目前无数据可算。

**原因**：D5 审计门控在真实会话中触发次数少（我们大部分工作是 WorkBuddy 会话，不走 dsh harness）。

**优化方向**：不急着"造数据"——等真实 dsh 使用后自然积累。但可以做一件事：
让 `trace_report.py` 在报告里显示"审计反馈 N 条，不足以校准"的提示，避免误以为机制坏了。

---

### 三、开 PR 上游：值不值得？

#### 我们的补丁内容（`config/patches/autoparser-fix.patch`）
两行修复 `chat-auto-parser-generator.cpp`：
- **444 行**：`format.per_call_start` → `p.optspace(format.per_call_start)`（允许前导空白）
- **473 行**：`p.until(trigger_marker)` → `p.until(trim_whitespace(trigger_marker))`（marker 前后空白不误判）

**症状**：工具调用标记前后有空白时解析失败（Qwen3.6 中文模板下必现）。
**本地已打**（源码 444/473 行确认），每次升级要重打。

#### 上游状态
- **#29307 token-aware parsing**：未合并（62 commits），是大重构，**不会吸收我们的小修**
- 没有现成的针对这两行的 issue/PR（搜过）

#### 判断：**值得开，但优先级中等**

| 维度 | 评估 |
|---|---|
| 修复正确性 | 高——两行都是防御性空白处理，不破坏现有行为 |
| 复现成本 | 中——需要写最小 chat template + 工具调用样例，证明"有空白时失败/修复后成功" |
| 维护收益 | 中——每次升级省 2 分钟手打；更重要的是**社区背书后不用再维护 patch 文件** |
| 风险 | 低——即使被拒也不影响本地（补丁继续留着） |

**建议**：先做 A1/A2/A4（本地收益确定），等 dsh 升级稳定后，再花半天写个 PR（含 repro + 测试）。
PR 标题建议：`common: tolerate whitespace around tool-call markers in tagged parser`。

---

### 四、优化清单（按 ROI 排序）

| # | 动作 | 成本 | 收益 | 风险 |
|---|---|---|---|---|
| **1** | 迁脚本到 `D:/Brain/workspace/bench`，`p/` 改指稳定路径 | 30 min | **可移植性质变** | 中（要改 AGENTS.md 路径约定 + 全测）|
| **2** | 归档 167 个实验文件 + 45MB 会话转储 + 16M 调优日志 | 10 min | 目录清爽、找文件快 | 低（保留 3 个生产 jsonl）|
| **3** | 扩展 `config_check.py` 为全栈一致性 | 1 h | 防隐性配置漂移 | 低 |
| **4** | 清 `__pycache__` + 过期 installer.exe（276M）| 2 min | 省空间 | 低 |
| **5** | `trace_report.py` 加"数据不足"提示 | 10 min | 避免误判机制坏了 | 无 |
| **6** | 拆 `index.mjs` 为 6 个模块 | 半天 | 可维护性质变 | **高**（必须全测 + 回放）|
| **7** | 给上游开 autoparser PR | 半天 | 社区贡献 + 免维护 patch | 低 |
| **8** | dsh 升到 rc.3（需 GUI） | 用户操作 | 新功能 | 中（4 个行为变化）|

**推荐顺序**：2 → 4 → 5 → 3 → 1 → 8 → 7 → 6。
（先做零风险的清理，再做可移植性改造，最后才动引擎/架构/上游。）

---

### 五、一句话总结

**这个脑的架构方向是对的（harness 外置 + append-only + 分层记忆），但"物理布局"还没跟上"逻辑架构"**——
7 个 junction 绑死时间戳、167 个实验文件混在根目录、配置四处维护只查两处。
这三件事解决后，它才真正从"一台机器上的精调系统"变成"可复制的脑"。

---

## 原报告：`AUTOCARD_POSTMORTEM_20261122.md`

## 自动推卡复盘：阻碍、未意识到的盲区、科技树覆盖审计（2026-11-22）

> 两轮端到端无人值守推卡（S13 verifyRan收紧、S22 工具面治理工程）全部完成并独立核验通过。
> 但过程中暴露的问题比功能本身更有价值——本文系统性沉淀，供 A3/A5 自走闭环设计参考。

### 一、实际遇到的阻碍（按发生顺序）

| # | 阻碍 | 案例 | 应对 |
|---|---|---|---|
| 1 | **模型自报不可靠** | S13/S22 都漏同步运行版 sha；S13 报告把 raw hash 标成 normalized；"全绿"自报实际 42/43 | 独立核验三件套：门禁真跑 + 判据真验 + sha 真比 |
| 2 | **测试恒真/假测试** | format_correction 集成测试 3/4 是 `check(...,true)`；S22 的"真断言"是 Python MockState 重写 JS 逻辑 | 补事件级真测试（真调 apply()+emit）；把测试纳入门禁 |
| 3 | **门禁覆盖缺口** | self_harness_gate.py 被改坏（删 main/半截行/漏 import）但 43/43 照样过——它不在 run_all 里 | 加入门禁；量化发现 12 个 test_*.py 只有 1 个在门禁（8%） |
| 4 | **grep 判据 ≠ 行为正确** | S22 判据 grep `DISABLED_TOOLS` 通过，但模块级全局 Set 跨会话共享的语义 bug 抓不到 | 判据分层：结构 grep + 行为断言 + 语义审查 |
| 5 | **模型在同一文件连续失败 ≥2 次** | self_harness_gate.py 改了 3 次（删 main → 半截行 → 漏 import/假阴性断言） | 纪律：连续失败 ≥2 次换方法（我代修），别死循环 |
| 6 | **可行性事后才发现** | S22 原方案"从工具面移除 job_*/web_fetch"——dsh runtime 无裁剪 hook，做不到 | 投递前先查可行性；改为 harness 层拦截提示 |
| 7 | **上下文压缩** | S13 跑 92 步、两次 compaction/prune，靠 P0 存档恢复任务 | 机制有效，但说明简单卡也可能需要 50 分钟；watch 要续挂 |
| 8 | **watch 超时 ≠ 卡死** | 我设的 1800s 超时，会话仍 running=true，续挂 3 次 | 超时后查 sessions 状态，别急着判失败 |
| 9 | **数据假象反复出现** | trace mock（ms:0/outChars:2）、zstd 多帧、bridge cursor 无效、累积快照重复计数 11810 | 任何统计先验证数据源：去重/分页/单帧 vs 多帧 |

### 二、先前未意识到的问题（更深层的盲区）

#### BLIND-1：门禁覆盖面从未被审计
- **量化**：`tools/test_*.mjs` 34 个（glob 自动全纳入），`tools/test_*.py` **12 个只有 1 个显式在 run_all**（8%）；
  另有 `self_harness_gate.py` 带 self_test 但命名不符、完全不在门禁。
- **后果**：任何 Python 侧测试改坏了，门禁全绿也发现不了——S22 实锤。
- **与现有卡的关系**：A1_5「判据元验证」查的是**判据自身四类病**（自引用/格式/恒真/sid污染），
  **不查"测试有没有被门禁覆盖"**——这是空白。

#### BLIND-2：结构判据与行为正确性是两回事
- grep/file_exists 只能证明"代码存在"，证明不了"行为对"。
- S22 模块级全局 bug、`_s22_disabled_warned` 跨会话污染——grep 全过，行为错。
- A1「机器判据」体系擅长验状态，不擅长验语义。

#### BLIND-3：伪行为测试比没有测试更危险
- 模型写的 Python MockState 把 JS 逻辑重写一遍再断言——"测试通过"给人虚假信心。
- 判别标准：测试是否真的调用被测系统（apply()/真实函数），而非重新实现其逻辑。

#### BLIND-4：数据源可信度需要"元数据级"验证
- 累积快照去重（callId）、zstd 多帧（stream_reader().read()）、bridge cursor 无效、
  trace mock（ms=0）——每次都差点用错数据得出错误结论。
- A0「数据可信（sid 黑名单）」只解决 trace 里的测试 sid 过滤，不覆盖"统计数据源本身的结构陷阱"。

#### BLIND-5：价值判断与工程执行必须拆开
- M5（治理原则）需用户拍板，S22（工程执行）autonomous=true——这个拆分是两轮推卡最顺手的设计。
- 但 A3/A5 的自走闭环目前没有这个区分机制（backlog）。

### 三、科技树覆盖审计

| 教训 | 现有卡覆盖? | 说明 |
|---|---|---|
| 模型自报不可靠/独立核验 | ⚠️ 部分：A1_5「判据元验证」查判据病，A1_7「评审可观测性」查评审打点 | **没有一张卡覆盖"agent 自报结果必须独立核验"的纪律** |
| 门禁覆盖缺口 | ❌ 无 | A1_5 四类病不含"测试未纳入门禁" |
| grep 判据 ≠ 行为正确 | ⚠️ 部分：S17「函数外置模式」要求纯函数+单测 | 但没明确"结构判据必须配行为断言" |
| 伪行为测试 | ❌ 无 | — |
| 数据源结构陷阱 | ⚠️ 部分：A0 sid 黑名单 | 不覆盖快照去重/zstd多帧/cursor无效 |
| 连续失败换方法 | ❌ 无 | A4「会转弯」是 D1 重复探测的 meta_decision，语义接近但针对"探测循环"非"修文件失败" |
| 价值判断/工程执行拆分 | ⚠️ 部分：M5/S22 两卡体现了，但没抽象成通用原则 | A3/A5 backlog 没写这个拆分 |
| 失败后自我纠偏/代执行 | ⚠️ 部分：harness 有纠正器只读代执行 | 但"agent 改同一个文件 3 次失败后由谁接手"没有明确规则 |

**结论：8 类教训中，完全覆盖 0 项、部分覆盖 5 项、完全空白 3 项。**

#### 后续追查（2026-11-22 09:45）：D4「0 次真实证据」是假警报
用户问"地基是否建立在沙子上"，追查 D4 的 3 个 SKIP：
- **机制是好的**：D4 代码在 index.mjs:1830-1852，补全测试场景（先 write 产物置 writeCalls>0，
  再 present）后，3 条断言全部 PASS——"present 无验收→steer+文案含做的人不能自己签字+每轮1次"全过。
- **根因是测试场景错误**：旧测试只 emit present、没有 write → `taskProfile.needsTreeCheck=false` → D4 按设计跳过。
  第三条"每轮仅1次"数的是总 steer（含 verify-on-stop 的另一条），语义也错——改为只数 D4 自己的。
- **另一个教训**：D4 在真实 trace 0 次，不代表机制没接上——可能只是生产里 present 总伴随验收痕迹，
  D4 按设计不拦。**"0 次证据"的正确解读是"该机制在真实会话中未被触发验证"，不等于"机制失效"。**
- 剩余 2 个 SKIP（D5/P1）：生产 D5 审计 8 次/几千步、P1 todo 40 次——机制都有真实证据，
  是测试场景与生产不符（人为制造 no-progress 信号/混合守卫噪音），保留 SKIP 并标注准确原因。
- 至此 6 个 SKIP → 4 条转 PASS（D4×3 + CritBank），2 条保留诚实 SKIP。

### 四、科技树调整建议（待用户拍板）

#### 建议新增 1 张卡（高优先级）
**A6「验收可信度加固」（tier=1, risk=low, autonomous=true）**，判据：
1. `run_all.sh` 覆盖全部 `test_*.py`（当前 1/12）+ 带 self_test 的脚本（self_harness_gate）
2. `check_verify.py` 加第 5 类病：**测试未被门禁纳入**（漏跑）
3. 新增"行为断言规范"文档：禁止用源码 grep / MockState 重写冒充行为测试（如 S22 的 `test_disabled_tools.mjs` 是真范例）
4. 全门禁通过数从 44 提升到 ≥55（12 个 py 测试纳入后）

#### 建议更新 2 张现有卡
- **A1_5**（done → 补充 desc）：把"测试未纳入门禁"加入它检测的四类病（变五类），并加判据 `check_verify.py` 输出含 `not-in-gate` 检测
- **A0**（done → 补 caveat）：数据源结构陷阱（累积快照去重/zstd 多帧/bridge cursor 无效）作为独立 caveat 写进卡，避免下次统计又踩

#### 建议新增 1 张 backlog 卡（低优先级）
**A7「agent 自报可信度」**：明确"agent 说完成≠完成"的三层核验协议（门禁+判据+sha），
以及"连续 2 次在同一文件失败→换方法"的纪律。可与 A3/A5 自走闭环一起设计。

#### 不建议动的部分
- S18（自改进正则化）/ S21（验证层去自审）：方向对但与本次教训不同层，不混改
- 已完成卡的状态：不为"加了教训"就回退 done 状态——用 data_gates 补充即可

### 五、数据来源
- 两轮推卡 trace：session-f56ec374（S13, 92步/2次压缩）、session-f429de9d（S22, turn3/45步）
- 核验发现：commits fe32a83/cba4600/614d29c/169df56（S13）、19c2ba7/43542c4/4710a32/60b0527（S22）
- 门禁覆盖量化：tools/run_all.sh vs tools/ 目录文件名统计
- 科技树：TECH_TREE.html DATA（59 张卡）+ CAPABILITY_LADDER.yaml + ROADMAP_GRAPH.md
