# 引擎优化深入：预取/源码/显存（2026-11-23）

> Q4_K 预取、源码级优化、显存剖析、mmproj Q8 发现

> 本卷合并 7 份原报告（2026-11-25 整理）。

## 本卷目录

- `Q4K_PREFETCH_AND_QUANT_MODEL_RESEARCH_20261123.md`
- `SOURCE_LEVEL_OPTIMIZATION_FINAL_20261123.md`
- `FIRST_PRINCIPLES_OPERATOR_OPTIMIZATION_20261123.md`
- `ENGINE_BLOAT_AUDIT_AND_MULTIMODAL_VRAM_20261123.md`
- `Q8_MMPROJ_FOUND_20261123.md`
- `WHY_7_7G_VRAM_20261123.md`
- `EXPERT_PARALLEL_PATCH_RESULT_20261123.md`

---

## 原报告：`Q4K_PREFETCH_AND_QUANT_MODEL_RESEARCH_20261123.md`

## q4_K 补丁实测 + Q3_K 质量 + 更适合 harness 的模型调研（2026-11-23 晚）

> 用户三问：① 接着做 q4 补丁 ② Q3_K 混合精度会不会降质量 ③ 有没有更适合 harness 的模型（脑区升级 CPU，先调研）

### 一、q4_K 软件预取补丁：**做了，但交叉验证证伪，不采用**

#### 1.1 改动
- 位置：`ggml/src/ggml-cpu/arch/x86/quants.c:2120` `ggml_vec_dot_q4_K_q8_K` 的 AVX2 分支
- 改法：前向预取第 i+4 个 block 的 q4/q8 qs 到 L2（`_mm_prefetch(..., _MM_HINT_T1)`），12 行纯性能提示、不改数值
- 编译：成功（quants.c 重编 + ggml-cpu.dll 链接）
- 依据：社区同类补丁在 AVX512-VNNI 上报 +61%，预取部分 ISA 无关

#### 1.1.1 "纯性能提示不改数值"到底改没改到真东西？（用户追问）
`_mm_prefetch()` 不是注释，是真实 intrinsic。证据链：
- 补丁编译时的中间产物 `build-gdn/.../arch/x86/quants.c.obj`（mtime 15:54:53，补丁生效时）里扫到 **2 条 `PREFETCHT1` 机器码**（字节 `0F 18 54 C6`，偏移 69094），正好对应我加的 `x[i+4].qs` 和 `y[i+4].qs` 两处
- 对比：`ggml-cpu.dll` 里另有 2 条 prefetch（T0）来自上游 q4_0 路径，**与本补丁无关**
- 所以补丁**确实编译进二进制、CPU 确实会执行**

但这不等于有收益：① prefetch 是 **hint**，CPU 可以忽略；② 硬件预取器可能已经把数据搬好了，软件预取多余；③ 交叉验证证明无提速。
**准确表述：补丁"生效"（有机器码）但"无用"（无性能收益）。原报告"纯性能提示不改数值"的表述容易误解为"没改真东西"，特此澄清。**

#### 1.2 实测：交叉验证推翻初测
| 顺序 | base（无预取）| patch（预取）|
|---|---:|---:|
| 第一轮 | 28.51 | **32.71**（看似 +14.7%）|
| 反向 | 29.17 | 29.05（**持平**）|

patch 自己两轮 32.7/29.1（差 3.7），base 两轮 28.5/29.2——**反向时完全持平，第一轮是顺序/噪声效应**。

#### 1.2.1 为什么第一次差异看起来那么大？（用户追问的统计回答）
两轮原始数据（各 5 次，单位 t/s）：
- 第一轮 base: 33.06/28.09/25.29/28.51/34.77，patch: 36.43/32.71/29.45/25.29/32.74
- 反向 patch: 27.78/31.32/29.05/34.17/22.80，base: 23.02/24.96/33.64/29.17/30.53

统计：
- 全部 20 次 pooled sd = **3.98 t/s**，单次极差 13.6 t/s（22.8~36.4）
- 5 次中位数的标准误 ≈ **1.78 t/s**
- 第一轮差 +4.20 t/s，反向差 −0.12 t/s → **符号翻转**
- 合并 10 次：base 29.10 vs patch 30.17，差 +1.07，标准误 1.81 → **t = 0.59**（远低于显著阈值 2.0）

**结论：第一次的 +14.7% 是噪声，不是信号。** 单项波动（±4 t/s）比配置间差异（+1 t/s）大 4 倍。
根因是测量条件不稳定：① 2 次 warmup 不足（MoE cache 按需增长，冷/暖差 ~7%）；② WorkBuddy/dwm 抢 3D 调度；③ 笔记本功耗/温度状态漂移。这解释了为什么第一轮 patch 的 r0 恰好撞到 36.43（全场最高）。

#### 1.2.2 "硬件预取做了同样的事"——证据分层（诚实标注）
**这是推断，不是本机实测**。分层如下：
- **事实**：① 补丁生成了 2 条 PREFETCHT1 机器码（obj 已扫到）；② 交叉验证无提速（t=0.59）；③ 上游 q4_0 路径自带 `_mm_prefetch(T0)` 4 处（说明上游作者认为预取在这类 kernel 有价值）；④ 本机 CPU 是 i7-12650H（Alder Lake，有 L2 streamer + adjacent line 硬件预取器）
- **机制推断（教科书层面，未在本机验证）**：我们的 q4_K dot 外层 `for i` 遍历**同一专家内部**的连续 block（每 block 144 字节），这是硬件 L2 streamer 最擅长的线性跨步模式 → 硬件很可能已经提前搬好 → 软件再提示一次是冗余。**但我没有读 MSR 确认预取器开关，也没有用 perf 计数器测 L2 miss，所以"硬件做了"未被证实**
- **无法排除的其他解释**：预取距离 4 不合适；瓶颈在 scale 解包而非取数；CPU-bound 下 A 核乱序执行已足够掩盖延迟

#### 1.3 结论
**不采用**。可能原因：DDR4 延迟已被 MoE cache 命中 +硬件预取器掩盖，或预取距离 4 不对。
- 方法论再次验证：**任何 >10% 的 decode 差异必须交叉验证**（这次和 t8 测试形成对比：t8 交叉后收益稳定，预取交叉后消失）

### 二、Q3_K 混合精度会不会降质量？——**会，而且社区的正确做法反直觉**

#### 2.1 关键纠正：不是"降 experts"，而是"保 experts、降别的"
我之前一直想降 routed experts 的比特。**社区实测证据指向相反方向**：

