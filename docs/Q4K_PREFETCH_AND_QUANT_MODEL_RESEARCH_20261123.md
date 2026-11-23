# q4_K 补丁实测 + Q3_K 质量 + 更适合 harness 的模型调研（2026-11-23 晚）

> 用户三问：① 接着做 q4 补丁 ② Q3_K 混合精度会不会降质量 ③ 有没有更适合 harness 的模型（脑区升级 CPU，先调研）

## 一、q4_K 软件预取补丁：**做了，但交叉验证证伪，不采用**

### 1.1 改动
- 位置：`ggml/src/ggml-cpu/arch/x86/quants.c:2120` `ggml_vec_dot_q4_K_q8_K` 的 AVX2 分支
- 改法：前向预取第 i+4 个 block 的 q4/q8 qs 到 L2（`_mm_prefetch(..., _MM_HINT_T1)`），12 行纯性能提示、不改数值
- 编译：成功（quants.c 重编 + ggml-cpu.dll 链接）
- 依据：社区同类补丁在 AVX512-VNNI 上报 +61%，预取部分 ISA 无关

### 1.2 实测：交叉验证推翻初测
| 顺序 | base（无预取）| patch（预取）|
|---|---:|---:|
| 第一轮 | 28.51 | **32.71**（看似 +14.7%）|
| 反向 | 29.17 | 29.05（**持平**）|

patch 自己两轮 32.7/29.1（差 3.7），base 两轮 28.5/29.2——**反向时完全持平，第一轮是顺序/噪声效应**。

### 1.3 结论
**不采用**。可能原因：DDR4 延迟已被 MoE cache 命中 +硬件预取器掩盖，或预取距离 4 不对。
- 方法论再次验证：**任何 >10% 的 decode 差异必须交叉验证**（这次和 t8 测试形成对比：t8 交叉后收益稳定，预取交叉后消失）

## 二、Q3_K 混合精度会不会降质量？——**会，而且社区的正确做法反直觉**

### 2.1 关键纠正：不是"降 experts"，而是"保 experts、降别的"
我之前一直想降 routed experts 的比特。**社区实测证据指向相反方向**：

- **APEX 团队**（对 Qwen3.6-35B-A3B 同架构）：shared expert 权重峰度 **13.10**（routed 只有 3.41）→ routed experts 近高斯、对量化最不敏感；**降 experts 是最安全的选择**
- 但质量拐点不在 experts，而在 **SSM/conv/gate 张量**——线性注意力状态累积误差对精度极敏感（这正是我们 31 层 DeltaNet 的命门）
- **Cerebellum GGUF 实测**：针对这个架构，把 routed experts 降到 Q3_K、**保住 SSM/conv 和 shared expert 高精度**，结果 **14 GiB 反超 16 GiB 的 uniform Q3_K_M**

### 2.2 对我们 harness 的直接回答
**会降质量，风险点正好在我们的场景**：
- BFCL V4 pilot：Qwen3 `parallel_multiple`（并行多工具调用）Q4=46/50，**Q3_K_M=44/50（−4pp）**
- arxiv 实测：tool calling 里"**是否调用工具**"比"调哪个"更脆弱；多轮/多调用类目 Q8=25.5→iq3_xxs=15.0→iq2_m=7.5
- 我们的 harness 有 **28 个工具面 + 多轮长链任务**——正是量化最脆弱的场景
- PPL 会骗人：Q4→Q3 PPL 只 +2.4%，但 kyumly 同结构实验 LiveCodeBench −26 分

**结论：如果一定要做混合精度，正确配方是"experts Q3_K + SSM/conv/shared expert 保 Q4+/Q8"，而不是我原先想的"只降 experts"。即便如此，在我们的多工具调用场景仍有 −2~4pp 风险，必须用 BFCL + 自建工具基准验收。**

## 三、有没有更适合 harness 的模型？——**有明确候选，但要换引擎思路**

### 3.1 第一性原理：CPU-bound 下该看什么
我们瓶颈是 CPU 每 token 读的专家字节（590% 满载）。所以"脑区升级 CPU"要找：① 总参数小 ② 激活参数少 ③ 专家更窄 ④ 线性注意力（状态固定、KV 小）。

### 3.2 候选（调研结论）
| 候选 | 架构 | 对 CPU-bound 的意义 | Agent 能力 |
|---|---|---|---|
| **Qwen3.6-35B-A3B（当前）** | 35B-A3B MoE + DeltaNet | 3B 激活已很小，但 256 专家 top8 仍要读 570MiB/token | 强（当前 harness 基线）|
| Qwen3.6-17B/30B-A3B（若存在）| 更小 MoE | 专家总量更小→每 token 字节更少 | 待核实 |
| GLM-4.5-Air / Kimi Linear | MoE + 线性注意力 | Kimi Linear 用 KDA（与 DeltaNet 同类），decode 快 | 需实测 |
| Qwen3.6-14B/32B dense | 纯 dense | 无专家读取瓶颈，但每 token 全量计算，CPU-bound 下可能更慢 | 强 |
| **IQ4_XS 同架构量化** | 35B-A3B | 体积 21→17GiB，减少 CPU 字节 | PPL +1.9%，agent 待验 |

### 3.3 诚实结论
**没找到"明确比当前更快且 agent 能力不降"的模型**。当前 35B-A3B 在"3B 激活 + 强 agent 能力"这个点上已是合理选择。真正能确定性提速的是**同架构混合精度**（按 2.1 的正确配方），而不是换模型。换模型的风险是 harness 已调优的中文思维链锚点、工具解析、MTP 行为全部要重验。

## 四、生产状态与建议
- 生产已恢复：t8 / share=1.0 / cache 1350 / Q4_K_XL / health 200
- q4_K 补丁已撤销（gdn-src 恢复干净）
- **建议排序**：① 保持现状（已是最优）② 若要质量/速度交换，按"保 experts Q3 + 保 SSM 高精度"做混合精度 GGUF ③ 不换模型

## 五、方法论沉淀（第三次验证）
**交叉验证已成铁律**：q4_K 预取 +14.7% 初测 → 反向持平 → 证伪。加上前两次（GDN 补丁、share 初测），这是第三次"单次 A/B 被交叉验证推翻"。任何优化结论没有交叉验证都不算数。
