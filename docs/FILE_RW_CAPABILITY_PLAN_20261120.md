# 文件读写能力：路线图优先级调整与新卡提案（2026-11-20）

> 用户："它的弱点在于读写文件，当务之急是赋予它高水平的读写能力，防止浪费大量时间写垃圾。
> 这个目标有哪些卡靠得比较近、优先级前提；有哪些可以做成新卡，调研并放进路线图。"

## 0. 证据基准（先摆事实，避免凭印象开卡）

### 0.1 真实 trace 工具失败率（过滤测试 sid，今天 2026-11-20）

| 工具 | OK | FAIL | 失败率 |
|---|---|---|---|
| **write** | 24 | 0 | **0%** |
| read | 169 | 7 | 4.0% |
| edit | 15 | 2 | 11.8% |
| grep | 21 | 3 | 12.5% |
| glob | 23 | 4 | 14.8% |
| **pwsh** | 102 | 20 | **16.4%** |

**关键结论**：`write` 工具本身 100% 成功——"读写能力弱"**不是写工具坏了**。
真正的浪费来自：①pwsh 跑 python/node 的 ENOENT/ParserError（16.4% 失败）
②edit old_string 匹配失败（11.8%）③写了 24 次却大多写到临时补丁脚本而非有效产物。

**垃圾率实证**：A1_6 一张卡留下 5 个临时补丁脚本（`_apply_fix.py`/`_apply_future_claim.py`/
`_fix_index.py`/`_patch_future_claim.py`/`fix_index.js`）全部"写了没应用"，最终归档到
`docs/archive/a16-patch-scripts/`。有效产物只有 index.mjs 一处改动。
**写 24 次 ≈ 5 个垃圾 + 1 个有效**——这是"浪费时间写垃圾"的直接量化。

**所以正确目标不是"让 write 更可靠"，而是"让 agent 少绕路、少写垃圾、写完必落盘"。**

### 0.1b 读写漏斗（用户的"识字率"类比，量化）

按 sid+时间重建真实事件序列（8 个真实 sid）：

| 指标 | 值 | 含义 |
|---|---|---|
| read 调用 | 148 | "读"动作 |
| write/edit 调用 | 41 | "写"动作 |
| **read→write 转化** | **18.2%** | 读了 5.5 次才落 1 次盘 |
| 出现"连续读≥5无写"的会话 | **6/8** | 系统性，非偶发 |
| 单会话最多 read | 63 次 | 8554ffde |

**瓶颈定位**：不是"写不准"（write 0% 失败），也不是完全"读不到"（read 仅 4% 失败），
而是**读了大量内容却没有转化为写入**——决策（读什么）与执行（写什么）之间的断层。
这正对应"识字率"类比：认识字（能 read）不等于会写文章（能产出），
中间缺的是"读完后形成写入决策并落地"的转化能力。

### 0.2 harness 的控制边界（重要）

工具（write/edit/read/pwsh...）是 **dsh 原生**的，harness 只是旁观+注入（index.mjs 无工具注册，
只有 trail/trace 记录）。我们**改不了 dsh 工具的实现**。

⚠️ **上一版结论"只能行为治理"是错的，已纠正**：工具实现改不了 ≠ 编辑格式改不了。
学术+工程证据（见 §6）表明**编辑格式才是最大杠杆**：
Aider 换编辑格式让 GPT-4 Turbo 20%→61%、GPT-4 26%→59%（3 倍），
同模型好脚手架 SWE-bench 49% vs 简脚手架 18-22%。
而格式是能通过 **AGENTS.md / 技能卡 / 派活 prompt 引导**的——不需要碰 dsh 工具代码。
→ 新卡应同时覆盖"行为治理"和"编辑协议升级"两条线。

**现场证据**：`config/AGENTS.md:105` 当前指引是 `read 目标 → edit → 验证`——
正是最弱的裸 search/replace，且没有"紧邻重读 + 最短唯一锚点"要求。这就是可直接改的杠杆。

### 0.3 今天的事故模式

1. **edit old_string 截断**：中文残片漏进 index.mjs（C-010）
2. **补丁脚本不应用**：反复写修复脚本却从没成功落地（A1_6，read 循环 + pwsh 死循环）
3. **pwsh 绕路**：agent 用 pwsh 跑 python/node，ENOENT/ParserError 反复失败
4. **"我将..."将来时承诺不落盘**：A1_6 守卫已治