- **APEX 团队**（对 Qwen3.6-35B-A3B 同架构）：shared expert 权重峰度 **13.10**（routed 只有 3.41）→ routed experts 近高斯、对量化最不敏感；**降 experts 是最安全的选择**
- 但质量拐点不在 experts，而在 **SSM/conv/gate 张量**——线性注意力状态累积误差对精度极敏感（这正是我们 31 层 DeltaNet 的命门）
- **Cerebellum GGUF 实测**：针对这个架构，把 routed experts 降到 Q3_K、**保住 SSM/conv 和 shared expert 高精度**，结果 **14 GiB 反超 16 GiB 的 uniform Q3_K_M**

#### 2.2 对我们 harness 的直接回答
**会降质量，风险点正好在我们的场景**：
- BFCL V4 pilot：Qwen3 `parallel_multiple`（并行多工具调用）Q4=46/50，**Q3_K_M=44/50（−4pp）**
- arxiv 实测：tool calling 里"**是否调用工具**"比"调哪个"更脆弱；多轮/多调用类目 Q8=25.5→iq3_xxs=15.0→iq2_m=7.5
- 我们的 harness 有 **28 个工具面 + 多轮长链任务**——正是量化最脆弱的场景
- PPL 会骗人：Q4→Q3 PPL 只 +2.4%，但 kyumly 同结构实验 LiveCodeBench −26 分

**结论：如果一定要做混合精度，正确配方是"experts Q3_K + SSM/conv/shared expert 保 Q4+/Q8"，而不是我原先想的"只降 experts"。即便如此，在我们的多工具调用场景仍有 −2~4pp 风险，必须用 BFCL + 自建工具基准验收。**

### 三、有没有更适合 harness 的模型？——**有明确候选，但要换引擎思路**

#### 3.1 第一性原理：CPU-bound 下该看什么
我们瓶颈是 CPU 每 token 读的专家字节（590% 满载）。所以"脑区升级 CPU"要找：① 总参数小 ② 激活参数少 ③ 专家更窄 ④ 线性注意力（状态固定、KV 小）。

#### 3.2 候选（调研结论）
| 候选 | 架构 | 对 CPU-bound 的意义 | Agent 能力 |
|---|---|---|---|
| **Qwen3.6-35B-A3B（当前）** | 35B-A3B MoE + DeltaNet | 3B 激活已很小，但 256 专家 top8 仍要读 570MiB/token | 强（当前 harness 基线）|
| Qwen3.6-17B/30B-A3B（若存在）| 更小 MoE | 专家总量更小→每 token 字节更少 | 待核实 |
| GLM-4.5-Air / Kimi Linear | MoE + 线性注意力 | Kimi Linear 用 KDA（与 DeltaNet 同类），decode 快 | 需实测 |
| Qwen3.6-14B/32B dense | 纯 dense | 无专家读取瓶颈，但每 token 全量计算，CPU-bound 下可能更慢 | 强 |
| **IQ4_XS 同架构量化** | 35B-A3B | 体积 21→17GiB，减少 CPU 字节 | PPL +1.9%，agent 待验 |

#### 3.3 诚实结论
**没找到"明确比当前更快且 agent 能力不降"的模型**。当前 35B-A3B 在"3B 激活 + 强 agent 能力"这个点上已是合理选择。真正能确定性提速的是**同架构混合精度**（按 2.1 的正确配方），而不是换模型。换模型的风险是 harness 已调优的中文思维链锚点、工具解析、MTP 行为全部要重验。

### 四、生产状态与建议
- 生产已恢复：t8 / share=1.0 / cache 1350 / Q4_K_XL / health 200
- q4_K 补丁已撤销（gdn-src 恢复干净）
- **建议排序**：① 保持现状（已是最优）② 若要质量/速度交换，按"保 experts Q3 + 保 SSM 高精度"做混合精度 GGUF ③ 不换模型

### 五、方法论沉淀（第三次验证）
**交叉验证已成铁律**：q4_K 预取 +14.7% 初测 → 反向持平 → 证伪。加上前两次（GDN 补丁、share 初测），这是第三次"单次 A/B 被交叉验证推翻"。任何优化结论没有交叉验证都不算数。

---

## 原报告：`SOURCE_LEVEL_OPTIMIZATION_FINAL_20261123.md`

## 从引擎源码出发的优化空间：完整结论（2026-11-23）

> 用户问："从原理出发（引擎源代码），还有什么优化的空间？"
> **答案：第一性原理算清后，这个负载是 DDR 带宽墙，41 t/s 附近已是当前配置的结构性天花板；源码里能动的开关几乎都被实测证伪。当前 t8 配置是唯一经交叉验证稳定且最快的配置。**

### 一、第一性原理：瓶颈到底是什么（用源码+GGUF元数据精算）

#### 1.1 每 token 的字节账
```
每专家: gate_up[1024,2048] + down[2048,512] = 3.146M 权重
q4_K = 4.375 bpw = 0.547 B/weight → 1.72 MiB/专家
每 token: 40 层 × 8 专家 = 320 专家 × 1.72 MiB = 551 MB 从 DDR 搬到 CPU
34 t/s → 18.7 GB/s / DDR4-3200 双通道实用 35-40 GB/s → 利用率 ~50%
```

#### 1.2 算力账
```
FLOPs = 1.0 G 权重 × 2 = 2.0 GFLOP/token × 34 t/s = 68 GFLOP/s
6P+4E AVX2 峰值 ~700-1000 GFLOP/s → 利用率仅 7-10%
→ ALU 严重闲置，不是瓶颈
```

#### 1.3 结论：**DDR 带宽墙，不是算力墙**
理论带宽上界 40 GB/s ÷ 0.551 GB/token ≈ **72 t/s**，考虑解包/同步开销，现实可达上界约 **45-55 t/s**。当前 34 t/s 还有 ~1.5x 空间，但空间来源是"减少字节"而非"更快计算"。

### 二、源码逐项排查结果（全部带行号）

