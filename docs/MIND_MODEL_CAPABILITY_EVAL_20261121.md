# 心智模型能力评估（2026-11-21~22）

> 异构/外设/反馈蒸馏三类评估与科学测量

> 本卷合并 6 份原报告（2026-11-25 整理）。

## 本卷目录

- `HETEROGENEOUS_MODELS_EVALUATION.md`（原文件保留为引用桩）
- `PERIPHERAL_MODELS_EVALUATION.md`（原文件保留为引用桩）
- `FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md`（原文件保留为引用桩）
- `SCIENTIFIC_MEASUREMENT_20261122.md`
- `PERIPHERAL_CAPABILITIES.md`
- `PEER_HARNESS_BENCHMARK.md`

---

## 原报告：`HETEROGENEOUS_MODELS_EVALUATION.md`

## 异构多模型角色分工：可行性评估（2026-11-19）

> 用户设想：35B 做 planner/验收员，0.8B 小模型做其他角色，扩展 harness 上限。
> 结论先行：**方向对，但角色分工恰好反了，且 0.8B 选小了。不建议按原设想做。**
> 有一条更窄、更稳的可行路径，见 §5。

### 一、本机现状（先纠正两个前提）

| 前提 | 实际情况 | 来源 |
|---|---|---|
| "内存还没放满" | ✅ 属实：RAM **63.7G 总量 / 53.6G 空闲**；显存 **8188MiB 总量 / 7251MiB 空闲**（评估时 llama 空闲） | PowerShell + nvidia-smi |
| "验收员用 35B" | ❌ **验收员本来就不是 LLM**：`runVerifyAgent()` 直接跑 `verify_agent.py`（纯 Python 规则，三态 PASS/FAIL/INCONCLUSIVE），零 LLM、零 35B 占用 | index.mjs:1325 |
| "所有角色都调 35B" | 部分属实：audit / critic / corrector / planner 走 `callLLM(cfg.endpoint)` = 35B；**执行者是 dsh 主会话**（cordis provider `llama-35b`），与角色调用是两条链路 | cordis.patch.yml:36/87 |

**关键含义**：用户想优化的"验收员用 35B"这个成本**根本不存在**；真正花 35B 时间的是 audit / critic / corrector / planner 四个旁路角色（实测 212 次 LLM 调用，服务不稳时大量空返回）。

### 二、社区与论文证据（两路独立调研交叉验证）

#### 2.1 支持异构的架构（方向对）

- **Mixture-of-Agents (MoA)**：多层 agent 各用不同模型，writer 出草稿、aggregator 综合，6.7%→65.1% 提升（Alibaba Research/Tsinghua, arXiv 2406.04692）。但注意：MoA 里小模型是**并行提案者**，不是评委。
- **RouteLLM / FrugalGPT / Model Cascades**：小模型先答、难的路由到大模型，成本降 2-5×（RouteLLM; FrugalGPT arXiv 2306.05148; CascadeRouter arXiv 2510.06599）。**规律是"小模型先跑、大模型把关"，不是反过来的"大模型规划、小模型执行"。**
- **Speculative Decoding**：小 draft + 大 verify 是本机已用的 MTP 机制（draft-mtp，p_min=0.8，nmax=5）——同一原则在 token 级已验证有效。
- **Self-Refine / CRITIC**：critic 反馈能提升 actor，但前提是 critic 能识别错误。

#### 2.2 反对"0.8B 做评审角色"的证据（决定性）

- **JudgeBench (arXiv 2406.19314)**：小模型 judge 与人类一致率仅 **45–60%**，随机基线 50%——接近抛硬币。
- **Stronger judges are more robust (arXiv 2411.13268)**：小 judge 存在**冗长偏见 + 自我增强偏见**；**LLM-as-judge 要可靠，参数量必须 ≥ 被评模型**。
- **Multi-agent 失败模式 MAST (arXiv 2503.13657)**：分析 7 个主流 MAS 框架的 1600+ 条标注轨迹，
  归纳出 **14 种失败模式 / 3 大类**（系统设计、agent 间失配、**任务验证**）——其中"任务验证"类直接对应
  弱 verifier 放行强 actor 错误的问题。注：初稿曾误引为 2505.17469，已按原文核实更正。
- **"LLMs as Judges Are Not Always Reliable" (EMNLP Findings)**：模型扩大后方差降、与人类一致率升；小模型做不到。
- **Shrinking AI Model Can Boost Performance (arXiv 2508.18748)**：反例只出现在**简单 narrow task**，且"质疑能力"反而下降——评审恰是需要质疑的任务。
- **社区共识**：AgentLite 明确 "evaluator using a stronger model than the actor"；ChatDev 用更弱的模型做角色时会退化。

#### 2.3 小模型真正适合的场景

- 确定性分类（JSON 修复、格式校验、命令意图分类）：**小模型足够**，甚至规则更好。
- 草稿生成（speculative decoding / draft）：已被本机 MTP 验证。
- 简单工具路由、意图分类、非关键摘要。

### 三、角色 × 最小可行规模（决策表）

| 角色 | 当前实现 | 原设想（0.8B）| 评估 | 理由 |
|---|---|---|---|---|
| **验收员** | Python 规则脚本 | 35B | ❌ **不需要 LLM** | 已是三态规则判定，比任何 LLM 都可靠且零成本 |
| **Planner** | 35B LLM（1 次/会话）| 35B | ✅ 保持 35B | 验收标准需语义理解；用量极小（全 trace 仅 6 次）|
| **审计员** | 35B LLM（门控触发）| 0.8B | ❌ **不能降** | 要识别"模型自己没发现的错"，弱模型会漏判/误判，错误验证放大 |
| **纠正器** | 35B LLM（双败触发）| 0.8B | ❌ **不能降** | 需要构造性修正包，弱模型会给错误修正 |
| **Critic** | 35B LLM（present 前）| 0.8B | ⚠️ **条件性可行** | 只有改成"反馈信号而非门禁"才可；Qwen3-0.6B 可作为轻量预警，但必须 35B/规则复核 |
| **执行者** | dsh 主会话 35B | — | ✅ 保持 | 主推理质量是底线；换小模型等于换脑 |

### 四、为什么"0.8B"这个量级选错了

1. **Qwen3-0.6B 非思考模式只有 4/29 任务成功**，Qwen2.5-0.5B-1M 在长上下文表现更差（Qwen3 技术报告）。
2. 评审任务的失败不是"慢一点"，是**静默放行错误**——比没有评审更危险（错误验证放大）。
3. 小 judge 的 45-60% 一致率意味着**近一半判断不可信**，而我们的门控正依赖它决定"要不要返工"。

### 五、可行路径（推荐，但降级为低优先级）

不是"大模型规划 + 小模型评审"，而是反过来：

> **小模型做草稿/格式修复/分类，35B 做验证门禁；验收继续用规则。**

