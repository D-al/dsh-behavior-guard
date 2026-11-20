# Reflection: M8 — 轨迹 FSM 监控器

> 本卡由 agent 在**新会话**（session-7412cc71）里实现：写 eval_fsm.py、跑出真实 heldout AUC、
> 接入 index.mjs 的 FSM_SIGNAL。观察者只在 4 个卡点做必要提示（产物路径 / TypeError /
> 测试 sid 污染 ×2 / 接入位置），最后的 reflection + 验证 + 提交由观察者收尾
> （agent 卡在重复的 ask_user_question：误以为 node/git 不可用，实际只是它 pwsh 工具路径 ENOENT）。

## 1. 实现内容（agent 主体）

- `tools/eval_fsm.py`：从 `_trace.jsonl` 提取 FSM 局部失败特征
  - 状态机：IDLE → DETECTING_LOOP / PATH_MISTAKE / TOOL_ERR → FAILURE_LIKELY → SUCCESS_RECOVERED
  - 特征：consecutive_repeats（同工具+目标连续重复）、path failure、tool_error_chain
  - 标签：未来 `N_PREDICT_STEPS=5` 步内出现 FAIL 且无有效动作 = failure
  - 按 sid 分组做 held-out（train/test split，seed=42）
- `_fsm_eval.json`：**heldout_auc = 0.8927**（干净数据，≥0.85 判据）
- `index.mjs`（1924-1961 行，SURF-FSM-SIGNAL 白名单内）：
  - 读 FSM 局部信号 + `trace({kind:'fsm_signal'})` 埋点 + 控制回合 `parts.push` 预警文案
  - 只做局部可观察信号，不碰 D1-D5 判定/运行时注入通道

## 2. 卡片两问（真实证据）

### Q1: FSM 预警的误报是什么模式？误报比漏报更伤吗？

**实测数据**：hold-out class balance 为 `fail=25, success=520`——**极度不平衡**（失败样本仅 4.6%）。
AUC 0.8927 是在这个不平衡集上算的。误报模式从样本可见：大量 `sid=session-` 的 OK 样本被打分
（这些是控制回合/非工具步骤，FSM 特征全 0，分数 0.0），低分未触发预警——说明当前误报主要来自
"进入 DETECTING_LOOP 但随后恢复"的序列（SUCCESS_RECOVERED 分支）。

**误报 vs 漏报**：在这个场景下**误报更伤**——FSM 预警进的是控制回合 prompt（软提示），
频繁误报会让模型"狼来了"，反而忽略真实的重复探测信号（D1 已有硬信号，误报会和它冲突）。
所以接入时只做 `parts.push` 文案 + trace 埋点，**不自动拦截、不改 D1-D5 判定**——这是有意的保守设计。

### Q2: 哪些失败签名是 FSM 抓不到、必须交主模型的？

从特征设计看，FSM 只抓**局部、连续、可观察**的模式（连续重复、工具报错链、路径连续失败）。
抓不到的：
- **长轨迹因果归因**（跨越很多步的因果链）——Jev 实测 0.56≈随机，已知交主模型
- **语义层失败**（工具调用语法成功但内容错、目标漂移、用户意图变化）
- **低频单次灾难**（第一次就走错、没有重复信号）——FSM 状态机还停在 IDLE
这些都明确不在 FSM 判据内，由主模型/三角色/Critic 负责。

## 3. CritBank 教训

```yaml
signal: "FSM 评估首版 heldout_auc=0.9058 看似达标，但 training_sessions 混进 b/b7332eb6/budget-4/fb/r 等测试 sid"
lesson: "AI 自评的 AUC 达标必须先查数据卫生——尤其 sid 黑名单必须在最早读 trace 的 loader 阶段整条跳过，而不是 train/test split 后过滤（那样 training_sessions 列表已经被污染）。判据只查数值不查数据来源，'PASS' 可能是假经验堆出来的"
source: "reflection-M8.md + docs/WALK_EXPERIMENT_M8_20261120.md"
trigger: "任何用历史 trace 做训练/评估的卡（M8/L6/L9 意图分类器等）"
action: "跑完评估后核对 train+heldout sid 列表与 test_sids.json 交集必须为空；干净数据上 AUC 仍达标才算完成"
priority: high
```

第二条（环境类）：

```yaml
signal: "agent 声称 node/git 不可用而卡在 ask_user_question，实际是它自己的 pwsh 工具路径 ENOENT"
lesson: "工具调用失败 ≠ 系统缺依赖。agent 应先用另一个工具通道(bash)复测再下'环境不可用'结论，否则会把可完成的卡误报为阻塞"
source: "reflection-M8.md"
trigger: "任何 'command not found / ENOENT' 的工具失败"
action: "换一个执行通道复测(node --version / git --version)，确认系统级不可用再上报"
priority: medium
```

## 4. 验收（全绿）

```
verify M8: 3/3 PASS（eval_fsm.py 存在 / heldout_auc=0.8927 干净数据 / index.mjs FSM_SIGNAL×3）
real_diff_check(SURF-FSM-SIGNAL, 真实改动): allowed=true
node --check index.mjs: OK
self_test 14/14 | run_all 17/17
test_sids 交集: train=∅ heldout=∅（实测确认）
```
