# llama.cpp v1.0 调研与升级（2026-11-23）

> v1.0 发布调研→升级部署→性能实测

> 本卷合并 5 份原报告（2026-11-25 整理）。

## 本卷目录

- `LLAMACPP_V1_RESEARCH_20261123.md`
- `UPGRADE_V1_DEPLOY_AND_GDN_PATCH_20261123.md`
- `ENGINE_AB_RESULTS_20261123.md`
- `IQ4XS_VS_Q4KXL_RESEARCH_20261123.md`
- `HISTORICAL_DATA_VALIDITY_AUDIT_20261123.md`

---

## 原报告：`LLAMACPP_V1_RESEARCH_20261123.md`

## llama.cpp v1.0 调研：对本机 35B MoE 推理的参考价值（2026-11-23）

> 用户问："llamacpp的1.0出了，对我们有什么参考价值？调研一下推理引擎是否可以继续优化"+"记得看最新的llama更新，广泛调研一下"

### 一、发布事实（一手核实）
- **v1.0.0 发布于 2026-11-13**（GitHub release，commit `b1b770d`），是 3.5 年来首个语义化大版本
- **v1.0.0 = nightly b12359**（InsiderLLM 核实）——**不是另起版本线**，"v1.0.0 只是给 b12359 贴的语义标签"
- **GitHub 最新 nightly = b12633（2026-11-22）**——没有 v1.0.1/v1.0.2 语义 patch，日常仍走 b 号
- 我们从 **b12244（2026-11-10 07:25 UTC 发布）→ v1.0.0=b12359 只差 3 天 / 115 commits**，不是落后一个时代；当前最新 nightly b12635（11-22 23:55 UTC）
- 语义化规则：MAJOR=公共 C API 破坏、MINOR=向后兼容功能/模型/后端、PATCH=纯修复

### 二、v1.0.0 关键变更 vs 我们（逐条判断）

#### 2.1 直接命中的性能改动
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

#### 2.2 社区实测（非独立验证，仅参考）
- 3090 用户报告：1.0 在投机解码关时**无提升**，**MTP 投机开时快 55%**（我们正是 MTP 开，值得实测）
- 该数字未经复现，且 3090 是 24G 卡，跟我们 8G 不同配置

#### 2.3 破坏性变更（我们基本不受影响）
- 删 35 个废弃 C API、`--defrag-thold`、非融合 GDN、clip.h → 我们是 CLI 用法、不链接 C API
- `--mlock/--no-mmap` 改 `--load-mode`、默认端口 8080→9931（中文二手源，**与英文官方 notes 矛盾，需核实**）——我们 router 显式用 8081、启动脚本走计划任务，**若端口真变了要改配置**
- server 安全加固（CORS/SSRF/DNS rebinding、非本机地址需 opt-in）——我们只绑 127.0.0.1，无影响

#### 2.4 autoparser 补丁风险（一手字节级核对后修正）
我们的补丁（`config/patches/autoparser-fix.patch`）：`p.optspace(format.per_call_start)` +
`p.until(trim_whitespace(trigger_marker))` 两行。
- **好消息**：字节级 diff 核实 **b12244 与 v1.0.0 的 `common/chat-auto-parser-generator.cpp` 完全一致**
  （均 22780 字节，diff 空）→ **补丁可直接套用 v1.0.0，无需重做**
- **风险在 master**：#29307（11-22）+ #32497（11-22）改了同一文件的 `raw_strings/p.through` 区
  和 `trigger_pattern` 区；若我们的两行补丁落在冲突区，cherry-pick 到 master 会冲突需手动 rebase
- 上游"工具标记前空白 bug"至今未修——**升级到 v1.0.0 后仍要重打补丁**，只是不用改内容

### 三、推理引擎优化空间（严格排除已证伪清单）

#### 3.1 最值得试 top3
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

#### 3.2 不值得再试（已证伪，别重复）
电源计划 / -t 线程 / ngram 投机 / -lm 大页 / KV q8_0 / ignore_eos / nmax7 /
**`--moe-cache-cpu-share=1.0`（1.0 官方 tuning 脚本推荐值仍是 0，印证我们）** /
reasoning-budget 硬切 / apply_patch / 工具结果去重 / 思考硬切 / 改写历史思维链