具体候选（按 ROI）：
1. **JSON/格式修复器**：`jsonRetryTimes=1` 现在是"同一 35B 再问一次"，浪费 10-45s。改用一个常驻小模型（0.6B）只做格式重写，零质量风险（有 35B 的第一次输出兜底）。**这是唯一没有"弱验证强"风险的改动。**
2. **Critic 轻量预警层**：0.6B 先扫一遍给"疑似问题"，命中再调 35B；未命中不拦截（只记 trace）。收益是减少 35B 调用，风险可控（漏判=回到现状，不会误伤）。
3. 不碰 audit / corrector / planner / 验收员 / 执行者。

**实现前提**（本机已具备）：
- autostart 支持 `LLAMA_PROFILES=35b,small` 多实例（不同端口），引擎层零改。
- 内存/显存余量充足（53.6G RAM / 7.2G 显存空闲）。
- 需下载 Qwen3-0.6B Q4（~0.5GB，当前本机无小模型文件）。
- harness 需给 `callLLM` 的 ctx 加 endpoint 覆盖（约 5 行改动）。

**但**：当前 Critic ≤2 次/会话、planner 1 次、audit 门控触发——**角色 LLM 调用总量本就不是瓶颈**。真正的性能瓶颈是主会话推理（每 token 30+ 步 × 35B）。因此这条路径的收益上限有限。

### 六、结论与路线图处理

- **不按原设想做**（把角色下放给 0.8B / 让 35B 做验收）。
- 把"小模型格式修复器"记为**中期可选优化（M7）**，前置条件是先拿到真实的角色调用耗时占比（当前 212 次调用分散在多时段，需重新测量稳定期成本）。
- 把"Critic 轻量预警"记为**长期探索（L5）**，需先做 A/B：0.6B 预警的召回率 ≥ 80% 才值得上。
- 记录为"已证伪的方向"：小模型做审计/纠正/验收。

相关：[PEER_HARNESS_BENCHMARK](PEER_HARNESS_BENCHMARK.md) · [CADENCE_REDESIGN](CADENCE_REDESIGN.md) · [ROADMAP](../ROADMAP.md)

### 证据链接

- MoA: https://arxiv.org/abs/2406.04692
- RouteLLM: https://arxiv.org/abs/2406.18665
- FrugalGPT: https://arxiv.org/abs/2306.05148
- JudgeBench: https://arxiv.org/abs/2406.19314
- Stronger judges robust: https://arxiv.org/abs/2411.13268
- Multi-agent failure taxonomy (MAST): https://arxiv.org/abs/2503.13657
- Shrinking model boost: https://arxiv.org/abs/2508.18748
- Qwen3 tech report: https://arxiv.org/abs/2505.09388

---

## 原报告：`PERIPHERAL_MODELS_EVALUATION.md`

## 超小模型作为"周围神经系统"：可行性与方案评估（2026-11-19）

> 用户设想：把 0.1B-1B 超小模型全扔进空闲内存（53G），作为主模型的"周围神经系统"——
> 做感知/分类/反射/路由/修复，扩展脑的实力，**不替代主模型判断**。
> 结论：**这次和"小模型当评审员"那轮不同——有大量真实成功案例，方向成立。**
> 但要选对模式：router-first + 守门/分类，不要 cascade 式的"小模型先答、不行再升级"。

### 一、和上一轮评估的关键区别

| | 上轮（小模型当评审/验证） | 本轮（小模型当外设/周围神经） |
|---|---|---|
| 任务性质 | **判断**：要不要放行、产物好不好 | **信号**：分类、路由、格式修复、快速反射 |
| 失败后果 | 静默放行错误（比不审更糟）| 分类错了可回退到大模型/规则，损失只是延迟 |
| 证据 | 反对（JudgeBench 45-60%≈抛硬币）| **支持**（守门/路由/投机解码大规模生产验证）|
| 结论 | 证伪 | **成立，但要挑对模式** |

一句话：**小模型不适合"替大脑做判断"，非常适合"替大脑做感知和反射"。**

### 二、真实成功案例（按模式分类，带数字）

#### 模式 A：守门/分类层（最成熟，证据最硬）

生产级多层守门栈已是事实标准：

| 模型 | 参数 | 角色 | 延迟 | 显存/内存 |
|---|---|---|---|---|
| Meta Prompt-Guard 2 | **86M** (mDeBERTa-v3) | L1 注入/越狱检测 | GPU 1-3ms / **CPU <10ms** | ~350MB |
| Llama Guard 3-1B | 1B | L2 策略审核（14 类） | 15-40ms | INT4 <1GB |
| ShieldGemma | 2B | 可校准阈值审核 | 20-50ms | ~5GB |
| WildGuard / LlamaGuard-8B | 7-8B | L3 出口审核 | 80-200ms | 14-16GB |

- Vigil（启发式+embedding+微调）：注入检测率 ~95%，**延迟 <10ms，可跑在每次输入上**。
- USENIX 2024（5 攻击 × 10 防御 × 10 LLM × 7 任务）：**没有任何单一预防式防御足够**——必须纵深。
- 对本项目的意义：86M 分类器 CPU <10ms，几乎免费，可挂在每次工具结果/输入前做注入检测。

#### 模式 B：路由/级联（收益在成本，不在延迟）

- **RouteLLM**（ICLR 2025）：MT-Bench 只把 **14%** 查询发给强模型，保留 95% 质量，成本降 **>85%**。
- **FrugalGPT**（Stanford）：级联降本最高 **98%**。
- **SLM Orchestration Gateway**（arXiv 2606.03557，8GB 边缘设备）：微调 **0.5B Qwen2.5 做路由，准确率 83% / 延迟 392ms**；分层端到端中位 <1.5s；**比单独用 1.5B 做路由更快**（1.5B 路由要 1776.9ms）。
- ⚠️ **反直觉（关键）**：800 次真实调用的 sub-second triage 实测——"**Tiering did almost nothing for latency**"；cascade 在中段分布反而最慢（升级时串行跑 detector + reasoning）。真正收益是成本（fast $0.21/千请求 vs large $0.88，约 4×）和安全召回。
- ⚠️ **router-first > cascade**（交互式）：router 是单次跳转、p99 紧；cascade 每条都付"小模型+验证器"，升级率仅 1-3% 就可能吃掉收益。
- **收支平衡公式**：cascade 成本 ≈ cheap + verifier + escalation_rate × expensive；10× 价差下可升级 90% 才亏，3× 价差下上限 67%。

#### 模式 C：投机解码（本机已在用，token 级的外周）

- 本项目已用 MTP draft（spec-type=draft-mtp, p_min=0.8, nmax=5）——这本身就是"小模型配合大模型"的成功案例，只是发生在 token 级。
- EAGLE / Medusa / Lookahead 等变体各有加速倍数，但**需要改模型结构/训练 draft head**，与"权重零改"冲突，不是我们的路线。

#### 模式 D：System 1 / System 2 双过程（架构范式）

- **SwiftSage**（NeurIPS 2023）：小行为克隆模型做快速直觉动作，GPT-4 做子目标规划，ScienceWorld 30 任务超越 ReAct/Reflexion。
- **SOFAI 元认知仲裁**：快求解器先试，置信高就执行；低则计算 Expected Value of Control 再决定调慢求解器。
- **DPT-Agent**：慢系统不直接选动作，只更新持久策略/宏动作供快系统执行——**"慢系统学习、快系统执行"**。
- 与本项目契合点：我们的确定性门控 = 规则版 System 1；trace 系统 = 天然的校准/学习数据源。

