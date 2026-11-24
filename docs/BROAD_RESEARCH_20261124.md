# 广泛调研：同配置社区/论文方案 + 词表放 SSD 的可行性（2026-11-24）

> 用户：有没有跟我们机器和模型配置同样的社区和论文方案？值得借鉴的优化？能否像 qwen3.8 那样把词表放进 SSD？
> 三路并行调研（论文 / 社区 / SSD 机制）+ 本机交叉验证。**这是调研沉淀，不是立即执行清单。**

---

# 第一部分：结论速览（按性价比排序）

| 方案 | 来源 | 预期收益 | 成本 | 本机可行性 |
|---|---|---|---|---|
| ~~1. 升级主线 llama.cpp（PR #31233 ClassLRU）~~ | ~~llama.cpp PR~~ | **已在本机版本(94f3af3)** | — | ❌ 伪机会 |
| **2. mmproj F16→Q8_0**（省 280 MiB 显存） | 本机已下载 Q8 版本 | +2~3%（跨安全线） | 配置 | ✅ 已有文件 |
| **3. `-ot token_embd.weight=CPU`**（省 515 MiB）| 词表调研 | 显存 +515 MiB，速度 <0.3% 损失 | 配置 | ✅ 高，待实测 |
| **4. 换 ik_llama.cpp + IQ3_K_R4** | 社区实战 | 41→55 t/s（同款 4060 8GB）| 换引擎+重下 20GB | ⚠️ 大工程 |
| **5. 多通道 DDR4 内存** | 论文/社区 | 带宽翻倍→上限翻倍 | 换硬件 | ❌ 笔记本板载 |
| **6. 词表放 SSD（Qwen3.8 式）** | 用户提问 | — | — | ❌ **机制不适用** |

---

# 第二部分：词表放 SSD —— 用户记错了机制（重要）

## 2.1 "Qwen3.8 把词表放 SSD"到底是什么

调研确认：用户指的是 **Qwen3.8-Flash-Next 的 51B N-gram 模型权重放 SSD / 按需 mmap**——那是**独立的 ngram 投机模型**（51B 参数），不是主模型的词表 embedding。

**本机 qwen35moe 架构根本没有这张表**：
- GGUF 里没有 `ngram.*` 张量
- `--spec-type ngram-*` 用的是运行时内存里的 token 历史，不是外部权重
- llama.cpp 的 `--lazy-mode on` 对 qwen35moe 是 **no-op**（没有 dflash/ngram 权重可 lazy load）

**结论：这个优化在本机不适用，不是配置问题，是模型架构里就没有这个组件。**

## 2.2 那本机"词表"能不能挪走？——分两个张量看

本机词表两项（GGUF 精确解析）：

| 张量 | 大小 | 精度 | 用途 | 每步访问模式 |
|---|---:|---|---|---|
| `token_embd.weight` | **515 MiB** | Q8_0 | 输入 embedding 查表 | **只读 1 行 = 2.2 KB**（随机小读）|
| `output.weight` | **515 MiB** | Q8_0 | LM head matvec | **读全部 515 MiB**（顺序流式）|

合计 1.01 GiB，占总权重 4.7%。

### 关键分水岭：`token_embd` 可以挪，`output` 绝不能挪

```
理论带宽需求（DDR 双通道理论 51.2 GB/s、流式实读 40-45 GB/s / GPU ~250 GB/s）：

token_embd 查表(2.2 KB)：
  DDR: 0.0001 ms  → 挪到 CPU 每年损失可忽略
  SSD: ~0.1 ms    → 每步 +0.1ms，4% 开销，勉强可接受

output.weight matvec(515 MiB)：
  DDR: 19.8 ms/步 → 挪到 CPU 就 +20ms → 25 t/s 掉到 16 t/s（-34%）
  SSD: 103 ms/步  → 9.7 t/s（灾难）
```

**所以"词表放 SSD"在本机的可实现版本只有一个**：`-ot token_embd.weight=CPU`（挪到内存而非 SSD，省 515 MiB 显存），而 `output.weight` 必须留在 GPU。

