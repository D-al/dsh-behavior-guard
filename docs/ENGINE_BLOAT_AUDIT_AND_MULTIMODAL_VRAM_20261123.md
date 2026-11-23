# 引擎多余部件审计 + 多模态显存优化方向（2026-11-23 深夜）

> 用户问："引擎本身有没有多余部件被加载进显存？能否抠出来？" + "希望它能支持多模态" + "这部分能不能放进内存？偶尔发图片"

## 一、编译期：已经裁干净了，省不了显存

### 1.1 当前编译配置（CMakeCache.txt 实测）
```
CMAKE_BUILD_TYPE=Release / NDEBUG 已开
CMAKE_CUDA_ARCHITECTURES=89           ← 只编译 sm_89（RTX4060 Ada），单一架构
GGML_CUDA=ON / GGML_VULKAN=OFF / GGML_METAL=OFF / GGML_SYCL=OFF / GGML_OPENCL=OFF / GGML_BLAS=OFF
GGML_AVX=OFF / GGML_AVX2=OFF(native) / GGML_AVX512=OFF / GGML_AVX_VNNI=OFF / GGML_AMX=OFF
GGML_CUDA_FA_ALL_QUANTS=OFF（只编译 5 种 FA 量化组合）
```
**结论：通用性裁剪之前已经做过。** Vulkan/Metal/ROCm/多 SM 架构/AVX512 全没编进来。

### 1.2 唯一还能裁的编译项（但省不了显存）
- `GGML_CUDA_NCCL=ON`：多 GPU 通信库，单 GPU 用不到
- `GGML_SCHED_MAX_COPIES=4`：pipeline 关闭，实际只用 1
- `ggml-cuda.dll` 207.5 MiB（实测 217,529,344 B） 里含所有量化类型的 MMQ kernel（Q2~Q6/IQ 系列），我们模型只用 Q4_K(68%)+Q5_K(32%)

**但关键认知（调研给出铁证）**：编译进去的未用 kernel 只是**磁盘上的 DLL 字节**。CUDA 11.7+ 默认 **lazy module loading**——设备代码在该 kernel **首次 launch 时**才上传显存，用不到的量化 kernel 的 SASS **永远不会进 VRAM**。
- 实测 PTX 全是 `.target sm_89`（147 处），**无多架构 PTX 可裁**；改 `89-real` 只省磁盘
- 约 14 种量化类型（q5/q6/IQ 系列等）是死代码，但裁掉它们显存变化 ≈ 0
- **编译期裁剪 = 省磁盘/加载时间，不省显存。** 这条路对当前目标无效

调研同时纠正：`ggml-cuda.dll` 实测 **207.5 MiB**（非早先估计的 253 MiB）。

## 二、运行期显存里唯一的大件：mmproj-F16（858 MiB）

### 2.1 事实
- `Qwen3.6-35B-A3B-mmproj-F16.gguf` = **857.6 MiB**，F16 精度
- 当前 `MMPROJ_OFFLOAD=1` → 视觉编码器常驻显存
- server 启动即加载 mtmd_context（`tools/server/server-context.cpp:1264`），**没有按需加载机制**
- 当前显存 7769/8188 MiB（余 419 MiB）—— mmproj 占了 858 MiB，是余量的 2 倍

### 2.2 三个方案对比（用户要求保留多模态）

| 方案 | 显存 | 视觉质量 | 速度 | 判定 |
|---|---:|---|---|---|
| A. 禁用视觉（MMPROJ=''）| 省 858 MiB | **失去多模态** | — | ❌ 用户明确不要 |
| B. 放内存（MMPROJ_OFFLOAD=0）| 省 858 MiB | 不变 | **CPU 编码 141s/张**（历史实测，ADR-0005）| ❌ 太慢 |
| C. **量化 mmproj 到 Q8_0** | **省 402 MiB** | **几乎无损** | GPU 编码保持快 | ✅ **推荐** |
| D. 量化 mmproj 到 Q4_K | 省 616 MiB | OCR 准确率约 −1.5pp | GPU 编码保持快 | ⚠️ 备选 |

### 2.3 量化质量证据（社区实测）
- Qwen3-VL mmproj F16(839MB) → Q8_0(454MB)："**体积减半，视觉识别质量几乎无损失**"（多来源一致）
- ArmorOCR(Qwen3-VL-8B) AdvSpot 基准：F16 基线 55.7 → **Q8_0 56.9（反而略高）** / Q4_K_M 54.2（−1.5pp）
- 结论：**Q8_0 是甜点**——省一半显存、质量无损甚至微升

### 2.4 障碍：没有现成的量化工具在 build/bin
- `llama-quantize.exe` 不在当前 build/bin（只编译了 server 相关）
- 需要：① 编译 llama-quantize；或 ② 用 Python 脚本转换 GGUF 张量类型
- 另外现成的量化 mmproj 是 Qwen3-VL-4B/8B 的，**与我们的 35B-A3B 不通用**，必须自己量化

## 三、省下的显存怎么用（这才是收益所在）

当前 MoE cache 1350 MiB、命中率 70-85%。省下 402 MiB（Q8_0）后：
- 显存余量 419 → **821 MiB**
- MoE cache 可提到 ~1750 MiB → 命中率提升
- **命中率是当前 CPU-bound 的最大杠杆**（miss 专家在 CPU 算，命中在 GPU 算）

这才是"抠显存"的真正价值——不是为了省而省，而是把 mmproj 的多余精度换成 MoE cache 的命中率。

## 四、回答用户的三个问题

1. **"引擎有没有多余部件在显存里？"** — 编译期已经很干净；运行期唯一的大件是 mmproj 858 MiB
2. **"希望支持多模态"** — 所以不禁用，走量化（Q8_0 省 402 MiB、质量无损）
3. **"能不能放进内存？偶尔发图"** — 技术上可以（`MMPROJ_OFFLOAD=0`），但历史实测 CPU 编码 141s/张，不可接受；新引擎可能有改善但风险高。**量化 GPU 常驻是更稳的方案**——既保留多模态、又省显存、又不牺牲速度

## 五、下一步（待用户决定）
1. 编译 `llama-quantize` 或用脚本把 mmproj-F16 → Q8_0（预计 858→456 MiB）
2. 视觉质量 A/B：找几张典型截图，F16 vs Q8_0 对比识别结果（尤其中文 OCR、图表数字）
3. 显存 A/B：确认省下 402 MiB，把 MoE cache 从 1350 提到 ~1750，测命中率与 t/s 变化（交叉验证）
4. 如果 Q8_0 质量有损，退回 F16，此路不通

## 六、方法论
上次专家并行的教训：**先校准测量方法**。这次如果做 MoE cache 命中率 A/B，必须先解决"命中率日志拿不到"的问题（优雅退出或用 LLAMA_MOE_CACHE_TRACE），否则又是噪声。