#### 模式 E：CPU 常驻小模型群（最贴合本机硬件）

- **多专家懒加载实证**（中文社区）：主模型常驻显存 + 子模型懒加载，8G 单卡可容纳主 q4(0.3G) + 子 q4(0.9G) + 激活(1G) ≈ 2.2GB；路由 0.5B ~5ms，首次加载 ~200ms/切换 ~50ms。
- **Mesh LLM**（2 台 4 核 CPU 主机池化）：跨节点转发延迟差 <0.4s（噪声内）；0.5B/1B 模型加 `--ctx-size 8192` 后稳定 1.78GB。
- ⚠️ **CPU 小模型不是零延迟**：0.5B 在 4 核 CPU 上单次 ~3.5s（无 GPU）；本项目 i7-12650H 10C/16T + 53G RAM 会更好，但**并行吞吐/串行延迟必须实测**。

### 三、反面证据与失败条件（必须遵守）

1. **过度自信是致命的**：小模型"经常错但很少怀疑"。实测 gpt-4.1-nano 过敏案例以 0.8 置信返回 false 绕过阈值→召回 100%→94%；"错但不确定"可利用，"自信地错"摧毁级联。
2. **原始置信度不可用**：让小模型自评 0-10 设阈值是 theatre（系统性过度自信）→必须在标注集上画实际胜率 vs 置信曲线定阈值。
3. **换模型/换版本后校准漂移**：准确率相近但对错误答案置信更高→同阈值下准确率暴跌 >15 点。
4. **分布外（OOD）**：小模型在 OOD 上幻觉更多→任务必须限定在清晰定义域，加"未知路由到前沿"规则。
5. **升级风暴**：小模型层广泛失败时每请求付两次钱→需 circuit breaker 全量回退大模型。
6. **路由器本身可能比省下的还贵**：7B 路由器放在 $0.15/M 目标模型前，路由比省的贵→**路由器成本必须比便宜路径低一个数量级**。
7. **切换模型的隐藏成本**：session 中途换模型使 KV/prompt cache 失效——一次 20K token cache miss 抹掉切换节省。规则：**单轮查询激进路由，多步 agent 固定一个模型**。
8. **过拒绝**：安全分类器边界样本误拦（医疗/历史/创作）→阈值分场景设，不能一刀切。

### 四、对照本 harness 的挂载点评估

现有可挂 LLM 的点：4 个 `callLLM`（audit/planner/critic/corrector）+ 规则驱动的 CritBank/FEP/情景检索 + 主会话 35B。
实测角色 LLM 耗时（稳定期）：audit 中位 23.8s / corrector 18.0s / planner 11.6s。

| 挂载点 | 小模型能做什么 | 是否"外设"性质 | ROI | 判定 |
|---|---|---|---|---|
| **工具结果注入检测** | 86M Prompt-Guard 扫工具输出/web 内容里的注入指令 | ✅ 纯信号，误报可回退 | **高**（CPU <10ms，每次输入）| **推荐 P0** |
| **JSON/格式修复** | 0.6B 只重写格式，不动语义 | ✅ 有 35B 首轮兜底 | 中（省一次重试 10-45s）| 推荐（=M7）|
| **CritBank/情景检索打分** | 小 embedding/classifier 做候选排序 | ✅ 检索是信号不是判断 | 中 | 可选 |
| **角色 LLM 路由**（简单 query 用小模型答） | 0.5B 先试，难的升级 35B | ⚠️ cascade 面容/失败多 | 低（交互延迟不降，升级率吃掉收益）| **不推荐** |
| **audit/corrector 下放** | 让 0.8B 做审计/纠正 | ❌ 判断性质 | 负 | **证伪（上轮）** |
| **主会话推理下放** | 换小模型做执行 | ❌ 换脑 | 负 | 不做 |

### 五、本项目的独特优势（别的 agent 没有的资产）

1. **trace 系统 = 天然校准数据源**：可记录每条请求的"门控决策 / 小模型置信 / 是否升级 / 最终结果 / 延迟 / 成本"——这正是所有文献强调必须记录、但连商业路由器都空白的一环。我们能画可靠性图、定阈值、做 shadow 对比。
2. **确定性门控 = 天然安全默认**：所有文献建议"router 失败时 fail toward large model"，我们的规则门控能硬性实现且可解释。
3. **闭环学习**：大模型离线从 trace 提炼门控规则/阈值，下发给小模型群——对应"高层学习、低层执行"。

### 六、结论与建议指标

**方向成立**，但只做"外设"不做"判断"，且 router-first 而非 cascade。

建议的量化目标（文献经验值，作为起点非承诺）：
- 路由准确率 ≥95%；fast path 覆盖率 ≥80%；升级率 ≤20%
- 质量 delta vs 全大模型基线 <2%
- 端侧路径 p95 <400ms；升级路径 p95 <2s
- 升级率 >2× 基线或校验违规激增 → circuit breaker 全量回退

**落地前必须实测**（本机独特条件）：53G RAM 常驻多个 0.5B 的并行吞吐、CPU 推理串行延迟、小模型置信校准曲线（ECE/Brier）。

### 七、对路线图的更新建议

- **新增 P0（高性价比）**：工具结果注入检测层（86M Prompt-Guard，CPU，<10ms）——这是"周围神经"最纯粹的形态，且与现有确定性门控互补。
- **保留 M7**（小模型格式修复器）为 P1。
- **L5 降级/收紧**：Critic 轻量预警改为"只做信号不拦截"，并加校准阈值前置条件。
- **新增验证任务**：小模型 CPU 推理基准（吞吐/延迟/校准曲线），是所有后续决策的前置。
- **不新增**：小模型做审计/纠正/验收/主推理。

相关：[HETEROGENEOUS_MODELS_EVALUATION](HETEROGENEOUS_MODELS_EVALUATION.md)（上轮：判断类证伪）· [ROADMAP](../ROADMAP.md) · [PEER_HARNESS_BENCHMARK](PEER_HARNESS_BENCHMARK.md)

### 证据链接
- Prompt-Guard / Llama Guard / ShieldGemma / WildGuard 生产对比: https://www.llms.blog/posts/open-source-safety-and-moderation-classifiers-in-production-comparing-llama-guard-3-shieldgemma-wildguard-and-prompt-guard
- RouteLLM: https://neuraltrust.ai/blog/llm-model-routing ; FrugalGPT: https://arxiv.org/abs/2306.05148
- SLM Orchestration Gateway (0.5B 路由 83%/392ms): https://arxiv.org/html/2606.03557v2
- sub-second triage 实测（tiering 不降延迟）: https://bessavagner.com/blog/sub-second-llm-triage
- router-first vs cascade: https://dnt.co.il/why-llm-cascades-fail-for-interactive-apps-use-router
- SwiftSage: https://arxiv.org/abs/2305.17390 ; MoD: https://arxiv.org/abs/2404.02258
- Mnehmos Agentic Nervous System: https://mnehmos.github.io/Mnehmos/blog/from-chatbot-to-organism
- Mesh LLM CPU 池化实测: https://www.itnotetk.com/2026/11/04/mesh-llm-pooled-inference
- 多专家懒加载（中文实证）: https://blog.csdn.net/chuchu00000000/article/details/162838522

