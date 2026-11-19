# 成长卡片设计：让路线图成为 agent 的成长手册（2026-11-20）

> 用户要求：路线图至少要能让 agent 理解**要干什么 / 为什么这样干 / 干了解锁什么 / 对自己什么好处 / 付出什么代价 / 过程中注意什么**，这样它能逐步成长。
> 本文是设计说明；机器可读实体在 `CAPABILITY_LADDER.yaml`，执行器在 `tools/roadmap_check.py`。

---

## 1. 从"任务清单"到"成长手册"的跨越

旧路线图（ROADMAP.md）是给人看的：目标 + 性价比 + 依赖 + DoD + `[ ]` 勾选。agent 读到的是"一列待办"，它不知道**为什么要做、做完对自己有什么意义、哪里会踩坑**——所以它只能被指挥，不会自己成长。

新设计把每个条目变成一张**成长卡片（Growth Card）**，多出 6 个"动机与反思"字段：

| 字段 | 回答的问题 | 对 agent 的价值 |
|---|---|---|
| `what` | 要干什么 | 目标明确，不靠猜 |
| `why` | 为什么这样干（解决什么痛点） | 理解动机 → 遇到变形情况能自己判断，不机械执行 |
| `unlocks` | 干完解锁什么 | 看到自己在能力树上的位置，知道"往上爬"的方向 |
| `benefit_to_self` | 干完对自己有什么好处 | **内在动机**——"我以后处理长任务会更省力"，而非"人让我做" |
| `cost` | 时间/风险/显存/可逆性 | 能自己做性价比取舍，知道哪些值得先做 |
| `caveats` | 过程中要注意的坑（来自历史教训） | 不重复踩已证伪的路 |
| `reflection` | 干完必须回答的反思问题 | **成长的核心**——把一次经验变成可复用的能力 |
| `abort_if` | 什么情况该止损 | 防死循环、防烧光 token |

我在用户列的六项外，加了 **`benefit_to_self`、`reflection`、`abort_if`** 三项——理由见 §3。

---

## 2. 一张完整的成长卡片长什么样

```yaml
- id: M1
  title: "情景检索进主循环"
  what: "把离线 es.exe 检索接进控制回合，长任务里自动注入 top-3 历史经验"
  why: "现在历史经验躺在 trace/日志里，靠人肉搬运；长任务重复踩同样的坑，没有情景记忆的'想起来'"
  unlocks: [L1]                      # 完成 M1 让世界模型有了经验输入
  benefit_to_self: "以后遇到'这个错误我见过'时能真的想起来，少走重复探测的弯路"
  cost: {time: "1-2 天", risk: low, vram: 0, reversible: true}
  caveats:
    - "evidence_cited 埋点必须由本任务一起做，否则判据永远 FAIL（鸡生蛋）"
    - "检索结果只进控制回合，不占运行时注入通道（ADR-0017 教训：FEP 曾挤掉 D5 额度）"
    - "过滤测试 sid（s1/outcome-），否则检索到的是假经验"
  reflection:                        # 干完后 agent 必须回答，沉淀进 CritBank/skills
    - "检索到的 3 条里，有几条真的被后续动作引用了？没被引用的为什么没用？"
    - "有没有一次'想起来的经验是错的/过时的'？怎么写进可控遗忘？"
  abort_if: "注入后 D5 审计额度被挤占，或长任务 token 增幅 >10% 且无质量提升"
  deps: [ground, S1_data, GWT_FEP]
  risk: low
  autonomous: true
  status: ready
  verify: [...]                      # 零 LLM 判据（见 CAPABILITY_LADDER.yaml）
```

---

## 3. 我额外加的三项，为什么重要

### 3.1 `benefit_to_self` —— 给它"为自己成长"的理由

社区经验（MIND_GAPS 的 System 3 价值缺口）：现有 agent 有目标（用户指令）但没有**价值排序**，多目标冲突时靠规则不靠价值。`benefit_to_self` 用一个具体、切身的好处（"你以后会更省力/更少犯错"）替代抽象的"这是个高收益目标"，让 agent 在无人指挥时知道**为什么该爬这一项**。这比 `why`（对项目的意义）更接近 agent 自己的动机。