| 方向 | 源码位置 | 结论 | 状态 |
|---|---|---|---|
| **scale 解包外提** | `arch/x86/quants.c:2151-2161` | 理论可改但收益≤5%，且 scale 12B→16B(+2.8%带宽) 在带宽墙上可能净负 | ❌ 不值得 |
| **tiled matmul 强制** | `ggml-cpu/tiled/tiled.cpp:583` | 强制后暴跌 11.8 t/s（默认 29.2）——decode 每专家 rows=1~6<8，tiled 摊不平 | ❌ 实测证伪 |
| **L2 软件预取** | `arch/x86/quants.c:2120` | 机器码确实生成（obj 扫到 2 条 PREFETCHT1），但交叉验证 t=0.59 无收益 | ❌ 实测证伪 |
| **CPU 绑核 P 核** | `common/arg.cpp:1519` + `ggml-cpu.c:2571` | 初测 33.03，反向掉到 25.25；当前 t8 自由调度两轮 32.46/32.37 极稳 | ❌ 实测证伪 |
| **repack 加速** | `repack.cpp:5244` | CPU_REPACK buffer `is_host=nullptr`，MoE cache 要求 host → 二者互斥，开 repack 丢 70-85% 命中率 | ❌ 互斥 |
| **CUDA Graph** | `ggml-cuda.cu:3313` | MUL_MAT_ID 同步 + GDN state 指针每步变 → 整图 capture 失效 | ❌ 不适用 |
| **采样/DRY** | `llama-sampler.cpp:2923` | 只扫候选集非全词表，<50μs/token，占 30ms 的 <0.2% | ❌ 已最优 |
| **MoE cache 零槽/LRU** | `llama-moe-cache.cpp:453` | n_zero=8 正好，bitmask O(1)，上传循环 share=1.0 时零执行 | ❌ 已最优 |
| **expert deferral** | `qwen35moe.cpp:199-222` | 静态图技术上能改，但残差硬依赖+router 读 cur+需同时改 scheduler，且破坏数值语义 | ❌ 高风险无验证收益 |
| **流水线并行** | `llama-context.cpp:581` | scheduler 有 4-copy pipeline，但 MoE cache 场景**显式关闭**；开启需解决 copy callback 多 copy 冲突 | ⚠️ 理论 1.3-1.4x，实现代价大 |
| **--n-cpu-moe 精确调度** | `common/common.h:1296` | 把部分层专家放回 GPU 减少 CPU 字节——**但显存只剩 346 MiB，放不下** | ⚠️ 受显存约束 |

### 三、被排除方向背后的共同规律

五次"单轮看起来有效、交叉验证推翻"的经历（GDN 补丁 / share / q4_K 预取 / tiled / 绑核）说明：
- **这个系统上 decode 测量的 sd ≈ 4 t/s，任何 <8 t/s 的单轮差异都不可信**
- 真正稳定的收益只有 t6→t8（+18%，交叉验证两轮 33.2/34.2 vs 29.2/28.3）和 share=0→1.0（+28%，两轮方向一致）
- 前者利用了 E 核算力，后者绕开了 PCIe 同步——**都是结构性改变，不是指令级微调**

### 四、最终结论：**源码层面还有空间吗？**

**结构性空间（理论 1.3-1.5x）但实现风险高：**
1. **流水线并行**：打开 `llama-context.cpp:581` 被禁的 pipeline，让 CPU 专家与 GPU attention 真正重叠。需解决 MoE cache copy callback 的多 copy 冲突，工作量大
2. **降低每 token 字节**：混合精度（Q3_K 专家）或更激进的 cache 命中率提升——但前者需换模型文件（质量风险，见 Q3K 调研），后者受 8G 显存限制

**指令级微调：全部被第一性原理或实测排除。** 这个负载是带宽墙，dot kernel 已经是 AVX2 高度优化版本，scale 解包/预取/tile 都动不了。

**当前配置（t8 + share=1.0 + cache 1350 + Q4_K_XL）已是"不改模型、不改引擎结构"条件下的最优解。** 想再进一步，只有两条路：
- 接受质量风险，换混合精度 GGUF（减少每 token 字节）
- 接受实现风险，改 scheduler 打开流水线并行

### 五、一句话回答用户
**从源码第一性原理看，还有 ~1.5x 空间，但全部卡在"字节墙"上，且能低成本试的开关我都试过并证伪了。真正的下一步是决策：换混合精度模型（质量风险）还是改引擎流水线（实现风险）——不是再找一个小补丁。**

---

## 原报告：`FIRST_PRINCIPLES_OPERATOR_OPTIMIZATION_20261123.md`

## 第一性原理 + 算子级优化调研（2026-11-23 下午）

> 用户问："有没有像改算子的方案（或手搓改其他算子）可以进一步提升解码速度和输出质量？从第一性原理和社区论文方向看"

### 〇、最重要发现：瓶颈定位错了 3 个月

**实测**（发持续 500-token decode 同时采样）：
| 指标 | 值 | 含义 |
|---|---:|---|
| GPU 显存带宽利用率 | **12-29%** | GPU 在摸鱼 |
| GPU 功耗 | **30W**（满血 115W）| GPU 几乎空闲 |
| CPU 实例进程 | **590%**（6 线程满载）| **CPU 才是瓶颈** |
| router 进程 | 0.3% | 无干扰 |

**之前的"GPU 带宽瓶颈"假设完全错了**。真实瓶颈是 **CPU 侧 share=1.0 的专家 matmul + 反量化**，6 线程跑满。

这解释了所有历史现象：
- 为什么 share=1.0 比 0 快 28%（把专家从 PCIe 上传变成 CPU 算，绕开 GPU 等待）
- 为什么 GPU 带宽只有 12-29%（GPU 在等 CPU 喂数据）
- 为什么混合精度专家是最大杠杆（直接减少 CPU 字节）

### 一、零成本收益：CPU 线程 6→8（**已部署**）

i7-12650H 是 **6P+4E**，当前 `-t 6` 只用 P 核。线程扫描（stream 前 128 token，5 次中位）：

| 线程 | 第一轮 | 反向验证 | 判断 |
|---:|---:|---:|---|
| t6（旧）| 29.18 | 28.31 | 基准 |
| **t8（新）** | **33.21** | **34.24** | **+18%，顺序无关** |
| t10 | 32.82 | — | 与 t8 噪声内 |
| t12 | 25.28 | — | **超订用**（HT 兄弟争抢）|
| t16 | 28.29 | — | 同样掉 |

机理：t8 用上 2 个 E 核帮忙；t12 起用 HT 兄弟反而争抢内存控制器。

**已改 `.env.llama` → `LLAMA_35B_THREADS=8`，生产重启验证 threads=8 / health 200。**

注：旧注释"−t 已封顶、57t/s"是 b12244/另一模型的测试，与 master 1.0 + Qwen35B 的 29-34t/s 不是同一条件，已更正。

### 二、算子级手搓可行性（源码分析结论）

#### 2.1 CPU 侧 q4_K dot（真正热点）——有空间但需权衡
- **位置**：`ggml/src/ggml-cpu/arch/x86/quants.c:2120-2200`，`ggml_vec_dot_q4_K_q8_K`
- **热点**：每个 block（32 权重）做 `memcpy(utmp, x[i].scales, 12)` + 4 行位运算重组 scale/min + `_mm256_cvtepu8_epi16`；内层仅 4×2 次 `maddubs`
- **解包指令数 ≈ dot 指令数**，是真实的优化空间
- **改法**：repack 阶段预生成"对齐的 scale 表"，dot 里直接 load，省掉每 block 的 memcpy+位运算（约 30-40 行，语义不变）
- **风险**：社区有类似补丁（预取 ISA 无关部分 +61%），但没有针对我们这个版本的现成 diff；需重编译 + 完整质量验证