---

## 原报告：`FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md`

## 前馈流水线误差放大、NSED 协议、学生中心蒸馏：三问评估（2026-11-19）

> 用户三问：① planner→审计→纠正→验收是前馈流水线，误差逐级放大，NSED 协议是否有效？
> ② 主模型有什么 harness 无法修补的固有弱点，能否用专门训练的超小模型补？
> ③ 能否用学生中心蒸馏让主模型"亲自打造"专属小模型队友？
> 结论先行：**① 诊断正确，NSED 的循环共识思想对症但完整协议不适合本机；
> ② 有可补的弱点，但要选"外部可观测"的那类；③ 黑盒 Q4 teacher + 8G 显存下，大规模蒸馏不现实，
> 但"窄任务专属队友"是唯一可行的切口。**

---

### 一、问①：前馈流水线的误差放大 + NSED

#### 1.1 诊断：用户说得对，我们就是前馈 DAG

现有链路：`Planner（验收标准）→ 执行者 → 审计员 → 纠正器 → 验收员/Critic`。
这是**单向 DAG**，每一级的输出是下一级的输入，**没有状态回流**。误差传播有两种：

- **漏判型**：审计没发现执行错误 → 错误流到验收 → 验收若也漏 → 直接交付。
- **误判型**：审计误报 → 纠正器按错误诊断改 → **引入新错误**（比原错更糟）。
  这正是 MAST 分类学（arXiv 2503.13657，14 种失败模式/3 大类）里的"任务验证"类失败。

**本地数据佐证（重要发现）**：代码里有审计自校准闭环
（`auditEval`：干预后 3 步看失败是否消失 → 写 `_audit_feedback.jsonl`），
但**该文件实际不存在**——说明审计干预的成功率从未被度量。也就是说：
**我们目前无法回答"审计/纠正到底有没有帮上忙"，误差放大是盲区。**
（注：9 次成功 audit 调用集中在服务稳定期，INTERVENTION 需要走完整流程才落盘。）

#### 1.2 NSED 协议核实（用户提到的缩写，已查证）

**准确定义**：NSED = **N-Way Self-Evaluating Deliberation**（N 路自评估审议），
出自 Mixture-of-Models 论文（Pecerskis & Smirnovs, arXiv **2601.16863**, 2026-01；
v2 标题改为 "Distributed Inference over Heterogeneous LLMs as Model-Level Mixture-of-Experts"）。

**核心思想**（正好对症前馈问题）：
- 把多 agent 协作从**前馈 DAG** 改造成**宏观语义 RNN**：共识状态 `S_t` 回流到下一轮，
  带语义遗忘门 γ，迭代精炼而非单向传递。
- **中间错误不必是终局**——后续轮次可以修订先前的共识，这正是前馈流水线缺的。
- 治理机制：身份盲路由 + 对角自投票掩码（禁止自评）+ 二次投票（Quadratic Voting）+ 动态专长经纪人
  （模型选择建模为多维背包问题，按实时遥测和成本约束分配角色）。
- **效率-疲劳模型**（R²≈0.99）：共识 = 信号提取 vs 上下文噪声累积的权衡，给出**最优停止点**——
  防止"过度审议"，也直接回答"几轮之后该收工"。

**实证数字**：
- AIME 2025：<21B 的开放权重模型集合**接近 120B MoE（GPT-OSS-120B）**；
  更大集合达 **90.0%**（接近当时闭源前沿）。
- LiveCodeBench v5 Hard：报告称集合达 64.5%（对比 DeepSeek-R1 63.6%）。
- DarkBench：**谄媚（sycophancy）比最佳单 agent 降低约 40%**（身份盲 + 对等纠错）。
- 硬件：论文卖点是 4-8× 更少的资本开支，用消费级模型逼近企业级。

**局限/前提**（必须诚实说明）：
- 这些数字来自作者自己的实验与商业推广页（peeramid.xyz），**独立复现尚少**，应打折看待。
- 需要**多个独立模型**并行审议——本机只有 1 个 35B + 可选小模型，"N 路异质模型"条件不具备。
- 论文用的是 <20B **稠密/半稠密**模型集合；本机是 35B-A3B MoE，架构不同。
- 多轮审议 = 多轮 LLM 调用，与本机"延迟Already是瓶颈"的现实冲突。

#### 1.3 对本 harness 的判断

**完整 NSED 不适合本机**（无多模型、延迟敏感、累加 token 贵），
**但其两个思想可以低成本移植**：

| NSED 思想 | 本机移植方案 | 成本 |
|---|---|---|
| 共识状态回流（循环而非前馈） | 审计/纠正的结论不直接改产物，先写入 `s.reviewState`；下一轮执行前把"上次的问题+是否修复"作为**有状态反馈**注入，而不是重新开始 | 低（state 字段+注入）|
| 自投票掩码（禁止自评） | 现有 Critic 已"只看产物不看过程"（异质 rubric），符合精神；**审计员不要再评自己的纠正结果** | 零（已有）|
| 效率-疲劳/最优停止 | 给"审计→纠正"循环设**最大轮次**（如 2 轮）+ 收敛判据（连续 N 步无新 FAIL 即停），防死循环 | 低（规则）|
| 自校准闭环缺失 | **先修 `_audit_feedback.jsonl` 落盘问题**——没有数据就无法判断误差是放大还是收敛 | 低（诊断）|

**优先级**：先做"自校准落盘"（让误差可度量）→ 再做"有状态反馈 + 循环上限"（抑制放大）。
这两项都不需要小模型、不增加 LLM 调用，是纯 harness 改动。

---

### 二、问②：主模型固有弱点 + 专用小模型弥补

**判断原则**：外部小模型能补的弱点必须满足"**外部可观测 + 窄任务 + 有明确反馈信号**"。

#### 2.1 我们主模型的固有弱点（按 harness 可补性分类）

| 弱点 | 实证 | harness 能补吗 | 专用小模型能补吗 |
|---|---|---|---|
| **Q4 量化的指令遵循退化** | Q4_K_M vs Q8_0：IFEval **-9.2 点**、GSM8K -3.4 点；
  Mistral-Nemo 测试里 Q4 把"部分失败"变成"四信号全崩"（schema/一致性/STOP/oracle 同时失效）| ❌ **prompt 补不回权重里丢的精度** | ⚠️ 可补格式层（schema 校验/修复），补不回语义 |
