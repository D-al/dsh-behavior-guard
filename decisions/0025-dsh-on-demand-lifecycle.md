# ADR-0025：dsh 按需生命周期——测试时拉起，测完自动关

- 状态：accepted
- 日期：2026-11-22
- 决策者：用户（显式批准："dsh 不用长期跑着，只需要在要测试的时候拉起它，测试完一段时间后就把它先关了" → 选择"现在就关 + 建自动关停机制"）
- 决策层级：一般决策 G（运维方式，不改判据）
- 支撑决策：ADR-0019（GPU 引擎守护）

## Context（背景）
本机 8GB 显存，dsh + 多个 llama-server 常驻占 ~7.8GB（余 145MiB，逼近换页红线）。
实测并发 3 实例时显存告急、延迟数据被资源竞争污染（KR4 测量已作废那批数据）。
用户决定：dsh 不常驻，按需拉起、测完关掉。

核实事实：
- `RestartDsh` 计划任务 State=Ready，不会自动拉起；已验证可从 interactive session 启动
- `freeze_watch.py` 的 `get_slot()` 在无 slot 时直接 sleep——**不会把主动关停误判为冻死重启**（安全）
- bridge descriptor（`D:/Brain/dsh-data/session-bridge.json`）在 dsh 关掉后**不会自动清理**——
  曾误报 pid=28444 而需核对真实进程；`bridge health` 不可用于判活
- 真实 dsh 进程名是 "DeepSeek Harness"（不是 dsh）——按名查进程时必须用全称
- 会话对象有 `updatedAt`（毫秒），是真实最后活动信号；descriptor mtime 只在启动时写，不可靠

## Options
| 方案 | 做法 | 结论 |
|---|---|---|
| A 维持常驻 | 不改动 | ❌ 占显存、并发污染测量 |
| B 手动 Stop-Process | 每次手动 | ❌ 无协议、易忘、descriptor 误报 |
| C 按需生命周期工具（选中）| start/stop/status/auto-stop 四命令 + ADR | ✅ 有协议、真实判活、空闲自动关 |

## Decision
1. 建 `tools/dsh_lifecycle.py`：
   - `start`：复用 RestartDsh 计划任务（全速 interactive session）
   - `stop`：先优雅 cancel 活跃会话 → 再停 "DeepSeek Harness" 进程；记录日志
   - `status`：**按真实进程判活**，标注 descriptor 是否陈旧（不用 bridge health）
   - `auto-stop --idle-minutes N --once`：空闲 N 分钟后自动关；空闲判据 = 所有会话 `updatedAt` 最大值距今
2. 每次测试前 `start`，测完确认无活跃会话后 `stop` 或交给 auto-stop。
3. Keep：`freeze_watch` 与 `RestartDsh` 不改——已确认对主动关停安全。

## Counter-evidence（反证）
- **最强反对**：关掉 dsh 后会话桥/descriptor 陈旧，其他依赖桥的工具（kr4_from_dsh / kill_switch / 会话推送）会误以为还活着 → 需所有桥调用方先 status 核对。
  对冲：status 提供真实判活；本 ADR 明确"bridge health 不可判活"。
- **第二反对**：auto-stop 用 updatedAt，若 dsh 在跑长任务但会话 updatedAt 不刷新，会误关。
  对冲：stop 前检查 `running_sessions()`，有活跃会话一律不关；只关 0 活跃会话的空闲态。
- **翻案条件**：若按需启停导致测试前启动耗时影响实验可重复性（冷态 prefill 波动），
  需为 benchmark 固定"启动后预热 N 轮"协议，或恢复常驻（重开 ADR）。

## Consequences
- 正面：省显存、消除并发测量污染、关停权可审计（jsonl 日志）。
- 负面：每次测试前要 start（10~70s）；冷态延迟波动——KR4 已用"冷启动排除"处理（ADR-0022）。
- 验证：`dsh_lifecycle.py status` 报真实状态；auto-stop 不误关活跃会话；stop 后进程名查不到。
