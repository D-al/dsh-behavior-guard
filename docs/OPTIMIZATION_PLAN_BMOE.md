# BigMoeOnEdge 可抄项落地方案（2026-11-25）

> 前提：35 tok/s 不可比（见 BROAD_RESEARCH 第十八/十九部分）。本方案只针对**有同卡数量级证据**的两条路线。
> 铁律：任何"加速"必须端到端验证（share=1.0 历史反转就是 decode t/s 骗人的教训）。

## 0. 前置条件（必须先解决，否则基线漂移）

### 0.1 两个 build 的陷阱（本次新发现）
- **生产**：`D:/llama.cpp/build/bin/llama-server.exe`（11-23 10:48，autostart DEFAULT_DIR 写死）
- **测速**：`D:/llama-gdn-src/build-gdn/bin/llama-server.exe`（11-23 11:27，ep_speed.py 写死）
- 同为 94f3af3 源码但**四个 DLL 哈希全不同**（llama.dll 47e95c48 vs 76a6d96f 等）
- **结论：所有 A/B 必须固定同一个 build**；建议在 ep_speed.py 加 `--exe` 参数显式指定，
  默认改成与生产一致的 D:/llama.cpp/build/bin。

### 0.2 单一变量原则
每次只改一个参数，顺序按下面 1→6；每步跑 ≥5 次中位 + 端到端 agent 步耗时。

## 1. 引擎能力核实（部分完成）

| 项 | 支持 | 入口 | 备注 |
|---|---|---|---|
| `-ot exps=CPU` | ✅ | CLI `-ot` / env `LLAMA_ARG_OVERRIDE_TENSOR` | arg.cpp:2729 |
| `n_threads_batch` | ✅ | CLI `-tb` | arg.cpp:1510；独立于 `-t` |
| `swa_full` | ✅ | CLI `--swa-full` | arg.cpp:1673；默认 true（llama-context.cpp:4426）|
| `n_outputs_max` | ✅ 内核字段 | CLI 待核实 | 默认 = n_batch=4096（llama-context.cpp:345）→ 白占 logits 预留 |
| `moe_cache_size` / `cpu_share` | ✅ 在用 | CLI | 我们已用 |
| `GGML_CUDA_REGISTER_HOST` | API有/无调用方 | 需加5-10行胶水+重编译 | 单独设env是no-op |
| ClassLRU | ✅ | 内建 | b12214+ 已有，我们 94f3af3 更新 |
| `n_outputs_max` CLI | ❌ 无 flag | 仅 API/common.cpp 内部 | server 固定为 n_batch，需改代码 |
| OpenMP 线程坑 | ❌ 不适用 | — | upstream server 本来就单线程计算，bmoe 的问题是它自己的 planner 引入 |

## 2. 落地项（按风险/收益排序）

### A0（前置，零风险）：统一 build
ep_speed.py 加 `--exe`，默认指向生产 build。

### A7（最低风险，先做）：MTP nmax 5→3
- 依据：bmoe 实测 3 最优；我们 11-24 日志 nmax3=25.09 > nmax5=24.56（已隐含支持）
- 做法：preset 的 spec-draft-n-max 5→3，A/B 5次中位
- 判据：decode ≥24.5 且接受率不降 → 采纳（顺带省显存）
- 回滚：改回 5

### A4（低风险）：n_outputs_max 压到 512
- 依据：默认 4096 = 整个 ubatch 预留 logits，白占显存（bmoe 说 2048 token 上 1.7GiB）
- 做法：**无 CLI flag**（common.cpp:1310 固定为 n_batch）；需改 common.cpp 或 server 启动代码，重编译
- 判据：显存余量增加 ≥500MiB 且 prefill/decode 不掉 → 把省下的 VRAM 给 cache（下一步）
- 回滚：恢复默认


### A1+A2（中风险，核心）：expert 全留 host + 大 GPU cache
- 依据：bmoe 同卡 31.9 → 61.8/77.9 tok/s
- 做法：`-ncmoe 40` → `-ot exps=CPU`（全部 256 专家留 host RAM），
  GPU cache 从 1350 提到实测能放下的最大（目标 ~2079MiB，但必须留 ≥450MiB 安全线）
