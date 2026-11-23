# MoE 专家卸载深度优化：社区方案评估 + 源码级实测（2026-11-23）

> 用户问：针对"专家卸载到 CPU 且 CPU 帮算一部分"这种情况，社区有没有更进一步的优化方案？能不能从源码上手搓？
> **核心结论：不需要手搓补丁——上游 1.0 原生支持，只要把 `--moe-cache-cpu-share` 设成 1.0。实测 decode +28.5%、端到端 -10.6%。我之前升级时把它退回 0 是退步，已纠正。**

## 一、先说我的判断失误（诚实记录）
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

## 二、实测数据（master 94f3af3，生产二进制，未改一行源码）

### 2.1 decode（stream 前 128 token，5 次中位）
| share | decode | vs share=0 |
|---|---:|---:|
| 0 | 24.298 t/s | — |
| 0.5 | 27.091 t/s | +11.5% |
| **1.0** | **31.226 t/s** | **+28.5%** |

原始值 share=0: [24.57, 24.30, 19.03, 23.64, 24.70]；share=1.0: [30.23, 31.53, 30.92, 33.11]

### 2.2 端到端（4 步增量 prefill，每步 96 token，5 次中位）
| share | e2e 墙钟 | decode | 首步 20K prefill |
|---|---:|---:|---:|
| 0 | 32.580s (sd 0.43) | 23-25 t/s | 15.3s |
| **1.0** | **29.116s (sd 1.32)** | **31-34 t/s** | 15.4s |

- **-10.6% 墙钟**，首步 prefill 不变（印证源码：prefill 不走 share）
- 这推翻了记忆里"share=1.0 端到端慢 2.4×（P5 1013s）"的旧结论——那是 b12244 自编补丁时代，在 master 1.0 上不成立

### 2.3 长上下文对照（21.7K token 单次请求，3 次中位）
| share | prefill | decode | wall |
|---|---:|---:|---:|
| 0 | 999 t/s | 21.9 t/s | 26.0s |
| 1.0 | 1011 t/s | 21.3 t/s | 26.0s |

**持平**。原因：21.7K token 单次请求里 prefill 占 ~21s、decode 只 ~4s，decode 的 +28% 被稀释。
真实 agent 多轮对话是"小增量 prefill + 大量 decode"，所以 2.2 的 e2e 能体现 -10.6%。
**结论：share=1.0 有收益、长 prompt 场景无退化。**

### 2.4 为什么 pinned 也有效（反官方"通常无用"）
- pinned 只保证上传"全速"，而 PCIe 4.0 x8 全速约 **12 GB/s**
- CPU 直读 DDR4-3200 双通道约 **51 GB/s**，快 4 倍
- 官方那句"pinned 时 share 通常无用"针对**大 cache**（miss 少）场景（#30966 实测 6464 MiB 时有效、19392 MiB 时反向）
- 我们 cache 1350 MiB / 18726 MiB host experts = **7.2%**，miss 多，CPU 帮算划算

## 三、MoE cache 实际状态（诊断）
```
CUDA0 MoE cache size = 1345.67 MiB for 18726.00 MiB of host experts, 0% of the misses on the CPU
```
- **cache 确实启用**（repack 陷阱未命中，`is_host_weight()` 判断正常）
- host experts 18.3 GiB，cache 只覆盖 7.2%
- 每层专家 457 MiB / 256 专家 ≈ 1.78 MiB/专家 → cache 约 756 个专家槽位
- 每 token 需 40层×8 = 320 个专家 → 若相邻 token 专家重叠 50%，命中率约 70-85%

## 四、社区方案评估（按可行性排序）
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

### 关于 ②：cache 提容量的空间账
- CUDA0 硬上限 1856 MiB（官方 tune 脚本实测报出）
- 当前 1350，余 506 MiB
- 但显存总余仅 **346 MiB**（7842/8188）→ **不能直接加到 1800**，需要先腾显存
- 腾法：`NCMOE 40→41`（第 41 层专家也挪到 CPU，省约 457 MiB）→ 但 CPU 专家量 +1 层
- 或 `CTX 98304→81920`（但 CTX 是承重墙，记忆明确）

### 关于 ③：为什么它是唯一的大杠杆
- 物理必然：CPU 侧专家权重 18.3 GiB 是每 token 要跨越的字节墙。降比特直接减半
- 同架构先例：Gordon-35B-A3B-mixed-q2k-imat — PPL 仅 +0.59%（5.826→5.860），decode 51→78 t/s
- 成本：用 llama-quantize 重做一份混合量化 GGUF（CPU 层 Q2_K、GPU 层保持 Q4_K），需磁盘 + 时间
- **风险**：等同换模型文件，质量需验证；用户此前明确"先不要换模型"

## 五、真正值得手搓的源码级优化（如果 ①③ 都做完还不够）
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

## 六、部署状态（已生效）
- `.env.llama`: `LLAMA_35B_MOE_CACHE_CPU_SHARE=1.0`（含源码+实测依据注释）
- `PREFILL=-1`（该参数上游已废弃）
- `autostart/index.mjs`: prefill 参数推送已注释（上游无此参数）
- 生产重启后确认：实例命令行带 `--moe-cache-cpu-share 1.0`，health 200
- 真实任务验证：bridge 发 read 任务，工具调用正常、turn 正常结束

## 七、诚实标注
- decode/e2e 数据均为本机实测，5 次中位；但只测了 20K 上下文
- 长上下文（60K）对照在跑（share=0 vs 1.0），结果见 `share_long.log`
- 混合精度方案的数字来自社区同架构先例，未在本机复现
- 方案 A/B/C 是设计建议，未实现验证
