# llama.cpp v1.0 调研：对本机 35B MoE 推理的参考价值（2026-11-23）

> 用户问："llamacpp的1.0出了，对我们有什么参考价值？调研一下推理引擎是否可以继续优化"+"记得看最新的llama更新，广泛调研一下"

## 一、发布事实（一手核实）
- **v1.0.0 发布于 2026-11-13**（GitHub release，commit `b1b770d`），是 3.5 年来首个语义化大版本
- **v1.0.0 = nightly b12359**（InsiderLLM 核实）——**不是另起版本线**，"v1.0.0 只是给 b12359 贴的语义标签"
- **GitHub 最新 nightly = b12633（2026-11-22）**——没有 v1.0.1/v1.0.2 语义 patch，日常仍走 b 号
- 我们从 **b12244（2026-11-10 07:25 UTC 发布）→ v1.0.0=b12359 只差 3 天 / 115 commits**，不是落后一个时代；当前最新 nightly b12635（11-22 23:55 UTC）
- 语义化规则：MAJOR=公共 C API 破坏、MINOR=向后兼容功能/模型/后端、PATCH=纯修复

## 二、v1.0.0 关键变更 vs 我们（逐条判断）

### 2.1 直接命中的性能改动
| PR | 内容 | 对我们的意义 |
|---|---|---|
| **#29307** | token-aware parsing（**11-22 刚合并**，62 commits，1.0 之后）| 一手核实：把 `std::regex` 触发检测换成 grammar sampler 扫描，64k 下每 token 成本 Qwen3.8 从 **1014µs→1.1µs（约900×）**；3090/20B/16k decode 分窗口 **+4.3%/+0.3%/+6.1%/+11.0%**（越长收益越大）；**Qwen3.5+ parser 已支持**；但 `p.until()` 语义变了、`p.ac()` 被移除→**我们的 autoparser 补丁必须重做不是撤掉** |
| **#30966** | MoE cache CPU share（11-07）| 作者明确："CPU 跑 miss experts，速度取决于 CPU 读专家多快"；**官方 tuning 脚本推荐值竟是 share=0**——跟我们生产值一致，印证我们"share=1.0 是伪优化"的结论 |
| **#31233/#31888** | LRFU/ClassLRU 替换 + **no CPU wait on cached experts** | 缓解我们踩过的"CPU 等待"问题，但物理带宽瓶颈仍在，不撤销"share=0"结论 |
| **#30137** | context checkpoints 从 deep copy 改 **reference-counted** | 我们的 `CTX_CHECKPOINTS=2` 是承重墙（降到1慢23%），这条可能进一步降低 checkpoint 成本 |
| **#32078** | 移除 non-fused GDN 路径 | 我们 31 层 DeltaNet(GDN)；删的是 legacy 慢路径，预期不降速 |
| **#31660** | MTP conv snapshots 合并进一个 set_rows | 我们用 draft-mtp + nmax5，直接相关 |
| **#28392** | OCP FP8 KV cache (`-ctk/-ctv f8_e4m3`) | 我们 CTK q8_0/CTV q4_0、显存余 457MiB；FP8 可能省显存但**质量风险未验证** |
| **ggml 1.0** | few-row quantized matmuls + MoE fusion on CUDA | decode 小批量直接受益，但无该模型实测数字 |
| **b12627 (#32713)** | server fit non-causal batches in one ubatch | 我们用 UBATCH 1536，可能受益，需实测 |
| **PR #29353（10-14，我们已有）** | chunked GDN prefill kernel：35B-A3B 在 4090/5090 报 **+11~21% prefill** | 我们 b12244 已含；但作者说**投机解码开启时不生效**（我们开 MTP）——升级也未必吃到 |

### 2.2 社区实测（非独立验证，仅参考）
- 3090 用户报告：1.0 在投机解码关时**无提升**，**MTP 投机开时快 55%**（我们正是 MTP 开，值得实测）
- 该数字未经复现，且 3090 是 24G 卡，跟我们 8G 不同配置

### 2.3 破坏性变更（我们基本不受影响）
- 删 35 个废弃 C API、`--defrag-thold`、非融合 GDN、clip.h → 我们是 CLI 用法、不链接 C API
- `--mlock/--no-mmap` 改 `--load-mode`、默认端口 8080→9931（中文二手源，**与英文官方 notes 矛盾，需核实**）——我们 router 显式用 8081、启动脚本走计划任务，**若端口真变了要改配置**
- server 安全加固（CORS/SSRF/DNS rebinding、非本机地址需 opt-in）——我们只绑 127.0.0.1，无影响

### 2.4 autoparser 补丁风险（一手字节级核对后修正）
我们的补丁（`config/patches/autoparser-fix.patch`）：`p.optspace(format.per_call_start)` +
`p.until(trim_whitespace(trigger_marker))` 两行。
- **好消息**：字节级 diff 核实 **b12244 与 v1.0.0 的 `common/chat-auto-parser-generator.cpp` 完全一致**
  （均 22780 字节，diff 空）→ **补丁可直接套用 v1.0.0，无需重做**
- **风险在 master**：#29307（11-22）+ #32497（11-22）改了同一文件的 `raw_strings/p.through` 区
  和 `trigger_pattern` 区；若我们的两行补丁落在冲突区，cherry-pick 到 master 会冲突需手动 rebase
- 上游"工具标记前空白 bug"至今未修——**升级到 v1.0.0 后仍要重打补丁**，只是不用改内容

## 三、推理引擎优化空间（严格排除已证伪清单）

### 3.1 最值得试 top3
1. **升级到 v1.0.0/b126xx + 重做 autoparser 适配**（最高优先级）：
   - #29307 把 `p.until()`/`p.trigger_rule()` 语义改了、删了 `p.ac()`——我们的两行补丁
     (`p.optspace(format.per_call_start)` + `p.until(trim_whitespace(trigger_marker))`)
     在新版可能**无法直接套用**，需按新 API 重新实现"工具标记前空白 + 触发标记 trim"语义
   - 收益：64k 下 regex→grammar 每 token 从 ~1ms 降到 ~1µs；我们 ctx 98304 且工具面 15 个，
     理论上正是最受益场景（但 PR 数字来自 20B/3090，我们是 35B/8G，必须自测）
   - ⚠ 若升到 v1.0.0：补丁直接套用（字节一致）；若追到 master（含 #29307）：补丁可能冲突要 rebase
   - A/B 测三个数：
   - 20K decode t/s（基线 27.2）、prefill t/s（基线 800）、**每步端到端墙钟**
   - 重点看 MTP 开/关两档（社区报 1.0 对 MTP 有 55% 提升）
   - 风险：破坏性 API 变更、补丁失效、端口/参数变化；收益不确定，**必须 A/B 而非假设**
2. **用官方 `scripts/moe-cache-tune.py` 重新标定 MoE cache**：
   - 我们手工试过 share=1.0 失败，但科学标定（cache MiB × share 网格）没做过
   - 注意别被"decode t/s"误导——**判据必须是 P4/P5 端到端**，这是我们已经吃过的亏
3. **CTK/CTV 试 FP8**（`-ctk/-ctv f8_e4m3`）省显存：
   - 我们显存余 457MiB（安全线 450），FP8 可能腾出更多 KV 空间
   - 但质量风险未验证，且我们已证伪 KV q8_0（显存不够）——需先量化质量影响

### 3.2 不值得再试（已证伪，别重复）
电源计划 / -t 线程 / ngram 投机 / -lm 大页 / KV q8_0 / ignore_eos / nmax7 /
**`--moe-cache-cpu-share=1.0`（1.0 官方 tuning 脚本推荐值仍是 0，印证我们）** /
reasoning-budget 硬切 / apply_patch / 工具结果去重 / 思考硬切 / 改写历史思维链

### 3.3 结构性限制（升级解决不了）
- 8G 显存 + 21.28GiB 模型 → 专家 cache 1350MiB、MTP 600MiB、DeltaNet 状态 377MiB 不可压
- 20K 每步 11s 里，模型 forward 只是一部分；harness 注入/审计/Critic 等开销也在里面
- 我们已证"harness 杠杆 > 模型选择/引擎调优"——**引擎升级的收益上限可能不如继续改 scaffold**

## 三·补 两个待盯项的确切状态（一手核实）
- **#29307**：是 PR，**11-22 17:36 UTC 已合并**（merge commit `1014775c`），进入 b126xx nightly，
  **不在 v1.0.0**（v1.0.0 是 11-13）。改 autoparser +6/-4
- **#29949**：**是 Issue（Feature Request）不是 PR**，state=open（10-04 建，11-09 最后更新），
  无 merged_at、无合并版本。作者有实现在分支 `lru-upstream-v3`（commit `c81901a57`）但未开 PR；
  自测称快约 1.5×（未独立验证）。**短期不可能进主线**——记忆里"未合并"的说法据此精确化

## 三·ik 分支（ik_llama.cpp）调研
> 用户追加："同时看ik分支有没有值得跟进的优化"

### ik 定位
ikawrakow 的 llama.cpp fork（2024-06 起），README last updated **2026-11-17**，仍在活跃维护。
核心定位：**fused delta-net（GDN 在 llama.cpp 的叫法）在这里先落地**、MLA/quant repacking/
tensor parallel/MTP/DFlash 也都是它先做。IQ 量化（IQ2/IQ3/IQ4）是它的招牌。

### 架构支持（一手 README 核实）
- **明确支持**：Qwen3.5-MoE [PR 1288]、Qwen3-Next [PR 1266]、Qwen-3.8-Flash-Next [PR 2365]
- **MTP 支持**明写 "Qwen 3.5/3.6 [1698][1745]"——**Qwen3.6 的 MTP 头被点名**
- **fused delta-net** 明写 "for Qwen3-Next and Qwen3.5-MoE"——我们的 DeltaNet 架构同类，
  但 README **没有逐字写 "Qwen3.6-35B-A3B 支持"**——需实测加载确认

### 最相关的社区实测（同配置！）
RTX **4060 Ti 8G** + Qwen3.6-35B-A3B（桌面 4060Ti，非我们的 Laptop 版）：
- 主线 llama.cpp Q4_K_S + q8_0 KV：16k **41.6 t/s** → 163k **26 t/s**（掉 38%）
- **ik_llama.cpp + IQ3_K_R4 + q4_0 KV**：16k **57.6 t/s** → 163k **55.6 t/s**（**完全不掉**）
- 机制：R4 格式为 CPU+GPU 分割重排专家 FFN 权重改善 L3 局部性（3.4bpw，比 Q4_K_S 更小却更快）；
  `-ncmoe 99`（全专家 CPU）+ q4_0 KV → 每 token 固定流 ~11GB 专家权重，与上下文长度无关
- 显存：ncmoe=99 时 4.4GB（余 3+GB），ncmoe=30 时 7.5GB（+8% 速度但没余量）
- ⚠ 数字来自社区推文二手整理，**非独立复现**，且 4060Ti(DDR5 桌面) vs 我们 4060 Laptop(DDR4)

### 跟我们已证伪项的关系（关键）
- 我们证伪的是 `--moe-cache-cpu-share=1.0`（**上游 llama.cpp 的 MoE cache 机制**，
  decode 虚高但端到端慢 2.4×）
- ik 的 `-ncmoe 99` 是**另一套机制**（加载时把专家层放 CPU，不是运行时 cache miss 去 CPU）
  → **不冲突，值得一试**；但要用端到端判据，别被 decode t/s 骗
- 我们已在用 `NCMOE 40`（40 层专家 CPU），ik 案例用 99（全 CPU）——**方向一致，可对比**

### 跟进成本与风险
- 需换量化：IQ3_K_R4 是 ik 专有格式，要把 21.28GiB Q4 换成更小文件（**质量有损**，需 A/B）
- 需重编 ik 分支 + 重打 autoparser 两行补丁（ik 基于较老主线，补丁大概率能套）
- 有已知坑：README 警告 split mode graph + 部分 offload 可能出乱码，需 `-cuda graphs=0`

### 判断
**值得做一次受控 A/B**，但优先级低于"升 v1.0.0 + #29307"——因为：
① 收益数字是二手且硬件不同；② 要换量化格式（质量风险）；③ 我们 NCMOE 40 已在同类路线上。
若 A/B 做：固定 CTX/模型任务集，只换引擎+量化，判据用**端到端墙钟 + 质量评分**双指标。

## 四、诚实标注
- v1.0.0 发布事实、release notes 条目为 GitHub 一手核实；**性能数字**（+11~21% GDN、+55% MTP、+4.3~11% token-aware）均为 PR 作者/社区报告，**无独立复现**
- "中文源称默认端口改 9931"与英文官方 notes 冲突，**标为未核实**，升级前必须实测确认
- 我们本地二进制报 `0.9.0-dev (build 0, commit unknown)`——自编版没嵌入版本信息，b12244 来自项目记忆与备份目录名，非运行时可查
- 未做任何升级实测——本报告是调研，不是说"升级一定更好"