- 前置：算显存账（dense 3210 + KV 374 + compute 477 + runtime 260 + cache）
- 判据：端到端 20K agent 步耗时下降 + 无冻结（盯 nvidia-smi 余量）
- 回滚：恢复 ncmoe 40 + cache 1350

### A3（最高收益，需改代码）：pinned host buffer
- 依据：upload 9.9→20.6GiB/s，decode +7~27%
- 做法：**单独设 env 是 no-op**（源码无任何调用方），需在 `llama-model.cpp` load_tensors 附近加 5-10 行：
  取 `ggml_backend_get_default_buffer_type()` → cast 到 `ggml_backend_cuda_buffer_type_context` →
  检查 `host_buffer_type` 存在 → `ggml_backend_cuda_reg_host_buffer()` → 重编译
- 依赖/风险：Windows WDDM、load_mode=none（我们整模型预读进匿名内存，与 pinned 路径要额外拷贝）、
  charge-twice bug、需重编译（本机有现成全流程脚本 `tools/build_b12244.py` 可改）
- 判据：upload 带宽实测 + decode + 端到端
- 回滚：环境变量关闭

## 3. 明确不做
- 35 tok/s 数字本身（不可比）
- `--prefetch` / `--route-ahead` / `--expert-dropping`（bmoe 自己也证伪/lossy）
- 换 bmoe 引擎（21GB 常驻不走流式，它的核心优势用不上）
- 投机策略大改（我们和 bmoe 同量级 24.5/27.0 vs 25.2/27.4）

## 4. 状态
子任务调研中：引擎参数支持细节 + pinned host buffer 实现设计。


## 5. 第一路调研后的修正（重要）

- **A5 删除**：OpenMP 线程坑不适用于我们——upstream 94f3af3 的 llama-server 本来就把所有 GGML 调用
  放在同一线程（`server-queue.cpp:240` 注释），bmoe 的 122 线程问题是它自己 planner/calibrator 引入的。
- **A3 升级为改代码**：`GGML_CUDA_REGISTER_HOST` 的 API 在（llama.cpp/build/bin/ggml-cuda.dll 导出
  `ggml_backend_cuda_reg_host_buffer` 等），但源码里没有任何调用方——设环境变量不会有任何效果。
- **A-swa 删除**：Qwen3.6 是 Gated DeltaNet 不是 SWA，swa_full 对我们无效（但当前已是 true，无害）。
- **草稿补丁已就位**：`D:/llama-gdn-src/ggml/src/ggml-cuda/ggml-cuda.patch1` 把 moe cache max_batch
  32→256 并让 cpu_share 随 batch 衰减（就是 tps_ab.log 里 mtpoff 24.88 那批数据的来源）——
  **本地源码是脏树，重编译前必须先 diff 存档**，否则会把草稿带进生产 build。
- **两个 build 差异已定位**：D:/llama.cpp（生产）无此 patch？需 diff 确认；D:/llama-gdn-src（测速）有。


## 6. 两路调研完成后的最终排序（2026-11-25 08:20）

### 删除/降级
- **A5 删除**：OpenMP 线程坑不适用（upstream server 本来就单线程计算）
- **A-swa 删除**：DeltaNet 不是 SWA
- **A3 降级到 P3**：`GGML_CUDA_REGISTER_HOST` API 存在但无调用方（需加 5-10 行胶水+重编译），
  且**我们 `load-mode=none` 与它的"交还 mmap 页"机制冲突**——专家必然两份常驻（~40GB），
  省页缓存收益拿不到，只剩 DMA page-lock 一项。要先切回 mmap（我们当初专门避开，缺页停顿风险）才能拿全收益。
  性价比大降，不建议先做。
- **A4 降级到 P2**：无 CLI flag（子任务误报已纠正），需改 common.cpp 重编译。

### 最终优先级
1. **P0 A0**：统一 build（生产 D:/llama.cpp/build/bin vs 测速 D:/llama-gdn-src/build-gdn/bin，DLL 全不同）——
   不做这步，所有 A/B 数据都不可信。
