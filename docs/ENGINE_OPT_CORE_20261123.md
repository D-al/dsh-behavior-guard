# 引擎优化核心：卸载/缓存/精度（2026-11-23）

> MoE 卸载优化、缓存与精度、混合精度专家质量

> 本卷合并 3 份原报告（2026-11-25 整理）。

## 本卷目录

- `MOE_OFFLOAD_OPTIMIZATION_20261123.md`
- `CACHE_AND_MB256_AND_PRECISION_20261123.md`
- `MIXED_PRECISION_EXPERTS_QUALITY_20261123.md`

---

## 原报告：`MOE_OFFLOAD_OPTIMIZATION_20261123.md`

## MoE 专家卸载深度优化：社区方案评估 + 源码级实测（2026-11-23）

> 用户问：针对"专家卸载到 CPU 且 CPU 帮算一部分"这种情况，社区有没有更进一步的优化方案？能不能从源码上手搓？
> **核心结论：不需要手搓补丁——上游 1.0 原生支持，只要把 `--moe-cache-cpu-share` 设成 1.0。实测 decode +28.5%、端到端 -10.6%。我之前升级时把它退回 0 是退步，已纠正。**

### 一、先说我的判断失误（诚实记录）
| 阶段 | 我的判断 | 实际情况 |
|---|---|---|
| 升级部署时 | "上游 1.0 没了 prefill 分离参数，留 share=1.0 会变全局 1.0 毒害 prefill"，故退回 0 | **错**。源码证明 share 天生只作用于 ≤32 token 的批，prefill 根本不经过它 |
| 本轮初始 | "需要一个 batch gate 补丁，让 share 只在小批生效" | **多余**。上游已有 `max_batch=32` 的天然门槛 |
| 最终 | 直接设 share=1.0 | **对**，实测有效 |

关键源码证据（`src/llama-moe-cache.cpp:369, 697`）：
```cpp
static constexpr int64_t max_batch = 32;
// large batches use most experts of a layer, so they gain little from the cache
// and would evict the experts used in generation
if (n_tokens == 0 || n_tokens > max_batch || ...) return nullptr;
```

### 二、实测数据（master 94f3af3，生产二进制，未改一行源码）

#### 2.1 decode（stream 前 128 token，5 次中位）
| share | decode | vs share=0 |
|---|---:|---:|
| 0 | 24.298 t/s | — |
| 0.5 | 27.091 t/s | +11.5% |
| **1.0** | **31.226 t/s** | **+28.5%** |

原始值 share=0: [24.57, 24.30, 19.03, 23.64, 24.70]；share=1.0: [30.23, 31.53, 30.92, 33.11]

#### 2.2 端到端（4 步增量 prefill，每步 96 token，5 次中位）
| share | e2e 墙钟 | decode | 首步 20K prefill |
|---|---:|---:|---:|
| 0 | 32.580s (sd 0.43) | 23-25 t/s | 15.3s |
| **1.0** | **29.116s (sd 1.32)** | **31-34 t/s** | 15.4s |

- **-10.6% 墙钟**，首步 prefill 不变（印证源码：prefill 不走 share）
- 这推翻了记忆里"share=1.0 端到端慢 2.4×（P5 1013s）"的旧结论——那是 b12244 自编补丁时代，在 master 1.0 上不成立

#### 2.3 长上下文对照（21.7K token 单次请求，3 次中位）
| share | prefill | decode | wall |
|---|---:|---:|---:|
| 0 | 999 t/s | 21.9 t/s | 26.0s |
| 1.0 | 1011 t/s | 21.3 t/s | 26.0s |

**持平**。原因：21.7K token 单次请求里 prefill 占 ~21s、decode 只 ~4s，decode 的 +28% 被稀释。
真实 agent 多轮对话是"小增量 prefill + 大量 decode"，所以 2.2 的 e2e 能体现 -10.6%。
**结论：share=1.0 有收益、长 prompt 场景无退化。**

#### 2.4 为什么 pinned 也有效（反官方"通常无用"）
- pinned 只保证上传"全速"，而 PCIe 4.0 x8 全速约 **12 GB/s**
- CPU 直读 DDR4-3200 双通道约 **51 GB/s**，快 4 倍
- 官方那句"pinned 时 share 通常无用"针对**大 cache**（miss 少）场景（#30966 实测 6464 MiB 时有效、19392 MiB 时反向）
- 我们 cache 1350 MiB / 18726 MiB host experts = **7.2%**，miss 多，CPU 帮算划算