#### 2.2 repack 与 MoE cache 互斥——**此路不通**
- **互斥点**：`src/llama-moe-cache.cpp:313` 的 `ggml_backend_buffer_is_host()`；repack 后的 buffer `is_host=nullptr` → MoE cache 完全禁用
- **判断**：cache 命中率 70-85% 的收益远大于 repack kernel 的收益。**不能为了 repack 关 cache**

#### 2.3 DeltaNet/GDN 状态 fp32→fp16——收益有限
- **位置**：`ggml/src/ggml-cuda/gated_delta_net.cu:180+`，kernel 签名全是 `float*`；状态 `GGML_TYPE_F32`
- **现状其实不错**：状态一次读进寄存器、循环所有 token 后一次写回，不是逐 token 往返
- **收益**：RS buffer 251 MiB → 125 MiB，省约 1-2ms/token（~5%）。但 **GPU 不是瓶颈**（30W），收益会被 CPU 瓶颈掩盖
- **风险**：线性注意力状态有衰减机制，fp16 精度风险中等；改动量大（kernel 全是 float 计算）

#### 2.4 采样算子——已优化，无空间
- 有 CUDA 版 `top-k-mask.cu`；采样不是当前瓶颈（CPU 590% 主要是专家计算不是采样）

#### 2.5 CUDA Graph——不适用
- 我们是 MoE（动态路由）+ DeltaNet 混合图，动态 slot map 每步变，graph capture 会失效

### 三、社区论文方向评估（第一性原理）

| 方向 | 出处 | 机制 | 对我们的判断 |
|---|---|---|---|
| 专家混合精度 | APEX/Gordon/BFCL 论文 | 减少 CPU 读字节 | ✅ **最大杠杆**，但需换模型文件（用户未决定）|
| CPU 线程用满 E 核 | 本机实测 | 6P+4E 架构 | ✅ **已部署 +18%** |
| q4_K scale 预计算 | 社区 AVX2 补丁 | 减少解包指令 | ⚠️ 可做，30-40 行，需验证 |
| 预取/L2 hint | 论文 | 隐藏内存延迟 | ⚠️ 对 CPU-bound 有效，但未找到我们版本的现成 diff |
| GDN fp16 状态 | flash-linear-attention | 减少状态字节 | ❌ GPU 不是瓶颈，收益被掩盖 |
| Expert deferral | KTransformers SOSP'26 | 打破串行图 | ❌ ggml 静态图做不到 |
| 投机 acceptance 提升 | EAGLE3 等 | 摊薄每 token 成本 | ⚠️ 已有 MTP 0.77-0.81，提升空间有限 |

### 三·五、源码深挖的补充发现（2026-11-23 晚）

#### A. 真正的瓶颈是 DDR 带宽墙（源码+元数据精算）
- 每专家 gate_up[1024,2048]+down[2048,512] = 3.146M 权重，q4_K 4.375bpw → 1.72 MiB/专家
- 40 层 × 8 专家 = **~551 MB/token 必须从 DDR 搬到 CPU**
- 34 t/s → 18.7 GB/s，DDR4-3200 实用带宽 ~35-40 GB/s → 利用率约 50%，还有 2x 理论空间
- FLOPs 2.0 G/token × 34 = 68 GFLOP/s，AVX2 峰值 ~700-1000 GFLOP/s → **ALU 利用率仅 7-10%，不是瓶颈**
- 子任务独立复核：scale 解包占 dot ALU 10-15%，但预解包会把 scale 读取 12B→16B（+2.8% 带宽），在带宽墙上**可能净负收益** → scale 外提不值得做

#### B. Windows 不区分 P/E 核（源码铁证）
- `common.cpp:153-201` 的 `is_hybrid_cpu()`/`is_running_on_efficiency_core()` 被 `#if defined(__x86_64__) && defined(__linux__)` 包住 → **Windows 分支完全不区分 P/E 核**
- `ggml-cpu.c:557-735` 的 NUMA/绑核逻辑全 Linux-only，Windows `:2291-2292` 是空函数
- **本机实测拓扑**（GetLogicalProcessorInformationEx）：P 核=逻辑 0-11（6 核×2HT，eff=1），E 核=逻辑 12-15（eff=0）
- 后果：`-t 8` 时 Windows 可能把线程摆在 HT 兄弟或 E 核上，被最慢核拖住（straggler）

#### C. 可实测的纯参数钩子
- `-C <hexmask>` / `-Cr lo-hi`（`common/arg.cpp:1519-1538`）：Windows 下走 `SetThreadAffinityMask`（`ggml-cpu.c:2571-2603`）
- `--prio 1/2`（`arg.cpp:1547`）：关 Windows 11 核心停放（源码注释明说 n_threads>4 时很关键）
- `GGML_CPU_TILED_MM_FORCE=1`（`tiled.cpp:583`）：强制 tiled kernel。**已测：暴跌到 11.8 t/s（vs 默认 29.2，−60%）** — 因为 tiled 只在 rows>=8 划算，decode 时每专家 rows=1~6，这个开关坐实了传统 vec_dot 是当前路径

#### D. 绑核 A/B 初测（待交叉验证）
| 配置 | 中位 | 均值 | sd |
|---|---:|---:|---:|
| t8 自由 | 32.46 | 30.49 | 4.07 |
| t6 绑 6P 核(0x555) | 33.03 | **31.94** | 3.74 |
| t8 绑全 P 核(0xFFF) | 29.57 | 28.78 | 4.95 |
| t12 自由 | 34.17 | 32.26 | 5.42 |

初测显示绑 6P 核均值最高，但 sd 巨大。**交叉验证结果（推翻初测）**：

| 配置 | 第一轮 | 反向 |
|---|---:|---:|
| t8 自由调度（当前）| 32.46 | **32.37**（极稳）|
| t6 绑 6P 核 (0x555) | 33.03 | **25.25**（掉 8）|

**结论：绑核证伪，保持 t8 自由调度。** t8 两轮几乎一致（32.46/32.37），是当前唯一稳定的配置；t6 绑核剧烈波动（33.03→25.25）。说明 HT 兄弟实际上在帮忙，绑掉后算力不足。子任务"E 核拖累"的推测在本机不成立。这是第五次单次 A/B 被交叉验证推翻。

### 四、结论与建议排序
1. **✅ 已做**：CPU 线程 6→8（+18%，零成本，已部署）
2. **⚠️ 可做但需决策**：混合精度专家 Q3_K（预计 decode +23~29%，但需重做 GGUF）
3. **⚠️ 可手搓**：q4_K scale 预计算（30-40 行，语义不变，预期收益待实测）
4. **❌ 不建议**：GDN fp16 状态、repack、CUDA Graph（要么 GPU 不是瓶颈，要么互斥）

