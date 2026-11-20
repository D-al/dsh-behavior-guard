# 承重 bug：frame_limiter 的 SLOTS 缺 model 参数（2026-11-20 20:55）

> 用户报告："dsh 窗口占用了视频核心，导致 CUDA 核心和 Copy 核心没法用了。"
> 这是真实的性能阻塞，不是幻觉——诊断和修复记录如下。

## 1. 诊断（证据分层，不用聚合 util%）

| 指标 | 故障值 | 健康值 | 判据 |
|---|---|---|---|
| 聚合 util | 100% | 23-32% | **骗人**（3D 满载也会 100%）|
| 显存带宽 util | 1% | 20-27% | 真判据 |
| 功耗 | 25.3W | 37-46W | 真判据 |
| pmon llama SM | 99% | 34% | 99% + 低带宽 = **CUDA spin-wait 等 Copy 喂数据** |
| pmon llama MEM | 0% | 24% | Copy 引擎被 3D 抢占 |

结论：3D 引擎（UI 渲染）抢占 Copy，CUDA 核心空转等待——用户描述完全准确。

## 2. 根因（一行代码）

`frame_limiter.py:48`：

```python
SLOTS = "http://127.0.0.1:8081/slots"     # ❌ router 要求 model 参数
```

路由模式下 `/slots` **必须带 `?model=<已加载模型>`**（这是项目记忆里的铁律，脚本漏了）。
无参数时 router 返回 `{"error":{"code":400,...}}` → `is_processing()` 的
`any(bool(s.get("is_processing")) for s in slots)` 遍历的是 dict 的 key 字符串 → 恒为 False
→ **frame_limiter 永远认为"没在推理"，永远不降 3D 进程的帧**。

讽刺的是：我记忆里明确记着"路由模式下 /slots 必须带 model"，但实现脚本时漏了——
**知道规则 ≠ 每一处都落实**。

## 3. 修复

三份副本同步改（生产 + publish 两处 + 行为守卫 tools 副本）：

```python
SLOTS = "http://127.0.0.1:8081/slots?model=Qwen3.6-35B-A3B-UD-Q4_K_XL"
```

重启 frame_limiter（旧 pid 80004 → 新 pid 22020，参数 `--apply --parent-pid <dsh> --fresh`）。

## 4. 效果（实测）

- 聚合 util 100% → 23-32%
- 显存带宽 1% → 20-27%
- 功耗 25.3W → 37-46.7W
- llama SM 99% → 34%、MEM 0% → 24%（Copy 恢复供数）

推理从 spin-wait 恢复为健康执行。

## 5. 沉淀

- **判据铁律重申**：不要用聚合 util% 判推理；用 Copy 引擎 + 显存带宽 util + 功耗。
- **新卡需求**：这是"代码存在但参数错导致机制静默失效"的典型——和今天开过的
  A1_7（评审机制可观测性）同类。frame_limiter 日志只有 `start` 没有 `THROTTLE`/`sample`，
  说明它缺少"自检失败"的可见信号。应给 A1_7 或新卡加一条：
  **关键机制必须有 heartbeat/自检日志**（如 `is_processing probe ok/fail`），
  否则静默失效几周都没人发现（本次从 14:54 启动到 20:55 发现，静默 6 小时）。
- **最小化 dsh 窗口无效**：我试过 `bridge.mjs minimize`，指标无变化——真凶不是 dsh 窗口，
  是 frame_limiter 失效导致所有 3D 进程都没被限速。

## 6. 系统性排查（避免过度归因）

我一度以为"所有承重脚本都漏了 model 参数"，实测纠正：
- ✅ `freeze_watch.py`（看门狗）和 `gpu_engine_guard.py`（GPU守护）**是对的**——它们先调
  `loaded_model()` 从 `/v1/models` 拿模型名，再拼 `?model=`（freeze_watch:40-48 / guard:124-134）
- ❌ 只有 `frame_limiter.py` hardcode 了裸 URL
- ⚠️ `live_trace.py`/`stall_sampler.py`/`sweep.py`/`final_check.py` 等诊断基准脚本确实裸调，
  但它们不是承重守护，静默失效影响有限（记为低优先级清理）

**结论**：这是单点 bug，不是系统性崩塌。但教训普适——凡是 hardcode 路由 URL 的地方都要过一遍
"router 模式必须带 model"的检查清单。

## 7. 降帧效果实测：EcoQoS 调用成功，但对 Chromium gpu-process 实质无效（21:08）

用户问"同时降帧是否有效果？"——做了证据链核查，答案：**机制通了，效果没有**。

| 环节 | 状态 | 证据 |
|---|---|---|
| frame_limiter 识别推理 | ✅ 修复后正常 | SLOTS 带 model → is_processing=True |
| THROTTLE 调用 | ✅ 成功 | 21:01:22 `THROTTLE pid=10756 WorkBuddy eng3d=66.0`，EcoQoS 返回 ok |
| 3D 占用下降 | ❌ 几乎无 | 66% → 62.5%（仅 -3.5pp）|
| 进程优先级 | ❌ 未被节流 | WorkBuddy gpu-process 仍 `AboveNormal`，51 线程优先级 10-13 |
| GPU 恢复 | 归因 cancel | 100%/25W → 5%/20W 是 cancel 停推理带来的，非降帧 |

**机制层面的两个洞**：
1. **EcoQoS 对 Chromium gpu-process 无效**：WorkBuddy 的 `--type=gpu-process` 是高优先级渲染线程，
   Windows EcoQoS（ProcessPowerThrottling）对这类进程的帧率节流效果有限。
2. **降帧只做一次、永不复查**：frame_limiter 把 pid 加入 `active` 后，后续推理轮次不再重新调用
   `eco_qos(pid, True)`（21:01:22 之后 7 分钟无新 THROTTLE，即使新会话又开始推理）。
   如果第一次降帧无效，就永远无效。

**结论**：`min_3d` 限帧这条路在当前 WorkBuddy+Chromium 环境下走不通。
真正能释放 Copy 引擎的是**减少可见窗口合成量**（dwm 35% 是合成所有窗口）——但这与"我在 WorkBuddy 里观察"矛盾。
实用策略：推理期把 dsh/浏览器最小化、避免高频 IDE 操作；重负载用计划任务跑（沙箱派生进程已被 CPU 限速的记忆也印证这点）。

**待优化**（可开卡）：frame_limiter 应加"降帧效果回读"——采样 THROTTLE 后 3D 是否下降，
若 N 轮无下降则升级手段（设 ProcessPriorityClass=Idle 或记 WARN），而不是假装降过就算数。
这又是"机制存在 ≠ 效果达成"的典型——和今天 A1_7（评审可观测性）同类。