### 三、MoE cache 实际状态（诊断）
```
CUDA0 MoE cache size = 1345.67 MiB for 18726.00 MiB of host experts, 0% of the misses on the CPU
```
- **cache 确实启用**（repack 陷阱未命中，`is_host_weight()` 判断正常）
- host experts 18.3 GiB，cache 只覆盖 7.2%
- 每层专家 457 MiB / 256 专家 ≈ 1.78 MiB/专家 → cache 约 756 个专家槽位
- 每 token 需 40层×8 = 320 个专家 → 若相邻 token 专家重叠 50%，命中率约 70-85%

### 四、社区方案评估（按可行性排序）
| 方案 | 出处 | 实测收益 | 对我们可行性 |
|---|---|---|---|
| **① MoE cache + cpu-share=1.0** | 上游 #30966/#31233/#31888，官方 docs/moe-cache.md | decode +28.5%，e2e -10.6% | ✅ **已部署**，0 成本 |
| **② cache 容量 1350→1800** | 官方 tune 脚本 + 显存余量 | 预计 +3-8%（miss 减少） | ✅ 低风险，需挤显存 |
| **③ 混合精度专家（CPU 侧降比特）** | Gordon-35B-A3B-mixed-q2k-imat 先例 | **PPL +0.59%，decode 78 vs 51 t/s (+53%)** | ⚠️ 需重新量化（=换模型文件），用户尚未同意 |
| ④ MTP draft-n-max 5→3 | 减少验证批专家读取 | 未知，可能 -5% decode 换更少 miss | ⚠️ 可能损失投机收益 |
| ⑤ 专家预取（prefetch） | ik `ggml-moe-prefetch.cpp`；上游无等价 | 作者宣称有效 | ❌ 每层独立 router，无法跨层预知；工作量高 |
| ⑥ 异步传输/计算重叠 | 上游 backend scheduler | 部分已在 1.0 中 | ❌ 已生效，无额外空间 |
| ⑦ GPU-resident LRU | #29949 issue（未开 PR） | 作者自测 1.5× | ❌ 短期不进主线，移植风险高 |
| ⑧ KTransformers 式 expert offload | 其他项目 | 强 | ❌ 架构差异大，等于重写 |

#### 关于 ②：cache 提容量的空间账
- CUDA0 硬上限 1856 MiB（官方 tune 脚本实测报出）
- 当前 1350，余 506 MiB
- 但显存总余仅 **346 MiB**（7842/8188）→ **不能直接加到 1800**，需要先腾显存
- 腾法：`NCMOE 40→41`（第 41 层专家也挪到 CPU，省约 457 MiB）→ 但 CPU 专家量 +1 层
- 或 `CTX 98304→81920`（但 CTX 是承重墙，记忆明确）

#### 关于 ③：为什么它是唯一的大杠杆
- 物理必然：CPU 侧专家权重 18.3 GiB 是每 token 要跨越的字节墙。降比特直接减半
- 同架构先例：Gordon-35B-A3B-mixed-q2k-imat — PPL 仅 +0.59%（5.826→5.860），decode 51→78 t/s
- 成本：用 llama-quantize 重做一份混合量化 GGUF（CPU 层 Q2_K、GPU 层保持 Q4_K），需磁盘 + 时间
- **风险**：等同换模型文件，质量需验证；用户此前明确"先不要换模型"

### 五、真正值得手搓的源码级优化（如果 ①③ 都做完还不够）
按 ROI 排序，都基于我们已确认的瓶颈（DDR 字节 + PCIe 字节）：

**A. 让 share 覆盖中等批（32-256 token）**
- 当前 `max_batch=32` 一刀切。HARNESS 的多步增量 prefill 常在 100-2000 token
- 手搓：把 max_batch 提到 256，并让 share 随批大小衰减（`share * 32/n_tokens`）
- 风险：中等批 CPU 算不过来会拖慢。需实测
- 位置：`src/llama-moe-cache.cpp:369`

**B. cache 热专家固定（pin top-K）**
- 当前 LRFU/ClassLRU 全动态。可以统计高频专家，固定常驻，只对长尾做 LRU
- 收益：提高命中率。风险：实现复杂

**C. MTP 与 share 协同调优**
- MTP 验证批（6 token）走 share，CPU 算 6×8 专家。如果 CPU 成为瓶颈，可对 MTP 批用较低 share
- 位置：`share_q` 计算处按 n_tokens 细分

**D. 量化层面：只给 CPU 层专家 Q2/Q3**
- 见方案 ③，不是传统"源码补丁"，是量化配方

