# M3 反模式匹配检测器落地 + 漂移 trace 时机字段（2026-11-22）

> 用户："改成反模式匹配检测器，漂移 trace 加时机字段"

## 一、反模式匹配检测器（观察线，只写 trace）
**模块**：`tools/s6_pattern_guard.mjs` → `detectPatternLock(window, stepsSinceGoal)`
- 信号：最近 12 次工具名中主导工具占比 ≥0.6（工具分布固化）
- **时机门槛**：距上次目标重述 ≥6 步才判（StepShield 教训：高召回但时机随机=没用）
- 与 D1 不重叠：D1 要"同工具失败≥2次"，本检测器不要求失败，只要"固化 + 无目标重述"
- 零 LLM、零网络、纯数组统计

**接入**：index.mjs 的 `agent/pre-step`，state 新增 `toolWindow`(滑窗24) /
`goalRestatedStep` / `lastPatternLockStep`(冷却6步)；用户指令更新 goalRestatedStep，
tool/call push 工具名。命中 → trace `pattern_lock`（dominant/repetition/stepsSinceGoal/window）。
**只写 trace 不 steer**（与 S6 分类器同档），开关 `patternLockTraceEnabled=true`。

## 二、漂移 trace 时机字段
`intent_drift` trace 新增：
- `stepsSinceLastDrift`：距上次漂移的步数（新 state 字段 `lastIntentDriftStep`）
- `stepsSinceGoal`：距目标重述步数
- `controlCount`：第几次控制回合
（tracer 自动补 turn/controlTotal）

## 三、验证
- `test_s6_pattern_guard.mjs` 6/6（真阳/时机门槛/阴性/半锁定/字段）
- `test_pattern_lock_wire.mjs` 4/4（真实事件流打 trace、只写 trace 不 steer、冷却生效）
- `test_intent_drift_trace.mjs` 5/5（含新时机字段断言）
- 门禁 **77/77**；运行版 index.mjs + 新模块 sha 一致（上次门禁盲区教训）

## 四、诚实边界
- 原型里的 `goal_keyword_hit` 信号在真实工具参数里恒≈0，**未纳入**——检测器只看工具分布固化，
  这是"行为层模式匹配"信号，不是"语义目标偏离"信号
- 0.6 阈值和 6 步时机门槛是**经验值**，无标注数据验证；当前只写 trace，
  需用真实 trace 观察命中率和时机后再决定是否收紧或 steer
- "反模式匹配"检测的是论文证实的漂移**主因形态**，但不能替代目标遵循度本身——
  它只是观察线，不是防线
