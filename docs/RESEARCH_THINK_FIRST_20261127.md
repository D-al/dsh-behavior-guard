# 调研：让模型先思考任务本身（2026-11-27 01:35）

> 用户问题："能不能让模型自己先思考一轮任务本身？论文和社区有没有方案？"
> 背景：实测发现模型在**两个同名 `client.js` 之间犹豫**（recycle-bin vs hardware-monitor），
> read 37 次仍不确定改哪个。这正是"任务理解"缺失，不是"执行力"不足。

## 一、结论先行

**能，但关键不是"让它想"，而是三个条件同时满足：**

1. **权限锁定**（Plan Mode）—— 口头说"先想想"没用，它一边想一边就把文件改了
2. **消歧证据**（结构化）—— 不是让它自由发挥，而是给出"候选有哪些、差异在哪"
3. **触发条件**（不确定性阈值）—— 不是所有任务都需要前置思考（改一行 typo 不需要）

我们已有的 `control_turn`（每 8 步元决策）**失败在时机**：它在第 27 步（空转中）才注入，
而 Plan 必须在**第 1 步动手前**注入。这是本质区别。

## 二、论文证据

### 1. Plan-and-Solve Prompting（ACL 2023, arXiv 2305.04091）

Zero-shot-CoT 的三个 pitfall：
- calculation errors
- missing-step errors
- **semantic misunderstanding errors** ← 我们的病

PS = 先制定计划拆分任务 → 按计划执行子任务。PS+ 加详细指令（"pay attention to calculation"）。

**量化**：10 个数据集、3 类推理任务、GPT-3 上 **一致大幅超越 Zero-shot-CoT**，
接近或超过 Zero-shot-PoT，数学推理上与 **8-shot CoT 相当**。

### 2. SAGE-Agent（arXiv 2511.08798 / ICLR 投稿）

**最贴切的一篇**。专门解决"模糊指令下工具调用消歧"：
- 把工具调用建模为 POMDP，用 **EVPI（Expected Value of Perfect Information）** 选问题
- 明确**分离两类不确定性**：
  - **specification uncertainty**（用户到底想要什么）
  - **model uncertainty**（模型能力限制）
- **量化**：ClarifyBench 上 coverage **+7~39%**，问题数减少 **1.5~2.7 倍**；
  When2Call 准确率 36.5% → **65.2%**（3B）、36.7% → **62.9%**（7B）

**这条分离直接验证了我之前的判断**：我们的问题主要是 specification uncertainty
（两个同名文件不知道改哪个），不是 model uncertainty（35B Q4 的能力边界）。
前者**可以用 harness 解决**。

### 3. Ask-before-Plan（Zhang et al. 2024）

"proactive planning agents that predict clarification needs and collect information **before execution**"
—— 关键词是 **before execution**。

### 4. Princeton/Google 的 conformal prediction 消歧（CoRL 2023, 最佳学生论文）

量化人类语言的模糊度；当**多个候选同时进入概率阈值**时触发求助。
例子："把碗放进微波炉"但桌上有金属碗和塑料碗 → 机器人必须问。

**这和我们的场景完全同构**："改 client.js 的宽度"但有两个 client.js。

## 三、社区方案：Claude Code Plan Mode

### 核心机制（不是提示词，是权限）

> "用自然语言要求 Claude'先规划'，它可能一边规划一边就开始改文件了。
> Plan Mode 是**强制锁定**：Claude 在只读状态下没有修改文件的权限，**物理上做不到边想边动手**。"

> "就像你跟包商说'先画图再施工'，他可能画到一半就开始敲墙了。
> 但如果你把工具锁在仓库里，他拿不到铁锤，就只能老老实实画完。"

### 四阶段工作流
`Explore（只读）→ Plan（产出方案）→ Code（可写执行）→ Commit`

### 触发判断（社区共识）
> "如果改动能用一句话描述清楚 diff，跳过 Plan；
> **如果连描述都需要先'看下代码再定'，必须走 Plan**。"

我们的场景："把 client.js 宽度改成 1700px" —— 表面一句话能说清，
**但有两个同名文件，必须先探索才能描述清楚** → 应该走 Plan。

### 官方文档提醒
Plan Mode "adds overhead"，只用于"不确定方案、改动跨文件、对代码不熟悉"。
**不要一刀切全开**。

## 四、我们的 harness 里怎么实现

### 已有能力（可直接用）
- `tools/pre-execute` waterfall → `deny + reason`（实测已验证）
- `tools/post-execute` → 替换结果
- `agent/pre-step` → 注入
- `session/event` → 观察 tool_result

### 最小可行方案：**消歧门控**（不需要真的让模型"写计划"）

**触发**：`tool/result` 里 glob 返回**多个同名文件**（basename 重复）→ 标记 `ambiguity = true`

**门控**：write/edit 工具的 `pre-execute` 检查：
- 如果 `ambiguity && file_path` 只是 basename（无目录分隔符）→ **deny**，附上候选清单：
  ```
  发现 3 个同名 client.js：
  1. node_modules/dsh-session-recycle-bin/client.js
  2. node_modules/dsh-hardware-monitor/client.js
  3. workspace/hardware-monitor-plugin/client.js
  请先明确要改哪一个的完整路径，再调用 write。
  ```
- 如果 file_path 带目录（已消歧）→ 放行

**为什么这比"让它写计划"强**：
1. 不依赖模型自愿输出思考（它可以直接跳过）
2. 提供的是**结构化证据**（候选路径列表），不是笼统的"你想想"
3. 只在检测到歧义时触发，符合"不要一刀切"

**对应论文**：SAGE-Agent 的 specification uncertainty 消歧 +
Claude Code Plan Mode 的权限锁定 + Ask-before-Plan 的 before execution。

## 五、诚实边界

1. Plan-and-Solve / SAGE 的数据来自 GPT-3 / GPT-4o / Qwen2.5-14B，**我们是 35B Q4**。
   但消歧门控是**确定性规则**，不依赖模型能力——这是它比提示词方案可靠的原因。
2. "glob 返回同名文件"只是歧义的**一种**信号；还有参数模糊、目标模糊等，本次不覆盖。
3. 社区 Plan Mode 需要人工确认；我们做的是**自动消歧**（用文件路径作为确认信号），
   牺牲了人的判断，但适配无人值守场景。
4. 如果模型始终不给完整路径，会形成新的死循环——需要预算上限（最多 deny 2 次后放行）。

## 六、待办

- [ ] 实现消歧门控（glob 检测 + write 门控 + 预算上限）
- [ ] 实测：用"改 client.js 宽度"样本验证是否在 1~2 步内消歧
- [ ] 回归验证
