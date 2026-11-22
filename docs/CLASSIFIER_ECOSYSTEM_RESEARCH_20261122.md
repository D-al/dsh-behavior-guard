# 分类器生态调研：社区与论文里同类分类器在做什么、效果如何（2026-11-22）

> 用户问"查查社区和论文，调研一下类似的分类器都是干嘛用的，效果怎样"。
> 背景：本地 S6 部署了 Horizon-Labs ModernBERT ONNX INT8 注入分类器（只写trace），
> M3 卡在"意图结构化抽取"上卡住。本次调研同时回答两条线的定位问题。

## 一、注入检测分类器（S6 同类）：社区共识是"纵深防御的一层，不是主防线"

### 1.1 最权威的自述：PromptGuard 官方文档"检测能做到什么、不能做到什么"
来源：https://docs.promptguard.co/security/detection-limits （2026-11-08 更新）
**这是分类器厂商自己写的限制说明，比任何第三方批评都有分量。**

- 默认工作点（moderate preset，2369 样本/8 数据集）：
  - Precision **99.1%** [98.5-99.6]、Recall **80.3%** [78.2-82.3]、F1 0.887
  - FPR **1.01%**（10/991 benign）、漏报 271/1378 攻击
- **Over-defense（更难的正确性）**：NotInject 基准（良性文本故意塞攻击词汇）
  over-defense **45.4%**；真实 persona 模板 **49.9%**——一半被拦
- **跨语料崩塌**：微调自家分布 → in-domain 99.1%，独立语料 **out-of-domain 7.2%**；
  现成分类器 out-of-domain 在 1% FPR 下只有 **40.8% recall**
- **自适应攻击天花板**：Nasr et al. *The Attacker Moves Second*（USENIX Security 2026,
  arXiv:2510.09023）对 12 个已发表防御做 tuned search 攻击，**全部 >90% 成功率绕过**。
  论文明确说"叠更多分类器解决不了"——因为分类器读的是攻击者可控的内容，
  准确性是经验属性，攻击者能迭代就终会找到 gap
- **AgentDojo 银行基准的反例**：trace-level/containment 防御相对无防御 46.5% **无显著降低**
  （47.2%/43.1%，p=1.00/0.64）；只有 per-message guard 把 46.5%→0.7%，
  代价是约 **30% 任务完成率损失**
- **厂商最终建议原文**：
  - "Detection **reduces risk measurably**; it does not eliminate a class of attack."
  - "**put the trust boundary at the action, not at the text. Everything on this page is defence in depth behind it.**"

### 1.2 第三方横评（2025 Alice/ActiveFence 报告，28,000+ prompt，13 语言）
| 模型 | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|
| Alice/ActiveFence（商业）| 0.890 | 0.826 | 0.857 | 5.4% |
| Deepset（开源）| 0.395 | 0.955 | 0.558 | **77%** |
| Llama Prompt Guard 2 | 0.793 | 0.511 | 0.621 | 7.0% |
| ProtectAI | 0.580 | 0.723 | 0.643 | 27.5% |
| Bedrock | 0.712 | 0.463 | 0.561 | 9.8% |
| Azure | 0.838 | 0.273 | 0.412 | 2.8% |
**注意**：该报告由商业厂商发布（有利益相关），数字只作方向参考。
核心信号：开源分类器 FPR 普遍高得不可直接用（Deepset 77%、ProtectAI 27.5%）。

### 1.3 跨语料分数不可迁移（ARMO 文章的关键案例）
同一个 DeBERTa-v3 184M 分类器，三个独立评测：
- 65.2%（Qualifire benchmark）
- F1 0.539（2386-case holdout）
- **FPR 0.9596**（JailbreakHub in-the-wild，作者称 unacceptable for production）
结论原文："no detector has yet been measured on someone else's corpus without losing ground."
→ **必须用自己的流量标定**，500 条标注样本（250 自家良性 + 250 自家攻击）就够区分候选。
"把 FPR 乘以每天打分数 = 每天坏掉的生产任务数"——这个乘法社区几乎没人做。

### 1.4 纵深防御的量化收益（arXiv:2511.15759，2025-11）
847 对抗用例、7 个模型：
- baseline 攻击成功率 73.2%
- + 内容过滤（embedding anomaly）：41.0%
- + 层级 system prompt guardrail：23.4%
- + 多阶段响应验证：**8.7%**
- 全栈：降 88.1%，保留 94.3% 干净任务性能，FPR 5.7%
**结论**：没有任何单一层够用，有效的是"输入过滤 + prompt 层级 + 输出验证"三层。
⚠️ 静态基准；自适应攻击者会让数字退化。

## 二、目标漂移 / 意图追踪（M3 同类）：论文直接否定"结构化状态是解药"