### 六、部署状态（已生效）
- `.env.llama`: `LLAMA_35B_MOE_CACHE_CPU_SHARE=1.0`（含源码+实测依据注释）
- `PREFILL=-1`（该参数上游已废弃）
- `autostart/index.mjs`: prefill 参数推送已注释（上游无此参数）
- 生产重启后确认：实例命令行带 `--moe-cache-cpu-share 1.0`，health 200
- 真实任务验证：bridge 发 read 任务，工具调用正常、turn 正常结束

### 七、诚实标注
- decode/e2e 数据均为本机实测，5 次中位；但只测了 20K 上下文
- 长上下文（60K）对照在跑（share=0 vs 1.0），结果见 `share_long.log`
- 混合精度方案的数字来自社区同架构先例，未在本机复现
- 方案 A/B/C 是设计建议，未实现验证

---

## 原报告：`CACHE_AND_MB256_AND_PRECISION_20261123.md`

## 方案1/方案2 实测 + 混合精度调研（2026-11-23 下午）

> 用户三项要求：① 试方案1（cache 加大）② 试 max_batch 32→256 + share 随批衰减 ③ 充分调研混合精度质量

### 一、方案1：cache 1350→1800（配 NCMOE 40→41 腾显存）

#### 1.1 机制验证：成功且比预想好
| 配置 | VRAM used | cache 实际值 | host experts |
|---|---:|---:|---:|
| A: NCMOE 40 / cache 1350 | 7837 MiB | 1345.67 MiB | 18726 MiB |
| C1: NCMOE 41 / cache 1700 | **7816 MiB** | **1696.40 MiB** | 19190 MiB |
| C2: NCMOE 41 / cache 1600 | 7853 MiB | ~1596 MiB | 19190 MiB |

- **cache=1800 装不下**：needs 7185 MiB > free 7106 MiB，实例直接退出（status 0）
- **NCMOE 41 净省 11 MiB 显存**：把最后一层专家（+464 MiB host）挪到 CPU，腾出的显存刚好够 cache +350 MiB，总占用反降 21 MiB
- **所以 1700 是可行上限**（不是 1800）

#### 1.2 性能：噪声淹没了差异（诚实记录）
| 配置 | decode (5次中位) | e2e (3次中位) |
|---|---:|---:|
| A: 40/1350 | 29.639 (sd 3.10) | 29.327 (sd **17.36**，含 59.03s 异常) |
| C1: 41/1700 | 31.456 (sd 1.37) | **35.208** (sd 0.66) |
| C2: 41/1600 | 25.722 (sd 2.23) | 28.497 (sd 0.92) |

**三组数据互相矛盾**：C1 decode 最快但 e2e 最慢；C2 decode 最慢但 e2e 最快；A 有一个 59s 异常值。
- 配置间差异（decode 25.7~31.5，e2e 28.5~35.2，约 ±20%）与测量噪声同量级
- 违反记忆铁律"单次 ±10%，判优至少 2 次"——这里波动远超 10%

**可能原因**：① share=1.0 时 CPU 帮算，CPU 调度受其它进程干扰大 ② 笔记本功耗/温度墙 ③ 每轮 e2e 的 cache 起始状态不同 ④ 测试间隔太短，热态未稳定

**结论：方案1 机制可行（cache 确实能加到 1696 MiB 且总显存不涨），但收益无法用当前测量条件证明。不建议在噪声未排除前切换。**

#### 1.3 尝试过的更可靠判据（都失败）
- **命中率日志**：`log_stats()` 只在 `~impl()` 析构时打印，`terminate()` 强杀不触发；`CTRL_BREAK_EVENT` 对 llama-server 无效
- **官方 tune 脚本**：按单模型模式算显存（`room = free - used - 512`），我们 21GB 模型单模型模式 room<0，直接退"no room for cache larger than 512"

### 二、方案2：max_batch 32→256 + share 随批衰减

#### 2.1 源码分析（预期收益有限，甚至负面）
改了两处（`src/llama-moe-cache.cpp`）：
```cpp
static constexpr int64_t max_batch = 256;   // was 32

// share 随批衰减
const int64_t n_tok_share = sel->src[0]->ne[1];
uint32_t share_q = 0;
if (has_cpu && g.lru.n_filled == g.lru.n_slots && n_tok_share > 0 && n_tok_share <= max_batch) {
    share_q = n_tok_share <= 32 ? cpu_share_q
             : (uint32_t)((uint64_t)cpu_share_q * 32 / (uint64_t)n_tok_share);
}
```

