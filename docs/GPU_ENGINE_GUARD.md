# GPU 3D/Copy 争抢：诊断与主动降帧（2026-11-19）

> 现象：dsh 或 WorkBuddy 窗口一打开/前台显示，`3D` 引擎飙到 100%+、`Copy` 掉到 0、本地 35B 推理停滞；最小化即恢复。
> 环境：单 GPU（RTX 4060 Laptop 8G，无核显）+ WDDM + Electron UI + llama.cpp MoE（CPU 专家 + GPU 热缓存）。

## 一、根因（有证据）

1. **WDDM 多引擎 + 前台优先级**：DWM 合成路径（前台窗口）是内核调度器的高优先级队列；llama.cpp 的 CUDA compute/memcpy 是后台批处理低优先级。窗口一开，3D 合成抢占引擎时间片和**显存带宽**。
2. **Copy 引擎是 MoE 的命脉**：`--n-cpu-moe 40 --moe-cache-mib 1350 --moe-cache-cpu-share 1.0`（解码批）意味着每 token 都要在 CPU↔显存换专家权重，依赖 Copy 引擎 + 带宽。带宽被抢 → 专家换入 stall → Copy=0、功耗掉到 ~25W、解码计数不动（**空转，不是真 hang**）。
3. **8G 显存余量仅 430-450MiB 是放大器**：Chromium 为窗口分配 swapchain/纹理，逼近 OOM → CUDA 分配重试自旋。历史冻结复盘（156-224MiB 必卡）印证。
4. **聚合 util% 不可用**：空闲时 3D 也能报 100%。**唯一可信指标 = per-pid 分引擎（engtype_3d / copy / cuda）+ 功耗 + 解码计数是否推进。**

实测本机分引擎计数器可用（PowerShell `Get-Counter '\GPU Engine(*)\Utilization Percentage'`），路径里含 `pid_XXXX` 与 `engtype_3d|copy|cuda`，能定位到具体进程（如 pid 2368=WorkBuddy、1740=dwm）。

## 二、解法分层（按 ROI）

### L0 · 零成本配置（先做，不改任何代码）