## 1. 现有卡盘点与优先级调整（已落地）

| 卡 | 原状态 | 与读写能力的关系 | 调整 |
|---|---|---|---|
| **A3_5** 安全地基（真实diff+回滚）| done | 读写正确性地基：逐行 diff + sha256 前后校验 | cost 中→低（经验复用）|
| **M7** 格式修复器 | manual-blocked | edit 截断/格式错配的直接解药 | cost→低、benefit→高，值得评估解锁 |
| **S3** 频次 trace | done | 工具失败率画像的基础设施（本次分析就靠它）| cost→低 |
| A1 会记路（机器判据）| done | 判据可信是"写完验收"的前提 | 保持 |
| A1_5 判据元验证 | done | 防判据假绿 | 保持 |
| A1_6 将来时承诺守卫 | done | 防"说要写"不落盘 | 保持 |
| M4 工具面收敛 | manual-blocked | 减工具面→少 pwsh 绕路（治本但涉产品决策）| 保持 blocked，待用户拍板 |

**排序机制的坑**：`rank` 数字字段**根本没被代码读取**（grep 全库无引用）——
真正排序只看 `rank_hint` 分桶 + `benefit/cost` 分数（`sort_cards_by_roi()`）。
所以"优先级前提"的正确做法是改 `benefit/cost`/`rank_hint`，不是改 rank。已按此调整。

## 2. 新卡（已开，均 ready / deps=A1）

| id | 卡 | what | 为什么现在开 | 判据 |
|---|---|---|---|---|
| **S13** | verifyRan 收紧（read≠验证）| 把 `index.mjs:913` 的"read/cat 即 verifyRan"收紧为真实验证证据 | **假绿源头**：A1_6 连续 6 次 read 同段无 write 却一路绿灯 | test_verify_ran.py + file_grep |
| **S11** | 写后校验覆盖全部写工具 | verify-on-edit 从只认 write/edit 扩到 8 种写工具 | `DEFAULT_WRITE_TOOLS` 列了 8 种，`:1042` 只捕获 write/edit，其余 6 种零校验 | test_write_verify_all.py |
| **S12** | 补丁应用闭环（禁写脚本不落地）| 补丁脚本写入后必须有 apply 证据（目标 mtime+语法）| 一张卡 5 个补丁脚本全没应用——"写了脚本≠应用了脚本" | test_patch_applied.py |

三卡形成闭环：**S13 让"验证过"可信 → S11 让"所有写入都校验" → S12 让"写脚本必须落地"**。

## 3. 明确不做（避免重复证伪方向）

- ❌ **改造 write 工具本身**：trace 实证 write 0% 失败，工具没坏——造这种卡是浪费
- ❌ 无差别提高自动化频次（§8 已证伪）
- ❌ apply_patch 替代 edit（§8 已证伪：无稳定收益）
- ❌ 小模型做审计/纠正（§8：一致率 45-60% 近抛硬币）
- ❌ 堆更多 judge（§8：9 judge≈2 票）

## 4. 落地动作（已完成）

1. ✅ 优先级调整：A3_5/M7/S3 的 benefit/cost（真正生效的字段）
2. ✅ 开 3 张新卡 S11/S12/S13 进 ROADMAP_GRAPH + LADDER
3. ✅ `--refresh` 重排视图（24 张卡）
4. ⏳ 下一步：从 S13 开始推卡（假绿源头优先）

## 5. 调研来源

- Explore-1：现有卡盘点 + CritBank + rank 机制（发现 rank 数字是装饰品）
- Explore-2：harness 读写机制深挖（发现 8 写工具仅 2 个被校验、`:913` read 即验证）
- 主代理：trace 工具失败率硬证据 + A1_6 垃圾率量化 + 控制边界确认

## 6. 学术根因调研（2026-11-20，已核实关键论文真伪）

> 用户类比："高质量读写 = 正确决策（读什么/写什么）+ 准确执行（找到文件、写入设想内容），
> 就像识字率——不识字则心智无从谈起。"下面按"决策层 / 执行层 / 压缩 / 自救 / 评测"分层给证据。
> 【证据】=论文有实验数据；【推测】=文献外推、本环境未验证。

### 6.1 决策层：为什么选错要读的文件

