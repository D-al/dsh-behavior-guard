# 路线定位与最高效演化策略（2026-11-21 广泛调研）

> 来源：4 路并行 WebSearch 子任务（路线谱系 / test-time 与验证不对称 / 自我进化与记忆 / 合成心智与认知架构）+ 主代理 domain_search 与一手论文交叉验证。
> 目的：回答"我们在哪条路线上"和"怎样演化 35B+harness 最高效"。所有关键数字都经过至少一个一手来源核验。

---

## 一、我们在哪条路线上：明确的答案

2026 年的共识公式：

```
Agent = Loop(LLM + Harness)
Harness = Context + Tools + Memory + State + Execution + Feedback + Verification + Guardrails
```

一句被反复引用的概括：**"stochastic generation stays; stochastic control flow goes"**（保留随机生成，剔除随机控制流）。

学术谱系（arXiv:2606.20683 综述等三份独立综述收敛）：
- **路线 A**：Harness 工程化/分类学（六元组 H=(E,T,C,S,L,V)）——已制度化
- **路线 B**：Harness 自动合成与进化——2026 论文密度最高，**我们在这里**
- **路线 C**：Harness 可表示化/可迁移（NLAH）——研究可比较性的前提
- **路线 D**：验证优先、确定性验收作为一等公民

**我们的精确坐标**：路线 B（harness 递归自改进）+ 路线 D（fail-closed 证据链）的混合体，处在"用机器可读路线图驱动 harness 自我改进"这个细分方向上。这个方向本身在学术界是前沿（AutoHarness / Life-Harness / RRSI / HarnessForge），但我们已经碰到了该路线的**已知陷阱**。

---

## 二、最重要的一条负面证据：我们可能在过拟合自己的测试台

RRSI（arXiv:2609.24972，Google Cloud AI + Stanford/UNC/WashU）直接研究"harness 递归自改进"：

- 三类过拟合：**benchmark-specific encoding / noise chasing / complexity accumulation**
- 无正则化的自进化，在 OOD 基准上**跌破初始基线 H0**
- RRSI 加正则（提案侧退火编辑预算 + 选择侧 critic/pruner/噪声地板/成本规则）后：演化集 +14.1pp、OOD +4.7pp，且比无正则化**少 30% policy token**

另一篇四预注册研究（arXiv:2610.05533）：21 个有显著搜索集增益的设置里，**平均 54% 归因于过拟合、14% 归因于 test-time scaling**，剩下的才是真机制。

**映射到我们的现状（诚实到刺痛）**：
- 我们的 `agentlab.py` 7 小任务 / `projectlab.py` P1-P5 就是"演化集"；今晚往 harness 加的所有守卫/门控都在这个小集合上验证过
- 我们没有 hold-out 任务集、没有编辑预算退火、没有噪声地板（单次 ±10% 我们知道却没当判据）、没有成本规则、没有剪枝
- "加了机制 → 门禁 30/30 → 宣称完成"正是 RRSI 说的 `complexity accumulation`
- 反向检验发现 S15 单测 57/57 却从未接线、S11/A1_7 判据写错——这是"noise chasing"的另一种形式

**结论：我们目前的自改进循环，按论文标准属于"无正则化的 RSI"，其 OOD 收益很可能是负的。** 这比"下一张卡推什么"重要得多。

---

## 三、最反直觉的一条正面证据：不要堆弱模型，质量压倒多样性

Self-MoA（arXiv:2502.00674，Princeton）200+ 实验的结论：
- **混合不同模型（MoA）通常劣于只采样最强模型多次（Self-MoA）**：AlpacaEval 2.0 上 Self-MoA 比 Mixed-MoA 高 **6.6 分**，MMLU/CRUX/MATH 平均高 **3.8 分**
- 即使刻意构造"每个模型各擅长一个子任务"的混合任务，Mixed-MoA 也只以 0.17%/0.35% 微弱胜出
- 质量对结果的影响远大于多样性：最优区域是**高质量、相对较低多样性**

JudgeBench（arXiv:2410.12784）：GPT-4o 做客观正确性判断只有 **50.9%**（随机 50%）；ChatEval 双 agent 辩论 **~34%**；连专门的 judge 微调模型（PandaLM）在知识/推理上低于随机。判断能力与解题能力高度相关——**弱模型做 critic 是负资产**。

Snake Swarm / 异构对抗验证（子任务调研）：异构评委错误检出率 83%，同质 50%，单评委 17%。但注意：这里的"异构"是同等质量的异构，不是"强+弱"混合。

