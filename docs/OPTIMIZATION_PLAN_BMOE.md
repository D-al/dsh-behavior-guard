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
