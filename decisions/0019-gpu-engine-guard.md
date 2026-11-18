# ADR-0019：GPU 争抢用引擎级签名检测 + EcoQoS 优先，不动 Electron 启动参数

- 状态：accepted
- 日期：2026-11-19
- 决策者：项目所有者提出问题，调研给出证据后采纳

## Context（背景）

单 GPU（RTX 4060 Laptop 8G，无核显）环境下，打开 dsh 或 WorkBuddy 的 Electron 窗口会导致 `3D` 引擎 100%+、`Copy` 掉 0、llama.cpp 的 MoE 专家换入 stall、推理停滞；最小化即恢复。聚合 GPU util% 无法诊断此事（空闲 3D 也报 100%）。已有"发送消息后自动最小化"是静态的，无法覆盖"用户主动开窗"的场景。

调研（WebSearch + GitHub）发现：Electron 的 `--disable-gpu` / `--use-gl=swiftshader` 等启动参数在本场景**被实证证伪甚至反效果**（[Electron issue #50469](https://github.com/electron/electron/issues/50469)）；而 Windows 分引擎性能计数器（`Get-Counter '\GPU Engine(*)\Utilization Percentage'`，路径含 `pid_XXXX` 与 `engtype_3d|copy|cuda`）能精确定位争抢进程。

## Decision（决定）

1. **判据用引擎级签名**，不用聚合 util%：`is_processing && 3D≥85% && Copy≤2%` 连续 N 次。本机已实测计数器可读、可按 pid 定位。
2. **动作分三级**：L0 驱动层限帧 + 显存余量（NVIDIA Max Frame Rate 20-30 / moe-cache 1350→1024）→ L1 **EcoQoS 效率模式**（窗口保持可见，Chromium 自动降帧，已实测 API 可开关）→ L2 最小化兜底。推理结束后自动撤销。
3. **不修改 Electron 启动参数**（已证伪），不用 `SetWindowDisplayAffinity` / `SetPriorityClass` 等无效手段。
4. 守护逻辑落为 `tools/gpu_engine_guard.py`，先进 dry-run 验证误报，再启用动作；所有动作写 `_gpu_guard.jsonl` 审计。
5. 方案文档 `docs/GPU_ENGINE_GUARD.md`，与 autostart 库的显存参数调整分开记录（前者是运行时守护，后者是启动配置）。

## Consequences（后果）

- 正面：覆盖"用户主动开窗"这一静态最小化管不到的场景；EcoQoS 档保持窗口可见，不打断用户交互；判据基于引擎级事实，不会因聚合 util% 误报。
- 负面：EcoQoS 对 Chromium 帧率的实际压制幅度因应用而异（已验证 API 生效，但未在满载场景端到端量化）；最小化档仍会打断交互；驱动限帧需用户手动设一次（无法脚本化，GUI 配置）。
- 验证：`--selftest` 三项全过（计数器读取 / 判据逻辑 / EcoQoS 开关）；dry-run 空闲期无动作；启用后 Must-A/B：前台开窗 + Get-Counter 看 3D 下降、Copy 恢复、decoded 推进、功耗 25-40W。
