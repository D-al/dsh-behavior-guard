# 优化方案：接住模型已有的自发反思（论文 + 社区，2026-11-27 12:15）

> 承接 `REFLECTION_TENDENCY_MEASURED_20261127.md`：35B 有强反思倾向（87% 会话 /
> 44.7% 自我质疑 / 反思后改参 169:17），但 harness 注入激发反思 **0%**、产物被丢弃。
> 本文回答：论文和社区对"**接住已有反思**"这个具体问题有什么方案。

## 零、一句话总纲

**别造反思，接住反思；别立即沉淀，显式 gate；别信自评，外置验证；别全量注入，Top-1。**

文献的核心判断（arXiv:2605.12978）：把原始 reasoning 当**一等证据**，
整合（consolidation）必须显式 gate，不要每步触发——记忆效用随整合呈**倒 U 型**，
最终可低于无记忆基线（GPT-5.4 在原本 100% 能解的题上，用 ground-truth 整合后 **54% 失败**）。

## 一、论文方案（按对本项目适用性排序）

### 1.1 零成本分流：HVR 犹豫-验证比（SELFDOUBT, arXiv:2604.06389）⭐最该先做

- **机制**：检测轨迹里有没有不确定性标记，以及标记是否被**显式自我检查行为抵消**（Hesitation-Verification Ratio）。不需 logits。
- **数字**：7 模型 × BBH/GPQA-Diamond/MMLU-Pro。**不含犹豫标记的轨迹正确率高达 96%**；两阶段级联在 **71% 覆盖率下达 90% 准确率**，成本比采样式 semantic entropy 低 **10 倍**。
- **对本项目**：已有 reasoning_content，HVR 几乎零成本。**它把 169 次改参从"都是经验"变成"候选信号池"**——无犹豫的跳过，有犹豫且被验证的才进候选区。
- **注意**：arXiv:2603.15500 证明信号价值在"不确定性外化的信息量"，**不在关键词本身**——正则不能只匹配"等等"，要匹配"质疑 + 随后验证"的组合。

### 1.2 监控与控制解耦（Metacognitive Harness, arXiv:2605.14186）⭐时序错位的架构答案

- **机制**：解题前报 FOK、每次尝试后报 JOL + 理由；控制层决定 trust / retry / aggregate。**关键**：retry 上下文**显式排除先前 reasoning traces**，只给紧凑元认知反馈 + JOL 理由——规避 self-refine 的强锚定；最终聚合时隐藏 FOK/JOL。
- **数字**：固定 Claude Sonnet-4.6，pooled 准确率 **48.3 → 56.9**，无参数更新。
- **对本项目**：把 44.7% 的自我质疑句当**免费 FOK/JOL 替代信号**（无需额外提问），把 harness 注入从"反思之后"改为"**控制层在 retry 之前**"。**不要把你 169 次反思原文整段喂回去**。

### 1.3 反思改参必须外置验证（arXiv:2310.01798, ICLR 2024）⭐硬约束

- **数字**：GPT-4 GSM8K 95.5% → 91.5%（1 轮）→ **89.0%**（2 轮）；GPT-3.5 CommonSenseQA 75.8% → **38.1%**。有 oracle 反馈时提升 7–15%。**把对改错比错改对更频繁**。
- **对本项目**：**169:17 不能解读为"反思有效"**——必须配工具执行结果作锚点。优先用**工具真值**（verify_agent.py / 状态回读 / 测试命令），不要再造 LLM verifier（PRM 实际只高 1–2%，且 LLM-as-Judge 有自我偏见和 reward hacking）。

### 1.4 原始轨迹优先，整合要 gate（arXiv:2605.12978, UIUC+清华）⭐对"在线提炼"的直接否定

- **机制**：对比 episodic traces 与 LLM 重写出的 consolidated abstractions，三种腐化：误分组、适用性剥离、对窄近期流的过拟合。
- **数字**：效用**倒 U 型**；GPT-5.4 用 ground-truth 解法整合后 54% 失败；保留原始情节的 agent 准确率是强制整合的 **2 倍**；完全禁用整合与自动模式持平。
- **对本项目**：**不要每步把反思压缩成规则**。默认保留原始 reasoning 片段，只在"跨会话重复出现 + HVR 高 + 验证通过"三条件同时满足时才整合。

### 1.5 归因式记忆结构（ReasoningBank, arXiv:2509.25140）⭐存储格式

- **数字**：WebArena 40.5→48.8；SWE-Bench 34.2→38.8。**消融关键**：仅成功 46.5 vs 成功+失败 **49.7**（失败经验 +3.2pp）；但 AWM 加失败反而 44.4→42.2。检索 **k=1 最优（49.7），k=4 降到 44.4**——**多检索即噪声**。
- **对本项目**：记忆项用 `{title, description, content}`；失败反思和成功策略分开存；**检索 Top-1**，不要 top-3（我之前错题本设计写的 top-3 需要下调）。

### 1.6 时序前置：睡眠时计算与预加载