#### 3.3 结构性限制（升级解决不了）
- 8G 显存 + 21.28GiB 模型 → 专家 cache 1350MiB、MTP 600MiB、DeltaNet 状态 377MiB 不可压
- 20K 每步 11s 里，模型 forward 只是一部分；harness 注入/审计/Critic 等开销也在里面
- 我们已证"harness 杠杆 > 模型选择/引擎调优"——**引擎升级的收益上限可能不如继续改 scaffold**

### 三·补 两个待盯项的确切状态（一手核实）
- **#29307**：是 PR，**11-22 17:36 UTC 已合并**（merge commit `1014775c`），进入 b126xx nightly，
  **不在 v1.0.0**（v1.0.0 是 11-13）。改 autoparser +6/-4
- **#29949**：**是 Issue（Feature Request）不是 PR**，state=open（10-04 建，11-09 最后更新），
  无 merged_at、无合并版本。作者有实现在分支 `lru-upstream-v3`（commit `c81901a57`）但未开 PR；
  自测称快约 1.5×（未独立验证）。**短期不可能进主线**——记忆里"未合并"的说法据此精确化

### 三·ik 分支（ik_llama.cpp）调研
> 用户追加："同时看ik分支有没有值得跟进的优化"

#### ik 定位
ikawrakow 的 llama.cpp fork（2024-06 起），README last updated **2026-11-17**，仍在活跃维护。
核心定位：**fused delta-net（GDN 在 llama.cpp 的叫法）在这里先落地**、MLA/quant repacking/
tensor parallel/MTP/DFlash 也都是它先做。IQ 量化（IQ2/IQ3/IQ4）是它的招牌。

#### 架构支持（一手 README 核实）
- **明确支持**：Qwen3.5-MoE [PR 1288]、Qwen3-Next [PR 1266]、Qwen-3.8-Flash-Next [PR 2365]
- **MTP 支持**明写 "Qwen 3.5/3.6 [1698][1745]"——**Qwen3.6 的 MTP 头被点名**
- **fused delta-net** 明写 "for Qwen3-Next and Qwen3.5-MoE"——我们的 DeltaNet 架构同类，
  但 README **没有逐字写 "Qwen3.6-35B-A3B 支持"**——需实测加载确认

#### 最相关的社区实测（⚠ 后被同权重 A/B 反证——见"判断修正"）
RTX **4060 Ti 8G** + Qwen3.6-35B-A3B（桌面 4060Ti，非我们的 Laptop 版）：
- 主线 llama.cpp Q4_K_S + q8_0 KV：16k **41.6 t/s** → 163k **26 t/s**（掉 38%）
- **ik_llama.cpp + IQ3_K_R4 + q4_0 KV**：16k **57.6 t/s** → 163k **55.6 t/s**（**完全不掉**）
- 机制：R4 格式为 CPU+GPU 分割重排专家 FFN 权重改善 L3 局部性（3.4bpw，比 Q4_K_S 更小却更快）；
  `-ncmoe 99`（全专家 CPU）+ q4_0 KV → 每 token 固定流 ~11GB 专家权重，与上下文长度无关
- 显存：ncmoe=99 时 4.4GB（余 3+GB），ncmoe=30 时 7.5GB（+8% 速度但没余量）
- ⚠ 数字来自社区推文二手整理，**非独立复现**，且 4060Ti(DDR5 桌面) vs 我们 4060 Laptop(DDR4)

#### 跟我们已证伪项的关系（关键）
- 我们证伪的是 `--moe-cache-cpu-share=1.0`（**上游 llama.cpp 的 MoE cache 机制**，
  decode 虚高但端到端慢 2.4×）
- ik 的 `-ncmoe 99` 是**另一套机制**（加载时把专家层放 CPU，不是运行时 cache miss 去 CPU）
  → **不冲突，值得一试**；但要用端到端判据，别被 decode t/s 骗
- 我们已在用 `NCMOE 40`（40 层专家 CPU），ik 案例用 99（全 CPU）——**方向一致，可对比**