2. **P0 A7**：MTP nmax 3 vs 5 A/B（**正在跑**，最低风险，已有 11-24 日志隐含支持 nmax3 更优）。
3. **P1 A1+A2**：expert 全留 host + 大 GPU cache（真正的大头，同卡 31.9→61.8/77.9 数量级证据）。
   但注意：bmoe 的 1024 样本 77.9 t/s 靠"cache 填满到 97% 命中"，我们是 agent 场景
   （短增量 prefill + 长 decode），命中曲线不同，必须端到端验证。
4. **P2 A4**：n_outputs_max（需重编译）
5. **P3 A3**：pinned host buffer（需切 mmap，风险大）

### 落地纪律
- 每次 A/B 固定同一 build、同一 prompt、≥5 次中位 + 端到端 agent 步耗时
- 判优必须看端到端，不看 decode t/s 单点（share=1.0 历史反转的教训）
- 生产配置一个字不动，直到 P0/P1 全部有数据

## 7. SSD/内存管理核实（2026-11-25 08:15）

### 7.1 本机存储实况（纠正过时记忆）
- **只有一块 NVMe**：Intel SSDPEKNU512GZ 477GB，逻辑盘 C:249GB + D:226GB
- **E: 盘不存在**（记忆里"E: 1.9T NVMe"过时）
- 模型在 D:/GGUF_Download（NVMe）；实测 D 盘：读 **2420 MB/s**、写 **1183 MB/s**（256MiB + fsync）
- 结论：用户说"SSD 很快"**成立**，比旧记录 394 MB/s 快 6 倍

### 7.2 bmoe 的 SSD 管理机制逐项判定

| 机制 | 源码 | 我们适用？ | 理由 |
|---|---|---|---|
| `--release-mmap`（+46% decode）| session.cpp:1854-1872 | ❌ | unmap 文件 view + close section；我们 load_mode=none 无 mmap view 可释放 |
| `choose_io_lanes` / O_DIRECT | planner.cpp:3672-3705 | ❌ | 针对 expert slice 流式读取测速；我们 expert 全在 RAM，decode 不读 SSD |
| storage probe / headroom probe | hardware-planning.md:567/1076 | 部分 | 算法思想可借鉴（按实测定参数），具体实现针对流式 |
| memory ledger | hardware-planning.md:602 | ✅ 可借鉴 | 算"进程可持有内存"比静态 64GB 估算准，用于定 cache 上限 |
| GPU cache → RAM → flash 分层 | moe-streaming.md | ❌ | 模型 21GB < 64GB RAM，不走 flash 层 |

### 7.3 关键结论：SSD 快无法转化为 decode 提升

**decode 阶段完全不碰 SSD**（21GB 专家常驻 RAM + GPU cache），所以 NVMe 再快也不影响 token 生成速度。
bmoe 的 flash 路径是为"模型 > RAM"（手机/16GB Mac/125B 模型）设计的，我们场景不适用。

**SSD 唯一可能有收益**：一次性加载时间（21GB/2.4GB/s ≈ 9s 理论下限，实测 10-30s 已接近下限）
→ 优化空间很小，不值得投入。

### 7.4 可借鉴的残余项
- **memory ledger 思想**：cache 大小从手调 1350 改成按实测可用内存 + 安全余量算（做成脚本，不改引擎）
- 不做：release-mmap、O_DIRECT、io-lanes、flash 分层（全部流式专属）


## 8. A/B 执行中的坑：prompt 缓存卡死（2026-11-25 08:15）

第一次跑 `tools/nmax_ab.py` 卡死：server 日志停在 `f_sim_best=0.701, f_keep=0.985` + 
`prompt processing progress=0.37`，7 分钟无进展；GPU util 100% 但功耗 **25.8W**、显存 7851MiB
—— 记忆里记录的 WDDM 换页自旋症状（假 100%，实际空转）。