- **Sleep-time Compute**（arXiv:2504.13171，Letta+UC Berkeley）：空闲期预推理写入记忆，function calling 迭代 `rethink_memory` → `finished_thinking`。同准确率测试时 token **省 5×**，扩大睡眠算力再 +13%/18%。**用户查询可预测性与收益高度相关**——可预测性低时收益消失。
- **PaMER**（arXiv:2609.27286）：论文实证"**记忆操作需求在行动前就已编码在内部表征里**"——时序前置不是空想，信号在反思之前就存在，只是没读。
- **对本项目**：空闲期把历史改参教训预置为 candidate memory，而不是等反思发生后再注入。

### 1.7 显著性过滤，零生成式 LLM（SLICE-Mem, arXiv:2610.33015）

- **机制**：小型分类器判断哪些 turn 值得留存 + 谓词中心抽取；跨条目核对推迟到离线整合。
- **数字**：LongMemEval-S 56.8% vs 59.3%（精度接近），但 token 消耗降 **92.4% / 99.5%**。
- **对本项目**：用 HVR 当 salience filter，批量筛 169 次反思，离线整合，零额外 LLM 成本。

### 1.8 自我质疑句的离散化（Reasoning Scaffolding, arXiv:2509.23619）

- **机制**：从长 CoT 里用关键词（`wait`/`but`/`ok`）归为 **7 类语义信号**（如 Contrast and Concession），双换行切步，再语义校验纠错。
- **对本项目**：可给 169 次改参建 schema（质疑类型 → 后续动作类型），而不是一堆自由文本。

### 1.9 反面证据（必须设闸门）

- **记忆虚构**（UMBC 2026）：Reflexion agent 在 ALFWorld 写 121 条反思，**无一提及正确目标物品**；错误被存储→检索→执行→在后续反思中再强化。
- **巩固丢元层**（2026）：把"我好像有权限"巩固成"用户有权限"——**模态词丢失**。你的反思句带"也许/等一下"，写成干净规则就变成虚假确定。
- **SEVA**（arXiv:2606.29713）：HaluEval 提升但 TruthfulQA 下降——单调改进假设不成立。
- **自蒸馏抹掉不确定性**（SRD 相关）：自信产生更自信的正反馈，**不确定性表达加速消亡**。

## 二、社区实现（可直接抄的）

### 2.1 thinking block 抽取器 ⭐唯一完整实现

`github.com/parcadei/continuous-claude-v3`：
- `opc/scripts/core/extract_thinking_blocks.py`：遍历 JSONL → `message.content[]` 中 `type=="thinking"` 的 `thinking` 字段。`PERCEPTION_SIGNALS` 正则**可直接抄**：
  ```
  actually | realized? | the issue | that's why | turns out | I was wrong |
  works because | the problem is | Oh, | Aha | now I see | I see now |
  misunderstood | wait,? | hmm | unexpected | surprised | different than |
  not what I | wasn't expect
  ```
- 分类映射：`REALIZATION→CODEBASE_PATTERN`、`CORRECTION→ERROR_FIX`、`INSIGHT→CODEBASE_PATTERN`、`DEBUGGING_APPROACH→WORKING_SOLUTION`，另 8 种 type。
- 落库 `store_learning.py`：PostgreSQL+pgvector，**0.85 相似度自动去重**。质量规则："每 session 3–5 条，排除 procedural planning / 简单执行 / 确认 / 泛化调试"。
- SessionEnd hook 触发，daemon 检测 heartbeat stale >5min 后起 headless 提炼。

### 2.2 人审闸门与升级阈值

- **claude-reflect**（~1.8k stars）：`UserPromptSubmit` hook 正则捕获用户纠正 → 队列 → `/reflect` 语义复核（给 0.60–0.95 置信度）→ **人工逐条 Apply/Edit/Skip** → 写 CLAUDE.md。注意它捕获的是**用户纠正**，不是模型自述反思；可借骨架换触发源。v3.3 有 haiku 即时 band，**当轮生效**。
- **self-improving-agent**（pskoett）：`.learnings/` 三文件分级，唯一硬阈值 `Recurrence-Count >= 3 ∧ 跨 ≥2 任务 ∧ 30 天窗口` → 晋升为 1–3 句预防规则，写前展示 diff 人审。格式带 `Validation: pending|verified|unresolved`、`Decay-Type`。
- **agent-memory-guard-skill**：Source Attribution → Risk Assessment（source trust 0-4 + 置信）→ 分级响应：**0-2 立即写 / 3-4 延迟 5min / 5-6 人审 / 7-10 人工批准**，目录分 `trusted/quarantine/audit`。
- **腾讯混元 Hy-Memory chain_store.py 事故**：早期把"仅提议未执行"和"改失败 old not in s"都写进版本链 → 加失败闸门，原则"**抽错比抽不到更坏**"。

### 2.3 时序前移的工程答案