- 【证据】**Lost in the Middle**（Liu et al., TACL 2024, arXiv:2307.03172）：
  答案文档放首位 GPT-3.5-Turbo 得 75.8%，放中间仅 53.8%，放末尾 63.2%，
  而"不给任何文档"的闭卷基线是 56.1%——**放中间比没给还差**。U 型曲线在 MPT-30B、
  LongChat-13B、Claude-1.3 均复现；检索文档从 20 篇增到 50 篇仅提升约 1.5%。
- 【证据】**RULER**（Hsieh et al., ACL Findings 2024）：17 个声称支持 32K+ 的模型中
  只有约一半在该长度表现可接受；有效上下文约为标称长度的 60-70%。
- 【证据】**RepoGraph**（arXiv:2410.14684）：文件级 RAG 只找到"语义相似"而非"真正相关"；
  把仓库当扁平文档、缺全局结构时会窄焦个别文件陷入局部最优；引入行级代码图后
  SWE-bench 平均**相对提升 32.8%**。
- 【证据】**CodexGraph**（arXiv:2408.03910）：单文件任务强、仓库级任务弱，相似度检索在复杂任务召回低。

### 6.2 执行层：为什么决定了"写什么"却写不准

- 【证据·机制】**Frontier LMs Struggle to Copy**（Wen et al., arXiv:2607.16072，2026-07-17，
  已 WebFetch 核实论文存在与摘要）：根因是 **1D 位置编码（RoPE）的归纳偏置**——
  模型靠"局部上下文匹配"捷径复制，遇重复子串会跳到错误位置；提出 2D-RoPE
  （行 ID + 列 ID）让复制变成"固定列偏移检索"。摘要原话："even frontier models fail to
  perform a much simpler operation: exactly copying an input string that lies well within their
  context windows"。**这直接解释我们的 C-010：模型凭近似记忆重建 1300 字符 old_string 必然出错。**
  （具体复制率数字 21.6%→0% / 2D-RoPE 87.3% 是论文正文实验数据，摘要未直接给，引用需注明）
- 【证据】**BFCL**（Patil et al., PMLR 267, 2025, arXiv:2406.16657）：5,551 任务；
  gpt-4o 单轮简单 AST 79.4-95.5 分，但 **memory 仅 6.0/100**，全表最高 12.0——
  长程状态管理远未解决，**调用语法不是瓶颈**。
- 【证据·工程】精确字符串替换在真实仓库约 20-30% 失败（OpenCode 实践）——
  我们的 edit 11.8% 失败率其实优于业界常态。
- 【证据·工程】**Aider 编辑格式基准**（2023-12 laziness benchmark，来源 aiwiki.ai/wiki/aider，
  已核实）：GPT-4 Turbo 用 search/replace 仅 20%，换 udiff 后 **61%**；
  GPT-4 26%→**59%**。Diff-XYZ 2025：search/replace 对大模型最强，
  **结构化 udiff 变体对小模型更忠实**——对 35B 尤其相关。
- 【证据】失败反馈缺陷（opencode issue #42908）：old_string 不匹配时若只返回"未找到"
  而无上下文，中等模型多数直接放弃——不重读、不重试、静默 no-op。

### 6.3 压缩/长会话

- 【证据】**Context Rot**（Chroma, 2025-07）：18 个模型（GPT-4.1/Claude4/Gemini2.5/Qwen3 等）
  随输入变长性能单调下降；纯"复述单词"任务（25→10000 词）也退化，
  证明是**注意力分布属性而非理解失败**；仅插入 1 个似是而非的干扰项就掉点。
- 【证据】Google 自测 Gemini 3 Pro 在 MRCR 上从 128K 的 77% 跌至 1M 的 26.3%。
- 【推测】C-010 本质是压缩丢弃字节级精确信息，模型只能凭近似记忆重建 old_string；
  机制有文献支持，但本环境未做对照实验。

### 6.4 反馈自救

- 【证据】**LLMs Cannot Self-Correct Reasoning Yet**（Huang et al., ICLR 2024, arXiv:2310.01798）：
  无外部反馈的内在自我纠错无效甚至有害——GPT-4 GSM8K 95.5%→89.0%（2 轮），
  Llama-2-70B 62.0%→**36.5%**；模型更倾向把正确答案改错。