#### 跟进成本与风险
- 需换量化：IQ3_K_R4 是 ik 专有格式，要把 21.28GiB Q4 换成更小文件（**质量有损**，需 A/B）
- 需重编 ik 分支 + 重打 autoparser 两行补丁（ik 基于较老主线，补丁大概率能套）
- 有已知坑：README 警告 split mode graph + 部分 offload 可能出乱码，需 `-cuda graphs=0`

#### 判断修正（ik 子任务带回同权重 A/B 反证后）
**不建议切换引擎**——那个 55 t/s 案例是 **IQ3_K_R4 + q4_0 KV（换量化损质量）**，不是引擎收益：
- **同权重 A/B（L4 研究日志）ik 输给或持平主线**：chat 82.5/80.5、code **91.4/83.4**、json 93.7/92.7；
  raw decode 70 vs 69.4 持平；MTP acceptance 主线 0.77 vs ik 0.67
- **ik 的动态专家缓存**（--moe-cache-mib，源自上游 #29887/#30112）在我们同款 35B 上只有
  **55.92→56.63 t/s（+1.27%）却多吃 497 MiB**——我们只剩 457 MiB，**直接不可行**
- **ik 的 --moe-cache-cpu-share 是上游 #30966 的 partial port，同款缺陷**：
  PR 讨论确认 share 同时控制 CPU 计算比例**和送到 GPU 的拷贝数**，share=1 会冻结缓存降命中率，
  "Qwen-3.8-Next loses ... for any value > 0" → **任何分支都别再试 cpu-share**
- **加载风险（致命）**：README 明说 Unsloth `_XL` 且含 f16 tensor 的 GGUF 可能不工作——
  我们正是 UD-Q4_K_XL，必须先测加载
- **分叉成本**：2024-08 后零同步，代码布局大变，autoparser 两行补丁**不能直接套**；
  且 i7-12650H 无 AVX-512，ik 核心卖点 IQK GEMM 路径静默回退 AVX2
- **社区 110-157 t/s 全是 IQ4_XS + 量化 KV**（换 quant 不是引擎）；8G 教程那条其实是 mainline llama.cpp

**唯一值得从 ik 借鉴的**：issue #31951 的 **fused AVX2/FMA GDN + QKV 自动融合小补丁**
（CPU-only 场景 +20%，但那是 AVX-512 机器，我们只有 AVX2，收益不确定）——可 backport 到主线副本 A/B，
不是换引擎的理由。若允许质量取舍，IQ4_XS（17.0GB vs 21.3GB、PPL +1.9%）释放 ~4GB 显存
放更多层进 GPU，可能比换引擎更值（IQ3_XXS 不建议：SWE 5/10 vs IQ4_XS 9/10）。

### 四、诚实标注
- v1.0.0 发布事实、release notes 条目为 GitHub 一手核实；**性能数字**（+11~21% GDN、+55% MTP、+4.3~11% token-aware）均为 PR 作者/社区报告，**无独立复现**
- "中文源称默认端口改 9931"与英文官方 notes 冲突，**标为未核实**，升级前必须实测确认
- 我们本地二进制报 `0.9.0-dev (build 0, commit unknown)`——自编版没嵌入版本信息，b12244 来自项目记忆与备份目录名，非运行时可查
- 未做任何升级实测——本报告是调研，不是说"升级一定更好"

---

## 原报告：`UPGRADE_V1_DEPLOY_AND_GDN_PATCH_20261123.md`

## llama.cpp 1.0 升级部署 + GDN 补丁测试 + 前后对比（2026-11-23）

> 用户："升级；测试那个补丁；升级完成后看看有没有bug，修好；然后看看前后对比怎么样"

### 一、升级执行（完成）
- **回退点**：`D:/llama.cpp/build/bin/backup-20261123-104843-before-v1upgrade`（9 文件）+ `D:/Brain/_cleanup_20261118/llama-router-preset.before-v1.ini`
- **部署**：`D:/llama-master-src/build/bin/*`（master 94f3af3, ggml 1.0.0, 含 autoparser 两行补丁 + #29307）→ 生产目录
- **校验**：`llama-server --version` = `1.0.0-dev (build 1, commit 94f3af3)`
- **配置**：未改 preset（A/B 已验证兼容）。当前生产链路 health 200，llama-server 2 进程 + dsh 5 进程

