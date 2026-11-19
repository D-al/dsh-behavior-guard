# 超小模型作为"周围神经系统"：可行性与方案评估（2026-11-19）

> 用户设想：把 0.1B-1B 超小模型全扔进空闲内存（53G），作为主模型的"周围神经系统"——
> 做感知/分类/反射/路由/修复，扩展脑的实力，**不替代主模型判断**。
> 结论：**这次和"小模型当评审员"那轮不同——有大量真实成功案例，方向成立。**
> 但要选对模式：router-first + 守门/分类，不要 cascade 式的"小模型先答、不行再升级"。

## 一、和上一轮评估的关键区别

| | 上轮（小模型当评审/验证） | 本轮（小模型当外设/周围神经） |
|---|---|---|
| 任务性质 | **判断**：要不要放行、产物好不好 | **信号**：分类、路由、格式修复、快速反射 |
| 失败后果 | 静默放行错误（比不审更糟）| 分类错了可回退到大模型/规则，损失只是延迟 |
| 证据 | 反对（JudgeBench 45-60%≈抛硬币）| **支持**（守门/路由/投机解码大规模生产验证）|
| 结论 | 证伪 | **成立，但要挑对模式** |

一句话：**小模型不适合"替大脑做判断"，非常适合"替大脑做感知和反射"。**

## 二、真实成功案例（按模式分类，带数字）

### 模式 A：守门/分类层（最成熟，证据最硬）

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

### 模式 B：路由/级联（收益在成本，不在延迟）

- **RouteLLM**（ICLR 2025）：MT-Bench 只把 **14%** 查询发给强模型，保留 95% 质量，成本降 **>85%**。
- **FrugalGPT**（Stanford）：级联降本最高 **98%**。
- **SLM Orchestration Gateway**（arXiv 2606.03557，8GB 边缘设备）：微调 **0.5B Qwen2.5 做路由，准确率 83% / 延迟 392ms**；分层端到端中位 <1.5s；**比单独用 1.5B 做路由更快**（1.5B 路由要 1776.9ms）。
- ⚠️ **反直觉（关键）**：800 次真实调用的 sub-second triage 实测——"**Tiering did almost nothing for latency**"；cascade 在中段分布反而最慢（升级时串行跑 detector + reasoning）。真正收益是成本（fast $0.21/千请求 vs large $0.88，约 4×）和安全召回。
- ⚠️ **router-first > cascade**（交互式）：router 是单次跳转、p99 紧；cascade 每条都付"小模型+验证器"，升级率仅 1-3% 就可能吃掉收益。
- **收支平衡公式**：cascade 成本 ≈ cheap + verifier + escalation_rate × expensive；10× 价差下可升级 90% 才亏，3× 价差下上限 67%。

### 模式 C：投机解码（本机已在用，token 级的外周）

- 本项目已用 MTP draft（spec-type=draft-mtp, p_min=0.8, nmax=5）——这本身就是"小模型配合大模型"的成功案例，只是发生在 token 级。
- EAGLE / Medusa / Lookahead 等变体各有加速倍数，但**需要改模型结构/训练 draft head**，与"权重零改"冲突，不是我们的路线。

### 模式 D：System 1 / System 2 双过程（架构范式）

- **SwiftSage**（NeurIPS 2023）：小行为克隆模型做快速直觉动作，GPT-4 做子目标规划，ScienceWorld 30 任务超越 ReAct/Reflexion。
- **SOFAI 元认知仲裁**：快求解器先试，置信高就执行；低则计算 Expected Value of Control 再决定调慢求解器。
- **DPT-Agent**：慢系统不直接选动作，只更新持久策略/宏动作供快系统执行——**"慢系统学习、快系统执行"**。
- 与本项目契合点：我们的确定性门控 = 规则版 System 1；trace 系统 = 天然的校准/学习数据源。

### 模式 E：CPU 常驻小模型群（最贴合本机硬件）

- **多专家懒加载实证**（中文社区）：主模型常驻显存 + 子模型懒加载，8G 单卡可容纳主 q4(0.3G) + 子 q4(0.9G) + 激活(1G) ≈ 2.2GB；路由 0.5B ~5ms，首次加载 ~200ms/切换 ~50ms。
- **Mesh LLM**（2 台 4 核 CPU 主机池化）：跨节点转发延迟差 <0.4s（噪声内）；0.5B/1B 模型加 `--ctx-size 8192` 后稳定 1.78GB。
- ⚠️ **CPU 小模型不是零延迟**：0.5B 在 4 核 CPU 上单次 ~3.5s（无 GPU）；本项目 i7-12650H 10C/16T + 53G RAM 会更好，但**并行吞吐/串行延迟必须实测**。

## 三、反面证据与失败条件（必须遵守）

