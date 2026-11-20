# 函数外置模式（2026-11-21 建立，供 agent 自己复用）

> 目标：让 agent 能安全地自修改——把 14 个嵌套函数逐步外置成"纯函数 + 单测 + 内联"三段式，
> 每次改动都有机器可验的等价证据，而不是靠人肉小心。

## 三段式模式（stateOf 之外的示范：taskProfile）

**第一步：外置纯函数** → `tools/task_profile.mjs`
- 无副作用、无外部依赖、只吃参数返回结构
- 顶部注释写明"为什么外置"（根因）+ 设计原则（确定性/零 LLM/fail-closed）

**第二步：写单测** → `tools/test_task_profile.mjs`
- 覆盖正常/边界/失败三类
- 每个断言是真行为断言，不许 `|| true` / `>=0` 恒真（今晚抓到 6 处这类假绿）

**第三步：内联到 index.mjs**（同内容）
- 插件加载路径在 node_modules，相对 import 会指错——必须内联
- 单测文件作为"规范副本"，内联版必须与它逐字一致（人工 diff 一次）

**第四步：动态集成测试** → `tools/test_task_profile_integration.mjs`
- 不只测纯函数，要测"接入守卫后行为真的变了"
- 本例：只读任务守卫注入 0 次（真对照）

## 为什么内联而不是 import

index.mjs 是 dsh 插件，运行时从 `D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs` 加载。
相对 `./tools/xxx.mjs` 会解析到 node_modules 内的副本——三副本不同步的老问题会让内外版本不一致。
**内联保证唯一真相；tools/ 版本是规范+测试载体。**

## 剩余函数外置清单（agent 可自己按模式做）

| 函数 | 行号 | 依赖注入 | 难度 |
|---|---|---|---|
| `stateOf` | ~810 | states / trace / appendOutcome / appendPendingLearn | 高（4 依赖）|
| `buildTrailText` | ~1213 | 无（纯）| 低 ← 建议先做 |
| `collectCorrectorInput` | ~1414 | s.trail | 低 |
| `formatCorrection` | ~1554 | 无（纯）| 低 ← 建议先做 |
| `formatExecutorResult` | ~1599 | 无（纯）| 低 ← 建议先做 |
| `guardDecide` | ~1616 | cfg / state | 中 |
| `callLLM`/`runAudit`/`runCritic` | ~1346+ | trace / cfg / rubric | 高 ← 最后做 |

建议顺序：先 3 个"无依赖纯函数"（buildTrailText / formatCorrection / formatExecutorResult），
每个走完四步再下一个。每步 commit 可单独回滚。

## 黄金基线

`data/baseline/trace_pre_refactor_20261121.jsonl`（3.5MB）+ `trace_report_pre_refactor.txt`。
每个函数外置后跑对照，确认 trace kind 分布与基线一致（不能只看单测全绿——今晚证明单测会假绿）。