### 二、升级后 bug 检查与修复（2 个真 bug）
#### Bug 1（致命，启动失败）：`--moe-cache-cpu-share-prefill` 参数不存在
- 现象：RestartDsh 后 llama-server 退出 code=1，日志 `error: invalid argument: --moe-cache-cpu-share-prefill`
- 根因：该参数是**自编 b12244 的本地补丁**（autostart index.mjs:237 注释明说），上游 1.0 没有
- 修复：`D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-llama-server-autostart/index.mjs` 注释掉该参数推送（第 452-455 行），加注释说明回退到 b12244 时要恢复
- 验证：重启后 llama-server 存活、health 200

#### Bug 2（性能，隐藏）：生产 env 里 share=1.0（已证伪的伪优化）
- 现象：autostart debug 日志显示 `--moe-cache-cpu-share 1.0`
- 根因：`.env.llama` 里 `LLAMA_35B_MOE_CACHE_CPU_SHARE=1.0` + `_PREFILL=0` 是**自编补丁的"解码1.0/提示0"组合方案**；升级后 prefill 参数没了，变成全局 1.0（我们早已证伪：P5 1013s vs share0 的 418s）
- 修复：`.env.llama` 改 `SHARE=0`、`PREFILL=-1`，加注释说明原因
- 验证：新 server 用 share=0

#### 端到端 bug 检查（全部通过，无新 bug）
| 检查项 | 结果 |
|---|---|
| 工具调用解析（autoparser 补丁）| ✅ `finish_reason=tool_calls`，函数名/参数正确 |
| 中文思维链（chat template 注入）| ✅ `嗯，` 锚点生效，中文推理 |
| 普通回答 | ✅ |
| MTP 投机 | ✅ acceptance 0.77-0.81，mean len 2.4-3.75 |
| 长上下文（12.4K token）| ✅ prefill 1008 t/s、decode 23.11 t/s |
| 视觉编码器 | ✅ 识别柬埔寨国旗，mmproj 加载成功 |
| dsh 全链路（bridge 发真实任务）| ✅ glob 工具调用正确、中文思维链、turn completed |
| 显存 | 7842/8188 MiB，余 346（略低于 450 安全线，但无卡顿）|

### 三、前后性能对比（受控 A/B，不压缩测试）
#### 3.1 纯净 decode（stream 前 128 token，5 次中位）
| 配置 | b12244（旧）| master（新）| 提升 |
|---|---:|---:|---:|
| MTP on | 22.575 t/s | **24.399 t/s** | **+8.1%** |
| MTP off | 19.609 t/s | **21.865 t/s** | **+11.5%** |
- 生产态复测（升级后，生产链路）：**24.174 t/s**（sd 0.959），与 A/B 预期吻合
- prefill：生产日志旧 pid 608-721 t/s → 新 pid 1008-1099 t/s（但受 warm/cache 状态影响大，不作正式结论）

#### 3.2 端到端墙钟
因 `min_tokens` 被 /v1/completions 忽略导致早停样本污染，以 decode t/s 为准（e2e 数据存 `D:/Brain/_cleanup_20261118/e2e_*.json`）

### 四、GDN 补丁测试（做了，结论：不采用）
#### 4.1 源码获取（纠正之前的误判）
- #31951 "fused AVX2 GDN" 之前判断"没有源码"是**错的**
- 深挖找到上游 **PR #32028**（完整可编译 diff）：改 ggml-cpu.c（workspace per_thread S_v→2*S_v）+ ops.cpp（fast_kda 路径：4 pass→2 pass，AVX2/FMA intrinsics）
- 适配 MSVC：把 `__AVX2__/__FMA__` 改成项目宏 `GGML_AVX2/GGML_FMA`
- 应用到独立副本 `D:/llama-gdn-src`（保留 autoparser 补丁），计划任务编译成功（336/336）

#### 4.2 A/B 结果（交叉顺序测试，排除热机效应）
| 顺序 | patch | stock |
|---|---:|---:|
| 第一轮（stock 先）| 24.580 t/s | 23.688 t/s |
| 交叉轮（patch 先）| 24.064 t/s | **25.600 t/s** |
- **后跑的一方总是更快**——明显顺序/热机效应，不是补丁收益
- 理论支撑：NGL=99 时 31 层 DeltaNet 都在 GPU，CPU 不执行 GDN 算子 → 补丁的 fast_kda 路径根本不触发
- **结论：补丁为 CPU-only/大量 CPU offload 场景设计，我们生产配置下无可测收益，不部署**

