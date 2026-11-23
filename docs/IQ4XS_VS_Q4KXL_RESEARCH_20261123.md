# IQ4_XS vs Q4_K_XL 调研（2026-11-23）

> 用户："广泛调研IQ4_XS和我们正在用的K_XL的区别"（本轮不换模型，只出决策依据）

## 一、最重要的可行性纠正：IQ4_XS 是 mainline 内置类型，不需要 ik 分支
**一手核实**：本机 clone 的 `llama.cpp master`（commit 94f3af3, ggml 1.0.0）里：
- `ggml/include/ggml.h:242` → `GGML_TYPE_IQ4_XS = 23`
- `src/llama-quant.cpp:1002` → `LLAMA_FTYPE_MOSTLY_IQ4_XS` 分支存在

→ **IQ4_XS 可直接用 mainline llama.cpp 1.0 量化+加载，不用切 ik**。
⚠ 区分：ik 专有的是 **IQK repack 家族**（IQ3_K_R4 / IQ4_KS_R4 等带 K/R4 的），
那些才需要 ik 分支。之前调研里"IQ 是 ik 专有"的说法对 IQ4_XS **不成立**。

## 二、量化原理差异
| 维度 | Q4_K_XL（当前）| IQ4_XS |
|---|---|---|
| 体系 | k-quants（super-block 分组量化）| importance-matrix 量化（按权重重要性分配码本）|
| 位数 | 4.5 bpw（含 scale/min 开销）| ~4.25 bpw |
| f16  tensor | Unsloth UD 版含 f16 tensor（注意力/输出层保精度）| 需确认保留情况 |
| 文件大小 | 21.28 GiB | ~17.0 GiB（省 ~4.3 GiB）|
| 工具 | mainline 内置 | mainline 内置（`-q IQ4_XS`）|

## 三、质量与速度证据（区分来源）
### 3.1 质量（PPL 与下游）
- 已知来源（L4 优化前沿日志，社区实测）：Q4_K_XL **PPL 5.8263** vs IQ4_XS **5.9363（+1.9%）**
- 同 L4 硬件 IQ4_XS **+3.2% t/s**（量化更小带来的带宽收益）
- 另一来源（8G 指南）：IQ4_XS 在 8G 机器上占 5.7GB、~10-15 t/s
- IQ3_XXS（更低档）：SWE **5/10** vs IQ4_XS **9/10**——**IQ3 档明显退化，不建议**
- ⚠ **未找到 Qwen3.6-35B-A3B 这个具体模型的独立 PPL/下游 benchmark 对比**；
  上述数字来自社区优化日志与小样本，不能当定论

### 3.2 速度（理论机制）
- IQ4_XS 小 ~4.3 GiB → 同样 8G 显存能多放 ~4 层专家进 GPU（或减少 CPU offload 层数）
- 我们当前 NCMOE=40（40 层专家在 CPU），如果能降到 30 左右，decode 可能显著提升
- 但注意：换量化是**质量换速度**，不是纯优化；且 MTP 头/DeltaNet 状态是否受量化影响需实测

## 四、对我们配置的判断
| 项 | 结论 |
|---|---|
| 可行性 | ✅ 高——mainline 1.0 直接支持，不用换引擎、不用 ik |
| 收益机制 | 省 4.3GiB → 可能多放专家层进 GPU 或减少 MoE cache 压力 |
| 质量代价 | PPL +1.9%（社区数字），下游任务退化程度未知 |
| 风险 | ① MTP 头/DeltaNet 状态的量化敏感性未测 ② Unsloth UD 版 f16 tensor 丢失的影响 ③ 缺该模型独立 benchmark |
| 建议 | **本轮不换**（用户已定）；若要试，先量化一份 IQ4_XS 到独立文件，做 A/B：同 CTX/同任务集，判据=端到端墙钟 + 质量评分双指标 |

## 五、诚实标注
- IQ4_XS 内置支持是本机源码一手核实（ggml.h + llama-quant.cpp）
- PPL +1.9% / +3.2% t/s / SWE 5vs10 均来自社区优化日志，**非独立复现**，且未必是 Qwen3.6-35B-A3B
- 未做本地量化测试——本报告是决策依据，不是实测结论