- 【证据】给 oracle 停止信号时 GPT-4 可达 97.5%；Reflexion 有效是因测试失败等真实反馈；
  CRITIC 去掉检索/代码执行工具后效果骤降。
- 【推测】35B 无外部验证时"自己想想哪里错了"大概率更差——**我们的守卫路线是对的**。

### 6.5 工具素养评测

- 【证据】**ToolBench**（Qin et al., ICLR 2024, arXiv:2307.16789）：16,464 API/49 类；
  ChatGPT-DFSDT 69.6%、ReAct 44.0%、ToolLLaMA 61.0%；**跨工具/I3-Inst 仅 40-57**。
- 【证据】**τ-bench**（Yao et al., 2024, arXiv:2406.12045）：GPT-4o retail 61.2%、
  airline 35.2%；**pass^8 retail <25%（一致性崩塌）**；弱模型去掉 policy 几乎不变
  （暗示弱模型根本没用规则）。
- 【未找到可靠来源】"tool-use literacy / API literacy"作为独立学术构念——
  用户的"识字率"类比无直接学术对应，概念散落在 tool learning / agent 基准中。

### 6.6 对本 harness 的可操作启示（已据此调整路线图）

1. **让模型引用而非重述**：强制"改前紧邻重读 → 最短唯一锚点 → 立即写"，
   避免凭记忆逐字重现长串（针对 RoPE 复制缺陷 + C-010）。→ 开卡 S14
2. **压缩设锚点护栏**：压缩后第一步强制重读目标文件再编辑（堵 C-010 类截断）。→ 并入 S14
3. **放弃自我纠错幻想**：失败后要求"重读 + 报告差异 + 重试"≤2 次，仍失败即上报
   （ICLR 2024 证据支持外部信号而非内省）。→ 并入 S12/S13
4. **编辑格式是最大杠杆**：AGENTS.md:105 的裸 `read→edit` 是最弱格式，
   应升级为带锚点/udiff 类结构化协议（Aider 3 倍证据）。→ 开卡 S14
5. **按 pass^k 而非单次成功率评估**：τ-bench 显示一致性崩塌，单次绿不代表可靠。
   → 并入 A1_5 判据元验证的经验
6. **工具面裁剪有学术依据**：跨工具编排 40-57%，28 个工具面确实偏多。→ M4 保持 blocked 待拍板


## 7. 社区工程实践调研（2026-11-20，关键论文已 WebFetch 核实）

> 来源：aider 官方基准/文档、Anthropic 官方工程博客、Claude Code GitHub issues、
> edit-doctor、Diff-XYZ（arXiv:2510.12487 已核实）、hashline（HN 623分）、Prosodica（AI Engineer 2026）。

### 7.1 为什么收敛到 old_string 精确匹配（而非行号）

- 【实测】**Claude Code 内部设计**（社区整理的 `claude-code-internals`）：字符串匹配四理由——
  无行号漂移、自验证（找不到显式失败而非静默改错）、上下文可审、近似幂等；强制"先读后改"、
  old_string 必须唯一、大重构拆小编辑。
- 【经验】行号三宗罪：漂移/off-by-one、LLM 数不准但复制文本准、把 Read 输出的 `12→` 前缀一起复制必然失配；
  以及"过期视图"（模型脑子里的原文是十轮前读的）。
- 【实测】aider 明确让模型写 `@@ ... @@` 而非行号——"GPT is terrible at working with source code line numbers"。

### 7.2 edit 失败的字节级根因（与 C-010 同构）

- 【实测】**Claude Code issue #26996**：Go 文件 tab 缩进，Read 把 tab 显示成空格 → Opus 4.6 用空格复现 →
  **同一文件连续 6 次 Edit 全失败**，最终放弃 Edit 改用 `python3 -c` 带 `\t`。
  关联 #9163/#7197/#6729/#2644 均 "auto-closed without resolution"。
- 【实测】#52813：`\u00A0` 被归一化为 NBSP，六种 ASCII 字符永远匹配不上；
  **Windows 头号成因是 CRLF vs LF**（#13456/#27718），还有 BOM/UTF-16。
- 【实测】**aider `SearchReplaceNoExactMatch` 四类根因**：模型意译而非复制、输出错格式、
  文件在 chat 外被改、stale；强模型第二次通常恢复，**弱模型循环到 "Only 3 reflections allowed, stopping"**。
