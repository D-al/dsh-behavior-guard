# 云端模型如何区分"要不要写 todo_write 的长任务"（2026-11-22）

> 用户问："那云端模型是如何区分是否是个需要写todo_write的长任务的呢？"
> 答案出乎意料地简单：**没有分类器**。是"工具描述里写死的规则 + 模型自判 + 先探一步再判"。

## 一、Claude Code 官方 TodoWrite 工具描述（决定性证据）
来源：Claude Code system prompt 的 `## TodoWrite` 段（systemprompts.org / ccprompts.info `src/tools/TodoWriteTool/prompt.ts` / deepwiki Tools.json:390-433 三处一致）。

### 1.1 触发规则（原文逐字）
**When to Use This Tool — Use this tool proactively in these scenarios:**
1. Complex multi-step tasks - When a task requires **3 or more distinct steps** or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list
4. User provides multiple tasks - numbered or comma-separated list
5. After receiving new instructions - Immediately capture user requirements as todos
6. When you start working on a task - Mark it as **in_progress BEFORE beginning work**. Ideally only one todo as in_progress at a time
7. After completing a task - Mark it as completed and add new follow-up tasks

**When NOT to Use This Tool — Skip when:**
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no organizational benefit
3. The task can be completed in **less than 3 trivial steps**
4. The task is purely conversational or informational

重点强调原文：
> "NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly."

### 1.2 最关键的机制：先探一步，再判
官方 few-shot 例子（rename getCwd → getCurrentWorkingDirectory）：
```
User: Help me rename the function getCwd to getCurrentWorkingDirectory across my project
Assistant: *Uses grep or search tools to locate all instances of getCwd in the codebase*
          "I've found 15 instances of 'getCwd' across 8 different files."
Assistant: *Creates todo list with specific items for each file that needs updating*
The assistant used the todo list because:
  1. First, the assistant searched to understand the scope of the task
  2. Upon finding multiple occurrences across different files, it determined this was a complex task
```
**这正是我们上一份报告里 Heddle 的"第一步后判"**——先探明范围（grep），再据实测范围决定要不要建 todo。
判定规则是**写死在 prompt 里的 if/else + few-shot 正反例**，不是训练出来的分类器。

### 1.3 配套状态机（同样是 prompt 规则，非代码判定）
- 三状态 pending → in_progress → completed
- "Update task status in real-time"、"Mark completed IMMEDIATELY (don't batch)"
- "Only ONE task in_progress at any time"
- 反例教学："Add a comment to calculateTotal" → 直接用 Edit，不建 todo

## 二、为什么这解释了前面的调研结果
| 前面的发现 | 现在的理解 |
|---|---|
| 学术上找不到"指令→步数"分类器 | 因为云端根本不用分类器判长短，用 prompt 规则让模型自判 |
| prompt-only 预测 AUC 0.599 近随机 | 模型自判也不是靠"首条指令"，而是靠**探一步后的实测范围** |
| Heddle"第一步执行计划是强指示器" | 和 Claude Code grep-then-decide 同构 |
| 本地关键词规则 94.3%（读用户标签） | 相当于 Claude Code 规则第3/4条（用户明确要求/多项任务）的子集 |

## 三、本地对照：我们已经有类似机制，但位置不同
| 维度 | Claude Code | 本地 harness |
|---|---|---|
| 判定位置 | **工具描述里（prompt 层）**，模型收到指令即自判 | **harness 规则（代码层）**，`step>=4 && todoCalls==0` 才闹钟 |
| 判定依据 | 模型理解 + 先探一步的实测范围 | 确定性 step 计数 + taskProfile(只读/有产物) |
| 时机 | 事前（开始前） | 事后（第4步才提醒）|
| 依赖 | 依赖 frontier 模型自判能力 | 不依赖模型元认知（符合项目铁律）|
| 反面控制 | prompt 明写"3步以下不要用" | 只有正面闹钟，无"别过度规划"约束 |

本地 `messageNoTodo`：`"这是一个多步任务，但你还没有用 todo_write...立即停下：先调用 todo_write..."`
——是**补救式**的；Claude Code 是**预防式**的（模型一开始就建 todo）。

## 四、对本地 35B 的判断（诚实）
1. **不能照搬**：项目铁律"不能依赖模型元认知"——35B 自判"要不要 todo"的可靠性没有证据，
   云端靠的是 frontier 模型 + 大量 few-shot 教学
2. **但可以借鉴"先探一步"**：本地 `step>=4` 闹钟其实已是事后版；可以在第1-2步后
   用**确定性信号**（是否已发现多文件/多次失败/多个用户要求）决定是否提示 todo——
   这是规则驱动，不依赖模型自判
3. **可以补反面控制**：本地没有"简单任务别建 todo"的约束，可能过度规划（项目已有 D3 冗余 todo 守卫，
   说明这个问题存在）。Claude Code 的 4 条 skip 规则可转成确定性检查

## 五、子任务补充：三层结构 + 其它产品 + 效果数据