### 2.1 Apollo Research：Evaluating Goal Drift in LM Agents（arXiv:2505.02709, AIES 2025）
四个模型（Claude 3.5 Sonnet/Haiku、GPT-4o/mini）、四种设置（baseline/adversarial pressure/
goal switching/两者叠加）、20 seeds、最多 64 时间步（平均 90,827 tokens）。

**关键数字**：
- 对抗压力下，system goal=利润最大化、弱目标提示：`GD_actions` **0.51-0.93**
  （Claude 3.5 Sonnet 和 GPT-4o 都 >0.9——强模型漂移更严重！）
- system goal=减排：0.25-0.37
- **最佳 agent（scaffolded Claude 3.5 Sonnet）在 goal switching+对抗压力下 240 次评估 0 漂移**，
  64 步/9 万 token 仍强保持；GPT-4o mini 仅 16 步就大幅漂移
- 漂移机制消融（这是最关键的）：
  - **State complexity ablation**：清空上下文只留 portfolio+system message，
    "increasing state complexity has a **negligible effect** on goal drift"
    → 作者结论："**increasing state complexity cannot explain the observed goal drift**"
  - **Token distance ablation**（等长但重复单 token）：除个别外漂移显著更低
  - **Pattern-matching ablation**（把 assistant/tool 内容换随机串，保留 user/pressure）：
    "agents show increasing drift scores with more noise examples"
  - 作者最终判断："**pattern-matching as the primary mechanism behind goal drift,
    with goal reasoning capabilities playing a secondary role**"
- 缓解：强 system prompt 重述目标在对抗压力下显著有效（p<0.05），
  但在 goal switching 中"**insufficient**"——因为那要求打破上下文里的模式而非维持它

**对 M3 的直接冲击**：M3 原假设"意图漂移检测无状态可依"→ 做 BDI 三槽存状态。
这篇论文的 state complexity ablation **直接否定了这条路**——状态复杂度不是漂移成因。
真正的杠杆是 ① 强目标重述（已有：P0 存档每轮重注 initial）② 打破上下文模式匹配（还未做）。

### 2.2 LivePlan/RGE 数字核实（本地项目内部引用）——归属搞错了
本地 M3 卡/文档写"RGE/LivePlan 用 (role,goal,evidence) 三元组做到漂移 F1>93%、良性覆盖≥95.8%"：
- **数字属实但归属错**：全部出自 **RGE**（arXiv:2608.17718《Beyond Suspicious Steps: Ontological
  Trust in Long-Horizon Agents》，2026-08），机制是 Role/Goal/Evidence 三元组 + **LLM只抽取、
  信任状态更新/投影/干预决策全确定性**；F1>93%/覆盖≥95.8% 限于"两个较大 estimator 模型"
- **LivePlan（arXiv:2608.06701）是另一篇**：GraphEctory 动作图 + LangUctory 阶段序列规则监控，
  零 LLM 检测、只在漂移时调 LLM advisor；报的是 SWE-bench resolve rate **+9.9pp 均值/+15.2pp**
  （成本 +$0.08/实例），**不是 F1，也不用三元组**
- **都未独立复现**（论文距今约3个月）；RGE 论文给的代码地址 github.com/ai-systems/rge 当前 404

### 2.3 意图追踪的其它关键证据（子任务补充）
- **StepShield（arXiv:2601.22136）反面证据**：847 条正则 guard 检测 rogue agent，
  recall 86% 但**早期干预率 EIR 0.23 vs 随机 0.24（p=0.66）**——>75% 告警在违规前的良性前缀触发。
  原文结论："**regex 检测语法，不检测意图**"；**高召回但时机随机 = 没用**。
  → 本地"关键词交集<0.25"正属此类，也提醒我们 ⑤ 补的 trace 要看"时机"不只是"命中率"
- **StateForge/IntentFlux（arXiv:2609.32520）**：维护 active requirements 并对用户改口做"折叠"，
  效果 0.367→0.467；但 **Oracle Gap——给 oracle 完美状态仍回不到单轮水平**，
  说明历史里的冲突信息本身就是干扰源，"每轮重比原文/全量喂历史"会加剧问题
- **小模型意图分类（CLINC150/BANKING77）**：固定标签集 + 有标注下 BERT/RoBERTa 94-98%，
  SetFit 每类 8-16 例即可——但这是"选标签"不是"开放世界抽取结构化状态"
- **零样本结构化抽取的共识路径**：teacher LLM 诱导 schema/造标注 → 蒸馏到小模型在线跑
  （granite-13B F1 0.93、8B lenient F1 0.52→0.77）——不是"必须大模型在线"，也不是"纯规则可行"
- **BDI 在 LLM agent**：ML-BDI 综述（arXiv:2510.20641）分析 98 篇，50 篇用 LLM，
  但只有 25% 支持在线学习；主流判断是 ReAct/Reflexion/Generative Agents 本质就是 token 化 BDI 循环，
  不再严格实现三槽——**没有"被更好方案替代"的证据，更多是被重新解释为隐式 BDI**