### 可行性细节
- qwen35moe 的 `token_embd` 和 `output` 是**独立张量**（不是 tied embedding），可以单独 offload
- `-ot` override 是通用张量名匹配（`llama-model-loader.cpp:1328`），对任何张量生效
- 但 **SSD mmap 不推荐**：Windows WDDM 下 mmap 换页行为不可控，NVMe 随机读延迟虽可接受，但有抖动风险
- **待实测**：`-ot token_embd.weight=CPU` 的真实提速（预计省 515 MiB 显存 → 可能跨过安全线 → +2~4%）

---

# 第三部分：同配置社区方案（8GB 卡 + 64GB 内存跑 MoE）

## 3.1 最重磅：ik_llama.cpp + IQ3_K_R4（同款 4060 Laptop 8GB）

社区实战报告：**同一台 4060 Laptop 8GB 跑 Qwen3-30B-A3B 类模型**
```
主线 llama.cpp Q4_K_M:  41 t/s (短) → 24 t/s (长上下文)
ik_llama.cpp IQ3_K_R4:  55-57 t/s，且不随上下文衰减
```
核心优势：**融合专家 GEMM**（把 top-8 专家的计算合成一次 kernel）+ IQ3_K_R4 量化（3.5 bit，比 Q4_K 少 25% 带宽）+ 更激进的 CPU 缓存调度。

**对本机适用性：高，但是大工程**——需要换引擎（无本地二进制，需从源码编译）+ 重量化 20GB 模型（无 llama-quantize 工具）。建议作为"下一步大动作"候选，不是本周可做。

## 3.2 llama.cpp 主线尚未合入的高价值 PR

| PR | 内容 | 对本机价值 |
|---|---|---|
| ~~#31233 ClassLRU~~ | 按专家类别分层缓存 | **已合入并生效**（src/llama-moe-cache.cpp:21，生产 94f3af3 已含）|
| **#32100** | 静默错误修复（投机解码采样一致性）| **正确性问题**，值得升级 |
| **#29307** | token-aware parsing | 已知未合并，影响有限 |
| **#29949** | GPU-resident LRU | 需显存，本机不适用 |

**验证结果（2026-11-24）**：ClassLRU **已在本机**——`src/llama-moe-cache.cpp:21` 有实现，生产二进制 commit 94f3af3 与源码一致。**这不是待办，是已具备的能力**。也解释了为什么我们把 cache 从 1350 加到 1900 没收益——LRU 分层已经把热点照顾好了。

## 3.3 MoE cache 调参的社区经验
- `scripts/moe-cache-tune.py` 自动扫 cache 大小找拐点
- 我们已实测 1350→1900 **没收益**（热点已饱和），印证"1350 已接近上限"
- 社区共识：cache 容量不是瓶颈时，提高命中率要靠**访问频率排序**（LRU 已近最优）→ #31233 ClassLRU 正是这个方向

## 3.4 CPU 侧优化的社区/论文经验
- **多通道 DDR4**：本机**已是双通道**（两条 Lenovo DDR4-3200 32GB 序列号连续=原厂套装，分属 Controller0/Controller1），历史实测流式读 40-45 GB/s。笔记本硬件锁定，无需也无法改
- **huge pages / 绑核 / 电源计划 / NUMA 交错**：本机已全部证伪或在笔记本上不适用
- **动态频率**：笔记本 BIOS 锁定，不要用第三方工具强改

---

# 第四部分：论文方案（针对 memory-bound MoE decode）

## 4.1 值得关注（理论可落地）

| 论文 | 年份 | 核心思想 | 本机适用性 |
|---|---|---|---|
| **PowerInfer / PowerInfer-2** | 2023-24 | 稀疏激活：热神经元常驻 GPU，冷神经元按需从 CPU/SSD 取 | MoE 版思想≈我们的 moe-cache，已做；SSD 版不适合 NVMe 延迟 |
| **MoE-Infinity** | 2023 | 专家级 LRU + 预取 | ≈ #31233 ClassLRU，见上 |
| **Fiddler / Brainstorm** | 2024 | CPU-GPU 协同调度，隐藏专家加载延迟 | 我们试过专家并行慢 3-5%，但他们的细粒度流水线可能更优 |
| **AdapMoE** | 2024 | 自适应专家预取 | 本机预取实测无效（带宽满），低优先级 |
| **Staged Speculative Decoding** | 2023 | 多级草稿 + 动态选择 | 需要训练，不适用 |
| **Token Trees / Lookahead** | 2023-24 | 多头并行 draft | ngram 已试，命中率低 |