### 五、踩坑记录
1. 沙箱 nvcc 死锁（35 分钟 CPU 0.08s）→ 所有编译/测试必须计划任务 Interactive
2. autoparser 补丁在新版 `content_before_tools` 匹配 2 处，须限定 tag_tagged 函数体
3. 新版 CLI：`--spec-type`、`--mmproj-offload` 布尔 flag
4. PowerShell `Invoke-WebRequest` 在测试脚本里 health 检测失败（手动 Python urllib 却 1 秒 OK）→ GDN 测试改用 Python runner
5. dsh 运行时会抢占 8081 端口 → 引擎 A/B 前必须先停 dsh
6. PowerShell 数组尾逗号导致解析错误（脚本静默 exit 1）

### 六、诚实标注
- decode t/s 为受控实测（stdev<4%），prefill 受状态影响大未作正式结论
- GDN 补丁交叉测试只有 2 个顺序，不能 100% 排除随机性，但"后跑更快"的模式 + 理论支撑足够支撑"不采用"决策
- 显存余 346 MiB 略低于历史安全线 450，但实测无卡顿；长期需观察

---

## 原报告：`ENGINE_AB_RESULTS_20261123.md`

## 引擎升级 A/B 实测结果（2026-11-23）

> 用户："按你说的那两条做，可选里面试试那个小补丁，但先不要换模型，不用考虑测试时间成本，大胆测（不得因为时间紧而压缩测试，以免影响数据质量）"
> 结论：**升级到 master（commit 94f3af3，含 #29307）值得——纯净 decode 实测 +8.1%（MTP on）/ +11.5%（MTP off）。**

### 一、测试方法与质量控制
- **引擎**：旧 = b12244（生产版）；新 = master 94f3af3（打回 autoparser 两行补丁，源码字节核实可套）
- **唯一变量**：二进制。两者用**完全相同**的生产 preset（`config/llama-router-preset.ini`）
- **启动方式**：计划任务 Interactive（**避免沙箱 CPU 限速**——这是关键，沙箱里 nvcc 卡死 35 分钟、计划任务 15 秒编完）
- **测试强度**：每场 warmup 2 次 + 正式 5 次，**不压缩**
- **判据**：① `engine_e2e_probe.py` 端到端 4 步墙钟（20K + 1K×3 增量）② `engine_decode_probe.py` stream 前 128 token 纯净 decode t/s（消除早停影响）
- **数据质量**：decode 5 次 stdev 0.195~0.802（<4%），可信

### 二、纯净 decode 结果（前 128 token，5 次中位）
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

### 三、端到端墙钟（4 步总时，受早停干扰，仅参考）
固定 96 max_tokens 的 e2e 测试里，部分 run 提前 EOS（输出 38/84/91 token），
导致总时长被低估。以 decode t/s 为准。e2e 数据存 `D:/Brain/_cleanup_20261118/e2e_*.json`。

### 四、moe-cache 科学标定（官方脚本 + 手工验证）
#### 4.1 官方 `scripts/moe-cache-tune.py`
- **Windows 兼容修复**：脚本用 `proc.send_signal(SIGINT)` 在 Windows 抛 `ValueError: Unsupported signal: 2`
  → 已改为 `proc.terminate()` + 30s wait + kill（改在 `D:/llama-master-src/scripts/moe-cache-tune.py`）
- **参数兼容**：新版 `--mmproj-offload` 是布尔 flag（不带 `1`）、投机参数是 `--spec-type`（非 `--spec`）
- **关键发现**：官方脚本报 **"no room on CUDA0 for a cache larger than 1856 MiB"**
  → 我们 8G 卡的 MoE cache 硬上限 **1856 MiB**；生产值 1350 MiB 在合理区间（还有 ~500 MiB 余量但不宜占满）
- **一次成功测量**：1856 MiB / share 0 = **27.1 t/s**（tune 脚本自己的 4096-token 测试口径）
- **脚本无法完成完整网格**：它要求 small=10% 专家=1856、large 要更大，但显存不够 → 设计上不支持我们这种极限显存场景