- **`UserPromptSubmit` hook**：用户回车后、进 LLM 前，stdout 注入上下文——**这是唯一能真正前置的时机**。
- **Cursor `.mdc` Agent Requested 模式**：`alwaysApply:false` + 只给 `description`，agent 读描述自主决定是否加载——可插拔且省 token。
- **Letta dreaming**：`dreaming:{trigger:"step-count", behavior:"auto-launch", stepCount:25}`，后台子 agent 预整理，主 agent 不中断。
- **LangMem background 的同构坑**：`ReflectionExecutor.submit(msgs, after_seconds=10)` 有 debounce，但**本轮写入不影响本轮 prompt，下一轮才生效**——社区也没解决本轮注入。所以别指望"反思当下就看到教训"。

### 2.4 轻量反思协议（可直接抄的格式）

```
CONTEXT: [任务类型]
REFLECTION: [我注意到什么]
LESSON: [下次应如何做不同]
```
成功应用 3 次 → 提升到热存储（icattj/openclaw-skill-self-improving）。另有 `deepseek.club/skills/reflect-learn` 的 HIGH/MEDIUM/LOW 三级 + Skill-Worthy 五项 Quality Gate。

### 2.5 reasoning_content 的工程坑 ⚠️

DeepSeek thinking 模式下**工具轮次必须回传 `reasoning_content`，否则报 400**（LibreChat 源码 `includeReasoningContent`、n8n 社区节点专门修这个）。
**这可能正是"反思产物被丢弃"的技术原因之一**——如果 harness 或 client 在多轮工具调用时没回传该字段，第二轮反思就丢了。需排障确认。

## 三、对项目的具体优化清单（按优先级）

### P0：零风险，立即做

1. **用 HVR 分流**：在 `summarizeAssistant` 已拿到的 `reasoning`（994 行）上算"犹豫标记 + 是否被验证抵消"，无犹豫直接跳过。
2. **排障 reasoning_content 回传**：确认多轮工具调用时字段没丢（2.5）。
3. **保留原始 reasoning 片段**：默认存进 `_outcome.jsonl` 的字段，不压缩、不整合（1.4）。

### P1：低风险，接住已有反思

4. **抄 `PERCEPTION_SIGNALS` 宽正则**，替换当前过窄的 `CORRECTION_RE`（1006 行）——当前 `open_correction_captured: 0` 但 `open_correction_survived_compaction: 14` 证明有漏捕。
5. **捕获后进候选区**，带 `Validation:pending` + 来源锚点 + 原始模态词，不直接进 critbank。
6. **三闸门**：`Recurrence-Count >= 3 ∧ 跨 2 任务 ∧ 30 天` + 失败闸门（未执行/执行失败不入库）+ 风险分级（0-2 直写 / 5-10 人审）。

### P2：中风险，需 A/B

7. **监控-控制解耦**：把自我质疑句当控制信号，retry 时**只喂紧凑反馈、显式排除旧 reasoning 原文**（1.2）。
8. **检索 Top-1**（ReasoningBank 消融），不是我之前设计的 top-3。
9. **时序前置**：`UserPromptSubmit` 等价时机（dsh 需查是否有对应 hook）+ 后台 dreaming。

### P3：高风险，先验证再做

10. **不要加热路径反思工具**——模型已反思，缺漏斗不缺动机；加工具触发 overthinking 风险。
11. **不要 LLM verifier**——用工具真值；PRM 只高 1–2%，LLM-as-Judge 有偏见。
12. **不要每步整合**——倒 U 型，保留原始轨迹优先。

## 四、诚实边界

- 论文数字来自各自基准（WebArena/HotPotQA/GSM8K/ALFWorld），**不能直接套到本地编码 agent**，必须自做 A/B
- SEMDOUBT/HVR 的"96% 无犹豫即正确"依赖其模型与任务分布，需本地复核
- "跨会话重复 ≥3 次"阈值来自社区个人实践，非论文实证
- 部分 2026 年论文（2605.x/2610.x）需读者自行核实原文细节
- **没有任何论文直接测试"捕获 reasoning_content 里的纠错句并沉淀"的完整闭环**——这是研究空白，我们做的是工程组合创新

## 五、来源

**论文**：2604.06389 SELFDOUBT · 2603.15500 不确定性外化 · 2605.14186 Metacognitive Harness · 2310.01798 不能自纠 · 2605.12978 记忆整合倒U · 2509.25140 ReasoningBank · 2509.23619 Reasoning Scaffolding · 2504.13171 Sleep-time · 2609.27286 PaMER · 2610.33015 SLICE-Mem · 2610.08077 SRD · 2309.11495 CoVe · 2606.29713 SEVA · 2506.02158 ReAP

**社区**：parcadei/continuous-claude-v3（thinking 抽取器）· BayramAnnakov/claude-reflect · pskoett/self-improving-agent · orosha-ai/agent-memory-guard-skill · 腾讯混元 Hy-Memory · 得物技术自进化 · dsh-observational-memory@0.5.2 · LangMem background · Letta dreaming · LibreChat/n8n 的 reasoning_content 回传补丁

**项目内**：`REFLECTION_TENDENCY_MEASURED_20261127.md`（实测）· `REFLECTION_RECALL_GAP_20261127.md`（诊断）· `MISTAKE_BOOK_RESEARCH_20261127.md`（存储设计）