**映射到我们**：
- 我们曾设计"35B + 多个 0.8B 分饰 planner/审计/纠正/验收"——被这两篇直接证伪。会话记录里 Q13/Q19 已有警告（协调者悖论、弱 judge 放行强 actor 错误），现在是论文级证据
- 我们后来把 Critic/Planner 收回 35B 自己扮演 + Python 规则验收——**方向对了**，但"35B 自审"仍受 JudgeBench 限制（自偏好 0.520）
- **正确形态**：proposer 只用最强模型（35B 多次采样），verifier 尽量下沉到确定性检查（测试/schema/哈希），LLM judge 只用于真正无法断言的部分，且必须成对交换顺序 + 独立 rubric + 人工抽检

---

## 四、最高效演化：把确定性推到极致，而不是继续堆机制

### 4.1 已被反复验证的"能力无关内核"（留到模型再强也需要）

Mingbird（arXiv:2610.02001，288 个对照单元：4 harness × 4 模型(2B-35B) × 18 任务）：
- 0.886 vs goose 0.631 / opencode 0.479 / agent-mini 0.405
- **127 次失败中 85 次是"进程正常退出但零产物"（quiet stop）**——证明 artifact 级验收是刚需
- 单条 streak rule（禁止连续 8 次相同工具调用）关掉后，0.75B 得分暴跌 **0.411**
- 0.75B 档位最好与最差 harness 差距 **0.653**；35B 档位差距缩小——**harness 杠杆随模型变弱而增大，我们是 35B，处在杠杆仍显著的区间**

Forge：8B 模型 agentic 任务成功率 53% → 99%（rescue parsing / retry nudges / required_steps 状态机）。
Perplexity Portable Computer：确定性 orchestrator + OS 沙箱 + 按需 skills + 100K 有效窗口经验，53 任务 82.6%。

**与我们的对照**：我们已有 finish gate（D4 交付闸门）、streak/循环检测（D1 重复探测）、状态机（M8 FSM）、证据链（evidence_log）——**内核方向完全正确**。这说明我们不需要推倒重来，需要的是**剪枝与正则化**。

### 4.2 必须警惕的反向证据：harness 复杂度非单调

Cho 等（arXiv:2605.26731，432-run 受控实验，HEAT-24）：
- 前沿 chat 模型（Gemini 2.5 Flash）：harness 变啰嗦使成功率**下降 29-38pp**
- 前沿 reasoning 模型（Qwen3.5-122B）：strict harness 反而最优（91.7%，延迟最低）
- 2B 模型（Gemma4:e2B）：三种严格度都是 91.7%
- 失败分档：强模型多 `format_violation`，弱模型多 `wrong_file`

HarnessTax（UC Berkeley）：harness 选择对成功率影响小、对**成本影响大**——同模型同分数价格差 5 倍。
"模型吃掉 harness"（hellofig.io / Latent Space / Anthropic 实践）：为旧模型写的强指令（"CRITICAL: you MUST"）会让新模型过度反应；Claude Code 为新模型砍掉大部分 system prompt。**判别准则："如果模型比你更聪明，这条规则还需要吗？"**

**映射到我们**：我们今晚加了 N 个守卫。其中"改完必须跑测试/证据链/权限边界"是永久性的；"因为模型 20K 会漏看所以限制 500 行"这类是补偿性的，模型升级后要删。我们目前**没有补偿性/永久性分类，也没有定期删除机制**——这是待补的一课。

### 4.3 硬件不对称：不是缺陷，是结构性优势

子任务调研的关键发现（Dovetail / CPU-GPU 分工）：
- **并行批量验证适合 CPU**（独立样本显存开销小；每条测试更像 tinyML 工作负载），**串行草稿生成适合 GPU**（KV cache 主导，共享注意力优势大）——这与"验证放 GPU"的直觉相反
- RouteLLM / FrugalGPT / HybridLLM 级联可省 **50-75%** 成本、准确率反升
- 会话 Q141 的"CPU 变异农场 + GPU 选择压力"在论文中有对应（Blueprint First Model Second：源码蓝图 + 受限节点调 LLM，通过率 35.56% vs ATLAS 18%，约束违反减少 96%）

**映射到我们**：i7-12650H + 64G DDR4 + 8GB 4060 确实是"CPU 变异 + GPU 裁决"的理想载体。但注意会话 Q131 警告：相变速度快于 35B 串行裁决速度，控制必须在**相变之前**（连接度/边界），不能事后审批。今天凌晨 4 会话并发写仓库就是一次微型不可治理相变。

