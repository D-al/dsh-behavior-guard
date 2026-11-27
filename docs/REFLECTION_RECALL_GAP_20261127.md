# 诊断：harness 缺乏「主动反思 / 主动回忆」的执行空间

> 用户问题（2026-11-27）："我们通常会反思和回忆以总结经验，现在的 harness 是不是缺乏执行这两块行为的空间？即 35B 想要回忆和反思的时候没有现成的东西提供给它。"
> **结论：假设成立，且是代码级事实。** 不是"没有记忆机制"，而是**全部做成 harness 侧被动注入，模型触发权为零**。

## 一、核心证据（代码级）

### 1.1 决定性事实：harness 无法注册工具

`index.mjs` 全文件 **`registerTool` / `addTool` 命中 0 处**。harness 是 cordis 事件钩子插件，
唯一输出通道是 `createMessage()` → `role:'user'` 的 steering message（`index.mjs:977-984`）。
它**只能往 prompt 里塞文本，不能给模型增加动作**。

对比 Letta/MemGPT：`core_memory_append` / `core_memory_replace` / `archival_memory_search` /
`archival_memory_insert` 全是 agent 可调用工具；sleep-time 还有 `rethink_memory` / `finish_rethinking`（最多 10 次）。
**这才是"主动回忆"的标准范式——我们的 harness 架构上做不到。**

### 1.2 反思机制：12 项全部被动

| 机制 | 触发条件 | 分类 | 行号 |
|---|---|---|---|
| control turn | `step % 8 === 0` 或连续 6 步无 write | 被动 | 3373-3392 |
| mind_state | 跨步重复阈值 3 且 gap≥6 | 被动 | 3226-3239 |
| FEP 偏差 | 写前登记预期 / 写后比对 | 被动旁路（**连 prompt 都不进**） | 1684-1697, 1985-2024 |
| P0 压缩存档 | compaction 事件 | 被动 | 1494-1497, 3085-3152 |
| review echo | 审计结论置 pending | 被动 | 3063-3081, 3773-3780 |
| Critic / 审计 | present 前 / D5 门控 | 被动（**执行者不能请求审计**） | 2820-2860, 3671-3704 |
| episodicSearch | 嵌在控制回合内 | 被动（**查询词固定**取 `s.latest||s.initial` 前 120 字） | 3408-3425 |
| critbank | 仅审计 ISSUE 时匹配，最多 2 条 | 被动（**寄生在审计上**） | 903-918, 3737-3758 |
| learn_feedback 回灌 | 每会话 ≤2 条 | 被动 | 3595-3625 |
| 状态板 | 每 4 步，嵌在控制回合 | 被动 | 3393-3407 |
| 技能卡 | 关键词命中一次 | 被动 | 3208-3221 |
| 确定性消歧 | 同名文件歧义 | 被动 | 3330-3356 |

### 1.3 反思产物：写完了就丢

模型在思考里写"我反思一下，下次应该…"的完整路径：

1. reasoning/thinking block 收进 `s.last.reasoning`（`985-998`），**每次 assistant 覆盖式更新**（`1457-1459`）
2. `captureOpenCorrection`（`1460-1461`）只匹配**窄正则** `CORRECTION_RE`（`1006`）：
   要求「应该/需要/必须 + 改回/恢复/撤销/还原/修正/换成…」或「是个错误/写错了」等**具体纠错措辞**
3. "下次应该…"这类一般性反思**不匹配，直接 return**
4. 命中的才进 `s.openCorrections`（≤20 条），压缩后回灌（`3114-3119`）
5. `pendingLearn` 只由 FEP 偏差和 crit 命中写入（`2013-2018`, `3751-3754`）——**与模型思考文本无关**

**判定**：自由文本反思 ≈ 只留思维链 → 下次 assistant 覆盖 → 压缩丢弃。
不进 trace（全文件无 `kind:'reasoning'` 埋点）、不进 critbank、不进 pending_learn。
唯一例外是窄正则命中的"纠错句"，但那是"发现错误"不是"总结经验"。

### 1.4 素材可见性：想回忆时看不到什么

- **不可见**：`_outcome.jsonl`（23790 行，只写不读）、`_trace.jsonl`、`_pending_learn.jsonl`
- **部分可见**：`critbank` 只在审计 ISSUE 时见 1-2 条；`_learn_feedback` 每会话 ≤2 条
- **不可控**：`episodic_search.py` 只存在于 harness 的 `execFileSync`（`3413`），
  **从未注册给模型，prompt 也不告知可用**。理论上模型能用 `pwsh` 手动跑，但没有引导。

## 二、论文对照：别人怎么给 agent "空间"

| 系统 | 触发者 | 空间预算 | 素材结构 |
|---|---|---|---|
| Reflexion (2303.11366) | 系统（trial 末） | Ω=1-3 条 | 轨迹 + 标量奖励 + 测试反馈；反思比纯回放多 **+8%** |
| Generative Agents (2304.03442) | 后台阈值（importance 和 >150） | ~2-3 次/天 | 100 条近期记忆 + **证据指针** + 三维打分 |
| ACE (2510.04618) | 适配框架（每样本） | reflector 轮 ≤5 | bullet + helpful/harmful 计数 + delta |
| ReasoningBank (2509.25140) | 系统（任务末 auto top-k） | top-k | title/description/content + 失败反事实 |
| **LangMem** | **两者都有** | debounce 后台 | `create_manage_memory_tool` / `create_search_memory_tool` = **显式工具** |
| **Letta/MemGPT** | **agent 显式工具 + 定时** | rethink ≤10 次 | memory block / archival passage，**agent 自己决定存什么** |
| Voyager | 系统自动注入 | top-5 | description embedding → code |

