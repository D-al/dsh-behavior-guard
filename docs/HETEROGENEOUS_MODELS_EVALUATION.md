# 异构多模型角色分工：可行性评估（2026-11-19）

> 用户设想：35B 做 planner/验收员，0.8B 小模型做其他角色，扩展 harness 上限。
> 结论先行：**方向对，但角色分工恰好反了，且 0.8B 选小了。不建议按原设想做。**
> 有一条更窄、更稳的可行路径，见 §5。

## 一、本机现状（先纠正两个前提）

| 前提 | 实际情况 | 来源 |
|---|---|---|
| "内存还没放满" | ✅ 属实：RAM **63.7G 总量 / 53.6G 空闲**；显存 **8188MiB 总量 / 7251MiB 空闲**（评估时 llama 空闲） | PowerShell + nvidia-smi |
| "验收员用 35B" | ❌ **验收员本来就不是 LLM**：`runVerifyAgent()` 直接跑 `verify_agent.py`（纯 Python 规则，三态 PASS/FAIL/INCONCLUSIVE），零 LLM、零 35B 占用 | index.mjs:1325 |
| "所有角色都调 35B" | 部分属实：audit / critic / corrector / planner 走 `callLLM(cfg.endpoint)` = 35B；**执行者是 dsh 主会话**（cordis provider `llama-35b`），与角色调用是两条链路 | cordis.patch.yml:36/87 |

**关键含义**：用户想优化的"验收员用 35B"这个成本**根本不存在**；真正花 35B 时间的是 audit / critic / corrector / planner 四个旁路角色（实测 212 次 LLM 调用，服务不稳时大量空返回）。

## 二、社区与论文证据（两路独立调研交叉验证）

### 2.1 支持异构的架构（方向对）

- **Mixture-of-Agents (MoA)**：多层 agent 各用不同模型，writer 出草稿、aggregator 综合，6.7%→65.1% 提升（Alibaba Research/Tsinghua, arXiv 2406.04692）。但注意：MoA 里小模型是**并行提案者**，不是评委。
- **RouteLLM / FrugalGPT / Model Cascades**：小模型先答、难的路由到大模型，成本降 2-5×（RouteLLM; FrugalGPT arXiv 2306.05148; CascadeRouter arXiv 2510.06599）。**规律是"小模型先跑、大模型把关"，不是反过来的"大模型规划、小模型执行"。**
- **Speculative Decoding**：小 draft + 大 verify 是本机已用的 MTP 机制（draft-mtp，p_min=0.8，nmax=5）——同一原则在 token 级已验证有效。
- **Self-Refine / CRITIC**：critic 反馈能提升 actor，但前提是 critic 能识别错误。

### 2.2 反对"0.8B 做评审角色"的证据（决定性）

- **JudgeBench (arXiv 2406.19314)**：小模型 judge 与人类一致率仅 **45–60%**，随机基线 50%——接近抛硬币。
- **Stronger judges are more robust (arXiv 2411.13268)**：小 judge 存在**冗长偏见 + 自我增强偏见**；**LLM-as-judge 要可靠，参数量必须 ≥ 被评模型**。
- **Multi-agent 失败模式 (arXiv 2505.17469)**：42 个真实系统归纳出 **"错误验证放大"**——弱 verifier 放行强 actor 的错误，比不用 verifier 更糟。
- **"LLMs as Judges Are Not Always Reliable" (EMNLP Findings)**：模型扩大后方差降、与人类一致率升；小模型做不到。
- **Shrinking AI Model Can Boost Performance (arXiv 2508.18748)**：反例只出现在**简单 narrow task**，且"质疑能力"反而下降——评审恰是需要质疑的任务。
- **社区共识**：AgentLite 明确 "evaluator using a stronger model than the actor"；ChatDev 用更弱的模型做角色时会退化。

### 2.3 小模型真正适合的场景

- 确定性分类（JSON 修复、格式校验、命令意图分类）：**小模型足够**，甚至规则更好。
- 草稿生成（speculative decoding / draft）：已被本机 MTP 验证。
- 简单工具路由、意图分类、非关键摘要。

## 三、角色 × 最小可行规模（决策表）

| 角色 | 当前实现 | 原设想（0.8B）| 评估 | 理由 |
|---|---|---|---|---|
| **验收员** | Python 规则脚本 | 35B | ❌ **不需要 LLM** | 已是三态规则判定，比任何 LLM 都可靠且零成本 |
| **Planner** | 35B LLM（1 次/会话）| 35B | ✅ 保持 35B | 验收标准需语义理解；用量极小（全 trace 仅 6 次）|
| **审计员** | 35B LLM（门控触发）| 0.8B | ❌ **不能降** | 要识别"模型自己没发现的错"，弱模型会漏判/误判，错误验证放大 |
| **纠正器** | 35B LLM（双败触发）| 0.8B | ❌ **不能降** | 需要构造性修正包，弱模型会给错误修正 |
| **Critic** | 35B LLM（present 前）| 0.8B | ⚠️ **条件性可行** | 只有改成"反馈信号而非门禁"才可；Qwen3-0.6B 可作为轻量预警，但必须 35B/规则复核 |
| **执行者** | dsh 主会话 35B | — | ✅ 保持 | 主推理质量是底线；换小模型等于换脑 |

## 四、为什么"0.8B"这个量级选错了

1. **Qwen3-0.6B 非思考模式只有 4/29 任务成功**，Qwen2.5-0.5B-1M 在长上下文表现更差（Qwen3 技术报告）。
2. 评审任务的失败不是"慢一点"，是**静默放行错误**——比没有评审更危险（错误验证放大）。
3. 小 judge 的 45-60% 一致率意味着**近一半判断不可信**，而我们的门控正依赖它决定"要不要返工"。

## 五、可行路径（推荐，但降级为低优先级）

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

## 六、结论与路线图处理

- **不按原设想做**（把角色下放给 0.8B / 让 35B 做验收）。
- 把"小模型格式修复器"记为**中期可选优化（M7）**，前置条件是先拿到真实的角色调用耗时占比（当前 212 次调用分散在多时段，需重新测量稳定期成本）。
- 把"Critic 轻量预警"记为**长期探索（L5）**，需先做 A/B：0.6B 预警的召回率 ≥ 80% 才值得上。
- 记录为"已证伪的方向"：小模型做审计/纠正/验收。

相关：[PEER_HARNESS_BENCHMARK](PEER_HARNESS_BENCHMARK.md) · [CADENCE_REDESIGN](CADENCE_REDESIGN.md) · [ROADMAP](../ROADMAP.md)

## 证据链接

- MoA: https://arxiv.org/abs/2406.04692
- RouteLLM: https://arxiv.org/abs/2406.18665
- FrugalGPT: https://arxiv.org/abs/2306.05148
- JudgeBench: https://arxiv.org/abs/2406.19314
- Stronger judges robust: https://arxiv.org/abs/2411.13268
- Multi-agent failure taxonomy: https://arxiv.org/abs/2505.17469
- Shrinking model boost: https://arxiv.org/abs/2508.18748
- Qwen3 tech report: https://arxiv.org/abs/2505.09388