- 【经验】aider 官方：上下文 >25k tokens 后多数模型开始不遵守 system prompt，本地/量化模型更易违规；
  Ollama 默认 2K–4K 上下文静默截断 → 必然失配。
- 【实测】"applied 0 of N edits" 静默失败：工具报成功、代码半应用——
  这是"AI 说改好了 bug 还在"的最常见原因。

### 7.3 有效解决模式（含数据）

- 【实测】**edit-doctor**（PostToolBatch hook）：失败匹配是 validation error，
  PreToolUse/PostToolUseFailure 都不触发，只有 PostToolBatch 能看到；
  hook 重读文件、忽略空白/不可见字符差异、逐行列出 tab vs 空格并给可复制文本——
  **模型第二次即成功**，纯旁路诊断不改工具。← 最符合我们"dsh 工具不可改"约束
- 【实测】**aider 多级容错**：exact → 空白不敏感 → 缩进保留 → difflib 模糊；
  失败反馈含"Did you mean these actual lines? 其他块已成功，别重发，只回失败块"。
- 【实测】**hashline**（Can Bölük "The Harness Problem"，16模型×3格式×180任务×3次）：
  Grok Code Fast 1 从 patch 6.7%→**68.3%**；14/16 模型 hashline ≥ str_replace。
  ⚠️口径：10x 是对 patch，对 str_replace 仅约 +4.6pp——别夸大。
- 【实测·关键修正】**Diff-XYZ**（arXiv:2510.12487，NeurIPS'25 workshop，1000 真实 commit）：
  search-replace 对大模型最好、udiff 略弱；**"smaller open models benefit little from any formatting choice"**。
  → 我们是 35B，**不能套用 Aider 大模型 26%→59% 的结论**，S14 已据此从"结构化格式"转向"降低复现负担"。
- 【实测(转引)】aider issue #625：400 行以下全文重写成功率高于 search/replace；
  Cursor/Morph 收敛到同一边界。
- 【实测(需核实原始基准)】闭环反馈 > 换更强模型：能自跑测试看 lint 并迭代的 agent，
  与不能的差距 > 任意两个前沿模型之间差距。

### 7.4 工具数量：推翻"40 个上限"

- 【官方】**Anthropic 工程博客**：58 工具约 55K tokens → Tool Search + defer_loading 降至 ~8.7K（−85%）；
  MCP eval Opus4 49%→74%、Opus4.5 79.5%→88.1%；判据是 **10+ tools 就该考虑**、
  工具定义 >10K tokens，**没有说"超过 N 必然退化"**；Tool Use Examples 使复杂参数准确率 **72%→90%**。
- 【实测】Prosodica（AI Engineer 2026）：10工具78% → 100工具<40% → 741工具13.6%；语义路由 top-K=5 全程>83%。
- 【实测(社区)】弱模型拐点更低：DeepSeek V4 5→30 工具准确率 95%→53%，**拐点 12–15 个**。
- **结论**：40 是经验阈值非硬上限；弱/本地模型拐点可低至 12–15。我们 28 个工具在风险区——
  M5 工具面收敛卡的 why 已据此修正（保持 manual-blocked，需你拍板）。

### 7.5 反例/教训（避免重复踩坑）

- 【实测】aider 早期基准：**function calling API 反而比整文件 markdown 更差**（尽管厂商宣称更可靠）。
- 【经验/争议】"Fast Apply Models are Already Dead"（Cline）：前沿模型够强时 scaffolding 反成约束；
  但与弱模型/大目录场景不同，不可一概而论。
- 【实测】情绪化提示词（"用户是盲人/给$2000小费"）在 aider 基准上**更差**。
- 【经验】纯行号方案不是银弹：行号漂移 + stale edit 导致静默损坏，无通用最优格式。

### 7.6 由此产生的路线图修正（已落地）

1. **S14 重心修正**：从"结构化 udiff 格式"→"降低复现负担"（短文件整块、最短锚点、紧邻重读、失败诊断回灌），
   因 Diff-XYZ 证明小模型换格式收益小。
2. **M5 why 修正**：旧"社区上限约40"→ Anthropic 官方 10+、弱模型拐点 12-15。
3. **新增 edit-doctor 式失败诊断**并入 S14（纯旁路，不改工具）。
4. **工具面收敛仍是你的拍板项**（M5 autonomous=false）——证据更充分了，但价值判断不替你做。

