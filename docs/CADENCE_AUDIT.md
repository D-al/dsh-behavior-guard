# 自动化频次审计（数据底稿，2026-11-19）

> 本文只记录**可核验的事实**（代码当前值 + `_trace.jsonl` 真实触发数）。
> 科学依据与调整建议见 [CADENCE_REDESIGN.md](CADENCE_REDESIGN.md)（等社区/论文调研合并后写）。
> 数据来源：`index.mjs` DEFAULTS、10 个会话的 `_trace.jsonl`（5538 行，2026-11-17 17:26 ~ 11-18 16:41）。

## 一、代码里的全部频次参数（现状）

### 运行时注入类（有 token 成本）

| 参数 | 当前值 | 触发条件 | 会话上限 |
|---|---|---|---|
| `controlEverySteps` | 8 | 每 8 步 | `maxControlPerSession=24` |
| `mindStateLoopThreshold` | 3 | 跨步重复 3 次 | `maxMindStateInjections=6` |
| `verifyOnStop` | 写后无验证 | 每轮最多 | `maxVerifyOnStopSteers=2` |
| `feedbackMaxInjectPerSession` | 2 | 学习回注 | 2 |
| `maxSkillCardsPerSession` | 2 | 技能卡 | 2 |
| `dangerGuardMaxPerSession` | 5 | 危险操作 | 5 |
| `maxTodoInjectionsPerSession` | 4 | todo 闹钟 | 4 |
| `maxPresentGatePerSession` | 2 | 交付闸门 | 2 |
| `noTodoStepThreshold` / `staleStepThreshold` | 4 / 5 | 无 todo / todo 陈旧 | — |
| `maxInjectionsPerTurn` / `maxInjectionsPerSession` | 1 / 4 | 全局注入预算 | 4 |
| `sharedMaxPerTurn` | 3 | 每轮共享预算 | — |

### LLM 调用类（有金钱/时间成本，每次 10-20s）

| 参数 | 当前值 | 触发条件 | 会话上限 |
|---|---|---|---|
| `auditEverySteps` | 8 | 每 8 步 | — |
| `auditEveryStepsAnomaly` | 4 | 异常时每 4 步 | — |
| `auditEvidenceRounds` | 2 | 审计证据轮数 | — |
| `maxCriticPerSession` | 2 | present 前 | 2 |
| `maxPlannerCheckPerSession` | 1 | 规划检查 | 1 |
| `jsonRetryTimes` | 1 | JSON 解析失败 | — |

### 旁路类（零运行时 token）

| 机制 | 频率 | 说明 |
|---|---|---|
| `learn_watcher.py` | `INTERVAL=30s`；低频诊断每 30 轮≈15 分钟 | 心跳日志每 30s 一条 |
| `freeze_watch.py` | `POLL=8s`、`STUCK_SEC=120s`、`COOLDOWN=300s` | 真冻结才重启 |
| `gpu_engine_guard.py` | `GG_POLL=1.5s`、`SUSTAIN=3`、`COOLDOWN=20s` | 引擎争抢时降帧 |
| 压缩 | `thresholdRatio=0.55`（54K） | retain 16384 + headroom 16384 |

## 二、真实触发数据（5538 行 trace）

全局分布：

| 机制 | 次数 | 占比 | 有无 LLM |
|---|---|---|---|
| tool_call | 3249 | 58.7% | — |
| tool_result | 1457 | 26.3% | — |
| fep_cycle | 325 | 5.9% | 无（只记 trace）|
| llm | 212 | 3.8% | **有** |
| control_turn | 139 | 2.5% | 无（零 LLM）|
| skill_card | 71 | 1.3% | 无 |
| mind_state | 43 | 0.8% | 无 |
| verify_on_stop | 21 | 0.4% | 无 |
| crit_hit | 13 | 0.2% | 无 |
| learn_feedback | 8 | 0.1% | 无 |

LLM 调用按用途：audit 82、corrector 72、critic 52、planner 6 —— **共 212 次**。

### 重点会话 s1（3057 步，占全部工具调用的 94%）

| 机制 | 次数 | 折算频次 | 观察 |
|---|---|---|---|
| LLM 调用（audit 71 + corrector 65 + critic 52）| **188** | **每 16 步一次** | 长会话最重成本 |
| control_turn | 126 | 1/24 步 | ⚠ **注意**：trace 的 `step` 每轮 turn/start 重置（实测在 0-8 循环），`controlTotal` 是 state 级会话累计；此 126 次可能是同一 sid 多轮/旧 sid 复用所致，**不能据此推断上限掐断** |
| fep_cycle | 314 | 1/9 步 | 最高频，但零 LLM |
| mind_state | 40 | 1/76 步 | — |
| skill_card | 63 | 1/48 步 | — |
| verify_on_stop | 19 | 1/160 步 | — |
| learn_feedback | 0 | — | 长会话期间学习回注未命中（旁路 watcher 去重/无新沉淀）|

## 三、从数据直接可见的问题（不含外部理论）

1. **（已排除）控制回合上限掐断**：初看 s1 的 126 次 control_turn 恰好 = 上限 24 的倍数，怀疑被掐断；核实后 `step` 每轮重置、`controlTotal` 按 state 累计，126 次是"多轮累计"而非单会话超限。**此项不是问题**，但暴露 trace 缺少 `turn` 字段，无法从数据直接区分"跨轮"与"跨会话"——建议后续补记。
2. **LLM 审计密度过高**：188 次 audit/corrector/critic 对 3057 步 = 每 16 步一次，每次 10-20s。若按 15s/次算，s1 仅 LLM 机制就花 ~47 分钟。需要核实这些调用的边际收益。
3. **`auditEverySteps` 与 `auditEveryStepsAnomaly` 双轨**（8 / 4）但 trace 里 audit 82 次集中在 s1——尚无法区分是正常轨还是异常轨触发，需要加 trace 字段才能判断。
4. **学习回注在最长会话里 0 次**：`learn_feedback` 全局仅 8 次且不在 s1——学习闭环对正在跑的长任务**没有实时反馈**，只有跨会话的沉淀。
5. **FEP 每 9 步一次但只记 trace**：符合 ADR-0017"学习信号不占注入通道"的设计，但需确认 B 段 watcher 真的消费了这 325 条（目前 `new_hits=0 new_outcomes=0`，说明是消费后的稳定态）。

> 待调研合并：社区/论文对反思、审计、巩固、压缩、注入频率的实验数据，见 [CADENCE_REDESIGN.md](CADENCE_REDESIGN.md)。