**关键区分（论文交集）**：
- **热路径显式工具**：`recall` / `reflect` / `manage_memory` — agent 有动作位和触发权
- **后台反思提炼**：sleep-time agent / ReflectionExecutor（debounce）/ 确定性 delta merge — 不让实时推理付代价
- **我们的 harness 只做了第三类（后台/被动注入），前两类完全缺失**

## 三、反面证据：不是"加反思"就一定好

给 35B 加热路径长链反思有明确风险，必须设闸门：

1. **无外部反馈的反思会改错答案**（arXiv:2310.01798）：GPT-4 GSM8K 95.5→91.5（1 轮）→**89.0**（2 轮）；
   有 oracle 标签时 95.5→**97.5**。→ **验证信号必须外置**
2. **反思让答案摇摆**（ACL 2025, arXiv:2412.14959）：简单事实题出现 prompt bias
3. **长度非单调**（arXiv:2505.00127）：推理过长准确率下降
4. **overthinking 因果机制**（arXiv:2505.16448）：mask 输入后长度降 31-53% 且多数准确率上升
5. **反射 collapse**（ACE）：整体重写 18,282→122 tokens、准确率 66.7%→57.1%
6. **固定重试不收敛**（Reflexion WebShop）：100 任务 4 轮后 "no signs of improvement"
7. **小预算下控制反而负收益**（arXiv:2609.38147）：元推理 overhead 在紧预算时有害
8. **Meta-Harness**（arXiv:2605.14186）：FOK（解前）/JOL（解后）做**显式控制接口**，48.3→56.9——
   这是"自主决定何时再想"最直接的实证，但闸门是外置信号不是模型自评

## 四、补位方案（分技术路线）

### 路线 A：扩展 harness 的工具注册能力（根本解，改动大）

先决条件：确认 dsh 插件 API 是否支持注册工具。目前 harness 只监听 `ctx.on(...)`，
需查 cordis 是否有 `ctx.registry`/`ctx.on('tool/register')` 类似接口（**待调研**）。

若可行，暴露三个工具：
```
recall(query, k, scope)         scope ∈ lessons | tool_output | prior_trajectory | verification
reflect(reason, evidence_ids)   结构化反思，必须附证据 ID
finish_reflection()             显式停止动作（防 overthinking）
```
**风险**：35B 工具面已 28 个（风险区，社区拐点 12-15），再加 3 个会稀释注意力。
→ 必须先做工具面裁剪（28→18~20）腾出位置。

### 路线 B：不改工具面，用 prompt 引导通用工具（最小改动，可立即做）

不注册新工具，而是在现有注入里**显式告知模型可用路径**：
- 在控制回合注入：`如需回忆历史经验，可 read bench/critbank.json 或 pwsh 跑 python bench/episodic_search.py "查询词"`
- 把 `episodic_search.py` 的查询词从"固定取 latest 前 120 字"改成**从控制回合文本里提取模型自己写的关注点**（低成本）
- 加一个 `reflect` 提示模板：控制回合第三步固定问"本轮有什么值得记入错题本的教训？"

**优点**：零架构改动、零工具面扩张。**缺点**：依赖 35B 自觉遵守，实测它经常无视注入（同任务一次第4步edit、一次18步不 edit）。

### 路线 C：强化后台（不改热路径，收益稳）

- 把模型 reasoning 里的"纠错/反思"句**宽正则捕获** → 进 `openCorrections` → 压缩后回灌（现已窄正则，放宽即可）
- FEP 偏差从"只记 trace"升级为"生成候选 lesson 进 `_pending_learn`"（已有写入，需接人审）
- 把 `_outcome.jsonl` 做成**可查询视图**，在控制回合按需注入摘要（不是全量）

**这是最稳妥的一步**——不改触发权，只把"已经产生但被丢弃的反思"捞回来。

## 五、判断与建议

1. **用户假设成立**：缺的不是机制数量，是**模型的触发权和素材可见性**。12 项机制全是 harness 单向注入。
2. **不要第一步就加热路径反思工具**：论文反面证据明确（无验证反思把对的改错），且 35B 工具面已在风险区。
3. **推荐顺序**：C（捞回被丢弃的反思，零风险）→ B（prompt 引导复用现有工具，可 A/B）→ 调研 dsh 工具注册 API → A（若可行且工具面已裁减）。
4. **必须保留**：自动 top-k 注入作为底线（ReasoningBank/Voyager 范式），显式工具只用于二次追问。
5. **验证信号外置**：任何反思产物入库前必须过 `verify_agent.py` / 状态回读 / 测试命令——"抽错比抽不到更坏"。

## 六、与上一份错题本文档的关系

`MISTAKE_BOOK_RESEARCH_20261127.md` 回答"错题本怎么建"；本文回答"**谁有权翻和写**"。
前者是存储设计，后者是执行空间设计。两者合并才是完整闭环：
**素材（错题本）+ 动作位（reflect/recall）+ 触发权（agent 或混合）+ 验证闸门（外置）**。

## 七、待调研（未验证，不要当结论）

- dsh 插件 API 是否支持注册工具（`ctx.registry` / tool provider hook）——决定路线 A 可行性
- 工具面裁剪（28→18~20）的用户决策仍 pending
- 路线 B 的 A/B 设计：开关前后对比"主动回忆次数"与"同类错误率"
