# llama.cpp 1.0 升级部署 + GDN 补丁测试 + 前后对比（2026-11-23）

> 用户："升级；测试那个补丁；升级完成后看看有没有bug，修好；然后看看前后对比怎么样"

## 一、升级执行（完成）
- **回退点**：`D:/llama.cpp/build/bin/backup-20261123-104843-before-v1upgrade`（9 文件）+ `D:/Brain/_cleanup_20261118/llama-router-preset.before-v1.ini`
- **部署**：`D:/llama-master-src/build/bin/*`（master 94f3af3, ggml 1.0.0, 含 autoparser 两行补丁 + #29307）→ 生产目录
- **校验**：`llama-server --version` = `1.0.0-dev (build 1, commit 94f3af3)`
- **配置**：未改 preset（A/B 已验证兼容）。当前生产链路 health 200，llama-server 2 进程 + dsh 5 进程

## 二、升级后 bug 检查与修复（2 个真 bug）
### Bug 1（致命，启动失败）：`--moe-cache-cpu-share-prefill` 参数不存在
- 现象：RestartDsh 后 llama-server 退出 code=1，日志 `error: invalid argument: --moe-cache-cpu-share-prefill`
- 根因：该参数是**自编 b12244 的本地补丁**（autostart index.mjs:237 注释明说），上游 1.0 没有
- 修复：`D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-llama-server-autostart/index.mjs` 注释掉该参数推送（第 452-455 行），加注释说明回退到 b12244 时要恢复
- 验证：重启后 llama-server 存活、health 200

### Bug 2（性能，隐藏）：生产 env 里 share=1.0（已证伪的伪优化）
- 现象：autostart debug 日志显示 `--moe-cache-cpu-share 1.0`
- 根因：`.env.llama` 里 `LLAMA_35B_MOE_CACHE_CPU_SHARE=1.0` + `_PREFILL=0` 是**自编补丁的"解码1.0/提示0"组合方案**；升级后 prefill 参数没了，变成全局 1.0（我们早已证伪：P5 1013s vs share0 的 418s）
- 修复：`.env.llama` 改 `SHARE=0`、`PREFILL=-1`，加注释说明原因
- 验证：新 server 用 share=0

### 端到端 bug 检查（全部通过，无新 bug）
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

## 三、前后性能对比（受控 A/B，不压缩测试）
### 3.1 纯净 decode（stream 前 128 token，5 次中位）
| 配置 | b12244（旧）| master（新）| 提升 |
|---|---:|---:|---:|
| MTP on | 22.575 t/s | **24.399 t/s** | **+8.1%** |
| MTP off | 19.609 t/s | **21.865 t/s** | **+11.5%** |
- 生产态复测（升级后，生产链路）：**24.174 t/s**（sd 0.959），与 A/B 预期吻合
- prefill：生产日志旧 pid 608-721 t/s → 新 pid 1008-1099 t/s（但受 warm/cache 状态影响大，不作正式结论）

### 3.2 端到端墙钟
因 `min_tokens` 被 /v1/completions 忽略导致早停样本污染，以 decode t/s 为准（e2e 数据存 `D:/Brain/_cleanup_20261118/e2e_*.json`）

## 四、GDN 补丁测试（做了，结论：不采用）
### 4.1 源码获取（纠正之前的误判）
- #31951 "fused AVX2 GDN" 之前判断"没有源码"是**错的**
- 深挖找到上游 **PR #32028**（完整可编译 diff）：改 ggml-cpu.c（workspace per_thread S_v→2*S_v）+ ops.cpp（fast_kda 路径：4 pass→2 pass，AVX2/FMA intrinsics）
- 适配 MSVC：把 `__AVX2__/__FMA__` 改成项目宏 `GGML_AVX2/GGML_FMA`
- 应用到独立副本 `D:/llama-gdn-src`（保留 autoparser 补丁），计划任务编译成功（336/336）

### 4.2 A/B 结果（交叉顺序测试，排除热机效应）
| 顺序 | patch | stock |
|---|---:|---:|
| 第一轮（stock 先）| 24.580 t/s | 23.688 t/s |
| 交叉轮（patch 先）| 24.064 t/s | **25.600 t/s** |
- **后跑的一方总是更快**——明显顺序/热机效应，不是补丁收益
- 理论支撑：NGL=99 时 31 层 DeltaNet 都在 GPU，CPU 不执行 GDN 算子 → 补丁的 fast_kda 路径根本不触发
- **结论：补丁为 CPU-only/大量 CPU offload 场景设计，我们生产配置下无可测收益，不部署**

## 五、踩坑记录
1. 沙箱 nvcc 死锁（35 分钟 CPU 0.08s）→ 所有编译/测试必须计划任务 Interactive
2. autoparser 补丁在新版 `content_before_tools` 匹配 2 处，须限定 tag_tagged 函数体
3. 新版 CLI：`--spec-type`、`--mmproj-offload` 布尔 flag
4. PowerShell `Invoke-WebRequest` 在测试脚本里 health 检测失败（手动 Python urllib 却 1 秒 OK）→ GDN 测试改用 Python runner
5. dsh 运行时会抢占 8081 端口 → 引擎 A/B 前必须先停 dsh
6. PowerShell 数组尾逗号导致解析错误（脚本静默 exit 1）

## 六、诚实标注
- decode t/s 为受控实测（stdev<4%），prefill 受状态影响大未作正式结论
- GDN 补丁交叉测试只有 2 个顺序，不能 100% 排除随机性，但"后跑更快"的模式 + 理论支撑足够支撑"不采用"决策
- 显存余 346 MiB 略低于历史安全线 450，但实测无卡顿；长期需观察