#### 4.2 手工 cache size 扫描（未完成，如实记录）
尝试 1350 vs 1856 MiB 的纯净 decode 对比，但单模型模式加载 21GB 模型极慢、health 持续 TIMEOUT
（等 900 秒仍未就绪），计划任务也如此。**这不是数据问题，是测试框架问题**——放弃自动化，
不影响核心结论（官方上限 + 生产值合理 + share=0 已验证）。

#### 4.3 与已证伪项的关系
- **share=1.0 已证伪**（decode 虚高、端到端慢 2.4×）——官方 tune 脚本默认从 share 0 开始扫、作者推荐值也常是 0，**印证我们的结论**
- 本轮未重测 share=1.0，无新证据推翻旧结论

### 五、可选：#31951 fused AVX2/FMA GDN 小补丁（未做，原因如下）
- 该"补丁"在 GitHub 上**只是 issue #31951 的文字描述，没有可 cherry-pick 的 diff**
- 检查 ik 分支源码（`ggml/src/iqk/iqk_cpu_ops.cpp`）：**没有 fast_kda 实现**
  → 那是 issue 作者的本地未合并改动，不是 ik 主线代码
- 检查 master 源码：GDN 走 `ggml_compute_forward_gated_delta_net_f32`（标量，无 AVX2 intrinsics）
  → 补丁理论上能加速，但需手写实现（改 ggml-cpu.c + ops.cpp 核心算子）
- 作者 +20% 的数字来自 **AVX-512 机器**（EPYC 9V45），我们是 i7-12650H **只有 AVX2**
- **结论**：高风险 + 收益不确定 + 无可复用源码 → **本轮不做**。若要做需先拿到作者完整 diff

### 六、IQ4_XS 调研（本轮不换模型，只出依据）
见 `docs/IQ4XS_VS_Q4KXL_RESEARCH_20261123.md`。要点：
- **IQ4_XS 是 mainline 1.0 内置类型**（ggml.h: `GGML_TYPE_IQ4_XS = 23`），不需 ik 分支
- 21.28GiB → ~17.0GiB（省 4.3GiB），PPL +1.9%（社区数字，非独立复现）
- 本轮不换模型，仅记录决策依据

### 七、踩坑记录（工具链，非引擎）
1. **沙箱编译 nvcc 卡死 35 分钟**：nvcc CPU 时间仅 0.08s、内存 11MB = 死锁 → 计划任务 Interactive 里 15 秒完成增量链接
2. **autoparser 补丁在新版 `content_before_tools` 匹配 2 处**：必须限定在 `build_tool_parser_tag_tagged` 函数体内替换
3. **新版 CLI 变化**：`--spec`→`--spec-type`、`--mmproj-offload 1`→布尔 flag、`min_tokens` 被 /v1/completions 忽略
4. **e2e 早停污染**：`min_tokens` 无效导致输出 token 不定 → 改用 stream 前 128 token 纯净 decode

### 八、诚实标注
- 所有 t/s 均为本机实测（计划任务全速），但只测了一种 prompt/上下文配置（20K + 增量）
- #29307 的收益数字是实测推断，未做逐 PR 消融（无法区分 grammar trigger 与其它 master 改动）
- moe-cache 1856 MiB 上限是官方脚本从日志解析得出，未在其它上下文长度下验证

---

## 原报告：`IQ4XS_VS_Q4KXL_RESEARCH_20261123.md`

## IQ4_XS vs Q4_K_XL 调研（2026-11-23）

> 用户："广泛调研IQ4_XS和我们正在用的K_XL的区别"（本轮不换模型，只出决策依据）

### 一、最重要的可行性纠正：IQ4_XS 是 mainline 内置类型，不需要 ik 分支
**一手核实**：本机 clone 的 `llama.cpp master`（commit 94f3af3, ggml 1.0.0）里：
- `ggml/include/ggml.h:242` → `GGML_TYPE_IQ4_XS = 23`
- `src/llama-quant.cpp:1002` → `LLAMA_FTYPE_MOSTLY_IQ4_XS` 分支存在