### 五、方法论沉淀
**profiling 先于优化**：我差点基于"GPU 带宽瓶颈"去做 GDN 状态优化，实测发现 GPU 只有 30W、CPU 590% 后才定位到真正的瓶颈。**任何算子优化前必须先用功耗/带宽/CPU 占用三维定位，不能只看 t/s**。

---

## 原报告：`ENGINE_BLOAT_AUDIT_AND_MULTIMODAL_VRAM_20261123.md`

## 引擎多余部件审计 + 多模态显存优化方向（2026-11-23 深夜）

> 用户问："引擎本身有没有多余部件被加载进显存？能否抠出来？" + "希望它能支持多模态" + "这部分能不能放进内存？偶尔发图片"

### 一、编译期：已经裁干净了，省不了显存

#### 1.1 当前编译配置（CMakeCache.txt 实测）
```
CMAKE_BUILD_TYPE=Release / NDEBUG 已开
CMAKE_CUDA_ARCHITECTURES=89           ← 只编译 sm_89（RTX4060 Ada），单一架构
GGML_CUDA=ON / GGML_VULKAN=OFF / GGML_METAL=OFF / GGML_SYCL=OFF / GGML_OPENCL=OFF / GGML_BLAS=OFF
GGML_AVX=OFF / GGML_AVX2=OFF(native) / GGML_AVX512=OFF / GGML_AVX_VNNI=OFF / GGML_AMX=OFF
GGML_CUDA_FA_ALL_QUANTS=OFF（只编译 5 种 FA 量化组合）
```
**结论：通用性裁剪之前已经做过。** Vulkan/Metal/ROCm/多 SM 架构/AVX512 全没编进来。

#### 1.2 唯一还能裁的编译项（但省不了显存）
- `GGML_CUDA_NCCL=ON`：多 GPU 通信库，单 GPU 用不到
- `GGML_SCHED_MAX_COPIES=4`：pipeline 关闭，实际只用 1
- `ggml-cuda.dll` 207.5 MiB（实测 217,529,344 B） 里含所有量化类型的 MMQ kernel（Q2~Q6/IQ 系列），我们模型只用 Q4_K(68%)+Q5_K(32%)

**但关键认知（调研给出铁证）**：编译进去的未用 kernel 只是**磁盘上的 DLL 字节**。CUDA 11.7+ 默认 **lazy module loading**——设备代码在该 kernel **首次 launch 时**才上传显存，用不到的量化 kernel 的 SASS **永远不会进 VRAM**。
- 实测 PTX 全是 `.target sm_89`（147 处），**无多架构 PTX 可裁**；改 `89-real` 只省磁盘
- 约 14 种量化类型（q5/q6/IQ 系列等）是死代码，但裁掉它们显存变化 ≈ 0
- **编译期裁剪 = 省磁盘/加载时间，不省显存。** 这条路对当前目标无效

调研同时纠正：`ggml-cuda.dll` 实测 **207.5 MiB**（非早先估计的 253 MiB）。

### 二、运行期显存里唯一的大件：mmproj-F16（858 MiB）

#### 2.1 事实
- `Qwen3.6-35B-A3B-mmproj-F16.gguf` = **857.6 MiB**，F16 精度
- 当前 `MMPROJ_OFFLOAD=1` → 视觉编码器常驻显存
- server 启动即加载 mtmd_context（`tools/server/server-context.cpp:1264`），**没有按需加载机制**
- 当前显存 7769/8188 MiB（余 419 MiB）—— mmproj 占了 858 MiB，是余量的 2 倍

#### 2.2 三个方案对比（用户要求保留多模态）

| 方案 | 显存 | 视觉质量 | 速度 | 判定 |
|---|---:|---|---|---|
| A. 禁用视觉（MMPROJ=''）| 省 858 MiB | **失去多模态** | — | ❌ 用户明确不要 |
| B. 放内存（MMPROJ_OFFLOAD=0）| 省 858 MiB | 不变 | **CPU 编码 141s/张**（历史实测，ADR-0005）| ❌ 太慢 |
| C. **量化 mmproj 到 Q8_0** | **省 402 MiB** | **几乎无损** | GPU 编码保持快 | ✅ **推荐** |
| D. 量化 mmproj 到 Q4_K | 省 616 MiB | OCR 准确率约 −1.5pp | GPU 编码保持快 | ⚠️ 备选 |

#### 2.3 量化质量证据（社区实测）
- Qwen3-VL mmproj F16(839MB) → Q8_0(454MB)："**体积减半，视觉识别质量几乎无损失**"（多来源一致）
- ArmorOCR(Qwen3-VL-8B) AdvSpot 基准：F16 基线 55.7 → **Q8_0 56.9（反而略高）** / Q4_K_M 54.2（−1.5pp）
- 结论：**Q8_0 是甜点**——省一半显存、质量无损甚至微升

#### 2.4 障碍：没有现成的量化工具在 build/bin
- `llama-quantize.exe` 不在当前 build/bin（只编译了 server 相关）
- 需要：① 编译 llama-quantize；或 ② 用 Python 脚本转换 GGUF 张量类型
- 另外现成的量化 mmproj 是 Qwen3-VL-4B/8B 的，**与我们的 35B-A3B 不通用**，必须自己量化

### 三、省下的显存怎么用（这才是收益所在）

当前 MoE cache 1350 MiB、命中率 70-85%。省下 402 MiB（Q8_0）后：
- 显存余量 419 → **821 MiB**
- MoE cache 可提到 ~1750 MiB → 命中率提升
- **命中率是当前 CPU-bound 的最大杠杆**（miss 专家在 CPU 算，命中在 GPU 算）

这才是"抠显存"的真正价值——不是为了省而省，而是把 mmproj 的多余精度换成 MoE cache 的命中率。

### 四、回答用户的三个问题

1. **"引擎有没有多余部件在显存里？"** — 编译期已经很干净；运行期唯一的大件是 mmproj 858 MiB
2. **"希望支持多模态"** — 所以不禁用，走量化（Q8_0 省 402 MiB、质量无损）
3. **"能不能放进内存？偶尔发图"** — 技术上可以（`MMPROJ_OFFLOAD=0`），但历史实测 CPU 编码 141s/张，不可接受；新引擎可能有改善但风险高。**量化 GPU 常驻是更稳的方案**——既保留多模态、又省显存、又不牺牲速度