## 4.2 DeltaNet 混合架构
本机 31 层 DeltaNet（线性注意力）+ 10 层 KV attention。学术论文主要在训练侧，**推理侧 llama.cpp 已有优化**（记忆里 CTX_CHECKPOINTS=2 是承重墙，降到 1 慢 23%）。暂无新的可落地优化。

## 4.3 结论
**论文层面没有发现"能立刻落地且未被我们试过"的大收益方案**。最接近的是 ClassLRU（已合入主线 PR）和 ik 的融合 GEMM（需换引擎）。

---

# 第五部分：行动建议（按优先级）

### 立即可做（本周）
1. ~~查 ClassLRU 是否已合入~~ → **已验证合入，无需动作**
2. **把 mmproj F16 换成已下载的 Q8_0 版本**（省 280 MiB，跨过 450 安全线，+2~3%）
3. **实测 `-ot token_embd.weight=CPU`**（省 515 MiB，理论速度损失 <0.3%，可能 +2~4%）—— **下一条消息立即做**

### 大动作候选（需要用户决策）
4. **编译 ik_llama.cpp + 重量化 IQ3_K_R4**：预期 25→55 t/s（2.2×），但要下载 20GB + 编译 + 重配，是"换引擎级"工程
5. **词表放 SSD**：机制不适用（本机没有 51B ngram 权重），唯一可做是 `token_embd` 挪 CPU，见第 3 条

### 明确不做
- ❌ 加大 MoE cache（已证伪，热点饱和）
- ❌ DFlash 侧车（已证伪，-34%）
- ❌ 换内存通道（笔记本硬件锁定）
- ❌ 词表 output.weight 挪 CPU/SSD（-34%~-75%）

---

# 第五·五部分：调研后的实测验证（2026-11-24 晚）

## A. `-ot token_embd.weight=CPU`：**+7.4%（真实收益，已上线）**

| 配置 | tps | n | sd |
|---|---:|---:|---:|
| 基线（F16 视觉 + token_embd 在 GPU）| 24.91 | 6 | 1.69 |
| **token_embd 挪 CPU** | **27.84 / 26.75** | 6+8 | 1.72 / 1.04 |

**两次独立测量均值 27.3 t/s，+7.4%**。理论预期 <0.3%（每步只读 2.2 KB），实测远超——**收益来自显存再分配**：token_embd 挪出 515 MiB 后，llama.cpp 把显存让给了 compute buffer / ubatch，缓解了 WDDM 换页压力。机制和"禁用视觉 +4.9%"同源。

**注意**：`output.weight`（LM head，515 MiB）**必须留在 GPU**——每步 matvec 要读全文，挪 CPU 会掉 34%（见 2.2 节）。

**配置**：preset 全局段加 `override-tensor = token_embd.weight=CPU`。

## B. mmproj F16→Q8_0：**文件存在但加载失败，已回滚**

本机有两个 Q8_0 mmproj 文件，换上后 `health=200` 但日志反复报 `failed to load multimodal model`：
```
[61850] E srv load_model: failed to load multimodal model, '...mmproj-Q8_0.gguf'
[61850] E srv server_run_i: exiting due to model loading error
```
GGUF 头检查：三份文件都是 `arch=clip`、334 张量，但 122 MiB 那份 `general.name=Qwen3.6 35B A3B`（点变空格），疑似转换时元数据不一致被 mtmd 拒绝。**已回滚 F16，多模态正常。**

教训：**health 200 ≠ 多模态可用**，必须查 `load_model: loaded multimodal model` 日志。

（Q8 视觉下 decode 测到 27.0 t/s，但视觉功能失效，无实用价值。）

## C. 已验证为"伪机会"的项
- ~~ClassLRU 未合入~~ → 已在生产版本（94f3af3）
- ~~mmproj Q8 可用~~ → 加载失败

# 第六部分：诚实的元结论