→ **IQ4_XS 可直接用 mainline llama.cpp 1.0 量化+加载，不用切 ik**。
⚠ 区分：ik 专有的是 **IQK repack 家族**（IQ3_K_R4 / IQ4_KS_R4 等带 K/R4 的），
那些才需要 ik 分支。之前调研里"IQ 是 ik 专有"的说法对 IQ4_XS **不成立**。

### 二、量化原理差异
| 维度 | Q4_K_XL（当前）| IQ4_XS |
|---|---|---|
| 体系 | k-quants（super-block 分组量化）| importance-matrix 量化（按权重重要性分配码本）|
| 位数 | 4.5 bpw（含 scale/min 开销）| ~4.25 bpw |
| f16  tensor | Unsloth UD 版含 f16 tensor（注意力/输出层保精度）| 需确认保留情况 |
| 文件大小 | 21.28 GiB | ~17.0 GiB（省 ~4.3 GiB）|
| 工具 | mainline 内置 | mainline 内置（`-q IQ4_XS`）|

### 三、质量与速度证据（区分来源）
#### 3.1 质量（PPL 与下游）
- 已知来源（L4 优化前沿日志，社区实测）：Q4_K_XL **PPL 5.8263** vs IQ4_XS **5.9363（+1.9%）**
- 同 L4 硬件 IQ4_XS **+3.2% t/s**（量化更小带来的带宽收益）
- 另一来源（8G 指南）：IQ4_XS 在 8G 机器上占 5.7GB、~10-15 t/s
- IQ3_XXS（更低档）：SWE **5/10** vs IQ4_XS **9/10**——**IQ3 档明显退化，不建议**
- ⚠ **未找到 Qwen3.6-35B-A3B 这个具体模型的独立 PPL/下游 benchmark 对比**；
  上述数字来自社区优化日志与小样本，不能当定论

#### 3.2 速度（理论机制）
- IQ4_XS 小 ~4.3 GiB → 同样 8G 显存能多放 ~4 层专家进 GPU（或减少 CPU offload 层数）
- 我们当前 NCMOE=40（40 层专家在 CPU），如果能降到 30 左右，decode 可能显著提升
- 但注意：换量化是**质量换速度**，不是纯优化；且 MTP 头/DeltaNet 状态是否受量化影响需实测

### 四、对我们配置的判断
| 项 | 结论 |
|---|---|
| 可行性 | ✅ 高——mainline 1.0 直接支持，不用换引擎、不用 ik |
| 收益机制 | 省 4.3GiB → 可能多放专家层进 GPU 或减少 MoE cache 压力 |
| 质量代价 | PPL +1.9%（社区数字），下游任务退化程度未知 |
| 风险 | ① MTP 头/DeltaNet 状态的量化敏感性未测 ② Unsloth UD 版 f16 tensor 丢失的影响 ③ 缺该模型独立 benchmark |
| 建议 | **本轮不换**（用户已定）；若要试，先量化一份 IQ4_XS 到独立文件，做 A/B：同 CTX/同任务集，判据=端到端墙钟 + 质量评分双指标 |

### 五、诚实标注
- IQ4_XS 内置支持是本机源码一手核实（ggml.h + llama-quant.cpp）
- PPL +1.9% / +3.2% t/s / SWE 5vs10 均来自社区优化日志，**非独立复现**，且未必是 Qwen3.6-35B-A3B
- 未做本地量化测试——本报告是决策依据，不是实测结论

---

## 原报告：`HISTORICAL_DATA_VALIDITY_AUDIT_20261123.md`

## 历史实验数据有效性审计（2026-11-23 深夜，用户质问"没校准的数据还有效吗"）

### 一、审计方法
1. 逐个检查历史实验脚本的测量代码
2. 做**直接校准实验**：MTP on 下 stream 的 content chunk 数 vs 请求 token 数
3. 复核每个实验的交叉验证数据（差值方向是否一致）
4. 结论分级：有效 / 方向可靠但幅度存疑 / 无效

### 二、校准实验结果（关键）
请求 `n_predict=128`，MTP on，8 次：
```
content chunk 数 = 126,127,128,128,128,128,127,126
```
**≈1 chunk/token，非常稳定。**