---

## 五、综合判断：最高杠杆的三件事（按证据强度排序）

### 第 1 名：给自改进循环加正则化（RRSI 纪律）——这是"元"级别的最高杠杆

具体动作：
1. **hold-out 任务集**：从 agentlab/projectlab 里切出 30% 永不用于选卡/调判据，只用于最终验收
2. **编辑预算退火**：早期允许多机制捆绑，后期一次只改一个可归因机制
3. **噪声地板**：先测未改动基线方差，落入方差内的"提升"不算提升（我们知道单次 ±10%，却一直没当判据）
4. **成本规则**：新增机制必须证明 token/时间收益，否则拒收
5. **剪枝机制**：每季度删一次"不再挣钱"的守卫，区分补偿性 vs 永久性规则

理由：没有这个，后面所有"改进"都可能是过拟合。RRSI 的无正则方法 OOD 跌破基线，就是我们的前车之鉴。

### 第 2 名：验证层重构——质量压倒多样性，判断下沉

具体动作：
1. Critic/Planner 不再"35B 自审"，改成**同模型多次采样（Self-MoA 式）** + 确定性 rubric + 成对交换顺序
2. 弱模型（0.8B 等）**只做 proposer 候选生成，绝不单独做 verifier**（JudgeBench + 会话 Q19 双证）
3. 所有可断言的判断下沉到 Python 规则/测试/哈希，LLM judge 只留开放语义部分
4. CritBank 注入硬预算 3-5 条 / ≤500 token，按失败模式复合键检索，首尾放置（会话 Q79/Q81 + 子任务 CritICL/Context Keeper 数据）

### 第 3 名：补"能力无关内核"的最后缺口 + 控制复杂度

具体动作：
1. 确认已有：finish gate / streak / 状态机 / 证据链 / 沙箱——保留，它们不会过时
2. 补上：工具面硬预算（我们现在 28 个工具，社区拐点 10+ 就该考虑，弱模型 12-15 拐点）、上下文分层预算、动态 skills 按需加载
3. 建立 harness 基准：leave-one-mechanism-out + 噪声带，量化每个守卫的边际收益——我们今晚的 35/35 门禁全是"有判据"而非"机制消融"
4. 审查"补偿性脚手架"：给每条守卫标注 permanent / transient，transient 的设复查日期

---

## 六、不做什么（同样重要）

- ❌ 不堆 0.8B 多角色 critic 系统（Self-MoA + JudgeBench 双证伪）
- ❌ 不在没有 hold-out 的情况下继续加机制（RRSI）
- ❌ 不追求群体相变 / 让分类器互调成网（会话 Q129-137 + OpenAI 1200 agents 自建通道事件；我们的中心化架构是优势，别丢）
- ❌ 不做数字生命 Phase 3 / 自我修改治理结构（会话 Q111/Q113：元治理锁必须在系统外）
- ❌ 不为"更聪明"而加规则，只为"可审计/可回滚/权限边界"加（模型吃掉 harness 的判别准则）

---

## 七、一句话结论

**我们在 harness 递归自改进（路线 B）上；这条路线 2026 年最前沿的教训不是"加更多机制"，而是"给自改进加正则化 + 把判断权下沉到确定性层 + 用最强模型单次多样采样替代弱模型 ensemble"。我们的内核方向对了，但缺 hold-out、缺噪声地板、缺剪枝、缺工具面预算——这些比再爬 10 张技术卡都重要。**

---

## 附：关键一手来源

- arXiv:2606.20683（agent/harness 综述，六元组分解）
- arXiv:2609.24972 + github.com/google-research/rrsi（RRSI 正则化自改进）
- arXiv:2610.05533（harness 增益归因：54% 过拟合）
- arXiv:2610.02001（Mingbird 288 单元对照）
- arXiv:2502.00674（Self-MoA：质量>多样性）
- arXiv:2410.12784（JudgeBench：GPT-4o 50.9%）
- arXiv:2605.26731（harness 复杂度非单调）
- arXiv:2606.01779（HarnessForge：harness-policy 兼容性矩阵）
- arXiv:2605.22166（Life-Harness：+28.7pp/迁移 +3.5pp）
- arXiv:2603.03329（AutoHarness：harness-as-policy）
- Perplexity Portable Computer（确定性 orchestrator 产业实现）
- hellofig.io《The model is eating the harness》（补偿性 vs 永久性脚手架）
