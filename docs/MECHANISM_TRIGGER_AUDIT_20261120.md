# 机制触发效果审计（2026-11-20 20:30）

> 用户："继续让它推卡，你继续观察，着重留意它的表现，以及之前所有功能的触发效果。"
> 方法：证据分层——真实 trace 的 kind 分布（过滤测试 sid）+ 代码 trace 打点 + 时间戳交叉。
> 铁律：文档宣称完成 ≠ 代码实际生效；health 200 ≠ 进程活着；进了 prompt ≠ 评审真的用了。

## 1. 真实 trace 概况

`D:/Brain/workspace/bench/_trace.jsonl`：总 15914 行，过滤测试 sid（s1/b/b7332eb6/budget-4/fb/r）后**真实 2555 行**（测试假数据占 84%——再次印证证据分层必要性）。

真实 sid 的 kind 分布（全时段）：

| kind | 次数 | 说明 |
|---|---|---|
| tool_result / tool_call | 1069 / 965 | 主流程 |
| injection_hit | 281 | 注入检测 |
| fep_cycle | 48 | 预期-观察闭环 |
| llm | 46 | 所有 LLM 调用（含 Critic/Planner）|
| mind_state / control_turn | 36 / 32 | 心智信号 / 控制回合 |
| **crit_hit** | 23 | **CritBank 教训命中（不是 Critic 产物评审）**|
| skill_card | 20 | 技能卡 |
| learn_feedback / review_state | 9 / 8 | 学习队列 / 评审状态 |
| archive_dedup / verify_on_stop | 7 / 5 | 存档去重 / 停止前验证 |
| review_echo / evidence_cited | 4 / 2 | 评审回显 / 证据引用 |

## 2. 今天推卡时段（UTC 12:00-12:30 = 北京 20:00-20:30）的真实触发

| 机制 | 触发 | 证据 |
|---|---|---|
| control_turn（控制回合）| ✅ 2 次 | 12:08:34 / 12:27:24 |
| injection_hit（注入检测）| ✅ 6 次 | 12:21-12:26 连续 |
| review_state / review_echo | ✅ 各 1 次 | 12:11:41 / 12:18:56 |
| crit_hit | ✅ 1 次 | 12:11:41，id=C-001（CritBank 教训，非 Critic 评审）|
| **verify_on_stop** | ❌ 今天无 | 最后 5 次不在本时段 |
| **Critic 第6维「规则-实例一致性」** | ❓ **无法验证** | 见下 |
| **Planner「假设披露」** | ❓ **无法验证** | 见下 |

## 3. 关键缺口：新 rubric 进了 prompt，但没有可观测的触发证据

代码证据：
- `CRITIC_PROMPT`（index.mjs:1381）把 `CRITIC_RUBRIC.dimensions` 全部展开进 prompt——新第6维**确实被送进去了**
- `PLANNER_PROMPT`（index.mjs:1353）同样展开 `PLANNER_RUBRIC.rules`——假设披露**确实被送进去了**
- 但 `runCritic`（1409）和 `runPlannerCheck`（1362）只调用 `callLLM(..., {tag:'critic'|'planner'})`，
  而 callLLM 的 trace 只记 `kind:'llm'`——**没有记录 rubric 版本、判了哪些维度、结论是什么**

后果：无法回答"第6维今天到底有没有拦下一次违规"——这正是用户要的"触发效果"。
按证据分层铁律，这属于"写到了 prompt 但没有独立产物/打点"，不能算真实生效。

## 4. 提议新卡：A1_7「评审机制可观测性」

- what：给 Critic/Planner 调用加专属 trace 打点（rubric_version / dimensions_checked / verdict / 触发的 gate），
  让每个评审机制有可审计的触发证据
- why：今天加的两个维度无法验证是否生效；没有打点就无法做证据分层，只能靠"代码里进了 prompt"自我安慰
- verify：① trace 里出现 `critic_review` / `planner_check` kind ② 打点含 rubric_version 字段 ③ 构造测试触发一次评审后能在 trace 查到
- caveat：别把 trace 写成"存在即成功"——要记录 verdict 和具体维度，否则又是假绿

## 5. 对 agent 表现的观察（同步记录）

会话 session-0428ceab：20:29:47 复活并写 todo 准备"编写 check_verify.py"——但 A1_5 已由 observer 完成并推送。
它不知道外部状态变化，正在重做旧任务。已投递引导消息转向 A1_6（20:31:15），产物做了快照保护
（`D:/Brain/_cleanup_20261118/check_verify.protected.py`）。

这是"会话无共享状态"问题的又一次实证——M10（会话生命周期治理）的必要性再加一条证据。