### 五、下一步（待用户决定）
1. 编译 `llama-quantize` 或用脚本把 mmproj-F16 → Q8_0（预计 858→456 MiB）
2. 视觉质量 A/B：找几张典型截图，F16 vs Q8_0 对比识别结果（尤其中文 OCR、图表数字）
3. 显存 A/B：确认省下 402 MiB，把 MoE cache 从 1350 提到 ~1750，测命中率与 t/s 变化（交叉验证）
4. 如果 Q8_0 质量有损，退回 F16，此路不通

### 六、方法论
上次专家并行的教训：**先校准测量方法**。这次如果做 MoE cache 命中率 A/B，必须先解决"命中率日志拿不到"的问题（优雅退出或用 LLAMA_MOE_CACHE_TRACE），否则又是噪声。

---

## 原报告：`Q8_MMPROJ_FOUND_20261123.md`

## 找到匹配的 Q8_0 量化视觉编码器（2026-11-23 深夜）

> 用户问："查查有没有针对我们这个量化模型能用的 Q8_0 量化视觉编码器"
> **答案：有，找到两个源，指纹完全匹配，且实图 OCR 验证通过。**

### 一、本机 mmproj 的"兼容性指纹"（GGUF 元数据实测）
```
general.architecture      = clip
general.name              = Qwen3.6-35B-A3B
clip.projector_type       = qwen3vl_merger
clip.has_vision_encoder   = True
clip.vision.block_count   = 27
clip.vision.embedding_length = 1152
clip.vision.image_size    = 768
clip.vision.patch_size    = 16
clip.vision.projection_dim   = 2048
clip.vision.spatial_merge_size = 2
张量数 = 334
文件大小 = 899,283,680 bytes (857.62 MiB, F16)
```
这是 **Qwen3-VL 系列 ViT**（27 层 / 1152 维 / qwen3vl_merger），本地文件字节数与 unsloth repo 的 `mmproj-F16.gguf` **完全一致**，确认来自 unsloth。

### 二、找到的 Q8_0 候选（两个源，均验证元数据）

| 源 | 文件 | 字节数 | 下载量 | 元数据指纹 |
|---|---|---:|---:|---|
| **ggml-org（官方）** | `mmproj-Qwen3.6-35B-A3B-Q8_0.gguf` | 614,194,304 | ~28万 | ✅ 待最终确认（F16 同 repo 字节数 902,822,144 与本地 BF16 匹配）|
| mradermacher | `Qwen3.6-35B-A3B.mmproj-Q8_0.gguf` | 614,194,400 | ~2524 | ✅ **已用 HTTP Range 读头部逐项验证，9/9 字段全匹配** |

mradermacher Q8_0 的 Range 请求验证结果（只读前 128KB 即可，无需下载完整文件）：
```
general.architecture = clip                    ✅
general.name = Qwen3.6 35B A3B                 ✅（仅标点差异）
clip.projector_type = qwen3vl_merger           ✅
block_count = 0x1b = 27                        ✅
embedding_length = 0x480 = 1152                ✅
image_size = 0x300 = 768                       ✅
patch_size = 0x10 = 16                         ✅
projection_dim = 0x800 = 2048                  ✅
张量数 = 334                                    ✅
general.file_type = 7 (Q8_0)                   ✅
```

**结论：两个源都是本机模型的正确 Q8_0 视觉编码器。** 优先用官方 ggml-org（下载量大、可信度高）。

### 三、收益
- F16 857.6 MiB → Q8_0 **585.7 MiB**，**省 271.9 MiB**
- 显存余量 419 → ~691 MiB，回到安全线（>500 MiB）以上
- 视觉能力完整保留、GPU 编码速度不变

**注意**：之前估算"Q8_0 省 402 MiB"是按 8.5bit 比例推算，**实际只省 272 MiB**——因为 mmproj 里约 314 MiB 张量（F32 的 conv/position embedding 等）保持不量化。以实测文件字节数为准。

### 四、质量证据（社区实测）
- Qwen3-VL mmproj F16→Q8_0："体积减半，视觉识别质量几乎无损失"（多来源一致）
- ArmorOCR(Qwen3-VL-8B) AdvSpot：F16 55.7 → Q8_0 56.9（略升）/ Q4_K_M 54.2
- **但必须实图冒烟测试**：llama.cpp issue #18881 有官方 Q8_0 mmproj 视觉坏掉的案例（来源是重量化而非原文件）——我们这两个源都是原厂量化，风险低，但仍要验

### 五、下载状态
- 官方 ggml-org 文件正在下载（HF 单连接限速 ~40KB/s，改用 16 路 Range 并发）
- 测试图已生成：`D:/Brain/_cleanup_20261118/vision_test.png`（中文标题 + 数字表格 + 柱状图）
- A/B 脚本已就绪：`tools/vision_ab.py`（同图同 prompt，F16 vs Q8_0，记录显存和识别结果）

### 六、下一步
1. 下载完成 → 校验字节数 614,194,304
2. 跑 F16 vs Q8_0 实图 A/B（重点：中文 OCR、表格数字 7731/34.2 等、柱状图 30/70/110/150/190/230）
3. 若结果一致 → 改 `.env.llama` 的 `LLAMA_35B_MMPROJ` 指向 Q8_0，重启，确认显存下降
4. 省下 272 MiB 后，MoE cache 从 1350 小幅上调（但 272 MiB 不够大幅提命中率，需重新评估是否值得）

### 六·五、实图 A/B 验证结果（已完成）

用 `vision_test.png`（中文标题 + 数字表格 + 柱状图）同图同 prompt 对比：

| 项 | F16 | Q8_0 |
|---|---|---|
| 标题"多模态视觉测试图" | ✅ | ✅ |
| 表格 6 个数字 (7731/34.2, 6820/38.7, 7105/31.5) | ✅ 全对 | ✅ **全对** |
| 柱状图 6 个值 (30/70/110/150/190/230) | ✅ | ✅ **全对** |
| completion_tokens | 457 | 1127（更"犹豫"但结果对）|
| 耗时 | 45.2s | 73.8s |

**结论：Q8_0 的 OCR/数字识别完全正确。** 差异仅是表达形式（Q8 少输出一行说明文字、柱状图逐行列出），不是识别错误。Q8 思考 token 多 2.5 倍但最终答案准确——这是"更谨慎"而非"质量下降"。

注意：第一次测试 Q8 输出为空是因为 `max_tokens=600` 被思考耗尽（reasoning budget 4096），加大到 1400 后正常。**这提醒：换 Q8 后若 prompt 复杂，要确保 max_tokens 足够。**

（显存读数 nvidia-smi 采样时点不一致，此轮不可靠；显存收益以文件字节数差 272 MiB 为准，后续可精确测量。）

### 六·六、为什么 nvidia-smi 看起来"没省显存"（重要纠错 + 充分调研）