### 5.1 Claude Code 是三层提示词引导（不是单一工具描述）
| 层 | 内容 | 强度 |
|---|---|---|
| L1 工具描述 | When to Use / NOT + few-shot 正反例 | 引导性（"proactively"）|
| L2 主系统提示词 | "Use these tools **VERY frequently**... if you do not use this tool when planning, you may forget important tasks — **and that is unacceptable**" | 强指令 |
| L3 运行时 reminder | "The TodoWrite tool hasn't been used recently... **gentle reminder - ignore if not applicable**" | 纯软建议 |

**关键一句话**：工具描述末尾 "**When in doubt, use this tool**"——不确定时默认倾向"用"，
这解释了 Claude Code"动不动就建 todo"的行为。正反信号并存是 intentional tension。

**官方公开文档（code.claude.com/docs/en/agent-sdk/todo-tracking）** 措辞是概率性的：
"Claude creates todos for **most** multi-step work... Claude **may skip** todos for very short requests"——
不是硬规则。

### 5.2 其它产品：云端也没全靠裸自判
| 产品 | 机制 |harness 侧保险 |
|---|---|---|
| Cursor | Plan mode，用户 Shift+Tab + **系统自动建议**复杂任务进 plan | harness 自动建议 |
| Windsurf/Cascade | Wave 12 起 planning **automatic, no manual toggles**，Cascade 自判 | **用更大模型做长期规划**（Wave 10 明示）|
| Gemini CLI | write_todos 工具（complex multi-turn only）+ Plan Mode | **规划路由 Pro、执行切 Flash** |
| Devin | 每次会话 proactive 规划，manager 拆给 child Devins | 多 agent 分工 |
| Codex | /plan、Ask→Code 两步人工流程 | 用户驱动 |

→ "云端靠 frontier 模型裸自判"这个前提**不完全成立**：至少三家在 harness 层加了规则/模型分工/用户开关。

### 5.3 效果数据（重要：自判不可靠，连 frontier 也过度自信）
- **CARD（arXiv:2601.4210，Qwen3-1.7B）**：裸提示自评复杂度 **76.1-79.8%**，
  且"**systematically misestimates and triggers too much decomposition on simple problems**"；
  微调 0.6B 专用估计器 MRCE 达 **89.2%**（token 还更少）——**专用小分类器 > 裸自判**
- **StyleBench（arXiv:2509.20868，15模型 270M-120B）**：meta-reasoning 策略选择"**emergent and
  not readily achievable through standard SFT**"；7B 微调后只学会固定偏好，32B 违反规则，72B+ 才稳定
- **MR-Ben（arXiv:2406.13975）**："**models smaller than Llama3-70B exhibit performance degradation
  with self-refinement**"——35B 落在灰区
- **Why LLMs Choose Bad Plans（COLM 2026）**：前沿模型困难任务系统性过度自信（Gemini 2.5 Pro
  预测 94% 成功率实际 22%），**强制结构化规划反而放大错误**；喂真实成功率才让所有 planner 立刻选对
- **官方 prompt engineering**：Anthropic 明确"prefer general instructions over prescriptive steps"，
  且指出最强模型上"verification instructions... cause over-verification"（要删）

### 5.4 新动向：新模型撤掉 TodoWrite
官方原文："**Newer models track multi-step work without a written todo list**, so on those you don't
need anything on this page"；工具默认仅在 Opus 4.7/Sonnet 4.6/Haiku 4.5 及更早模型可用。
→ 趋势是"**规划内化到模型，不再外化 todo**"（官方理由：definitions and reminders take up context）。

### 5.5 对本地 35B 的净判断（更新）
- **不能照搬裸自判**：35B 落在"元推理涌现但不可靠"灰区（StyleBench 32B 违反规则、72B 才稳定；
  MR-Ben 70B 以下自改进有害）；项目铁律"不能依赖模型元认知"同构
- **可以借鉴的三件事**（都是规则/系统侧，不靠模型自判）：
  ① 把"3+ 步/用户给列表/纯对话跳过"做成**确定性前置规则**（本地已有 step>=4 闹钟，可提前）
  ② **先探一步再判**（Claude Code 官方例子：grep 发现 15 处/8 文件才建 todo）——
     与 Heddle"第一步后判"同构，且能用确定性信号（文件数/失败数）而非模型自评
  ③ **补反面控制**：本地只有正面闹钟，无"简单任务别建 todo"约束（项目已有 D3 冗余 todo 守卫，
     说明过度规划确实存在）
- **若真要分类器**：CARD 证明 0.6B 专用估计器 89.2% > 裸自判 77-80%——
  但这是"复杂度分类"不是"步数预测"，且与前面 M9 结论不矛盾（M9 的原定位是 BDI 槽）

## 六、诚实标注
- Claude Code 工具描述来自 system prompt 泄露/整理（systemprompts.org、ccprompts.info、
  deepwiki 三处一致），非 Anthropic 官方 API 文档逐字发布——但三源一致，可信度高
- 官方公开文档只说 "most/may skip"，无硬规则；完整描述是泄露版
- 效果数据：CARD/StyleBench/MR-Ben 均为论文自报；"Why LLMs Choose Bad Plans" 的
  +72pp 等数字来自二次摘要，COLM 摘要只确认定性结论
- **未找到任何官方/社区统计"Claude Code 实际何时真的写 todo"的准确率**
- 本地对照是代码事实（index.mjs:147/218/2071）