**三道硬约束让预期收益很小**：
1. **n_slots 门槛**：`std::min(n_tokens*n_expert_used, slot_map->ne[1]) > n_slots` 仍会 return nullptr。我们 n_slots≈754，每 token 8 专家 → 实际只能到 **~94 token**，改 256 大部分范围进不去
2. **n_zero=8 限制**：每层最多 8 个专家能交 CPU 算（`if (z >= n_zero) skip`）。中等批 miss 几百个，只有 8 个能分流，衰减后的 share 基本无效果
3. **上游警告**：源码注释明写 "large batches ... would evict the experts used in generation"——中等批进 cache 会挤掉 decode 的热专家，**可能反而拖慢 decode**

#### 2.2 实测结果（已完成）

工作负载特意用 **60 token 增量**（在 patch 有效窗口 33..94 内），20K 首轮 + 60token×3，5 次中位：

| 配置 | e2e | decode |
|---|---:|---:|
| baseline (max_batch=32) | **26.604s** (sd 0.433) | 31.1 t/s |
| patch (max_batch=256) | 26.727s (sd 0.737) | 32.9 t/s |

**e2e 持平**（+0.46%，在噪声内），decode 的 +5.8% 未体现在端到端。

- **结论：补丁无实质收益，不采用。** 与源码分析的三道约束完全吻合
- 编译方式：在已完整编译的 build-gdn 上增量重编（只 7 个目标，1 分钟），避免全量 CUDA 重编（该环境下被 WorkBuddy 抢 CPU，速度只有正常 1/15）

### 三、混合精度专家：质量调研（已完成，详见 MIXED_PRECISION_EXPERTS_QUALITY_20261123.md）

**一句话结论：Q3_K 是安全区间，Q2_K 不可取，且 PPL 在 agent 任务上会失明。**

关键证据：
- 我们当前 UD-Q4_K_XL 在量化谱系里已是甜点（PPL 6.735，+0.22%）
- 官方 Unsloth 自己发布 UD-Q3_K_M（全 3-bit，PPL +2.4%）→ 3-bit 是工程可接受档
- **致命反例**：`kyumly/Qwen3.6-35B-A3B-MoE-expert-IQ2` 结构与我们要做的完全相同（只降专家），2.25bit → **LiveCodeBench −26 分、GPQA −13.6 分**
- PPL +7.7% 是质量拐点（APEX I-Mini 的 IQ2_S 中间层）

推荐配方（若做）：只降 40 层 `ffn_{up,gate,down}_exps` 到 **Q3_K**，attention/shared/output 保 Q4+/Q6，必须用 imatrix。预计专家 18.3→13.7 GiB（−25%），decode +23~29%，端到端 −5~8%。

**两个比量化更优先的发现**：
1. **MTP 可能让 function-calling 掉 40%**（protolabs 实测）——我们只测过 MTP 的 decode +8%，**从未测过工具调用准确率**。建议先做这个 A/B
2. **KV cache q4_0 可能让 DeltaNet 状态失稳**（DuoNeural 报告）——我们有 31 层 DeltaNet 且 `--cache-type-v q4_0`，建议试 q8_0（显存代价小）

### 四、下一步建议（按 ROI）
1. **先做 MTP 工具调用准确率 A/B**（零成本，可能发现 MTP 在伤害 agent 质量）
2. **试 KV q4_0→q8_0**（零成本，几乎无质量风险）
3. 方案1 若要确认，需要**严格测试条件**：关闭 WorkBuddy/frame_limiter、固定 seed、交叉顺序、每配置 10+ 次
4. 方案2 等编译测试结果
5. 混合精度 Q3_K 需重做 GGUF（=换模型文件），需用户决策

---

## 原报告：`MIXED_PRECISION_EXPERTS_QUALITY_20261123.md`

## 混合精度专家：质量代价充分调研（2026-11-23）

> 问题：把 CPU 侧 40 层专家降比特（Q4_K → Q3_K/Q2_K），质量与当前模型比差多少？
> **结论：Q3_K 是安全区间（PPL +2~2.4%，官方动态量化自己就在用），Q2_K 不可取（PPL +7% 拐点，同结构实测编码能力 −26）。但更重要的是：PPL 在 agent 任务上会失明，验收必须用工具调用准确率。**

### 一、当前模型在量化谱系里的位置（第三方实测，APEX 团队）
| 量化档 | BPW | PPL | ΔPPL | HellaSwag |
|---|---:|---:|---:|---:|
| UD-Q4_K_XL（**我们现在的**） | 4.75 | **6.735** | +0.22% | 82.3% |
| APEX I-Compact（Q4 边缘/Q3 中间） | 4.5 | 6.857 | +2.0% | 79.7% |
| UD-Q3_K_M（全 3-bit） | 3.85 | 6.883 | +2.4% | 78.7% |
| APEX I-Mini（中间层 IQ2_S） | 3.5 | 7.238 | **+7.7%** ← 质量拐点 | 74.2% |