**根因**：`--cache-ram 0` 只关了"新任务启动时存空闲槽"，**没关 LCP 相似触发的宿主 prompt 缓存同步 save/load**
（记忆 2026-11-06 已记录此坑，本次复现）。测速脚本每次用同样的 `FILLER[:20000]` → 前缀相似 → 触发。

**修复**：`tools/nmax_ab.py` 每个请求加 64 字符随机前缀，预热也用不同前缀，避免 LCP 相似。

**纪律**：后续所有 A/B 测速必须：
1. 每次请求用不同前缀（防缓存复用路径）
2. 监控 GPU 功耗（<30W + util 100% = 卡死，立即终止）
3. 设外层 timeout，不让卡死任务挂着占 22GB 内存


## 9. 新增指标维度：首字延迟 / 冷启动（用户 2026-11-25 08:15 强调）

用户指出：**首次加载、首字响应（TTFT）、冷启动也是性能指标**，不能只看 decode t/s。
这个批评成立——bmoe 的核心卖点之一就是"长 prompt 首字 5s vs colibri 近 2 分钟"，
而我们项目此前**从未专门测过 TTFT**（搜索日志/文档零命中），只有 prefill 吞吐（~800 t/s）和加载时间的零散记录。

### 9.1 现状估算
- 20K prompt ÷ 800 t/s ≈ **25 秒冷首字**（不含进程启动）
- 进程启动→health 就绪：历史记录 10-30s（21GB 从 NVMe 读入 RAM，理论下限 21GB÷2.4GB/s≈9s）
- 合计冷启动+首字约 35-55 秒——**这确实是值得优化的指标**

### 9.2 测量能力（本次新增）
`tools/ttft_probe.py`：把冷启动拆成三段分别测
1. 进程启动 → health 就绪（模型加载）
2. 请求发出 → 首个 token 到达（TTFT，含 prefill）
3. 64 token 生成总耗时
- 用流式 `/completion` 抓首 token，随机前缀避开 prompt 缓存卡死坑
- **待 A/B 完成后运行**（当前 8081 被 nmax A/B 占用）

### 9.3 与 SSD 的关系（修正 7.3 的结论）
7.3 说"SSD 快无法转化为 decode 提升"——对 decode 成立，
但**冷启动阶段完全受 SSD 读速约束**。D 盘实测读 2420MB/s 已接近 NVMe 上限，
21GB 加载理论下限 9s，实测 10-30s 有优化空间但不大。
真正可能的大头是 **prefill 阶段**（25s），需看 bmoe 的 prefill-device 机制能否借鉴（调研中）。


## 10. TTFT/冷启动调研结论（2026-11-25 08:20）

### 10.1 首字 5 秒之谜——解开了
bmoe 的"8GB 卡长 prompt 首字 5s"真相（bench-data 原文）：**4.6-4.7k prompt / 873-1212 t/s**，
首字计时**不含加载**。我们 20K prompt @ 800 t/s ≈ 25s 与其同量级（换算 20K 按 1212 也需 16.5s）。
**差距在 prompt 长度，不在 prefill 黑科技。**

### 10.2 最高优先项已核实为"已有"
- **`op_offload` 默认 true**（common.cpp:1772 `!params.no_op_offload`、arg.cpp:2943-2947 default true），
  我们没传 `--no-op-offload` → 已开。bmoe 实测关掉它 20.7k prompt 慢 4.5x 的收益**我们已经拿到**，
  此项收益 = 0。（无需 A/B，源码核实即可定案）
- **UBATCH 2048 << CTX 98304**：已满足。bmoe 实测 graph 宽=context 时首字 **786 秒（13 分钟）**，
  narrow 到 10240 后 8.4 秒——这个坑我们已避开，只需防止回退。

### 10.3 冷启动：常驻进程已是现状
- dsh 的 llama-server 是**常驻服务**（autostart 随 dsh 启动），不是 one-shot → 加载 10-30s 只在重启时付，
  bmoe 的"进程复用省 10-30s"我们已具备。
- `--dense-weights anon` / dense warm-up：我们 load_mode=none 全量常驻，已等价（bmoe 文档自认 "a wash"）。
- 跨 run 持久专家 cache：bmoe 明确 "not built"，无参考实现。