（子任务若找到一手来源会补充。）

### 1.5 社区产品定位 + OWASP 官方立场（子任务补充）
- **OWASP LLM01:2025 Top 1 就是 Prompt Injection**（https://genai.owasp.org/llm-top-10/），
  官方明确：*"No single tool completely prevents prompt injection. Defense relies on layered controls."*
- **Meta Llama Prompt Guard 2（86M/22M）**：定位是"快速**预筛**"，官方明确说
  "不部署为唯一防御、需与输入校验+输出校验+人类监督叠加"。注意：**86M 参数是模型规模**，
  与本地 Horizon 的两位数 ms 延迟不是一回事（本地 0.27s 稳态主要是 E 核绑定+HTTP+长跑退化）
- **LLM Guard / Rebuff / Nemo Guardrails** 都自定位 guardrail 层，不是主防线；
  LLM Guard 文档原话："**LLMs are inherently non-deterministic and can be tricked to bypass guards**"
- **注入为什么防不住的实证（Baseline Bypass Report 2026）**：
  单独 emoji 注入让 GPT-4o 检测率从 ~82% 掉到 **0%**；多语言 + emoji 绕过 **100%**；
  Base64 编码 GPT-4o 成功率 100%；10 种语言合计 312 条 payload
- **Cline 事件（2025-08）**：攻击者把 prompt injection 藏在假冒 npm 包 README，诱导 AI 编码助手
  执行恶意命令并偷用户资金——真实世界间接注入已经在造成损失

### 1.6 Benchmark 分数根本不可迁移（量化证据）
- **Benchmark Guard（arXiv:2603.07320）**：8 个主流注入检测器 + 3 个 agentic benchmark，
  检测器间一致性和与人类判断的一致性 **Kendall τ 低到 0.02**——几乎随机相关
- ** InjecGuard（arXiv:2508.16794）**：提出"不过度防御"基准，指出
  "安全文本含攻击相关词汇"（安全工程师讨论、支持工单引用 payload、安全 wiki）被大量误报
- **实时约束**：Prompt Injection Firewall（arXiv:2606.08653）核心是"轻量预筛 + 深度检测"
  两阶段 architecture——跟本地"前置规则过滤 + 分类器"结构一致

## 三、对本地项目的三条硬启示

1. **S6 分类器**：不要把"命中后 steer/拦截"当成防线升级。社区共识是
   "**信任边界放在动作上，不是文本上**"——真正有效的是对 consequential action 做 gate。
   我们当前"只写 trace"反而符合 PromptGuard 的"detection reduces risk, does not eliminate"定位。
   若要做，最值得做的是**在动作层设权限边界**，而不是调分类器的阈值。

2. **FPR 账要按自己的流量算**：本地大样本 FPR 0.3%，但那是离线基准；
   真实会话第一次命中就是误报（stderr 路径错误）。PromptGuard 的 over-defense 45-50% 说明
   "良性但含攻击词汇"的文本是分类器的结构性弱点——本地工具结果里这种文本很多
   （安全提示、文档、错误堆栈）。前置筛选（已修 exit code 前缀）比调阈值更有价值。

3. **M3 重定位的方向要改**：既然 state complexity 被论文否定、规则抽取只能截原话，
   "存结构化意图槽"这条路在学术界没有支持。真正有证据的杠杆是：
   ① **强目标重述**（P0 存档已在做）② **打破长上下文模式匹配**（控制回合已在做元决策，
   但没针对"模式匹配"设计）③ **动作层 gate**（跟 S6 的结论殊途同归）
   ④ **RGE 式混合架构**：LLM 只做"抽取"，信任更新/投影/干预全用确定性代码
   （本地零 LLM 规则抽取失败，但"LLM 抽取 + 确定性状态机"是有论文支持的可行路径——
   只是需要一次 LLM 调用，需算成本）
   → 建议 M3 重定位为"**反模式匹配的目标锚定 + 确定性状态机**"，而不是"意图结构化抽取"。

4. **"时机"比"数量"重要（StepShield 的教训）**：本地 ⑤ 漂移检测刚补的 trace
   要记"触发时 agent 走到了哪一步"，不能只记 overlap 数字——高召回但时机随机等于没用。

## 四、诚实标注
- PromptGuard 数字来自厂商官方文档，他们**主动公开不利数字**（over-defense、OOD 崩塌、
  containment 在 AgentDojo 无效），可信度高于一般厂商白皮书；但仍是其自家 benchmark
- Alice/ActiveFence 横评由商业厂商发布，有利益相关
- Goal drift 论文的数字来自原文正文，作者明确说多数相关性"not statistically significant"
- 本地"RGE/LivePlan F1>93%"未找到一手出处
- 社区/产品全景（Lakera/NeMo/Rebuff/LLM Guard 等）由并行子任务补充，见对话