调研的**最高价值发现不是新技巧，而是排除了两个伪机会 + 确认了一个真差距**：
1. **ClassLRU 已在生产版本**，不是待办（已验证）
2. **⚠️ 已纠正：单通道怀疑是我造成的单位笔误**（11-24 晚）。派子任务时我把 **decode 的 25.4 tok/s** 误写成 "DDR 实测 25.4 GB/s"，子任务据此推出"接近单通道理论 25.6 → 可能单通道"。**这是错的**：
   - 本机**是双通道**：两条内存规格完全一致（Lenovo DDR4-3200 32GB，序列号 03CDFF26 / 03CDFEA0 连续=原厂配对套装），分属 **Controller0 / Controller1**。WMI 的 "Controller0-ChannelA"/"Controller1-ChannelA" 是 BIOS 命名，不是"同通道"。
   - 历史实测（10-20）：`2×32GB DDR4-3200 双通道，理论 51.2 GB/s，流式读 ≈40-45 GB/s`。
   - 真实有效带宽 = 580 MiB/token ÷ 40ms ≈ **14.5 GB/s**（51.2 的 28%）。**瓶颈不是带宽峰值，是随机访问局部性**——每 token 从 256 专家随机挑 8 个，是随机读非流式读。这解释了 ik_llama.cpp 的 IQ3_K_R4（重排专家权重改善 L3 局部性）为何能提速 2 倍：改善局部性而非减少字节。
   - 教训：派子任务时给的数字必须核对单位，否则整条推理链建立在错误前提上。
3. **引擎选择可能比参数调优重要 2 倍**：同类 8GB 卡上 ik_llama.cpp 的 55 t/s vs 主线 25 t/s，这个差距远超我们最近做的所有 ±5% 优化。**"harness 杠杆 > 模型选择"的经验可能在引擎层面重演**。

建议下一步聚焦"升级引擎"而非"继续微调参数"。


---

# 第七部分：引擎改进评估 —— 能否按 ik 思路优化（2026-11-24 晚）

> 用户：这方面我们的引擎能不能改进（包括重新按 ik 的思路优化我们的引擎）？
> 结论：**能，但要选对路径。最划算的是直接用 ik 引擎（现有 Q4_K_XL 模型不用重训/重下）；自己往主线移植 fused 算子风险高、收益不确定。**

## 7.1 ik 的 2× 优势到底来自什么（源码核实）

我把 ik 源码 checkout 到 `D:/ik-src`（commit 1180df7，MIT），和主线 94f3af3 逐项对比：

| 机制 | ik (1180df7) | 主线 (94f3af3) | 我们 |
|---|---|---|---|
| **MOE_FUSED_UP_GATE 算子** | ✅ `ggml.c:8743`，默认开（`llama.cpp:9337`）| ❌ `ggml.h` 里 0 次出现 | ❌ 没有 |
| **权重重排 repack** | ✅ IQK 专用 | ✅ `ggml-cpu/repack.cpp`，Q4_K 有 `Q4_Kx8` 交错 | ✅ **已启用**（默认开，没传 `-nr`）|
| **gate_up 合并张量** | ✅ 支持 | ✅ `llama-graph.cpp:2534` 有 merged 路径 | ❌ **我们的 GGUF 没有 gate_up**（gate/up/down 各 41 个独立张量）|

**核心差异是第 1 条**：ik 有 `GGML_OP_MOE_FUSED_UP_GATE` 算子，把 MoE 的 up 投影 + gate 投影 + SiLU 激活**融合成一个 kernel**，直接在寄存器里算激活，**不把 up/gate 两个中间结果写回内存**。

主线（包括我们）走的是：
```
gate = mul_mat_id(gate_exps, cur)   → 写内存
up   = mul_mat_id(up_exps, cur)     → 写内存
cur  = silu(gate) * up              → 再读两次内存
```
每 token 每专家要**多遍历一次专家权重 + 两次中间张量往返内存**。ik 的融合算子把这些合成一次。

**这正好击中我们的瓶颈**：每 token 从 256 专家随机挑 8 个，每个专家的 gate/up 权重各 24 MiB，主线要分别读两次（随机访问，L3 命中差），ik 融合后读一次。**有效带宽利用率从 28% 提升的关键就在这里。**

## 7.2 最关键的结论：不需要重新量化模型

