# 错题本（mistake book）调研与设计：能否让 35B 越被纠正越聪明

> 用户问题（2026-11-27）：能否从过去错误中汲取教训？希望有可插拔、可修改的"错题本"，
> 高效积累错过的东西，做类似事情时迅速回忆起正确做法。
> 结论先行：**有条件能**。这是论文验证过的路线（Reflexion/ExpeL/ACE/ReasoningBank），
> 但"越学越聪明"不成立——准确说是"同类错误率下降"，且有严格前提。项目已有 60% 骨架，
> 缺的是验证闭环、纠错版本、按任务检索三块。

## 一、纠正认知：三个常见误传

| 误传 | 事实 |
|---|---|
| "A3 是 Google 的上下文工程框架" | **A3 在文献里是 Android Agent Arena**（arXiv:2501.01149，GUI agent 基准）。Google 的对应工作是 **ReasoningBank**（arXiv:2509.25140，ICLR 2026） |
| "ACE 是 Google 的" | **ACE 是 Stanford / SambaNova / UC Berkeley**（arXiv:2510.04618，ICLR 2026），作者 Qizheng Zhang、James Zou、Kunle Olukotun 等 |
| "工具调用天生弱，分类器能改善" | BFCL 复合分 0.6696 = BF16 的 **98.8%**，Q4 几乎无损。分类器只检测文本属性，**不增强能力**——层面错误 |

## 二、论文证据：能否"越纠正越聪明"

### 2.1 直接支持"从错误中学习"的实证

| 方法 | 论文 | 机制 | 关键数字 | ersistence |
|---|---|---|---|---|
| **Reflexion** | Shinn et al. 2023, arXiv:2303.11366, NeurIPS | 失败→语言反思→episodic memory→下次 trial 注入；**不更新权重** | AlfWorld 63%→**97%**(12 trials)；HotPotQA 32%→54%(trial7)，而 ReAct 重试基线 34% 起步**无提升**（关键对照：提升来自学习不是重试） | 同任务多次 trial |
| **ExpeL** | Zhao et al. NeurIPS 2023, arXiv:2308.10144 | 成功轨迹 kNN 检索 + **insights 规则**（对比失败/成功轨迹提炼）；insights 可**增/改/赞/踩，计数归零删除** | ALFWorld 任务相似度检索 **59.0%** vs 推理相似度 48.5% vs 随机 42.5% vs ReAct 40%；insights 可从 HotPotQA 迁移到 FEVER | 跨任务持久 |
| **ACE** | Zhang et al. 2025, arXiv:2510.04618, ICLR 2026 | context 当**演化 playbook**，Generator→Reflector→Curator；bullet 带 **唯一 ID + helpful/harmful 计数**；增量 delta 由**非 LLM 确定性代码**合并；含"常见失败模式" | agents **+10.6%**、finance **+8.6%**；延迟比 GEPA **-82.3%**、rollouts **-75.1%**。**反面案例**：整体重写使 18,282→122 tokens、准确率 66.7%→**57.1%**（低于无适配基线） | 跨任务持久 |
| **ReasoningBank** | Ouyang et al. 2025, arXiv:2509.25140, ICLR 2026（Google） | 从**自判成功与失败**经验提炼可迁移策略；记忆项结构化 **title/description/content**，明确含失败的**"预防性教训"** | WebArena/Mind2Web/SWE-Bench 相对 baseline **最高 +20%**，交互步数最多 **-16%** | 跨任务持久 |
| **Voyager** | Wang et al. 2023, arXiv:2305.16291, TMLR | 只把**验证成功**的技能（可执行代码）写入 skill library，按描述嵌入检索 | 独特物品 **3.3×**、行进距离 2.3×、里程碑最快 15.3×；技能可迁移。**但无失败技能删除机制** | 跨世界持久 |

### 2.2 结论的边界（重要，别过度承诺）

1. **"越学越聪明"要打折**：Reflexion 的 HotPotQA 若只是重试（无反思）**没有提升**；ExpeL 单用 insights 在 HotPotQA 只有 36%，低于组合。**提升来自"正确提炼 + 正确检索"，不是"记录得多"**。
2. **纯自我反思不可靠**：CRITIC（arXiv:2305.11738）证明必须**外部工具锚定**（搜索/解释器/验证器）。错题本必须有验证状态字段，否则错误反思会被当经验反复使用。
3. **检索省 token 但牺牲准确率**：Mem0 论文 LOCOMO 全上下文 **72.9%** vs 检索 **66.9%**，但检索上下文 1,764 vs 26,031 tokens、p95 1.44s vs 17.1s。**所以必须 top-k 精选，不能全量注入**。
4. **检索键比"是否检索"更关键**：ExpeL 消融——任务相似度 59% vs 推理相似度 48.5% vs 随机 42.5%。