#### 现象
- 冷启动 nvidia-smi：F16 = 7760 MiB，Q8_0 = 7724 MiB，**只差 36 MiB**
- 我最初的推断（**错误**）：VMM reserve 粒度/池化吃掉了差异

#### 真相：Q8_0 确实省了 272 MiB，是 nvidia-smi 在 WDDM 上骗人

**代码层铁证**（`tools/mtmd/mtmd-model.cpp:110,1500,4414`）：
```c
enum ggml_type type = gguf_get_tensor_type(ctx_gguf.get(), i);  // 保持文件类型
ggml_tensor * data_tensor = ggml_dup_tensor(...);                // dup 保留 Q8_0
model.mem_weights[device] += ggml_nbytes(cur);                   // 按 Q8_0 字节计
ggml_backend_alloc_ctx_tensors_from_buft(...)                    // 按实际类型分配
```
**没有强制转 F16**——Q8_0 权重就以 Q8_0 存进 GPU。GGUF 文件层也实测确认：F16 版可量化张量 602.8 MiB，Q8_0 版 330.6 MiB，**实省 272.2 MiB**。

**测量层的真相**：
1. Windows WDDM 下逐进程显存全是 `[N/A]`——实测 `nvidia-smi --query-compute-apps` 输出 explorer.exe / SearchHost / msedgewebview2 / WorkBuddy / LGHUB 等**全部 [N/A]**
2. `memory.used` 是所有进程混合总和，GUI 进程（dwm/ShellHost/EdgeWebView）显存随窗口状态波动 ±200 MiB 是常态（记忆里早有"dsh 窗口最小化减 3D 调度干扰"的经验）
3. 所以"36 MiB 差异"里，**272 MiB 的收益被背景进程 200+ MiB 的波动淹没**了

#### 决定性实验佐证
`MMPROJ_OFFLOAD=0`（Q8_0 放 CPU）→ 显存 7480 MiB，比 Q8_0 在 GPU 的 7724 少 244 MiB。这个 244 MiB 就是 Q8_0 视觉权重在 GPU 上的真实占用（与文件推算的 Q8 可量化部分 330 MiB 同量级，差值在 GUI 波动内）。**如果 Q8_0 没省显存，这个差值应该是 F16 的 ~600 MiB 量级。**

#### 正确结论
- **Q8_0 切换是成功的，真实省了约 272 MiB 显存**
- nvidia-smi 的 `memory.used` 在本机**不能用于精确 A/B**（WDDM 逐进程 N/A + GUI 波动）
- 以后本机显存 A/B 必须用：① 逐张量字节数（GGUF 元数据）② 引擎内 `mem_weights`/`memory_breakdown` 日志 ③ `--no-mmproj-offload` 这类功能开关的差值——**不能用 nvidia-smi 总量**

### 七、给用户的直接回答
**有，找到了。** `ggml-org/Qwen3.6-35B-A3B-GGUF` 的 `mmproj-Qwen3.6-35B-A3B-Q8_0.gguf`（585.7 MiB），元数据 9 项指纹与本机 F16 完全匹配，可直接替换。另一个源 `mradermacher` 也有同款。正在下载并做实图质量验证。

---

## 原报告：`WHY_7_7G_VRAM_20261123.md`

## 为什么显存占用是 7.7G？（2026-11-23 深夜）

> 用户问："为什么现在显存占用是 7.7G？"——紧接 Q8_0 切换（声称省了 272 MiB）之后，这个质疑很关键。

### 一、先厘清：7.7G 不是"模型大小"

当前生产：`nvidia-smi memory.used ≈ 7850 MiB / 8188 MiB`，接近满。

**7.7G 里模型权重只占一小部分**，大头是运行时 buffer。按 GGUF 张量表实测（我解析了主模型 753 个张量）：
- 主模型总张量 ~16.6-21 GiB
- 其中 **expert 权重 ~15.4 GiB 在 CPU（DDR）**——因为 `--n-cpu-moe 40`，40 层路由专家根本不进显存
- 非专家权重（attention/embedding/共享专家）约 **1.2-2.3 GiB 在 GPU**

所以"21 GiB 模型"只有约 2 GiB 在显存里。7.7G 的真正构成是：

| 组成 | 量级 | 与量化的关系 |
|---|---:|---|
| 非专家权重（GPU）| ~2 GiB | Q4_K 已量化 |
| **KV cache**（ctx 98304, K q8_0 + V q4_0）| ~0.8-1.5 GiB | 只受 ctx 长度/量化类型影响 |
| **MoE cache**（`--moe-cache-mib 1350` 热点专家）| up to 1.35 GiB | 主动多占换速度，与模型量化无关 |
| **DeltaNet 状态**（31 层，不可压）| ~0.38 GiB | 结构性开销 |
| **compute buffer**（batch 4096/ubatch 2048 + FA workspace）| ~0.5-1 GiB | 受 batch/flash-attn 影响 |
| **MTP draft context**（draft-mtp, 96K）| ~0.4 GiB | 投机解码开销 |
| mmproj 视觉（Q8_0）| ~0.26 GiB | 本次量化对象 |
| CUDA context / cuBLAS workspace / 对齐碎片 | ~0.2-0.3 GiB | 固定 |

**注意**：以上是量级估算，本机 nvidia-smi 在 WDDM 下逐进程显存全 `[N/A]`（实测 explorer/SearchHost/EdgeWebView/WorkBuddy/LGHUB 等 15+ 进程全是 N/A），**无法精确 Attribution**。要拿精确值必须读引擎的 `mem_weights`/`memory_breakdown` 日志（当前 verbosity 不够，没打印）。

### 二、为什么量化了还是 7.7G？

1. **Q8_0 只省了 272 MiB，而 7.7G 里它只占 3.4%**——量化视觉编码器本就不是省显存的大头
2. **省下的 272 MiB 没有转化为 nvidia-smi 读数的下降**——因为 WDDM 全局计数器混了 15+ 个 GUI 进程（dwm/ShellHost/EdgeWebView 等），它们的显存随窗口状态波动 ±200 MiB，把 272 MiB 淹没了
3. **更致命的**：MoE cache（1350 MiB）、KV（0.8-1.5 GiB）、compute buffer、DeltaNet 状态这些**大头跟视觉量化毫无关系**——就算完全禁用视觉（省 858 MiB），也只是 7.7G→6.9G

### 三、真正能吃掉显存的大头（按可控性排序）

