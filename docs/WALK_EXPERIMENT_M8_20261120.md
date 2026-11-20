# 「学会自己走路」第四张卡 M8 实验报告（2026-11-20 16:35–17:20）

> 用户："继续按路线图推进，让它多自己承担工作，你只需在必要时干预，有重大决策弹窗提醒我。"
> 本卡：2 次弹窗（白名单面 / pwsh 卡点），6 次必要干预；实现主体由 agent 在新会话完成。

## 1. 用户决策点（弹窗）

| # | 决策 | 用户选择 |
|---|---|---|
| 1 | M8 判据要改 index.mjs 但无白名单面 | **开新 SURF-FSM-SIGNAL 面**（只允许读 FSM 信号+埋点+文案；禁改 D1-D5/注入通道/阈值）|
| 2 | agent 误报 node/git 不可用、卡在 ask_user_question | **告诉它绕过 pwsh 用 bash 验证+提交**（不跳过验证）|

## 2. agent 自己完成的主体工作（新会话 session-7412cc71）

- `tools/eval_fsm.py`：trace → FSM 局部失败预测器
  - 状态机 IDLE → DETECTING_LOOP/PATH_MISTAKE/TOOL_ERR → FAILURE_LIKELY → SUCCESS_RECOVERED
  - 特征：连续重复、路径失败链、工具报错链；标签：未来 5 步内 FAIL 且无有效动作
  - 按 sid 分组 held-out（seed=42）
- `_fsm_eval.json`：**heldout_auc = 0.8927**（干净数据，过滤测试 sid 后）
- `index.mjs`（1924-1961 行，SURF-FSM-SIGNAL 内）：FSM_SIGNAL 读取 + `trace({kind:'fsm_signal'})` + 控制回合预警文案

## 3. 六次必要干预（诚实记录）

| # | 干预 | 为什么必要 |
|---|------|-----------|
| 1 | 产物路径纠正 | 它写到 default-workspace 而非权威仓库，判据找不到文件 |
| 2 | TypeError 提示 | `set(s[:n_test] for s in [...])` 把 list 放进 set，评估跑不起来 |
| 3-4 | 测试 sid 污染 ×2 | 首版 AUC=0.9058 含 b/b7332eb6/budget-4/fb/r 假经验；提示两次后在 loader 阶段整条跳过，得干净 AUC=0.8927 |
| 5 | 接入位置提示 | 它完成数据后反复读 eval_fsm.py 打转，给了 index.mjs 精确行号 |
| 6 | pwsh 卡点决策 | 它误判环境不可用两次 ask_user_question；弹窗后用户选"绕过 pwsh"，但它仍卡住 → 观察者接管收尾 |

**收尾由观察者完成**：reflection + claim/apply + 验证 + commit/push + lock（代码和判据都是 agent 做的）。

## 4. 一个判断失误（诚实记录）

第 3-4 次 sid 干预后，我读 `_fsm_eval.json` 看到 AUC 仍 0.9055、污染仍在，以为它没修好——
实际是**读到了它重写前的旧文件**（它 17:02 才写新版本）。我直接跑脚本复现后才确认它已经修对。
教训：检查 agent 产物必须看 mtime / 直接跑复现，不能只看一次文件快照。

## 5. 终态（全绿）

```
verify M8: 3/3（eval_fsm.py / heldout_auc=0.8927 干净 / index.mjs FSM_SIGNAL×3）
real_diff_check(SURF-FSM-SIGNAL): allowed=true | node --check OK
self-test 14/14 | a35 4/4 | run_all 17/17 | guard exit 0
push 8e6c407 → 解锁 A1 后 210553b | lock 收敛 | 本地=远端
能力阶梯: A0/A3_5/M1/M8 done，--next 原为 NO_READY_ITEM → 用户授权解锁 A1 → 下一卡 A1
```

## 6. 对"让它多承担"的观察

agent 这次**主体实现能力是够的**：从零写评估脚本、跑真实 AUC、接入主循环，都在无代劳下完成。
卡点集中在两类：①工具路径/环境误判（pwsh ENOENT 就以为系统没装 node）；②完成主体后不知道怎么收尾
（reflection/commit 反复 ask）。**下一步优化方向**：把"收尾清单"固化成卡片的一部分或 skill 卡，
让它完成判据后自动走收尾，而不是卡在 ask_user_question。