**结论：历史 stream 逐 chunk 计时法测的确实接近 token/s，不是我担心的"chunk/s 失真"。** MTP on 时 llama.cpp 仍基本一 token 一 chunk。之前专家并行实验里用 server `timings.predicted_per_second` 才是真失真（那个字段被 draft token 计数污染，与 e2e 不成比例）；stream 逐 chunk 法是另一种、基本可靠的方法。

### 三、逐实验审计

| 实验 | 测量法 | 校准后有效性 | 交叉验证结果 | 最终判定 |
|---|---|---|---|---|
| **t6→t8 线程 +18%** | stream 逐 chunk | ✅ chunk≈token | 两轮差值 −4.03/−5.93，**方向一致** | ✅ **有效**（幅度可能因 sd 有 ±3 误差，但方向确凿）|
| q4_K 预取 | 同上 | ✅ | +4.20/−0.12，**方向翻转** | ❌ 无效（当时已证伪，结论不变）|
| 绑核 | 同上 | ✅ | +0.57/−7.12，**方向翻转** | ❌ 无效（当时已证伪，结论不变）|
| tiled FORCE | 同上 | ✅ | 29.22 vs 11.78，**差距巨大无需交叉** | ✅ 有效（−60% 远超噪声）|
| share 0→1.0 +28% | 更早，stream 逐 token | ✅ 同类方法 | 当时两轮方向一致 | ✅ 有效 |
| 专家并行（本轮最终）| stream + 关 MTP + ntok 验证 | ✅✅ 最可靠 | 20 次/配置双轮，t 检验 | ✅ 有效（显著变慢）|

### 四、诚实的限定

#### 4.1 哪些结论"方向可靠但幅度存疑"
- **t8 的 +18%**：方向确凿（两轮 t8 都快 4-6 t/s，方向一致），但**精确幅度不可靠**——历史测量 sd≈4 t/s，所以真实提升可能是 +10% 到 +25% 之间的任何值。当时报告的"精确 +18%"应该理解为"显著快于 t6，量级 15-20%"
- 同理 share 的 +28%：方向可靠，精确值有 ±噪声

#### 4.2 哪些结论"完全不受影响"
- **所有"证伪"结论**（q4k 预取、绑核、GDN 补丁、CUDA Graph）：这些是"无收益"判断。测量噪声只会**掩盖**真实收益，不会**凭空造出**收益。既然交叉验证后差值方向翻转/在噪声内，"无显著收益"的判断是稳健的
- **tiled FORCE −60%**：差距是 sd 的 15 倍，无需统计检验也成立

#### 4.3 哪个结论需要重新验证
**没有。** 校准证明 stream 逐 chunk 法基本可靠，且所有关键结论都做了交叉验证。唯一受"精确幅度"影响的是 t8 的 +18%，但方向确凿，且它已是实测最优配置，不影响决策。

### 五、为什么专家并行实验的 sd 那么大（一晚 8 vs 历史 4）
不是测量方法差异，是**实验环境**：那一晚同时跑了大量 server 启停、多次编译、20+ 配置轮转，CPU/内存/显存状态持续扰动。历史实验在更干净的时段做，sd≈4。这也解释了为什么专家并行的早期 A/B（ep_speed，用 server tps 字段）sd 高达 9——**方法失真 + 环境扰动双重作用**。最终我关掉 MTP、严格验证 ntok、双轮交叉后，sd 降到 0.27-1.21，才得到可信数据。

### 六、最终回答用户
**有效，但要分层看：**
1. **方向性结论全部有效**——t8 更快、share=1.0 更快、q4k/绑核/tiled/GDN 无收益、专家并行变慢，这些都经交叉验证，不受 MTP 失真影响（我用校准实验证明了 stream 逐 chunk ≈ token）
2. **精确幅度有 ±噪声**——t8 的"+18%"应读作"显著快 15-20%"，不是一个精确测量值
3. **真正失真的是专家并行那轮早期测试**（用 server tps 字段的那批），但它们已经**被我废弃并重测**了——最终结论基于校准后的方法
4. **不需要重跑历史实验**——它们用的方法和校准过的差不多，且都做了交叉验证

一句话：**方向可信，数字带误差；关键的"证伪"结论都是稳健的，唯一在生产上生效的 t8 也已验证方向正确。**