| 动作 | 依据 | 代价 |
|---|---|---|
| **NVIDIA 控制面板 → Manage 3D settings → Max Frame Rate = 20~30 FPS**（全局或给 dsh/WorkBuddy 主 exe 单独设）| [Electron issue #50469](https://github.com/electron/electron/issues/50469) 实证该设置确实作用于打包 Electron 应用 | 无；UI 可能略不跟手 |
| **确认 Background Max Frame Rate = Off** | 同上 issue：该值会误伤前台 Electron，且有跟踪 bug（[NVIDIA 论坛](https://www.nvidia.com/en-us/geforce/forums/user/1678416//590979/)）| 无 |
| **`LLAMA_35B_MOE_CACHE_MIB` 1350 → 1024**（autostart 库 env）| 项目自己的冻结曲线：余量 600+MiB 安全，156-224MiB 必卡 | ~-1~2 tok/s，换 ~300MiB 余量 |
| **关 HAGS（硬件加速 GPU 调度）做 A/B** | WDDM 调度从 GPU 移回 CPU，抢占行为改变 | 方向不定，必须实测 |
| CTX 98304 → 81920 | ⚠ **不要单独改**：<83558 会改变压缩触发点，需同步调 compaction headroom（cordis.patch.yml）| 高，暂不做 |

### L1 · EcoQoS 效率模式（窗口保持可见，降帧）

`SetProcessInformation(hProcess, ProcessPowerThrottling=4, {Version:1, ControlMask:1, StateMask:1})`
把抢 3D 的 GUI 进程标记为"效率模式"：窗口**仍在屏幕上、仍可交互**，但 Chromium 检测到低优先级后降低 rAF/timer 频率 → 3D 提交率下降。

- 已用 Python ctypes 实测：对本机 WorkBuddy 主窗口 pid 设置/撤销均 `ok=True, err=0`。
- 这是"把窗口最小化"和"什么都不做"之间的中间档——**用户能看见窗口，但 GPU 不再被它拖垮**。
- 源码：`tools/gpu_engine_guard.py` 的 `eco_qos()`。

### L2 · 最小化兜底（最有效但打断）

`ShowWindow(hwnd, SW_MINIMIZE)`——把抢 3D 的窗口最小化；推理结束后 `SW_RESTORE` 还原。
现有 `dsh-session-bridge/minimize.py` 是"发送后最小化"的静态版；本脚本是"检测到争抢才最小化"的动态版。

## 三、守护脚本用法

```bash
# 1) 先自检（计数器读取 + 判据 + EcoQoS API）
D:/Python/python.exe tools/gpu_engine_guard.py --selftest

# 2) 先 dry-run 观察误报（推荐先跑 1-2 天，看 _gpu_guard.jsonl 里 ACTION 是否只在真卡时出现）
D:/Python/python.exe tools/gpu_engine_guard.py --dry-run --verbose

# 3) 确认无误报后启用动作
D:/Python/python.exe tools/gpu_engine_guard.py --apply
#   如 EcoQoS 效果不好：--apply --no-eco（只用最小化）
```

判据（可用环境变量调）：`is_processing=true AND 3D≥85% AND Copy≤2%` 连续 3 次（默认 1.5s/次）→ 动作；
推理结束后 2 次空闲 → 撤销 EcoQoS / 还原窗口；动作冷却 20s。
环境变量：`GG_POLL` / `GG_HIGH_3D` / `GG_LOW_COPY` / `GG_SUSTAIN` / `GG_COOLDOWN` / `GG_MIN_IDLE`。

审计日志：`bench/_gpu_guard.jsonl`（每条含 ts/ev/pid/eng3d/copy/action）。

**建议常驻**：仿照 `Startup/FreezeWatch.vbs` 加一个 `Startup/GpuGuard.vbs` 后台拉起（可选，先 dry-run 验证再挂）。

## 四、已证伪 / 不要试

| 手段 | 结论 | 来源 |
|---|---|---|
| Electron `--disable-gpu` / `--disable-gpu-compositing` 降 3D | **反效果**：打包版 GPU 反飙到 80-100% | [Electron #50469](https://github.com/electron/electron/issues/50469) 实测 |
| `--use-gl=swiftshader` / `--enable-features=UseSoftwareCompositing` | 无效 | 同上 issue 明确测试 |
| `--disable-frame-rate-limit` | 反向，解除上限 | flag 语义 |
| `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` | 只防截图，仍参与合成渲染，不降负载 | [MS Learn](https://learn.microsoft.com/windows/win32/api/winuser/nf-winuser-setwindowdisplayaffinity) |
| `SetPriorityClass` 提 llama 优先级 | 只影响 CPU 调度，不改 GPU 引擎；且已用 `--prio 2` | Win32 语义 |
| `nvidia-smi -c EXCLUSIVE_PROCESS` / CUDA MPS | GeForce+WDDM 基本不可用，llama.cpp 无对应开关 | 领域常识（推测）|
| 给 dsh 设 Background Max Frame Rate | 误伤前台 Electron + 跟踪 bug | Electron #50469 / NVIDIA 论坛 |

## 五、验证清单

改任一项后：前台开 dsh 窗口 → `Get-Counter '\GPU Engine(*)\Utilization Percentage'` 看 3D 是否下降、Copy 是否恢复 →
`freeze_watch.py --verbose` 看 decoded 是否继续推进 → 功耗是否维持 25-40W。三者同时正常才算生效。

相关：[ADR-0019](../decisions/0019-gpu-engine-guard.md) · [MANUALS 说明书](MANUALS.md) · [autostart 库](https://github.com/D-al/dsh-llama-server-autostart)