### 3.2 `reflection` —— "逐步成长"的真正引擎

用户说"这样它可以逐步成长"——**成长 ≠ 完成任务，成长 = 把一次经验变成下次的能力**。所以每张卡片都带一组"干完后必须回答的问题"，答案写进 CritBank（教训）/ skills（技能）/ trace（证据）。这样爬得越高，它积累的可复用经验越多，爬后面的任务就越快——**这是复利，不是线性**。

这也呼应之前调研的结论：`Strategy Genes`（230-token 规则胜过 2500-token skill）、`SkillRL`（成功留演示、失败压一句话规则）。reflection 的产物就按这个格式写：一条触发-动作规则 + 证据出处。

### 3.3 `abort_if` —— 防死循环的安全阀

`Repair–Generalization Gap` 实证：无监管的自主改进会"修好旧任务、弄坏新任务"。`abort_if` 给每项一个明确的止损条件（"token 涨了但质量没涨就停"），配合状态机的 `attempts>=3 → manual-blocked`，避免 agent 在一个不适用的任务上烧光预算。

---

## 4. 难度阶梯（difficulty ramp）—— 让"爬"是循序渐进的

卡片按 `tier` 分层，agent 只能爬**前置全 done 且 risk 最低**的项：

```
tier 0  地基/器官（已完成）        ← 站立点
tier 1  M1/M8 + A0/A3.5           ← 低风险、纯工程、零显存 → 先爬，建立正反馈
tier 2  M3/M2                     ← 中风险，改动主脑结构，人工确认
tier 3  M5/M7/S6_model            ← 价值判断/外部依赖 → manual-blocked，不自主爬
tier 4  L1/L2/L6/L8/L5/L3/L4/L7   ← 高成本/需世界模型 → 长期，人工排期
```

**自主化阶梯（A0-A5）与心智器官阶梯（M/L）并行**：
- A 阶让 agent 获得"会爬"的能力（读判据、验收、写回、反思）
- M/L 阶是它爬上去能解锁的心智器官
- 两者交叉：爬 A0/A1 时顺带完成低风险的 M1/M8；爬得越高，能自主处理的 M 项越多

---

## 5. 成长闭环（agent 每爬一步的完整流程）

```
① roadmap_check.py --next        → 选出下一张可爬的卡片（ready + deps done + risk 最低）
② 读卡片的 what/why/benefit/caveats → 理解目标、动机、好处、坑（不是机械执行）
③ 执行任务（harness 能力面）      → 有 caveats 约束，有 abort_if 止损
④ 跑 verify（零 LLM 判据）        → PASS 继续，FAIL 回滚 + attempts++
⑤ 回答 reflection 问题            → 产物写进 CritBank/skill/trace
⑥ 写回 status=done + evidence     → 权威 YAML；人类视图由 diff 审阅（闸门上移未取消）
⑦ 回到 ①                         → 经验已沉淀，下一张卡片爬得更快（复利）
```

第 ⑤ 步是"成长"与"完成任务"的分界线：没有它，agent 只是执行机器；有了它，agent 越爬越聪明。

---

## 6. 与用户原六项的对应

| 用户要求 | 卡片字段 | 落地位置 |
|---|---|---|
| 要干什么 | `what` | CAPABILITY_LADDER.yaml 每项 |
| 为什么这样干 | `why` | 同上 |
| 干了解锁什么 | `unlocks` | 同上（指向其他 ID）|
| 对自己什么好处 | `benefit_to_self` | 同上（我加的）|
| 付出什么代价 | `cost` | 同上（time/risk/vram/reversible）|
| 注意什么 | `caveats` | 同上（来自历史教训/证伪）|
| （逐步成长）| `reflection` + 状态机 | 同上 + roadmap_check.py（我加的）|