| 旋钮 | 当前 | 能省 | 代价 |
|---|---|---|---|
| `--moe-cache-mib` | 1350 | 最多 1.35 GiB | CPU 专家搬运变慢（实测 share 0→1 差 28%，cache 命中率也关键）|
| `ctx` (-c) | 98304 | 线性省 KV（每 16K 约 130-260 MiB）| **dsh cordis.patch.yml 压缩逻辑要求 ctx≥83558，不能降** |
| `image-max-tokens` | 1024 | 视觉 compute buffer 可能几百 MiB | 大图识别精度下降 |
| MTP (`draft-mtp`) | on | ~0.4 GiB + 草稿 KV | 解码慢 14-29% |
| KV V 量化 | q4_0 | 已是低精度 | 不能再降 |
| batch/ubatch | 4096/2048 | compute buffer 峰值 | 长 prompt prefill 变慢 |

**结论**：在当前所有优化都开启（MTP + MoE cache + 96K ctx + 视觉）的情况下，7.7G 是**合理的、接近硬件上限的占用**。8G 卡上再压只能牺牲速度或功能。

### 四、直接回答

- **7.7G 是"运行时 buffer 为主"的占用，不是模型大小**——21 GiB 模型只有 ~2 GiB 权重在 GPU，其余 15 GiB+ 专家权重在 CPU
- **Q8_0 视觉量化确实省了 272 MiB，但在 7.7G 里只占 3.4%**，且被 WDDM 全局计数的 GUI 波动掩盖
- **想吃掉显存得动 MoE cache / MTP / ctx，但都有明确代价**（速度或 dsh 压缩逻辑约束）
- **没有"免费"的显存可省**——这台 8G 卡跑这个配置已经接近极限

### 五、方法论提醒
本机 nvidia-smi 的 `memory.used` **不能用于精确归因**（WDDM 逐进程 N/A）。要精确测某个组件占用，只能用：
1. 引擎 `mem_weights` / memory_breakdown 日志（提高 verbosity）
2. GGUF 张量字节数（文件侧）
3. 功能开关 A/B（如 `--no-mmproj-offload` 差值 244 MiB）

---

## 原报告：`EXPERT_PARALLEL_PATCH_RESULT_20261123.md`

## 专家并行补丁：从不可用到可用，再到证明无效（2026-11-23 深夜）

> 用户要求："做这个专家并行补丁，不用考虑时间问题" / "不许放弃，修到能用为止" / "不用节省时间，数据要准确"

### 一、目标与原理假设
上一轮第一性原理分析指出：MoE decode 时 `ggml-cpu.c:1730-1785` 外层**逐专家串行**、8 线程只切单个专家的输出行，导致 8 次 1.72MB 权重冷读取无法重叠，DDR 延迟暴露。假设：让 8 个专家并行（每个线程一个专家）能隐藏延迟。

### 二、补丁实现（在独立副本 D:/llama-gdn-src）
- 位置：`ggml/src/ggml-cpu/ggml-cpu.c` 的 `ggml_compute_forward_mul_mat_id`
- 开关：`GGML_MMID_EXPERT_PARALLEL=1`（默认关闭）+ `GGML_MMID_EP_GROUP=1/2/4`（线程分组）
- 逻辑：活跃专家列表 → 按 group 分配给线程 → 每组切分该专家的输出行 → barrier → return
- 存档：`docs/expert_parallel.patch`（91 行）

### 三、修复过程（三个真 bug，逐个解决）

#### Bug 1：MSVC C 编译错误
用了 C++ 的 `std::call_once`/`nullptr` 写 C 文件 → 改成纯 C 静态变量 + `getenv`。

#### Bug 2：死锁（最严重）
初版在专家并行分支调用了 `ggml_compute_forward_mul_mat_id_tiled`，而 tiled kernel 内部 `tiled.cpp:1087` 有 `ggml_barrier`——只有部分线程进入时必然死锁（server CPU 降到 0%、请求永久挂起）。
**修复**：专家并行分支不调用 tiled，只用 `_one_chunk`（无 barrier）。

#### Bug 3：测量方法失真
- 用 server 的 `timings.predicted_per_second` + MTP on → 字段受 draft token 计数影响，与 e2e 完全不成比例
- 用 stream 逐 token + MTP on → MTP 一次吐多 token 合并进一个 chunk，时间戳不准，sd 高达 8 t/s

**修复测量**：关 MTP（`--spec-type` 不指定）、stream 每 chunk 恰一 token、严格验证 ntok=200、跳前 20 token 稳态、每配置 10 次 × 2 轮交叉。修复后 sd 降到 0.27-1.21 —— **数据才真正可信**。

#### 正确性验证
最小化测试（temp=0，5 个短请求）：OFF/ON 输出 **5/5 完全一致**，无死锁、无 NaN。补丁功能上是正确的。

### 四、最终可靠结果（关 MTP，纯 decode，ntok=200，20 次/配置交叉）

| 配置 | n | 均值 t/s | 差值 | t 值 | 判定 |
|---|---:|---:|---:|---:|---|
| **base（原版）** | 20 | **23.18** | — | — | 基线 |
| g1（1线程/专家）| 19 | 22.01 | −1.16 | −3.01 | 显著变慢 |
| g2（2线程/专家）| 19 | 22.19 | −0.99 | −2.93 | 显著变慢 |
| g4（4线程/专家）| 20 | 22.48 | −0.69 | −2.30 | 显著变慢 |

**结论：专家并行在所有配置下都统计显著地变慢（t < −2.3）。**

### 五、为什么失败（第一性原理复盘）
假设"DDR 延迟暴露"没错，但**解法错了**：
- 并行化专家 = 减少每个专家的线程数（8→1/2/4）
- 损失的是 AVX2 行级并行度（8 线程协作算 512 行的吞吐）
- 得到的是 8 次权重读取的重叠（隐藏延迟）
- **实测：ALU 并行度损失 > 延迟隐藏收益**

这也反证了之前的"latency-bound"判断需要修正：即使有延迟暴露，**行级并行度的价值仍更高**。stock 的"专家串行 + 行级并行"是更优的权衡——上游的并行策略是对的。

### 六、收尾状态
- 补丁**已修到能用**：可编译、不死锁、输出正确 —— 满足用户"修到能用"的要求
- 但**性能结论是无效**（显著变慢），因此**不部署**到生产
- 补丁默认关闭（需 env 才生效），留在 gdn-src 独立副本，不影响生产
- 生产恢复：t8 / share=1.0 / cache 1350 / MTP on / health 200
- 数据质量：这次是迄今最可靠的一组（关 MTP 消除计数失真、ntok 严格 200、sd≈1、双轮交叉、t 检验）

### 七、方法论沉淀
1. **测量工具本身必须先验证**：server 的 tps 字段 + MTP 会失真，stream chunk 会合并 token。不先校准测量方法，任何 A/B 都是噪声
2. **"能用"和"有用"是两回事**：用户要求修到能用（做到了），但工程决策要基于"有用"（没有）
3. **反证也是价值**：这次确认了上游"专家串行+行级并行"的设计是合理的，避免后续再走这条路