### 2.3 负样本的直接证据

- **Likra**（arXiv:2503.14391）：带负例训练每样本提升显著高于纯正例；**"合理但错误"的近错负例影响更大**——错题本应优先记"差一点就对"的错误。
- **GLOW**（arXiv:2601.4992）：5–7B 域内 +2.52%、域外 +1.65%；Qwen2.5-7B + GRPO on GSM8K 使 MMLU 72.82%→76.47%。
- **STaR**（NeurIPS 2022）：错则给答案 hint 反向补 rationale 再微调，CommonsenseQA 72.5%（+35.9pp）。但这是**改权重**，不是本项目路线。

## 三、社区/工业实现：可插拔与可编辑的现实答案

### 3.1 最接近用户诉求的（可插拔 + 可修改）

| 项目 | 机制 | 可插拔 | 可编辑 | 证据 |
|---|---|---|---|---|
| **MCP memory server** (`@modelcontextprotocol/server-memory`) | 本地 JSONL 知识图谱，9 个 CRUD 工具（create/delete entities、relations、observations） | **极高**（改 MCP 配置一行） | **极高**（三类删除齐全，可 git 版本化） | 无权威效果评测；50+ 实体后别用 read_graph |
| **CLAUDE.md / AGENTS.md / CONVENTIONS.md** | 纯 Markdown 规则文件 | 高（放文件即生效） | **极高**（纯文本） | 官方明示 >200 行遵守度下降、>4MiB 跳过；无严格遵守保证 |
| **claude-reflect**（~1.7k stars, MIT） | hook 捕获 "no, use X"/"actually..." → 队列 → `/reflect` **人工审核**后写规则；置信度 0.60–0.95 | 高 | 高（写入前人确认） | 仅宣称；第三方评估 57/100「谨慎使用」 |
| **self-improving-agent**（peterskoett 等） | `.learnings/{ERRORS,LEARNINGS,FEATURE_REQUESTS}.md`，带 `correction`/`knowledge_gap` 分类、Pattern-Key、status pending/resolved/**promoted**；高频经验升级到 CLAUDE.md | 高 | **高**（全 md，可回退） | 仅宣称；频率阈值可能把偶然纠正升为铁律 |
| **mem0**（~62k stars, Apache-2.0） | 两阶段 extract→update，CRUD 齐全，三级作用域，LLM 判 ADD/UPDATE/DELETE/NOOP | 高 | 高 | 数字口径冲突：论文 66.9%，官方新版 92.5；Letta 作者公开质疑复现性 |
| **Letta / MemGPT** | Core memory 是系统提示里的**可编辑 block**，agent 可自改；2026-02 有 Context Repositories（git 式版本管理，二手） | 低（接管 runtime） | **极高** | DMR ~92.5%（二手）；简单任务反而更贵 |
| **Zep / Graphiti** | **bi-temporal 知识图谱**：冲突时给旧边打 `invalid_at` 而非删除，保留历史 | 中 | 中高 | 官方自报 LoCoMo 75.14%；实体去重难、内存开销大 |

### 3.2 社区最硬的实战教训（决定设计必须做什么）

1. **"一条错规则会在之后每个会话重复它的错误"**（borghei/self-improving-agent 明确写出）→ **升级必须人审**。
2. **华为云生产案例**：记忆命中率 4 个月 **91%→63%**，而向量库健康/写入成功 100% 全绿。拆解：top-5 污染率 41%、**重复写入 34%**（38,000 条里 12,900 条说同一件事）、换 embedding 后漂移。修复后回 89–92%。
3. **腾讯混元 Hy Memory 2.0 源码级事故**（chain_store.py）：正则抓到 path/old/new 就把"提议改法"和"改失败的 old not in s 版本"也写入版本链，后续 agent 照错误版本继续写。修复加**失败闸门**，原则是 **"抽错比抽不到更坏"**。
4. **AgentPoison**（NeurIPS 2024, arXiv:2407.12784）：优化触发词使毒经验只在特定触发下被检索，ReAct/Reflexion/Voyager 攻击成功率**接近 100%**，正常任务影响近零。
5. **Cline Memory Bank 个人对照**：token 28,400→11,200（降约 60%），输出基本持平——这是社区唯一较硬的量化。
6. **"31 Days of Vibe Coding" Day 12**：`common-ai-mistakes.md` 用 ❌标题/Wrong/Right/Why 四段式，规则是**"同一错误纠正两次就记一条"**——最朴素的错题本范式。

### 3.3 社区共识

成熟的是「**可编辑的持久记忆 + 人审升级**」；不成熟的是「自动从错误中学习且越学越准」。几乎没有「喂了踩坑记录后同类错误率下降 X%」的严格 A/B。

## 四、项目现状：已有 60% 骨架

已在运行（实测确认）：

| 组件 | 现状 |
|---|---|
| `bench/critbank.json` | **10 条**错题（C-001~C-010），每条有 `id/tags/signal/lesson/source`——已是错题本雏形 |
| `_outcome.jsonl` | **23,790 行 / 4.9MB**，write/edit 结果持续追加 |
| `_pending_learn.jsonl` | **7,793 行**，crit_hit 排队 |
| `learn_watcher.py` | 每 30s 轮询，日志显示 `[round] new_hits=0`（当前无新增） |
| 注入机制 | `crit_hit` 命中时把 lesson 附进纠正/守卫消息（如 C-001 附在纠正器 abandon 后） |

**四个关键缺口**（对照 ACE/ExpeL/ReasoningBank）：

1. **无验证状态**：不知道某条 lesson 注入后是否真的避免了重犯（`_audit_feedback.jsonl` 有 `effective` 字段但没接回 critbank）
2. **无正负计数**：10 条一视同仁，无法区分"救场 10 次"和"从没命中过"
3. **无纠错版本**：手工改 lesson 后无痕迹、无回退；`supersede/retire` 只在配置里声明（`critbankDecayEnabled: true`），实际靠 `crit_decay.py` 旁路
4. **无按任务检索**：当前是把命中的 critique 全量附进去，没有"按当前任务相似度 top-k"——经验多了会 context collapse（ACE 实证：整体重写 18,282→122 tokens，准确率跌到 57.1%）

## 五、错题本设计（可插拔 + 可修改）

### 5.1 数据格式（演进 critbank，不另起炉灶）

在现有 5 字段上扩展，**保持向后兼容**：

```json
{
  "id": "C-011",
  "tags": ["edit", "anchor", "old_string"],
  "signal": "edit 锚点失配 FS_EDIT_NOT_FOUND",
  "lesson": "用消歧注入的完整行做 old_string，不要自己拼",
  "source": "2026-11-27 会话 af09fc7c",
  "verified": false,
  "status": "candidate",
  "helpful": 0,
  "harmful": 0,
  "version": 1,
  "created_at": "2026-11-27T02:20:44Z",
  "evidence_ref": "trace:af09fc7c:4",
  "supersedes": null
}
```

字段设计依据：
- `verified` + `evidence_ref` ← CRITIC/RISE 的"外部锚定"；腾讯混元的"失败闸门"（未验证不得入库）
- `helpful/harmful` ← ACE/ExpeL 的正负计数，计数归零自动 retire
- `status`（candidate→active→superseded/retired）← Mem0 的 CRUD + bi-temporal 思想
- `supersedes` + `version` ← Letta git 式版本化；**纠错用"追加更正条目"而非静默改写**

### 5.2 闭环六阶段（对应上图）

1. **捕获**：从 `_outcome.jsonl` + trace 提取 (失败信号, 最终成功动作) **成对**样本。只记"差一点就对"的近错样本（Likra 实证影响更大）。
2. **验证闸门**：外部验证器确认（`verify_agent.py` / 状态回读 / 测试命令）。**未验证的改动不入候选区**（腾讯混元教训）。
3. **候选区**：append-only 写 `critbank.candidates.jsonl`，status=candidate，`verified=false`。
4. **人工审核**：`promote` 命令或手工改 status→active。这是**必须保留的闸口**——"一条错规则会在每个会话重复它的错误"。
5. **检索注入**：按**任务描述相似度**（ExpeL 实证最优键）取 top-3，不是全量。三维打分：recency 衰减 + importance(helpful-harmful) + relevance（Generative Agents 公式）。
6. **反馈纠错**：注入后若同类错误再次发生 → harmful+1；若没发生 → helpful+1。计数归零自动 retire。

### 5.3 可插拔性（用户明确要求）

三层插拔，从上到下：

- **数据层插拔**：`mistakeBookPath` 配置项指向任意 JSON/JSONL 文件；换文件即换错题本，不改代码。
- **机制层插拔**：`mistakeBookEnabled` 总开关（默认关，A/B 验证后再开）；`mistakeBookTopK`、`mistakeBookMinScore` 可调。
- **实现层插拔**：作为独立模块 `tools/mistake_book.mjs`（纯函数：`capture` / `retrieve` / `promote` / `retire`），index.mjs 只 import 三个函数——和刚做的 format 单一真相源同构。

### 5.4 可修改性（用户明确要求：错题本本身错了还能改）

- **纯文本**：JSON 文件直接编辑（或提供 `mistake_book.py promote/retire/edit` CLI）
- **纠错不覆盖**：改 lesson 时写 `supersedes` 指向旧条目 ID，旧条目标 `superseded` 但保留——**可追溯、可回退**
- **版本化**：文件纳入 git，每次 promote/retire 自动生成 commit（或至少 diff 日志）
- **撤销**：`retire` 可逆（status 改回 active），不物理删除
- **人审闸口**：自动提炼的候选默认 candidate，**不人审永不生效**——这是防"错规则每会话重复"的根本手段

### 5.5 防污染（社区血泪教训）

- **来源锚定**：每条必须有 `evidence_ref`（trace 行/会话 ID），无来源不入库
- **失败闸门**：只有验证成功的修正才进候选；"提议但未执行"和"执行失败"的版本绝不入库（腾讯混元事故）
- **去重**：写入前语义相似度 >0.9 的合并（华为云 34% 重复写入问题）
- **容量上限**：激活条目 ≤50（Claude Code >200 行遵守度下降）；超限时按 helpful 排序 retire 尾部
- **信任等级**：错题本 lesson 的信任等级**低于可验证工具结果**——不能被注入内容改写（AgentPoison 防御）

## 六、落地路径（分阶段，每阶段可验证）

| 阶段 | 内容 | 验证标准 |
|---|---|---|
| **P0 观测** | 保持现状，只加 trace：每条 crit_hit 注入后记录后续 N 步是否重犯 | 拿到"当前 critbank 到底有没有用"的基线数据 |
| **P1 结构升级** | critbank.json 加 6 个新字段（默认 verified=false, status=active），向后兼容 | 回归全绿，真实会话注入不报错 |
| **P2 检索 top-k** | 实现 `mistake_book.mjs` 的 retrieve，按任务相似度取 top-3 | token 注入量下降；held-out 任务上同类错误率不升 |
| **P3 候选区 + 人审** | watcher 提炼候选写 `candidates.jsonl`，CLI promote | 候选质量人工抽检 ≥70% 可用 |
| **P4 反馈闭环** | helpful/harmful 自动更新 + retire | A/B：开/关错题本，同类错误率对比（**这是唯一能证明"越学越聪明"的实验**） |
| **P5 插拔封装** | 配置项 + 独立模块 + 文档 | 换一个错题本文件即可改变行为 |

**关键**：P0 和 P4 的 A/B 不可省。没有这两步，就只是"记了很多东西"，无法证明"越来越聪明"。

## 七、诚实边界

1. **这是上下文记忆，不是权重更新**：模型本身不会变聪明，是"同类错误被规则挡住"。换纯净模型后效果归零。
2. **强提示注入仍可能绕过**：错误文本如果被注入 lesson，人审是唯一防线。
3. **35B 的行为方差仍在**：错题本提高的是"命中同类任务时的正确率上限"，不能保证每次都执行（实测同任务一次第4步改对、一次18步不 edit）。
4. **论文数字不能直接套用**：Reflexion/ExpeL 在 AlfWorld/HotPotQA，我们的场景是本地编码 agent，必须自己做 A/B。
5. **记忆越多不一定越好**：腾讯"不是越多越好"、Claude Code ">200 行遵守度下降"、ACE "context collapse"——**容量上限和淘汰机制是必需的，不是可选的**。

## 八、来源

**论文**：Reflexion 2303.11366 · ExpeL 2308.10144 · Voyager 2305.16291 · Generative Agents 2304.03442 · MemGPT 2310.08560 · MIRIX 2507.07957 · Mem0 2504.19413 · ACE 2510.04618 · ReasoningBank 2509.25140 · CRITIC 2305.11738 · STaR 2203.14465 · RISE 2505.13445 · Likra 2503.14391 · GLOW 2601.4992 · AgentPoison 2407.12784 · Evo-Memory 2511.20857

**社区**：MCP memory server · CLAUDE.md/AGENTS.md 规范 · claude-reflect · self-improving-agent · mem0/Letta/Zep-Graphiti/LangMem · Cline Memory Bank · 31 Days of Vibe Coding Day 12 · 华为云记忆召回劣化案例 · 腾讯混元 Hy Memory 2.0 源码复盘

**项目内**：`docs/QWEN36_35B_WEAKNESSES_20261122.md`（BFCL 数字与能力边界）· `docs/MIND_MODEL_CAPABILITY_EVAL_20261121.md`（异构评审可行性）· `bench/critbank.json` + `_outcome.jsonl` + `learn_watcher.py`（现有基础）