| **Q4 的多步 JSON 结构崩溃** | 同上：hard case schema_ok=0 / stop_semantics_ok=0 | ✅ GBNF 约束解码可补（格式层）| ✅ 专用 formatter 可补 |
| **量化模型的内部自洽性下降** | ms_med_02：答案对但"内部推理步骤自相矛盾" | ⚠️ 过程审计能发现部分 | ⚠️ 需专用 process verifier |
| **知识截止 / 幻觉** | 权重里没有的知识，外部也不知道 | ✅ RAG 部分缓解 | ❌ 小模型也不知道，不能补 |
| **过度自信 / 校准差** | 小模型同样有，甚至更差 | ⚠️ 规则门控可兜底 | ❌ 小模型校准不比大模型好 |
| **长上下文 lost-in-the-middle** | 本 harness 已用压缩/存档缓解 | ✅ 已部分缓解 | ✅ reranker 可补检索精度 |
| **算术精确性** | 工具（pwsh/python）已补 | ✅ 已补 | ❌ 不需要 |

**结论**：真正"harness 补不了、值得专用小模型补"的只有一类——
**量化损伤中的格式/结构崩溃**（schema 校验+修复、约束解码）。
其余要么 harness 已覆盖，要么小模型也无能为力。

#### 2.2 一个反例提醒：QAD（量化感知蒸馏）

Liquid AI 的 LFM2.5 用 QAD 让 4-bit checkpoint 保留 **96.5-97.4% 的 BF16 精度**
（GPQA Diamond / MMLU-Pro / IFEval / BFCLv4）——说明"量化损伤"可以通过**训练时感知量化**来消除，
但那是**模型作者重训模型**的事，我们权重零改做不到。对我们只能外部补格式层。