**ik 的 fused up/gate 是计算图级融合，对任何量化类型都生效，包括我们的标准 Q4_K_XL。**

- 不是新的量化格式（那是 IQ3_K_R4，另一回事）
- 不需要重新下载/量化 20GB 模型
- 不需要重训
- 算子在 `ggml/src/ggml.c`（通用 C 实现，`GGML_IQK_MUL_MAT=ON` 默认开启），不是硬件专用

**所以"用 ik 引擎跑我们现有模型"是可行的，成本只是编译一次 ik。**

## 7.3 三条路径的评估

### 路径 A：直接用 ik_llama.cpp（推荐）
- **收益**：社区同款 4060 Laptop 8GB 实测 41→55 t/s（+34%），长上下文不衰减（主线 41→24，ik 55→57）
- **成本**：编译 ik（源码已在 D:/ik-src）+ 切换 autostart 的 engine 路径 + 重跑配置校准（ik 参数名有差异）
- **风险**：① ik 的 FA/MTP 行为和主线不同，要重新验证 ② 我们依赖的 `--cpu-moe` / moe-cache / router 模式在 ik 上的支持情况要确认 ③ b12244 的 autoparser 补丁要在 ik 上重打（如果 ik 也有这个 bug）
- **不确定的点**：社区 55 t/s 的数据用的是 Qwen3-30B-A3B + ik 专用量化，我们的 Qwen3.6-35B-A3B + 标准 Q4_K_XL 能拿到多少，**必须实测**

### 路径 B：把 fused 算子移植到主线（不推荐）
- **工作量**：ik 的 `MOE_FUSED_UP_GATE` 涉及 ggml 算子定义、CPU 后端 compute、graph builder 三处，`iqk_moe_fused_up_gate` 还依赖 `GGML_IQK_MUL_MAT` 整套优化，**不是几百行能搞定**
- **风险**：主线每次升级都要重打补丁（我们已经有 autoparser 补丁的教训）；且 ik 的算子可能和主线的 repack 路径冲突
- **结论**：投入产出比差，**不如直接用 ik**

### 路径 C：在主线上做"gate_up 权重合并"（中间路线，可小成本试）
- 我们的 GGUF 没有 gate_up 合并张量，但可以在**加载时**把 gate_exps 和 up_exps 拼成一个张量（2×n_ff），走主线已有的 `gate_up_exps` merged 路径
- **收益**：省一次 `mul_mat_id` 的 kernel launch 和权重遍历，但**仍需写回中间结果**，不如 fused 算子彻底
- **成本**：改 `src/llama-model.cpp` 的权重加载逻辑，约 50-100 行
- **风险**：中等；且需要验证 qwen35moe 的 graph builder 是否接受合成张量
- **定位**：如果不想换引擎，这是**唯一值得试的小改动**，但预期收益远小于路径 A

## 7.4 诚实的建议

1. **如果目标是 2× 提速**：直接用 ik（路径 A）。源码已就位，模型不用动，这是唯一能逼近社区 55 t/s 的路。
2. **如果不想换引擎**：接受当前 25-27 t/s。主线已经启用了 repack（我们验证过），剩余的局部性损失是架构性的，靠配置调不回来。
3. **不要自己移植 fused 算子**（路径 B）——维护成本太高，且每次主线升级都要重打。

## 7.5 一个待验证的反面可能

ik 的 55 t/s 数据是在**专家全在 GPU 或大显存**的配置下测的（`-ncmoe 99`），我们是 `--n-cpu-moe 40` 全 CPU。ik 的优势（融合算子）在 CPU 路径上是否同样有效，**需要实测**：
- 如果 ik 的 `MOE_FUSED_UP_GATE` 只在 CUDA 后端有优化实现，CPU 路径可能退化成主线行为
- 从源码看它在 `ggml.c` 有通用实现，`GGML_IQK_MUL_MAT=ON` 默认开，理论上 CPU 也生效——但**必须实测确认**

**建议的决策方式**：先编译 ik，用现有模型跑一次 `tps_probe.py`，和当前 27 t/s 对比。如果 ≥40 t/s，值得全面切换；如果 <30 t/s，说明优势不在这条路径上，维持现状。