**关键洞察**：我们已经在"量化甜点"上（+0.22%）。放弃 4.75→4.5 只差 0.25 bpw，却要付 +2% PPL。**降到 3.85 bpw 是 +2.4% PPL——这是官方 Unsloth 自己都在发布的档位（UD-Q3_K_M），说明是可接受的工程选择。**

### 二、致命警示：同结构"只降专家"的实测反例
社区 `kyumly/Qwen3.6-35B-A3B-MoE-expert-IQ2` 与我们要做的**结构完全相同**（只降专家，attention/shared/embed/output 保 BF16）：
- 2.25-bit 专家 → **LiveCodeBench −26 分、GPQA −13.6 分**
- 结论：**Q2 级专家在编码/推理任务上会断崖**

对比 Gordon-35B-A3B-mixed-q2k-imat（宣称 PPL 仅 +0.59%，decode 51→78）：
- 该 repo **几乎无独立验证**（2 likes / 31 downloads），README 里正则自相矛盾
- 其 PPL +0.59% 与 kyumly 的编码 −26 分**并不矛盾**——PPL 对结构化任务失明

### 三、为什么不能只看 PPL
- arxiv 实测：tool calling 中"**是否该调用工具**"比"调哪个工具"更脆弱（量化最先崩的是决策边界，不是格式）
- Qwen3-27B pilot：Q4 无损，**Q3 开始掉 parallel_multiple 4pp**，Q2 掉更狠
- 合同抽取任务：**连 2-bit 都几乎无损** → 说明**任务类型决定安全线**

### 四、推荐配方（如果要做）
只降 CPU 侧 40 层的 `ffn_{up,gate,down}_exps` 到 **Q3_K**（不是 Q2），其余保持：
```bash
## 示例（需按实际张量名调整 regex）
llama-quantize --imatrix imatrix.gguf \
  --tensor-type "blk\.(0|1|2|...|39)\.ffn_(up|gate|down)_exps=Q3_K" \
  --output Qwen3.6-35B-A3B-mixed-q3k.gguf \
  原模型.gguf Q4_K_M
```
- 收益：40 层专家 18.3 GiB → 约 13.7 GiB（−25%），DDR 读和 PCIe 传输同步下降，**预计 decode +23~29%**
- 端到端：预计 **−5~8%**（因为 prefill 占比大，稀释收益）
- 必须用 imatrix；必须保留 attention / shared_expert / output 在 Q4+/Q6

### 五、两个比量化更值得先做的事（调研附带发现）
1. **MTP 可能让 function-calling 掉 40%**（protolabs 在自己的部署里测到 agentic function-calling 准确率下降约 40%，疑似模型在 MTP 生成的 token 上训练不足）
   - 我们有 `MTP on` 的 A/B 数据（decode +8%），但**没有做过工具调用准确率的 A/B**
   - **建议先做这个**：同一组工具调用任务，MTP on vs off 比准确率。如果真掉 40%，那 MTP 的 +8% decode 完全不值得
2. **KV cache q4_0 可能已经在偷质量**
   - DuoNeural 报告：KV q4 会破坏 Gated DeltaNet 的 SSM 状态（DeltaNet state 存在 KV cache 里，低位量化会累积漂移）
   - 我们正是 `--cache-type-v q4_0` + 31 层 DeltaNet！
   - **建议试 `q8_0`**：KV 从 22.5 MiB 增到 45 MiB（8192 cells），显存代价小，可能提升长上下文质量

### 六、结论（对 agent 场景）
| 方案 | 质量风险 | 建议 |
|---|---|---|
| 保持 Q4_K_XL（现状） | 无 | ✅ 当前最优 |
| 只降专家到 **Q3_K** | PPL +2.4%，工具调用可能 −2~4pp | ⚠️ 可试，但必须用 agent 任务验收 |
| 只降专家到 Q2_K | PPL +7.7%，编码 −26 分 | ❌ 不要 |
| KV q4_0 → q8_0 | 风险降低 | ✅ **建议先试这个**（几乎零质量风险，显存代价小） |

**验收铁律**：不能用 PPL 或 decode t/s 验收量化。必须用我们真实的 agent 任务（工具调用准确率、多轮任务完成率）。