### 10.4 唯一待实测的加载瓶颈：Windows mmap serialisation
bmoe 实测：Windows 上 live mapping 使该文件并发 unbuffered 读串行化，4 lanes 2295-2665 → 895-930 MB/s（2.6x）。
**判据**：若我们加载稳态 ~900MB/s（30s 端）而非 2.4GB/s（9s 端）则命中。
**待做**：`tools/ttft_probe.py` 测 load_s，若 >15s 则需查此坑。

### 10.5 最终判定：TTFT/冷启动维度无低风险大收益
- 所有 bmoe 招牌机制（prefill-device arena / io lanes / dense anon / release-mmap）对我们 RAM 常驻 + 独显 + 20K 场景
  要么已等价、要么不适用、要么工程量极大且上限仅 1.2-1.5x
- 我们 800 t/s 与 bmoe 8GB 卡 873-1212 t/s 同量级，**不在同一个可优化差距上**
- 真正该做的只有：跑 ttft_probe.py 拿真实三段数据（当前空白），确认无隐藏瓶颈


## 11. nmax A/B 失败复盘（2026-11-25 08:22）

第一次：prompt 缓存卡死（f_keep=0.985 触发同步 save/load）→ 随机前缀修复。
第二次（4.6k×3? 实为 20K×3）：`timeout 420` 到期（exit=124），只拿到 1 个有效点
`nmax3 r0=23.38 t/s`；第二请求 ConnectionResetError。
server 日志：`selected slot by LRU, n_tokens=11307` → 即使 `cache_prompt=false` 仍选了上次槽位；
prefill 实测 577-585 t/s（低于 fa_prefill.log 的 806 t/s，因槽内有 11K token 增量路径）。

**根因**：20K prompt 单请求 ~35s prefill + 200 token decode ~8s = ~43s；
每变体 3 次 + 2 次预热 + 4 组交叉 = 20 次请求 ≈ 14 分钟，远超 7 分钟 timeout。
且 server 的 LRU 槽位选择 + 长 prefill 让请求间耦合（不是独立样本）。

**改进方案（下次做 A/B 时）**：
1. 用短 prompt（2K）+ 短生成（64 token），单请求压到 <10s，样本独立性更好
2. 或用 `-np 2` 双槽轮转，避免 LRU 复用
3. 每次变体切换重启 server（已做），但要给足 timeout（≥900s）
4. 核心指标改用**端到端 wall clock + decode t/s 双记录**，不只看 t/s

**当前结论**：nmax 3 vs 5 尚无有效 A/B 数据（仅 1 点 23.38），
不能据此改生产配置。11-24 旧日志 nmax3=25.09 > nmax5=24.56 仍只是单次观察。


## 12. TTFT 实测结果（2026-11-25 08:23，生产 build）

`tools/ttft_probe.py` 首次实测，4.6K prompt × 2 次：

| 指标 | 实测 | 对照 |
|---|---|---|
| 冷启动（进程→health） | **11.7s** | 理论下限 21GB÷2.4GB/s≈9s；接近下限 |
| 4.6K TTFT | **4.94s**（4.99/4.89）| **bmoe 4.7k/873t/s = 5.3s** |
| 64 tok 总耗时 | 4.99s | 首 token 后生成几乎瞬时 |

### 关键结论
1. **同 prompt 长度下我们与 bmoe 首字速度相同**（4.94s vs 5.3s）——
   "首字慢"的印象纯粹来自 prompt 长度（20K vs 4.6K），**不是引擎差距**。
2. **冷启动 11.7s 接近理论下限 9s** → **Windows mmap serialisation 未命中**
   （若命中会是 30s 端/~900MB/s）。10.4 节的待查项关闭。
3. 至此 TTFT/冷启动维度**全部核实完毕，无隐藏瓶颈、无低风险大收益**。

### 唯一仍未测的
20K prompt 的 TTFT（约 25s）——但那是 prompt 长度的客观结果，
按 bmoe 1212 t/s 换算也要 16.5s，差距 8.5s 且硬件不同，不值得为它改配置。


