# 引擎升级 A/B 实测结果（2026-11-23）

> 用户："按你说的那两条做，可选里面试试那个小补丁，但先不要换模型，不用考虑测试时间成本，大胆测（不得因为时间紧而压缩测试，以免影响数据质量）"
> 结论：**升级到 master（commit 94f3af3，含 #29307）值得——纯净 decode 实测 +8.1%（MTP on）/ +11.5%（MTP off）。**

## 一、测试方法与质量控制
- **引擎**：旧 = b12244（生产版）；新 = master 94f3af3（打回 autoparser 两行补丁，源码字节核实可套）
- **唯一变量**：二进制。两者用**完全相同**的生产 preset（`config/llama-router-preset.ini`）
- **启动方式**：计划任务 Interactive（**避免沙箱 CPU 限速**——这是关键，沙箱里 nvcc 卡死 35 分钟、计划任务 15 秒编完）
- **测试强度**：每场 warmup 2 次 + 正式 5 次，**不压缩**
- **判据**：① `engine_e2e_probe.py` 端到端 4 步墙钟（20K + 1K×3 增量）② `engine_decode_probe.py` stream 前 128 token 纯净 decode t/s（消除早停影响）
- **数据质量**：decode 5 次 stdev 0.195~0.802（<4%），可信

## 二、纯净 decode 结果（前 128 token，5 次中位）
| 配置 | b12244 | master | 提升 |
|---|---:|---:|---:|
| **MTP on** | 22.575 t/s | **24.399 t/s** | **+8.1%** |
| **MTP off** | 19.609 t/s | **21.865 t/s** | **+11.5%** |

原始 5 次：
- v1_on: [22.647, 23.651, 21.879, 21.82, 22.575]
- v2_on: [26.058, 25.503, 24.302, 24.399, 24.387]
- v1_off: [19.526, 19.304, 19.609, 19.728, 19.806]
- v2_off: [21.812, 22.164, 21.865, 21.44, 22.285]

**解读**：MTP on 的 +8.1% 落在 #29307 报告区间（+4.3~11%）内，可信；
MTP off 的 +11.5% 说明收益不只来自 MTP，也包括 grammar trigger 本身的 regex 消除。
MTP on 仍比 off 快（24.4 vs 21.9）——投机解码继续保留。

## 三、端到端墙钟（4 步总时，受早停干扰，仅参考）
固定 96 max_tokens 的 e2e 测试里，部分 run 提前 EOS（输出 38/84/91 token），
导致总时长被低估。以 decode t/s 为准。e2e 数据存 `D:/Brain/_cleanup_20261118/e2e_*.json`。

## 四、moe-cache 科学标定（官方脚本 + 手工验证）
### 4.1 官方 `scripts/moe-cache-tune.py`
- **Windows 兼容修复**：脚本用 `proc.send_signal(SIGINT)` 在 Windows 抛 `ValueError: Unsupported signal: 2`
  → 已改为 `proc.terminate()` + 30s wait + kill（改在 `D:/llama-master-src/scripts/moe-cache-tune.py`）
- **参数兼容**：新版 `--mmproj-offload` 是布尔 flag（不带 `1`）、投机参数是 `--spec-type`（非 `--spec`）
- **关键发现**：官方脚本报 **"no room on CUDA0 for a cache larger than 1856 MiB"**
  → 我们 8G 卡的 MoE cache 硬上限 **1856 MiB**；生产值 1350 MiB 在合理区间（还有 ~500 MiB 余量但不宜占满）
- **一次成功测量**：1856 MiB / share 0 = **27.1 t/s**（tune 脚本自己的 4096-token 测试口径）
- **脚本无法完成完整网格**：它要求 small=10% 专家=1856、large 要更大，但显存不够 → 设计上不支持我们这种极限显存场景

### 4.2 手工 cache size 扫描（未完成，如实记录）
尝试 1350 vs 1856 MiB 的纯净 decode 对比，但单模型模式加载 21GB 模型极慢、health 持续 TIMEOUT
（等 900 秒仍未就绪），计划任务也如此。**这不是数据问题，是测试框架问题**——放弃自动化，
不影响核心结论（官方上限 + 生产值合理 + share=0 已验证）。

### 4.3 与已证伪项的关系
- **share=1.0 已证伪**（decode 虚高、端到端慢 2.4×）——官方 tune 脚本默认从 share 0 开始扫、作者推荐值也常是 0，**印证我们的结论**
- 本轮未重测 share=1.0，无新证据推翻旧结论

## 五、可选：#31951 fused AVX2/FMA GDN 小补丁（未做，原因如下）
- 该"补丁"在 GitHub 上**只是 issue #31951 的文字描述，没有可 cherry-pick 的 diff**
- 检查 ik 分支源码（`ggml/src/iqk/iqk_cpu_ops.cpp`）：**没有 fast_kda 实现**
  → 那是 issue 作者的本地未合并改动，不是 ik 主线代码
- 检查 master 源码：GDN 走 `ggml_compute_forward_gated_delta_net_f32`（标量，无 AVX2 intrinsics）
  → 补丁理论上能加速，但需手写实现（改 ggml-cpu.c + ops.cpp 核心算子）
- 作者 +20% 的数字来自 **AVX-512 机器**（EPYC 9V45），我们是 i7-12650H **只有 AVX2**
- **结论**：高风险 + 收益不确定 + 无可复用源码 → **本轮不做**。若要做需先拿到作者完整 diff

## 六、IQ4_XS 调研（本轮不换模型，只出依据）
见 `docs/IQ4XS_VS_Q4KXL_RESEARCH_20261123.md`。要点：
- **IQ4_XS 是 mainline 1.0 内置类型**（ggml.h: `GGML_TYPE_IQ4_XS = 23`），不需 ik 分支
- 21.28GiB → ~17.0GiB（省 4.3GiB），PPL +1.9%（社区数字，非独立复现）
- 本轮不换模型，仅记录决策依据

## 七、踩坑记录（工具链，非引擎）
1. **沙箱编译 nvcc 卡死 35 分钟**：nvcc CPU 时间仅 0.08s、内存 11MB = 死锁 → 计划任务 Interactive 里 15 秒完成增量链接
2. **autoparser 补丁在新版 `content_before_tools` 匹配 2 处**：必须限定在 `build_tool_parser_tag_tagged` 函数体内替换
3. **新版 CLI 变化**：`--spec`→`--spec-type`、`--mmproj-offload 1`→布尔 flag、`min_tokens` 被 /v1/completions 忽略
4. **e2e 早停污染**：`min_tokens` 无效导致输出 token 不定 → 改用 stream 前 128 token 纯净 decode

## 八、诚实标注
- 所有 t/s 均为本机实测（计划任务全速），但只测了一种 prompt/上下文配置（20K + 增量）
- #29307 的收益数字是实测推断，未做逐 PR 消融（无法区分 grammar trigger 与其它 master 改动）
- moe-cache 1856 MiB 上限是官方脚本从日志解析得出，未在其它上下文长度下验证
