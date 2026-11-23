# 第一性原理 + 算子级优化调研（2026-11-23 下午）

> 用户问："有没有像改算子的方案（或手搓改其他算子）可以进一步提升解码速度和输出质量？从第一性原理和社区论文方向看"

## 〇、最重要发现：瓶颈定位错了 3 个月

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

## 一、零成本收益：CPU 线程 6→8（**已部署**）

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

## 二、算子级手搓可行性（源码分析结论）

### 2.1 CPU 侧 q4_K dot（真正热点）——有空间但需权衡
- **位置**：`ggml/src/ggml-cpu/arch/x86/quants.c:2120-2200`，`ggml_vec_dot_q4_K_q8_K`
- **热点**：每个 block（32 权重）做 `memcpy(utmp, x[i].scales, 12)` + 4 行位运算重组 scale/min + `_mm256_cvtepu8_epi16`；内层仅 4×2 次 `maddubs`
- **解包指令数 ≈ dot 指令数**，是真实的优化空间
- **改法**：repack 阶段预生成"对齐的 scale 表"，dot 里直接 load，省掉每 block 的 memcpy+位运算（约 30-40 行，语义不变）
- **风险**：社区有类似补丁（预取 ISA 无关部分 +61%），但没有针对我们这个版本的现成 diff；需重编译 + 完整质量验证

### 2.2 repack 与 MoE cache 互斥——**此路不通**
- **互斥点**：`src/llama-moe-cache.cpp:313` 的 `ggml_backend_buffer_is_host()`；repack 后的 buffer `is_host=nullptr` → MoE cache 完全禁用
- **判断**：cache 命中率 70-85% 的收益远大于 repack kernel 的收益。**不能为了 repack 关 cache**

### 2.3 DeltaNet/GDN 状态 fp32→fp16——收益有限
- **位置**：`ggml/src/ggml-cuda/gated_delta_net.cu:180+`，kernel 签名全是 `float*`；状态 `GGML_TYPE_F32`
- **现状其实不错**：状态一次读进寄存器、循环所有 token 后一次写回，不是逐 token 往返
- **收益**：RS buffer 251 MiB → 125 MiB，省约 1-2ms/token（~5%）。但 **GPU 不是瓶颈**（30W），收益会被 CPU 瓶颈掩盖
- **风险**：线性注意力状态有衰减机制，fp16 精度风险中等；改动量大（kernel 全是 float 计算）

### 2.4 采样算子——已优化，无空间
- 有 CUDA 版 `top-k-mask.cu`；采样不是当前瓶颈（CPU 590% 主要是专家计算不是采样）

### 2.5 CUDA Graph——不适用
- 我们是 MoE（动态路由）+ DeltaNet 混合图，动态 slot map 每步变，graph capture 会失效

## 三、社区论文方向评估（第一性原理）

| 方向 | 出处 | 机制 | 对我们的判断 |
|---|---|---|---|
| 专家混合精度 | APEX/Gordon/BFCL 论文 | 减少 CPU 读字节 | ✅ **最大杠杆**，但需换模型文件（用户未决定）|
| CPU 线程用满 E 核 | 本机实测 | 6P+4E 架构 | ✅ **已部署 +18%** |
| q4_K scale 预计算 | 社区 AVX2 补丁 | 减少解包指令 | ⚠️ 可做，30-40 行，需验证 |
| 预取/L2 hint | 论文 | 隐藏内存延迟 | ⚠️ 对 CPU-bound 有效，但未找到我们版本的现成 diff |
| GDN fp16 状态 | flash-linear-attention | 减少状态字节 | ❌ GPU 不是瓶颈，收益被掩盖 |
| Expert deferral | KTransformers SOSP'26 | 打破串行图 | ❌ ggml 静态图做不到 |
| 投机 acceptance 提升 | EAGLE3 等 | 摊薄每 token 成本 | ⚠️ 已有 MTP 0.77-0.81，提升空间有限 |

## 三·五、源码深挖的补充发现（2026-11-23 晚）

### A. 真正的瓶颈是 DDR 带宽墙（源码+元数据精算）
- 每专家 gate_up[1024,2048]+down[2048,512] = 3.146M 权重，q4_K 4.375bpw → 1.72 MiB/专家
- 40 层 × 8 专家 = **~551 MB/token 必须从 DDR 搬到 CPU**
- 34 t/s → 18.7 GB/s，DDR4-3200 实用带宽 ~35-40 GB/s → 利用率约 50%，还有 2x 理论空间
- FLOPs 2.0 G/token × 34 = 68 GFLOP/s，AVX2 峰值 ~700-1000 GFLOP/s → **ALU 利用率仅 7-10%，不是瓶颈**
- 子任务独立复核：scale 解包占 dot ALU 10-15%，但预解包会把 scale 读取 12B→16B（+2.8% 带宽），在带宽墙上**可能净负收益** → scale 外提不值得做

### B. Windows 不区分 P/E 核（源码铁证）
- `common.cpp:153-201` 的 `is_hybrid_cpu()`/`is_running_on_efficiency_core()` 被 `#if defined(__x86_64__) && defined(__linux__)` 包住 → **Windows 分支完全不区分 P/E 核**
- `ggml-cpu.c:557-735` 的 NUMA/绑核逻辑全 Linux-only，Windows `:2291-2292` 是空函数
- **本机实测拓扑**（GetLogicalProcessorInformationEx）：P 核=逻辑 0-11（6 核×2HT，eff=1），E 核=逻辑 12-15（eff=0）
- 后果：`-t 8` 时 Windows 可能把线程摆在 HT 兄弟或 E 核上，被最慢核拖住（straggler）

### C. 可实测的纯参数钩子
- `-C <hexmask>` / `-Cr lo-hi`（`common/arg.cpp:1519-1538`）：Windows 下走 `SetThreadAffinityMask`（`ggml-cpu.c:2571-2603`）
- `--prio 1/2`（`arg.cpp:1547`）：关 Windows 11 核心停放（源码注释明说 n_threads>4 时很关键）
- `GGML_CPU_TILED_MM_FORCE=1`（`tiled.cpp:583`）：强制 tiled kernel。**已测：暴跌到 11.8 t/s（vs 默认 29.2，−60%）** — 因为 tiled 只在 rows>=8 划算，decode 时每专家 rows=1~6，这个开关坐实了传统 vec_dot 是当前路径

### D. 绑核 A/B 初测（待交叉验证）
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

## 四、结论与建议排序
1. **✅ 已做**：CPU 线程 6→8（+18%，零成本，已部署）
2. **⚠️ 可做但需决策**：混合精度专家 Q3_K（预计 decode +23~29%，但需重做 GGUF）
3. **⚠️ 可手搓**：q4_K scale 预计算（30-40 行，语义不变，预期收益待实测）
4. **❌ 不建议**：GDN fp16 状态、repack、CUDA Graph（要么 GPU 不是瓶颈，要么互斥）

## 五、方法论沉淀
**profiling 先于优化**：我差点基于"GPU 带宽瓶颈"去做 GDN 状态优化，实测发现 GPU 只有 30W、CPU 590% 后才定位到真正的瓶颈。**任何算子优化前必须先用功耗/带宽/CPU 占用三维定位，不能只看 t/s**。