## 13. 落地执行结果（2026-11-25 09:5x）

### 13.1 测速基础设施（已交付）
- `tools/param_ab.py`：短 prompt(2K)+64tok+每变体重启 server+交叉顺序，单请求 <5s（原 43s）
- `tools/confirm_ab.py`：20K 长 prompt 单发确认，wall clock + t/s 双指标
- `tools/build_fingerprint.py`：A/B 前置 build 一致性守卫
- `tools/ttft_probe.py`：冷启动/首字三段测量
- 全部用**生产 build**（D:/llama.cpp/build/bin），commit `4971906`

### 13.2 A7：nmax 3 vs 5 —— 不改生产（短测台误导的铁证）

**短 prompt A/B**（2K×8 次/档，交叉）：
- nmax3: median **34.25** t/s (sd 4.47)
- nmax5: median **28.76** t/s (sd 6.95)
- 看似 nmax3 赢 19%

**20K 长 prompt 确认**（各 2 次）：
- nmax3: tps_med 29.76 / **e2e_med 21.3s** / prefill 577-583 t/s
- nmax5: tps_med 34.72 / **e2e_med 13.2s** / prefill 970-985 t/s
- **完全反转：nmax5 端到端快 40%**

**判定：保持生产 nmax5 不变。** 这正是项目经验"短任务测试台覆盖不到真实场景"的又一实证。
注意混淆变量：prefill 577 vs 970（nmax 不该影响 prefill 40%），说明短/长测的槽位状态不同，
但方向明确——生产现值在真实场景更优，无需变更。

### 13.3 其他项的落地判定（无需执行）
- `op_offload` 默认 true → 收益 0，不改
- UBATCH 2048 << CTX → 已满足，不改
- 冷启动 11.7s / 首字 4.94s@4.6k → 已核实，无瓶颈
- A5/A3/A4 → 调研已否（不适用/冲突/需重编译收益低），不落地


### 13.4 A1：专家布局（全 host `-ot exps=CPU` vs 当前 NCMOE40）
**短 prompt A/B**（2K×6 次/档，交叉）：
- 全 host+ot: median **32.74** t/s (sd 2.88)
- NCMOE40: median **30.34** t/s (sd 4.49)
- 全 host 略优 +8% 且方差更小

**20K 确认**：进行中（关键判据，短测台已骗过一次 nmax）
- 风险：全 expert CPU 时 MTP 层专家也在 CPU，GPU cache 覆盖不到，长 prompt 可能暴露问题
- 判定规则：20K 端到端若未明显优于 NCMOE40 → **不改生产**（保持已调优的 40）


### 13.5 A1 20K 确认结果 —— 指标分裂，不改生产
| 指标 | 全 host (`-ot exps=CPU`) | NCMOE40（生产）|
|---|---|---|
| 20K decode t/s | 33.14 | **39.82** (+20%) |
| 20K 端到端 | **21.2s** (+11%) | 23.6s |
| prefill t/s | 570-579 | 501-509 |

**指标分裂**：decode 说 NCMOE40 赢、e2e 说全 host 赢，无一项双指标同时胜出；
差异在噪声边缘（单次 ±10%）。**判定：不改生产**（保持已调优 NCMOE40）。
这是"decode t/s 是误导性指标"的第三次实证（前两次：share=1.0、nmax 短测台）。

### 13.6 落地执行最终结论
| 候选项 | 短测 | 20K 确认 | 决定 |
|---|---|---|---|
| nmax 3 | 赢 19% | **输 40% e2e** | **不改**（保持 5）|
| 全 host 布局 | 赢 8% | 指标分裂 | **不改**（保持 NCMOE40）|
| cache 1350→更大 | 未测 | 显存余量 457MiB 不足，需同时减 ctx/ub（多变量）| **不做** |
| op_offload / UBATCH / 冷启动 | — | 源码+实测已满足 | 不改 |
| A3/A4/A5 | — | 调研否掉 | 不落地 |

**生产配置全程未改动。所有候选优化均未通过端到端验证。**