相关：[Q4 量化实测](https://thenextgentechinsider.com/pulse/benchmarking-quantization-impacts-on-qwythos-9b-reasoning-performance) ·
[Mistral-Nemo Q4 评测](https://huggingface.co/pbhappliedsystems/mistral-nemo-instruct-2407-gguf-Q4-K-M) ·
[QAD](https://agentlenshq.com/blogs/01a68fd1-76e8-4c11-b41f-f1535456ae36)

---

### 三、问③：学生中心蒸馏 / 主模型打造专属队友

> 本节基于已完成的调研，结论明确。

#### 3.1 技术路径总览

| 路径 | 代表工作 | 数据/成本 | 黑盒 Q4 teacher 可行? |
|---|---|---|---|
| 知识蒸馏（logits） | Distilling Step-by-Step、MiniLLM | 需 teacher logits | ❌ 我们只有 API，拿不到 logits |
| 解释轨迹蒸馏 | Orca / Orca2（GPT-4 解释轨迹）| 需生成解释 | ⚠️ 可用，但 Q4 teacher 解释质量存疑 |
| 合成指令自生成 | Self-Instruct、Magpie、Alpaca | 几十k 条指令，单机可生成 | ✅ **最可行** |
| 黑盒蒸馏 | 只有输出，无概率 | 效果低于白盒 | ✅ 但需大量样本筛选 |
| 自我改进闭环 | STaR、Self-Rewarding | 需可验证奖励 | ⚠️ 需任务有客观对错 |

#### 3.2 本机条件评估（诚实版）

**硬约束**：
- Teacher 是 **Q4 量化的 35B**，只有 OpenAI 兼容 API（**黑盒，无 logits/权重**）。
- 无法微调主模型（权重零改）——但这不妨碍它**生成数据训练别的模型**。
- 训练硬件：**RTX 4060 Laptop 8G**——QLoRA 微调 0.5B-3B 可行（unsloth/LLaMA-Factory），
  但生成几十k 条数据 + 训练会占用数小时，且与主推理争抢显存（需错峰）。
- 53G RAM 可容纳小模型群，但**训练仍需在 GPU 上做**。

**收益判断**：
- 让 35B 生成"针对本机常见任务的专属数据"→ 训练一个 **0.5B-1.5B 窄任务队友**
  （如：只做工具参数格式化、只做 CritBank 分类、只做注入检测）——**理论可行**。
- 但：合成数据有小模型通病（模式坍缩、幻觉继承）；self-consuming loop 会退化（Shumailov et al. 模型自噬）；
  且**窄任务队友用规则/现成小模型往往更便宜**（Prompt-Guard 86M 已是成品）。
- 所以：**蒸馏不是首选，除非现有成品小模型覆盖不了某个本机特有任务**。

#### 3.3 合成数据的边界（关键：单次可以，递归不行）

- **模型自噬（Shumailov et al., Nature 2024）**：递归用自身输出替换真实数据训练，
  第 9 代输出退化为"野兔清单"式胡言乱语；纯合成数据 **5-10 代**出现可测退化。
- **但边界很窄**：Meta FAIR（Kang et al., EMNLP 2025，1000+ LLM / 10 万 GPU 小时）发现
  **单次**混合 ~1/3 重述合成 + 2/3 真实数据，训练**加速 5-10× 且无退化**；
  且 **~8B 生成器不比更大模型差**——这对我们（35B teacher）是好消息。
- **强模型崩塌（ICLR 2025）**：极端情况下 <1% 合成数据也能触发——但那是纯合成递归的严苛设定。
- **自蒸馏的隐藏风险**（微软研究）：数学推理自蒸馏后，认知性语言（"我不确定"）从 **182.5 token 降到 8.8（-95%）**，
  回答长度从 13054 降到 1873（-86%）——**模型"说不知道"的能力被抹掉**，在新问题上灾难性失败。
  这正好击中本项目最看重的"弃权通道（UNCERTAIN）"。

**对我们的含义**：**做单次蒸馏（n=1）是安全的；绝不能递归自喂。且必须保留 UNCERTAIN 样本**，
否则训练出的队友会"自信地错"——与 NSED 要防的谄媚/权威偏差同源。

#### 3.4 唯一值得做的切口

> **先用主模型生成"本机失败案例"的标注数据 → 训练一个专属于本 harness 的"误差预测器"**
> （判断当前轨迹是否会失败），而不是训练另一个"通用小模型"。

理由：
- 我们有 **trace 系统**（5500+ 条真实事件 + turn/controlTotal/audit error 字段）——
  这是别的蒸馏项目没有的**本机专属数据**（真实分布，不是合成）。
- 主模型能标签化这些 trace（"这一步是否为错误前兆"），生成训练数据。
- 误差预测器是**窄二分类任务**，0.5B 足够；输出只是信号，错了可回退——
  符合"周围神经"定位，不碰"判断"。
- 训练成本可控（几百到几千条标注 + QLoRA in unsloth/LLaMA-Factory，8G 卡可跑）。
- **前置条件**：先有 S8（审计自校准落盘）积累的"干预有效/无效"标签——没有它就没有训练信号。

---

### 四、三问的综合结论与路线图建议

1. **问①**：诊断正确。先修审计自校准落盘（误差可度量），再加"有状态反馈 + 循环上限"抑制放大。
   NSED 完整协议不适合本机（需多模型并行、延迟敏感），但其**循环共识 / 最优停止 / 禁止自评**
   三个思想可低成本借鉴。**关键发现：审计自校准文件实际不存在——误差放大目前是盲区。**
2. **问②**：有可补弱点，但只有一类值得动——**Q4 量化的格式/结构崩溃**（IFEval -9.2 点、
   多步 JSON 四信号同时失效）。其余要么 harness 已补（算术用工具、长上下文用压缩），
   要么小模型也无能为力（知识缺失、校准）。补法是 GBNF 约束解码 + 专用 formatter，不是另一个通用模型。
3. **问③**：大规模蒸馏在本机不现实（黑盒 API、Q4 teacher、8G 训练卡），但**单次蒸馏（n=1）安全**
   （Meta FAIR：1/3 合成 + 2/3 真实加速 5-10× 无退化）。唯一切口是用 trace + 主模型标注训练
   **"误差预测器"**（窄二分类、输出只是信号）。**必须保留 UNCERTAIN 样本**，否则队友会"自信地错"。

**新增路线图建议**：
- **S8**：审计自校准落盘修复（让误差可度量）——高性价比，纯代码。
- **S9**：reviewState 有状态反馈 + 审计纠正循环上限（≤2 轮）——中成本。
- **L6**：专属误差预测器（trace 标注 + QLoRA 0.5B）——长期探索，需 S8 数据先积累，且只做单次蒸馏。

---

### 证据链接
- NSED / Mixture-of-Models: https://arxiv.org/abs/2601.16863
- NSED 解读: https://api.emergentmind.com/topics/n-way-self-evaluating-deliberation-nsed
- MAST 多 agent 失败分类: https://arxiv.org/abs/2503.13657
- Q4 量化退化实测（IFEval -9.2pp）: https://thenextgentechinsider.com/pulse/benchmarking-quantization-impacts-on-qwythos-9b-reasoning-performance
- Mistral-Nemo Q4 结构化失败: https://huggingface.co/pbhappliedsystems/mistral-nemo-instruct-2407-gguf-Q4-K-M
- QAD 量化感知蒸馏（96-97% 保留）: https://agentlenshq.com/blogs/01a68fd1-76e8-4c11-b41f-f1535456ae36
- 模型自噬 Nature 2024: https://doi.org/10.1038/s41586-024-07566-y
- 合成数据边界（Meta FAIR 1/3 最优）: https://aifrontierpost.com/articles/synthetic-data-research-debate
- 自蒸馏抹掉不确定性（微软）: https://blog.pebblous.ai/report/self-distillation-synthetic-data/en

### 勘误记录
- 初稿引用 MAST 为 arXiv 2505.17469（错误）→ 经原文核实更正为 **2503.13657**，
  且数字从"42 个系统"更正为"7 个框架 / 1600+ 轨迹 / 14 种失败模式 / 3 大类"。
  已同步修正 [HETEROGENEOUS_MODELS_EVALUATION](HETEROGENEOUS_MODELS_EVALUATION.md)。

> 本文遵循知识资产沉淀规则：三问结论、证伪方向、修正的引用错误都留档。

---

## 原报告：`SCIENTIFIC_MEASUREMENT_20261122.md`

## 科学测量方法论：STRATEGY 六项能力指标基线（2026-11-22）

> 用户问："测量的时候要有科学依据"，并指出"还有推卡的时候产生的会话"。
> 这两点都直接改变了测量方案。

### 一、方法论依据（调研确认）

#### 1. GQM（Basili & Weiss 1984, IEEE TSE）
Goal（对象/目的/质量焦点/视角/上下文）→ Question → Metric → Data。
每个数据点必须可向上追溯到目标，**无目标归属的指标应退役**。
ISO/IEC 15939:2017 要求"判定分析结果有效性"；ISO 25010 给质量模型。

#### 2. 构念效度（Cronbach & Meehl 1955）
代理指标 ≠ 目标构念本身。有效性需验证：
内容效度（覆盖构念域）、聚合/区分效度（MTMM）、效标关联、已知群体区分度。
**这是本轮最重要的一课**：我上一轮说的"可追溯率 29.7%"是
`evidence_log 字段比例`，而 STRATEGY 要的是"跨会话目标/决策/约束可追溯率"——
**代理指标，构念效度未验证**，不能当基线。

#### 3. 统计严谨性
- 分布 > 点值：Wilson 95%CI（小样本比例，优于 Wald，k=0 时仍有效）
- 噪声地板：项目已实测 σ≈10%；RCI = 1.96·SEM·√2
- 样本量 `n ≥ 2(zσ/δ)²`：σ=10%、检测 10% 变化需 n≥16
- 回归均值 E[复测]=μ+r(x−μ)：r=0.6、观测 25 → 复测期望 35（+10 纯回归假增益）
- Simpson 悖论：分层与合并趋势可反向 → 必须分层报告

#### 4. Goodhart / Campbell
指标越用于决策越被腐蚀。对策：指标多样、隐藏集、与奖惩脱钩、过程优于输出。

#### 5. 测基线的依据（出处订正）
"If you can't measure it, you can't improve it" **在 Drucker 著作中查无实据**，
源出 Lord Kelvin 1883 ICE 演讲（Thomson 1889 p.73）；
Deming《The New Economics》1993 斥严格版为 "a costly myth"。
无基线即无效应量、无法做功效分析。

### 二、用户指出的关键修正：推卡会话必须分层

用户："还有推卡的时候产生的会话"——完全正确。

实测 8 个 sid：
| 层 | sid | 数量 | 特征 |
|---|---|---|---|
| synthetic | s1 | 1（9600条）| 单测假数据，必须隔离 |
| **probe** | **budget-3 / budget-4** | **2（各360条）** | **推卡探针：只有 tool_call/injection_hit/tool_result，无高级证据** |
| task | f429de9d / f56ec374 / 16ebf7b1 / 7d712f92 / s2 | 5 | 真实任务会话，有 review/evidence/control |

**如果混在一起算**：probe 会话的 0 证据会稀释分母 → 系统性低估（典型 Simpson 风险）。
测量器只在 **task 层**计算能力指标。

### 三、科学基线实测结果（`tools/baseline_metrics.py`）

| 指标 | 状态 | 实测 | 95%CI | 判断 |
|---|---|---|---|---|
| G1 同一性连续性 | **PROXY_ONLY** | evidence_cited=3 / 5会话 | [0.231, 0.882] | 代理指标，构念效度未验证 |
| G2 连续性执行 | **NOT_INSTRUMENTED** | compaction=0 | — | 没埋点，不是分为0 |
| G3 目标自生成 | **NOT_INSTRUMENTED** | goal_proposal=0 | — | 没埋点 |
| G4 价值校准 | **PROXY_ONLY** | crit_hit=4 / 5会话 | [0.376, 0.964] | 命中≠失败率下降，需对照 |
| G5 经验进化 | **NOT_INSTRUMENTED** | delta_rule=0 | — | 没埋点 |
| G6 开放环境适应 | **PROXY_ONLY** | gate_created=0 | — | git有记录但无法区分触发原因 |

**结论：可测 0 / 代理 3 / 未埋点 3 —— 当前不具备科学测基线条件。**
样本量 task=5 < 16，只能检测 >12.4% 的相对变化；G1 的 CI 宽 0.65，几乎没有信息量。

### 四、核心诚实原则（写入工具，不可违背）

1. ★ 不把"测不了"伪装成"测出来很低"
2. ★ 不把"代理指标"伪装成"目标构念本身"
3. ★ 单点数值必须带置信区间和样本量警告
4. ★ 每项标注 MEASURABLE / PROXY_ONLY / NOT_INSTRUMENTED
5. ★ 按会话类型分层报告（synthetic/probe/task）

### 五、自证（防"假精确"）
- 未埋点指标正确标 `NOT_INSTRUMENTED`（3项）而非给出假分数
- 分层正确：probe=2、synthetic=1、task=5（断言验证）
- G1 代理指标 CI 宽度 0.65（诚实暴露不确定性，不假装精确）
→ 三项自证通过

### 六、下一步（基于测量的科学判断）
不是"优化代理指标"，而是：
1. **给 NOT_INSTRUMENTED 的三项埋点**（compaction / goal_proposal / delta_rule）
2. **验证代理指标的构念效度**：人工抽样对齐 evidence_cited 与真实可追溯性（一致性 80-85% 才采信）
3. **凑够样本量**：≥16 个 task 会话才能检测 10% 变化
4. **建立 hold-out 对照**（G4 因果测量必需）

### 七、出处
Basili & Weiss 1984（GQM）；ISO/IEC 15939:2017；ISO 25010:2023；
Cronbach & Meehl 1955（构念效度）；Wilson 1927（CI）；
Goodhart 1975 / Campbell 1976 / Manheim-Garrabrant 五型；
Campbell & Stanley 1963（前后测八威胁）；Lord Kelvin 1883 ICE；
Deming 1993；KTH arXiv:2602.07150（pass@1 波动 2.2-6.0pp）。

---

## 原报告：`PERIPHERAL_CAPABILITIES.md`

## 外围能力调研（2026-11-18 凌晨）

> 问题：还能给这个本地 35B 赋予哪些"外围能力"（连接器 / MCP / 其他）？
> 结论先说：**不接 MCP，把外围能力做成 Skills**。下面是证据与替代方案。

### 一、MCP 生态现状（2026-11）

- PulseMCP 索引 **20,115 个 MCP server**（2026-07）；90% 走本地 stdio（数据不出本机）
- 独立测评的共识是 **3~6 个服务器**，而不是"越多越好"
- **客户端约 40 个工具后开始退化**（Cursor 有记载的约 40 硬限；超出后工具在设置里可见但对 agent 静默消失）
- 每个工具定义**每次请求都在上下文里**：轻量 server ~400 token/轮，重量级 3,500+/轮
  - GitHub MCP 默认 **42 工具**；Playwright 默认 23（全开 68）；三件套默认合计 **67 工具 > 40 上限**
- **"我连了 12 个 MCP，agent 变笨了"**是社区真实投诉

### 二、本地小模型的额外约束（这是决定性的）

mcptrove 针对**本地 LLM** 的专门分析：

> "A quantized 7B running on your own GPU has a smaller effective context and weaker
> instruction-following, which means it picks the wrong tool, invents arguments, or loops.
> The fix isn't a smarter server — it's fewer, clearer tools."

本地短名单只推荐三个：**Anyquery**（用 SQL 查文件/DB/40+ 应用）、**Git reference server**、
**GitMCP**（把 GitHub 仓库变成实时文档，治"编造 API"）。

### 三、我们的实测数据（决定性）

| 指标 | 数值 |
|---|---|
| 当前工具面 | **28 个**（已接近 40 退化线）|
| 单个真实会话（71 步）实际调用 | **11 个**（ask_user_question/edit/glob/list_agents/present/pwsh/read/todo_write/web_search/write + 一次 web_fetch）|
| 零调用工具 | **17 个** |
| dsh 的 MCP 支持 | **无**（cordis.patch.yml 无 mcp 节点，基础包无 mcp 服务）|

⇒ 加 MCP = 在 28 个之上再加 12~42 个定义，**直接跨过 40 线**；而 BFCL 实测 20+ 工具时准确率
已降到 65~78%，38% 的错误是参数填错。**这是负收益。**

### 四、外围能力怎么做（替代方案）

#### 1. Skills（已落地，正确载体）
过程性知识按需加载，**不占工具面**。已有 5 个：release-plugin / debug-llama-server /
verify-artifact / web-fetch / git-workflow。
- 社区依据：Keyhole 白皮书把 Skills 列为核心层——"只在相关时加载的过程性知识"
- 扩展方式：遇到"这类任务总是同一套步骤"，就沉淀一个 skill（成本：一篇 md）

#### 2. 给已有工具补能力（比新增工具便宜）
| 缺口 | 现状 | 低成本方案 |
|---|---|---|
| **网页正文抓取** | `web_fetch` 不可用（无 provider），只有搜索摘要 | **web-fetch skill**：python urllib + 正则提正文（已写）|
| 结构化数据查询 | 只能 read 文件 | python 解析（csv/json/yaml），必要时 sqlite3 模块 |
| 图片理解 | 有 `read_image` | ✓ 已有 |
| 联网搜索 | SearXNG ✓ | ✓ 已有 |

#### 3. 工具面裁剪（真正的"扩容"）
社区一致：**减少工具 > 增加工具**。我们 28 个里有 17 个零调用。
- 计划：用 `bench/trace_report.py` 积累一周的工具调用分布 → 把确认零调用的静态 disable
  （`cordis.patch.yml` 的 preset plugins 逐条 disabled）
- 目标：**工具面降到 18~20 个**，把省下的 context 让给上下文/思考
- 风险：低频但必需的（spawn_teammate / wait_agent / read_image / skill）不能盲目裁——
  用 trace 数据 + 一次真实任务回归来确认

#### 4. 明确不做的
- **MCP 服务器**：dsh 不支持 + 工具面已满 + 本地模型更怕工具膨胀（三重否决）
- **向量数据库记忆**：35B 的检索判断力撑不起 embedding 检索的质量门槛
- **浏览器自动化**（Playwright 类）：23 个工具，本地跑不动（显存/延迟），且我们不需要
- **GitHub MCP**：42 工具——想用 GitHub 就让用户在网页/Git Bash 操作

### 五、如果将来要接 MCP 的前置条件

1. dsh 支持 MCP（上游）
2. 工具面先降到 ≤20
3. 只接 **≤2 工具**的薄服务器（如 Context7 式文档检索），且要有"按需加载 schema"的机制
   （Claude Code 的做法：工具 schema 延迟到真正需要时才注入）

三条都满足之前，**不动**。

---

## 原报告：`PEER_HARNESS_BENCHMARK.md`

## 同族 harness 对标：社区在做什么，我们还能补什么（2026-11-19）

> 范围：GitHub 上真实存在的 Qwen3-35B-A3B 族 / dsh 生态 harness 项目。
> 判据：只写核实过仓库 README/源码的项目，不写搜索摘要里的二手结论。
> 我们的路线：权重零改动 + 纯 harness 文本注入 + 确定性门控（见 [README](../README.md)）。

### 一、核实过的项目

| 项目 | 定位 | 与我们相关的最有价值机制 |
|---|---|---|
| [qzzqzzb/Self-Harness](https://github.com/qzzqzzb/Self-Harness)（arXiv 2606.09498）| 让模型改进自己的 harness | 失败签名精确聚类 + 双 split 回归门禁 + 单 hook 最小改动；已纳入路线图（[方案](SELF_HARNESS_PLAN.md)）|
| [jb-san/mini-harness](https://github.com/jb-san/mini-harness) | 极小内核的本地 coding agent | **7 个原生工具**（read/write/list/shell/web_search/web_scrape/discover_skills），其余全靠 skill + skill 内脚本 + repo hooks；`beforeToolCall/afterToolCall/onToolError/onContextIncrease` hook；工具调用被 hook 拦截时以普通 tool error 呈现 |
| [nonentity303/dsh-browser-agent](https://github.com/nonentity303/dsh-browser-agent) | 浏览器里的 dsh mini harness（userscript）| **技能提示词永远排在固定安全规则之前**（无法覆盖安全底线）；跨域授权**仅本次任务有效**、不写持久白名单；工具默认关 + 逐次确认；插件在隔离沙箱跑（无 DOM/网络/存储）+ 死循环超时强杀；159 项自动化测试 |
| [microsoft/agent-lightning](https://github.com/microsoft/agent-lightning) | 用 RL 优化 agent harness（含 Qwen3.5-35B-A3B 案例）| harness 作为可训练对象（我们路线不适用，但证明"harness 是关键变量"）；其 CLI harness 实现可作结构参考 |
| [rllm-org/rllm](https://github.com/rllm-org/rllm) | LLM 训练/推理统一框架，含 `cli_harness.py` | CLI harness 的标准化接口（我们自建，可对照其任务封装格式）|

> 说明：直接在 GitHub 搜 `Qwen3-35B-A3B harness` 返回 0 结果——**这个精确模型名还没有专门的 harness 产品**。
> "35B-A3B 族"的适配主要散落在通用 agent 框架里（走 OpenAI 兼容端点），这正是我们的空位。

### 二、逐项对照

| 机制 / 优化 | 我们 | 社区 | 可借鉴 | 具体动作 |
|---|---|---|---|---|
| **工具面裁剪** | 28 个工具（待办：28→18-20，需用户拍板）| mini-harness 刻意只留 7 个，能力靠 skill + skill 内脚本；"加工具请求"默认当"加 skill"处理 | **高** | 把待办的工具面裁剪从"拍板数字"改成"结构改造"：保留最小内核（read/write/edit/search/shell/bridge），把低频能力挪进 10 个 skill 卡；hook 化拦截（`beforeToolCall` 对应我们的 DANGER 分级）|
| **hook 化运行时策略** | 策略写在 index.mjs 内部（L0-L3 / D1-D5 / danger）| mini-harness 的 hook 是**仓库/用户提供的外部文件**，加载一次、错误被捕获、超时、失败不崩内核 | **高** | 把危险操作分级和注入预算做成外部 hook 文件（现有 `danger` 规则外置），让策略可热替换而不改 index.mjs——正好服务 Self-Harness 的"可编辑面白名单"|
| **上下文利用率为注入触发** | 压缩 thresholdRatio 0.55（54K）固定 | mini-harness `onContextIncrease(util%)` hook：≥70% 自动触发外部动作（如重启）| 中 | 把我们的压缩阈值从"固定比例"升级为 hook 事件，允许外部脚本按利用率做轻量动作（如主动整理 todo），不改核心 |
| **安全规则优先级** | 安全规则在 prompt + 模板双层，未被明确"排序"| dsh-browser-agent 明确：**技能提示词永远排在固定安全规则之前，skill 无法覆盖安全底线** | **高** | 在 AGENTS.md 和 skills 加载顺序里显式声明"安全规则不可被 skill/prompt 覆盖"，加一条回归测试验证（当前靠约定，没有强制）|
| **授权作用域** | approval 已根治为 full-access + never（本机单人）| dsh-browser-agent：跨域授权仅本次任务有效、不写持久白名单、fail-closed | 中（本机不需要，但有参考价值）| 记录为 ADR 的安全对照：如果将来开放多用户，授权必须 task-scoped |
| **沙箱隔离执行** | 无（harness 不执行 LLM 生成代码）| dsh-browser-agent 插件在隔离沙箱跑，死循环超时强杀 | 低（我们本来就不执行生成代码）| 保持现状，不构成缺口 |
| **trace 可观测性** | `_trace.jsonl` + trace_report + D5 审计 | mini-harness 在 TUI 的 telemetry timeline 展示 hook 事件，hook 拦截/失败可见 | 中 | 把我们的 DANGER 拦截 / verify-on-stop 也进 trace（部分已有），确保"被拦"可见而不只是"通过"可见 |
| **自动化测试密度** | 106 PASS（7 文件）+ 30/30 门禁 | dsh-browser-agent 159 项自动化（含沙箱端到端）| 中 | 数量不是目标；补"安全规则不可覆盖""hook 失败不崩内核"两类语义测试更有价值 |
| **RL 优化 harness** | 不适用（权重零改 + 无训练）| agent-lightning 把 harness 当训练对象 | 不适用但值得知道 | 记入"明确不做"（训练），但保留其 CLI harness 接口作对照 |

### 三、最值得抄的 5 条（按 ROI）

1. **工具面结构改造**（高 ROI，中等成本）：把 28 个工具收敛到最小内核 + skill 化，用 hook 做危险拦截。
   这同时解掉待办里的"工具面裁剪"和 Self-Harness 的"可编辑面白名单"两件事。
2. **外部 hook 文件**：把 danger 分级 / 注入预算策略从 index.mjs 外置成 `hooks/*.mjs`，加载一次、错误隔离、失败不崩。
   让策略可替换、可测试，且不碰核心代码（对应 mini-harness 的 hook 模型）。
3. **安全规则不可覆盖的硬声明 + 回归测试**：在 AGENTS.md 显式排序，加一条测试确保 skill/prompt 无法覆盖安全底线。
4. **上下文利用率 hook**：把压缩阈值升级为事件，允许轻量外部动作（不新增 LLM）。
5. **hook 事件进 trace**：DANGER 拦截/失败也记 trace，让"被拦"可观测。

### 四、我们的相对位置

- **领先**：确定性门控的深度（L0-L3 + D1-D5 + 30/30 门禁）、引擎内部信号（MTP acceptance）、端到端证伪文化、跨层复用（GWT/FEP）。
- **齐平**：skill 化（我们有 11 个技能卡）、trace 可观测性。
- **落后**：策略的**外部化/hook 化**（我们写死在 index.mjs）、工具面**刻意做小**的工程哲学、安全优先级的**显式声明与测试**。
- **空位**：35B-A3B 族**没有专门 harness 产品**——我们在这条细分线上是最完整的实现之一（以本机单人场景为前提）。

相关：[COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md)（宏观社区对比）· [SELF_HARNESS_PLAN.md](SELF_HARNESS_PLAN.md)（harness 自进化）· [ROADMAP](../ROADMAP.md)
