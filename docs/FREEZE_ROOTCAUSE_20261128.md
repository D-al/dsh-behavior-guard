# dsh 冻死根因排查与根治（2026-11-28 15:10）

> 用户："选 A，排查根本原因"
> **根因找到并根治：不是 llama 冻死，是 runner 超时太短 + 超时后不 cancel 会话，
> 造成"残留会话抢单槽"的雪球效应。**
> 验证：修复前 45% 冻死 → 修复后 **9/9 全部成功、0 残留**。

## 一、排查方法

三条线并行：
- **llama/router/显存侧**（子代理只读调查）
- **dsh/bridge 事件循环侧**（子代理只读调查）
- 我自己采集现场证据 + 受控复现

## 二、误判排除

### 2.1 不是 llama 崩溃/OOM（llama 侧无罪）

llama-server 全程健康：prefill 644-870 t/s、decode 23-30 t/s，`print_timing` 无 >60s 空档。
无 CUDA 报错、无 OOM、无进程崩溃、A/B 窗口内 0 次模型重建。

我之前看到的 `n_prompt 11808→0` 跳变是**任务正常结束**（`slot release: task 118759`），不是崩溃。

显存余量 166 MiB 低于安全线 450，但 A/B 窗口无 stall 证据——是放大器，不是触发点。

### 2.2 不是 harness 内部并发（harness 无罪）

harness 的 audit/corrector/critic 全是 `await` 串行，无 `Promise.all`。
`voteOnCritic: false`，5 票并发路径未启用。harness trace 正常写盘（成功会话 13 行）。

## 三、真正的根因链条

```
runner 串行发送，但 wait_done 超时设 240s
  ↓
正常任务实际需要 243s+（实测 fc0749：11 步、243 秒、最后 turn/end=aborted）
  ↓  ← 第一层根因：超时阈值太短，误杀正常会话
runner 超时 → continue，但没有 cancel 会话
  ↓  ← 第二层根因：残留会话继续 running=true
每 4 分钟新增一个"僵尸会话"，从不退出：
  11:20 有 3 个 → 11:50 有 9 个 → 13:30 有 14 个
  ↓
僵尸会话继续按自己节奏发 LLM 请求（audit/corrector + 主循环）
  ↓
llama --parallel 1（单槽位），14 个调用者抢 1 个槽
  ↓
请求在队列等待 → fetch 拿不到响应头 → 90s AbortController 超时
  ↓
callLLM 的 jsonRetryTimes=1 再排一次队 → 累计 180s
  ↓
trace 写 {kind:llm, ms:180022, outChars:0, ok:false, error:timeout}
llama 写 "request cancelled while waiting for model"（141 次 cancel task / 211 次排队取消）
  ↓  ← 雪球效应
后续会话连首条 trace 都排不上 → total=0 → 我误判为"冻死"
```

**证据**：
- 21 个"冻死"会话中 12 个有 `ms≈180000, outChars=0` 的 LLM 超时
- 被 runner 放弃的 `cccb40d5` 在 2.5 小时后仍在产生事件（217 条）
- 并发 in-flight 证据：不同 sid 的 180s audit 调用时间重叠（单槽不可能同时执行）
- 13:48 plugin-guard 重启清空残留 → LLM 调用立刻恢复到 20-28s、会话 completed=True

## 四、根治措施（`tools/ab_randomized_runner.py`）

1. **超时后硬 cancel**（核心）
   - 验证过 `bridge.mjs cancel <sid>`：`running=true → accepted:true → running=false`，5 秒生效
   - 新增 `cancel_session()`，超时/卡死必调用，绝不留残留
   - 连续失败 4 次才兜底重启（不再是"连续 2 次就重启"）

2. **超时阈值 240s → 600s**
   - 实测正常任务 11 步需 243s，240s 必然误杀
   - 给足 10 分钟窗口

3. **卡死判据改为 dsh events**
   - 原来基于 harness trace（`_trace_last_ts`），但 trace 可能不落盘/延迟
   - 改为 `_dsh_last_event_ms()` 读 bridge events 的 `step/start` / `tool/call` 时间戳
   - 150s 无新事件才判定真卡死

4. **seed 解析健壮化**：支持字母后缀批次标签

## 五、验证结果

修复后受控跑 9 会话（seed=777777）：

```
[1/9] off        session-97e567 calls=13 fail=5 hs=1 done=True
[2/9] inject-on  session-ac79f1 calls=5 fail=1 hs=0 done=True
...
[9/9] on         session-b63a82 calls=2 fail=1 hs=0 done=True
完成，模式已恢复 off
```

**9/9 done=True，0 取消、0 残留（running 最多 1 = 当前会话）。**

对比修复前：
| 指标 | 修复前 | 修复后 |
|---|---|---|
| 冻死/超时率 | ~45% | **0%** |
| total=0 会话 | 21/37 | **0/9** |
| 残留 running=true | 累积到 14 | **0** |
| 平均耗时 | 240s 固定超时 | 正常完成（8-51 步 trace） |

## 六、附带的认知纠正

1. **"冻死"是误判**：那些会话没死，只是跑得慢（243s）+ runner 提前放弃 + 残留堆积。
   真正的问题是**实验基础设施**，不是模型或推理环境。
2. **llama 单槽位不是缺陷，是放大器**：`--parallel 1` 在正常串行情况下足够；
   只有当 runner 泄漏会话造成 14 路并发时才崩溃。
3. **`_trace.jsonl` 是可靠的**（我中途怀疑 harness 没挂，后发现是自己用 6 位截断 sid 查询，
   而 trace 用 8 位 short sid——查询方式错了，不是数据缺失）。
4. **显存 166 MiB 仍需关注**：虽非本次根因，但低于 450 安全线，是历史 WDDM 换页风险。

## 七、下一步

现在 runner 已稳定，可以重新跑 A 到 n=105/组（约 70 组 × 3 = 210 会话）。
按修复后速度（9 会话 13.5 分钟），约 5 小时可完成。

命令：`python tools/ab_randomized_runner.py 70 <seed> --append`

## 八、产物

- `tools/ab_randomized_runner.py`：`cancel_session()` / `_dsh_last_event_ms()` / 600s 超时 / seed 健壮化
- 本文件：根因链条与证据
- 验证数据：seed=777777 的 9 条记录（全部有效）