1. **过度自信是致命的**：小模型"经常错但很少怀疑"。实测 gpt-4.1-nano 过敏案例以 0.8 置信返回 false 绕过阈值→召回 100%→94%；"错但不确定"可利用，"自信地错"摧毁级联。
2. **原始置信度不可用**：让小模型自评 0-10 设阈值是 theatre（系统性过度自信）→必须在标注集上画实际胜率 vs 置信曲线定阈值。
3. **换模型/换版本后校准漂移**：准确率相近但对错误答案置信更高→同阈值下准确率暴跌 >15 点。
4. **分布外（OOD）**：小模型在 OOD 上幻觉更多→任务必须限定在清晰定义域，加"未知路由到前沿"规则。
5. **升级风暴**：小模型层广泛失败时每请求付两次钱→需 circuit breaker 全量回退大模型。
6. **路由器本身可能比省下的还贵**：7B 路由器放在 $0.15/M 目标模型前，路由比省的贵→**路由器成本必须比便宜路径低一个数量级**。
7. **切换模型的隐藏成本**：session 中途换模型使 KV/prompt cache 失效——一次 20K token cache miss 抹掉切换节省。规则：**单轮查询激进路由，多步 agent 固定一个模型**。
8. **过拒绝**：安全分类器边界样本误拦（医疗/历史/创作）→阈值分场景设，不能一刀切。

## 四、对照本 harness 的挂载点评估

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

## 五、本项目的独特优势（别的 agent 没有的资产）

1. **trace 系统 = 天然校准数据源**：可记录每条请求的"门控决策 / 小模型置信 / 是否升级 / 最终结果 / 延迟 / 成本"——这正是所有文献强调必须记录、但连商业路由器都空白的一环。我们能画可靠性图、定阈值、做 shadow 对比。
2. **确定性门控 = 天然安全默认**：所有文献建议"router 失败时 fail toward large model"，我们的规则门控能硬性实现且可解释。
3. **闭环学习**：大模型离线从 trace 提炼门控规则/阈值，下发给小模型群——对应"高层学习、低层执行"。

## 六、结论与建议指标

**方向成立**，但只做"外设"不做"判断"，且 router-first 而非 cascade。

建议的量化目标（文献经验值，作为起点非承诺）：
- 路由准确率 ≥95%；fast path 覆盖率 ≥80%；升级率 ≤20%
- 质量 delta vs 全大模型基线 <2%
- 端侧路径 p95 <400ms；升级路径 p95 <2s
- 升级率 >2× 基线或校验违规激增 → circuit breaker 全量回退

**落地前必须实测**（本机独特条件）：53G RAM 常驻多个 0.5B 的并行吞吐、CPU 推理串行延迟、小模型置信校准曲线（ECE/Brier）。

## 七、对路线图的更新建议

- **新增 P0（高性价比）**：工具结果注入检测层（86M Prompt-Guard，CPU，<10ms）——这是"周围神经"最纯粹的形态，且与现有确定性门控互补。
- **保留 M7**（小模型格式修复器）为 P1。
- **L5 降级/收紧**：Critic 轻量预警改为"只做信号不拦截"，并加校准阈值前置条件。
- **新增验证任务**：小模型 CPU 推理基准（吞吐/延迟/校准曲线），是所有后续决策的前置。
- **不新增**：小模型做审计/纠正/验收/主推理。

相关：[HETEROGENEOUS_MODELS_EVALUATION](HETEROGENEOUS_MODELS_EVALUATION.md)（上轮：判断类证伪）· [ROADMAP](../ROADMAP.md) · [PEER_HARNESS_BENCHMARK](PEER_HARNESS_BENCHMARK.md)

## 证据链接
- Prompt-Guard / Llama Guard / ShieldGemma / WildGuard 生产对比: https://www.llms.blog/posts/open-source-safety-and-moderation-classifiers-in-production-comparing-llama-guard-3-shieldgemma-wildguard-and-prompt-guard
- RouteLLM: https://neuraltrust.ai/blog/llm-model-routing ; FrugalGPT: https://arxiv.org/abs/2306.05148
- SLM Orchestration Gateway (0.5B 路由 83%/392ms): https://arxiv.org/html/2606.03557v2
- sub-second triage 实测（tiering 不降延迟）: https://bessavagner.com/blog/sub-second-llm-triage
- router-first vs cascade: https://dnt.co.il/why-llm-cascades-fail-for-interactive-apps-use-router
- SwiftSage: https://arxiv.org/abs/2305.17390 ; MoD: https://arxiv.org/abs/2404.02258
- Mnehmos Agentic Nervous System: https://mnehmos.github.io/Mnehmos/blog/from-chatbot-to-organism
- Mesh LLM CPU 池化实测: https://www.itnotetk.com/2026/11/04/mesh-llm-pooled-inference
- 多专家懒加载（中文实证）: https://blog.csdn.net/chuchu00000000/article/details/162838522
