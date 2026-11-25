# 引用与证据治理（2026-11-20~21）

> 引用审计协议+结果、证据分层标准、闸门证据标准

> 本卷合并 4 份原报告（2026-11-25 整理）。

## 本卷目录

- `CITATION_AUDIT_PROTOCOL_20261120.md`
- `CITATION_AUDIT_RESULTS_20261120.md`
- `REAL_TRACE_ACCEPTANCE_20261120.md`（原文件保留为引用桩）
- `GATE_EVIDENCE_STANDARD_20261121.md`

---

## 原报告：`CITATION_AUDIT_PROTOCOL_20261120.md`

## 引用核实协议：如何确保这次核实本身是对的（2026-11-20）

> 用户要求："逐一核实整个项目所有引用的论文和社区是否为真，依赖这些证据的决策是否严格成立，
> 梳理清单；同时告诉我你怎么确保你这次核实的正确性。"
>
> 本文回答第四问——**元层面：凭什么信这次核实**。

### 0. 为什么需要专门回答"你怎么确保正确性"

因为这次任务的失败模式我已经演示过两次：
1. agent 批量幻觉：7 篇 arXiv **编号真实、标题结论全编造**（MIND_GAPS_RESEARCH.md）
2. 我自己误用：把 Huang et al. ICLR2024（真论文，研究 intrinsic self-correction）
   拿来支撑"质疑式措辞有害"——**论文真，但它不支持那个主张**

所以"核实过"三个字本身不够——**核实方法必须能同时挡住"假引用"和"真论文误用"两类错误**。

### 1. 四层判据（每层独立判定，不许跳层）

| 层 | 判据 | 失败模式 | 标记 |
|---|---|---|---|
| L1 存在性 | WebFetch `arxiv.org/abs/<ID>` 有真实页面 | 404 / 抓取失败 | ❌不存在 / ⏳待核 |
| L2 标题匹配 | 引用声称的标题 vs 真实标题 | 编号对但标题完全无关 | ❌幻觉 |
| L3 结论匹配 | 摘要是否支持引用声称的结论 | 论文真但主张不在其研究范围 | ⚠️真实但误用 |
| L4 数字匹配 | 引用的具体数字是否在摘要中 | 数字在正文/编造/张冠李戴 | ⚠️正文未核 / ❌幻觉 |

**关键规则**：
- L1 通过 ≠ L2 通过。**"编号真实"是最容易骗过人的一层**——7 篇幻觉全过了 L1
- L3 必须读**摘要原文**，不读标题猜测。我自己的误用就是只看标题"Cannot Self-Correct"就认为支持质疑式主张
- L4 摘要没有的数字标"正文未核"，**不许默认真**——这避免了"因为论文真所以数字也真"的推论跳跃

### 2. 四重交叉验证（防止单一来源/单一执行者出错）

1. **并行分组**：86 篇 arXiv 拆 4 组给 4 个独立子任务，第 5 组核实 GitHub/社区——
   每组独立 WebFetch，互不参考，避免"一组判错全盘跟着错"
2. **主代理独立核实关键项**：决策链上的论文（ADR-0014 的 2310.01798、ADR-0018 的 2606.09498）
   我自己再 WebFetch 一遍，与子任务结果交叉。这不是不信任子任务，是**承重声明必须双源**
3. **对照原文摘录**：每条判定附真实标题 + 摘要关键句，不是只给"✅/❌"结论——
   结论可以错，原文摘录可被复查
4. **失败显式化**：WebFetch 失败标"⏳待核"，**绝不把抓取失败当通过**——
   这是"evidence layering"铁律（零证据先分辨：没触发/写到别处/默认关/真没有）

### 3. 决策链的严格性判据（回答"决策是否严格成立"）

证据真 ≠ 决策成立。对每条依赖文献的决策，分三档：

| 档 | 条件 | 处置 |
|---|---|---|
| **严格成立** | 证据 L1-L4 全过 + 决策是证据的直接推论 + 有本机实测/对照 | 保留 |
| **部分成立** | 证据真但只间接支持，或缺本机对照 | 保留但标注"依据强度：间接" |
| **不成立** | 证据假，或证据真但与决策无关 | 撤销决策或改为"未验证工程判断" |

**特别规则——不犯我上一轮的错**：
发现"证据假"时，**不许直接说"所以决策错"**（逻辑上假证据只能说明"未被证明"，
不能证明结论相反）。必须独立检查：有没有其他真证据支撑？没有就诚实降级为
"未验证的工程判断"，而不是替它找一个真论文硬套（那是我 ICLR2024 那次犯的错）。

### 4. 本次核实的覆盖与边界

- **覆盖**：86 个 arXiv 编号 + GitHub issue（#26996/#50469/#29307/#625/#42908/#6277 等）
  + 带数字的社区 URL（Anthropic 官方博客、aider wiki、hashline Context Rot 等）
- **边界**：
  - L4 数字若只在 PDF 正文、摘要未给 → 标"正文未核"，本次不下真伪结论
  - 社区博客的"营销宣称"（如 Cursor/Morph 加速倍数）单独标记，不与实测数据混为一谈
  - GitHub issue 以 WebFetch 页面可见内容为准；需登录/被删的标待核

### 5. 可复现性

- 引用清单生成脚本：`D:/Brain/_cleanup_20261118/_extract_all_citations.py`
- 引用上下文提取：`D:/Brain/_cleanup_20261118/_citation_context.py`（4 组）
- 决策链提取：`D:/Brain/_cleanup_20261118/_decision_chain.py`
- 核实结果清单：见 `CITATION_AUDIT_RESULTS_20261120.md`（本次产出）
- Protocol 本身进仓库，下次核实直接复用

### 6. 一句话总结

**"编号真实"只过 L1；我上次就在 L1 之后停了，所以放过 7 篇幻觉、还自己误用了 1 篇真论文。
这次强制走完 L1-L4 + 四重交叉 + 决策链三档判定，并把"正文未核/抓取失败"显式留白。**

---

## 原报告：`CITATION_AUDIT_RESULTS_20261120.md`

## 全项目引用核实结果清单（2026-11-20）

> 用户要求：①逐一核实所有论文/社区引用是否为真 ②依赖证据的决策是否严格成立
> ③梳理清单 ④说明如何确保核实正确性。本文是①②③，④见 `CITATION_AUDIT_PROTOCOL_20261120.md`。

### 0. 总览

| 项目 | 数值 |
|---|---|
| arXiv 编号（去重） | **86**，官方 API 全部返回（86/86，无 404）|
| GitHub issue 引用 | 9 个（第5路核实：真实一致为主，5 处小偏差需修正）|
| 社区 URL | 主核实 15 项：12 真实一致、0 幻觉、5 处小偏差 |
| 台账总条目 | **99**（config/citation_ledger.json）|
| 判定分布 | verified 7 / listed 67 / partial 6 / hallucinated 18 / pending 1 |

### 1. 幻觉引用清单（18 篇，❌禁止引用）

**特征**：arXiv 编号真实存在（过 L1），但项目编号对应的**真实论文主题与项目声称完全无关**，或数字方向相反。

#### 1.1 已清除且写进更正声明的 7 篇（ADR-0014 相关）
| 编号 | 项目曾声称 | 真实论文 |
|---|---|---|
| 2605.01403 | Answering Questions with Confidence / JS散度0.0186 | 多标签节点分类 GNN |
| 2605.11705 | Overthinking trope / -20.4pp | CAST 多模态数据选择 |
| 2605.14729 | Don't Think Twice / 二次思考降性能 | 宇宙学真空应力张量 |
| 2504.09864 | Re-Examination Prompt / 重查变差 | 平行板蒸发制冷 |
| 2605.00631 | System1/2 不是推理量 | H-RAG SemEval |
| 2606.05256 | Reasoning-Reflection-Doubt / 质疑伤小模型 | Reddit LLM 说服策略 |
| 2604.09715 | RSD / 自我怀疑致保守 | MuPPet 3D 姿态估计 |

#### 1.2 本次新增 11 篇（MIND_GAPS_RESEARCH.md，已逐条标注作废）
| 编号 | 项目声称 | 真实论文（arXiv 官方 API）|
|---|---|---|
| 2504.19413 | Mem0 71.7%/延迟14x/token+41% | Mem0 真实是 **91% 更低延迟 + 90% token 节省**（数字完全相反）|
| 2602.12106 | ESPRT | MedExChain 医疗区块链 PHR 共享 |
| 2603.25150 | Meta-CoT 22.2→46.7% | Goodness-of-pronunciation 语音发音评估 |
| 2605.02077 | Self-Constancy AUC>0.7 | Obscura Algorand 区块链隐私 |
| 2605.10686 | SkillCatalogue 54技能 | Ginzburg-Landau 超导理论 |
| 2605.11970 | Self-Braceless +10.1pp | NOFE 神经算子嵌入 |
| 2605.16281 | SkillRL 86.6→90.7% | Post-Deployment Accountability AI 治理 |
| 2605.25163 | SkillClaw | K-U-KAN 3D 牙科重建 |
| 2607.02021 | MemRL 50%反害 | 惯性自旋波物理 |
| 2608.14111 | AGU +21.3pp | NFA=FNFA 自动机理论 |
| 2608.22134 | GACP | Gopakumar-Vafa 不变量（Calabi-Yau）|

### 2. 真实但误用（6 篇，⚠️部分成立，仅作背景）

| 编号 | 真实论文 | 误用点 |
|---|---|---|
| 2310.01798 | LLMs Cannot Self-Correct Reasoning Yet | 研究 intrinsic（无外部反馈）自纠错，**不支持**"质疑式措辞有害" |
| 2606.09498 | Self-Harness: Harnesses That Improve Themselves | 真且高度相关，但 +18.7pp 摘要无（正文未核），不作 ADR-0018 唯一依据 |
| 2608.29168 | JudgePanel（紧凑 judge 达多 agent 审议，14B>70B）| 项目称"否决多 judge 投票"——论文其实**支持**用好 judge |
| 2510.12487 | Diff-XYZ | 摘要支持"小模型换格式收益小"，但项目补充"对精确锚点依赖度高"是推断非论文结论 |
| 2504.19413 等见上 | — | — |
| url:harnessrouter-hashline | Thin Model Thick Harness | 数字对但 comparator 错（原文 beat patch 14/16，项目写 ≥str_replace）|
| url:chroma-context-rot | Context Rot | 内容真，原文"non-uniform 含局部峰值"，项目写"单调"略夸大 |

### 3. 真实且一致（verified，可作决策依据）

- **arXiv:2607.16072** Frontier LMs Struggle to Copy — S14 编辑协议根因（主代理 WebFetch 核实摘要）
- **arXiv:2510.12487** Diff-XYZ — S14 小模型结论
- **arXiv:2609.38108** Plan Declaration-Execution Gap — AGENTS.md 路由表（22-45%保真率、0.48→0.92）
- **arXiv:2609.00006** Harness Engineering — ROADMAP §8（11 系统、无 vector retrieval）
- **url:anthropic-advanced-tool-use** — M5 工具面（10+ tools、72→90%、49→74%，四组数字原文核实）
- **url:aider-wiki** — S14（GPT-4 26→59%，原文 December 2023）
- **github:claude-code#26996** — S14（tab→空格 6 次 Edit 失败）
- **arXiv:2307.03172** Lost in the Middle 等 67 篇 `listed`（L1-L2 通过，未做 L3-L4）

### 4. 决策链审查（用户最关心：证据假，决策是否严格成立）

#### 4.1 已被幻觉污染但已修正的决策
- **ADR-0014 撤销强制二选一**：原 7 篇幻觉证据已清除；决策结论**保留但降级为"未验证工程判断"**——
  依据改为现场症状 + 谨慎表述，**不再声称论文证明**。理由：假证据只能说明"原推理链断了"，
  不能证明结论相反；但也没有真证据能证明它最优，所以降级而非保留"正确"标签。

#### 4.2 幻觉只停留在调研文档、未进入决策（本次核实的好消息）
- 11 篇新增幻觉**全部只在 `MIND_GAPS_RESEARCH.md`**，已标注作废
- 核查 `decisions/0015-*`（技能审批）、`config/critbank.json`、`config/AGENTS.md`：
  **均未引用这些幻觉编号**——即"技能审批/critbank/编辑协议"等机制不是建立在假证据上
- 结论：这些机制的依据需另行核实（本轮没有发现它们引用幻觉），但**未被本次幻觉污染**

#### 4.3 真论文误用方向的决策（需修正）
- **ROADMAP §8 "否决多 judge"** 引用 JudgePanel（论文其实支持紧凑 judge）→ 待修正表述
- **M5 工具面** 依据 Anthropic 官方博客：真实一致，决策严格成立 ✅
- **S14 编辑协议** 依据 RoPE 复制论文 + Diff-XYZ：真实一致，决策严格成立 ✅
- **AGENTS.md 路由表** 依据 Plan Declaration-Execution Gap：真实一致，决策严格成立 ✅

### 5. 必须修正的小偏差（社区/GitHub）
- OpenHands #6277 → 应写完整 `OpenHands/software-agent-sdk#6277`（裸号指向错误 repo）
- hashline "14/16 ≥ str_replace" → 原文是 "beat patch format for 14/16"
- Context Rot "单调下降" → 原文 "non-uniform with local peaks"
- Claude Code #26996 "6+ 分钟" → 原文是"连续 6 次 Edit 调用"

### 6. 架构级机制（已落地，确保未来决策与引用对应）

1. **`config/citation_ledger.json`**：99 条引用台账，每条带 status/真实标题/决策用途
2. **`tools/citation_guard.py`**：机器守卫——决策文档引用 hallucinated/missing/pending → FAIL；
   partial → WARN；`decision_uses` 非空必须 verified/n-a。已接入，`--quiet` rc=0
3. **`decisions/_ADR-TEMPLATE.md` 新增 Evidence 段**：未来 ADR 必填引用台账 ID + 核实状态清单
4. **本项目文档**：核实协议 + 本结果清单，均进仓库

**用户要求的固化达成**：存量已对应（幻觉清除/标注、真证据登记），未来由模板 + guard 强制对应。

---

## 原报告：`REAL_TRACE_ACCEPTANCE_20261120.md`

## 真实运行验收：路线图"已完成"声明到底兑现没有（2026-11-20）

> 用户质疑：会不会"看着 A 改 B"——文档宣称完成，实际改/验的是别的东西。
> 本文用**运行中 dsh 真实产生的 trace/产物**作为唯一证据，不用代码存在、不用单测通过、不用文档声明。

### 一、方法论：先排除假证据

`_trace.jsonl` 共 **9666 行**，但按 sid 分组后发现：

| sid | 行数 | 性质 |
|---|---|---|
| `s1` | **8592（89%）** | **单测伪造数据**（含 100 次假 audit fail、81 次假 critic fail）|
| `budget-3/4` | 139 | 我的 M4 调试会话 |
| 其他短 sid（`269ec283`/`f8a7f057`/`8a3fc041` 等）| **883** | **真实 dsh 会话** |

**任何不排除 s1 的"trace 里有 X 所以机制生效"论证都是被单测污染的。**
我曾经差点把"角色 LLM 成功率 9.7%"当成生产故障——那全是 s1 假数据。

### 二、逐项验收（真实会话 883 行）

| 路线图声明 | 真实 trace 证据 | 判定 |
|---|---|---|
| GWT 共享状态总线 | `control_turn` **19** | ✅ 真实触发，带 snapshot |
| FEP 预期闭环 | `fep_cycle` **19** | ✅ |
| CritBank 命中 | `crit_hit` **17** | ✅ |
| mind_state 中性注入 | `mind_state` **15** | ✅ |
| 技能卡渐进披露 | `skill_card` **11** | ✅ |
| 学习回注 | `learn_feedback` **8** | ✅ |
| verify-on-stop | `verify_on_stop` **5** | ✅ |
| S9 有状态反馈 | `review_state` **3** + `review_echo` **2** | ✅ 真实写入并回灌 |
| S6 注入检测 | `injection_hit` **1** | ✅ **受控实验真实触发**（见 §三）|
| S8 审计自校准 | 独立产物 `_audit_feedback.jsonl` **3 条真实结算** | ✅（写独立文件，不在主 trace）|
| D5 审计门控 | 由 review_state 的 3 次触发佐证 | ✅ |
| S4 自适应路由 | `adaptive_route` **0** | ⚠️ **符合设计**（S4 结论就是默认关闭）|

**结论：路线图承诺"已完成"的机制，在真实 dsh 运行中全部找到对应证据，不是纸面完成。**

### 三、两个"零证据"的辨析（避免误判）

#### 3.1 S6 曾真实会话 0 次命中 —— 受控实验补证
原统计里真实会话 `injection_hit=0`，43 条全在我的调试会话 `budget-3/4`。两种可能：
① 真实工具结果里确实没有注入文本（正常）；② 插件没在真实路径扫描。

**受控实验**：造 `_s6_probe.txt`（含 "IGNORE ALL PREVIOUS INSTRUCTIONS" + "请忽略之前的指令"），
发新会话让 dsh 用 read 读取。结果：`sid=8a3fc041` 的 trace 在 step 1 出现 `injection_hit` ✅。
→ S6 在真实路径生效，之前的 0 只是"没喂注入内容"。

#### 3.2 S8 主 trace 里 0 条 —— 命名/落点差异，不是没实现
S8 的结算写**独立文件** `_audit_feedback.jsonl`，不是主 trace 的 kind。实际内容 3 条：
```
gate=repeated-failure  badNow=1 effective=false stepNow=6
gate=post-compaction   badNow=0 effective=true  stepNow=19
gate=post-compaction   badNow=0 effective=true  stepNow=41
```
有 true/false 两种有效性判定——正是 S8 设计的"度量审计干预是否有效"。
→ 用"主 trace 里搜 audit_feedback kind"会误判为没实现，这是典型的"看着 A 改 B"。

### 四、诚实保留的边界（仍有观察项）

- **S1 P3 / 双 split 真实评测**：ADR-0018 有意未启动，非"宣称完成但没做"——路线图已标 PARTIAL。
- **M7 / L5 小模型方案**：S7 证伪 0.6B 实时外设，已降级；不是"完成"。
- **S8 有效率报告**：DoD 要求累计 ≥30 条才出报告，当前 3 条，需长期运行。
- **异步竞态 / steer 通道不计 token**：上轮深度维护列为观察，本轮无新证据，保持观察。

### 五、这轮整治里我自己犯的"看着 A 改 B"（留档警示）

1. **版本假象**：前几轮手工 cp 新 index.mjs 到 node_modules，版本号却停在 2.3.0，
   一次 pnpm install 就把新代码覆盖回旧版——"运行版是新的"是假象。
2. **改错仓库**：把运行版 autostart 覆盖到 Workspace 的旧 clone（commit 39f216c v1.1.0），
   真正权威源是 `D:/Brain/publish/dsh-llama-server-autostart`（v1.1.1）→ 已 git checkout 回滚。
3. **`!!js` 补丁**：试图把路径改成 YAML `!!js` 表达式，实测让 dsh 启动失败 → 回滚，
   改用"从包内 patch 删路径键、由参数化 DEFAULTS 接管"。
4. **限帧器残留**：`Stop-Process -Force` 不触发 Python finally，EcoQoS 残留 → 加 `--release-all` 兜底 + 父进程看门狗。

**这些教训共同指向一条铁律**：验收必须区分"权威源 / 运行版 / 副本"三份拷贝，且只认真实运行证据。

> 遵循知识资产沉淀规则。证据来自运行中 dsh 的 `_trace.jsonl` 与 `_audit_feedback.jsonl`，非单测非文档。

---

## 原报告：`GATE_EVIDENCE_STANDARD_20261121.md`

## 闸门证据标准：让"需拍板/需验证"不再空泛（2026-11-21）

> 缘起：用户问"按科技树是不是该先拍板哪些工具进内核"——查发现 M5 卡了很久，
> 不是因为决策难，而是**拍板需要的数据一直没结构化**：数据躺在 docs 和 dump 里，
> 闸门只写"用户拍板哪些工具进内核"，看不出"数据齐没齐、还差什么"。
> 用户要求"把所有类似问题解决了"——本文是通用解法。

---

### 一、问题：闸门有四种，只有一种该等人

| 闸门类型 | 例子 | 缺什么 | 怎么解 |
|---|---|---|---|
| **指标型** | P-86M-LATENCY 延迟<500ms | 无（有阈值）| 保持，跑测试验 |
| **数据支撑型** | P-USER-DECISION 拍板工具 | **数据没进闸门** | ← 本次修复重点 |
| **外部依赖型** | P-UPSTREAM-PR 等上游合并 | 无（等外部事件）| 标 HUMAN，不硬造 |
| **阈值待定型** | P-SWEBENCH 迁移子集 | 没定达标线 | 诚实标"阈值待定"，不硬造数字 |

**核心洞察**：`P-USER-DECISION` 不是"纯人工决策"——它是**数据可支撑的决策**。
把它归进"纯人工"是分类错误，导致数据缺口被隐藏。

---

### 二、M5 修复实例（模板）

**修前**：`preconditions: ['P-USER-DECISION: 用户拍板哪些工具进内核']`，manual-blocked，看不到数据状态。

**数据其实一直存在**：
- `docs/MEMORY_TO_MIND_MODEL_20261120.md` 记录"工具面28个、单会话只用11个、17零调用"
- `archive/session-dumps/_cur*.jsonl` 8个**累积快照**（首callId相同=同一会话），按callId去重后 **375 次唯一调用**

**但 `tools/tool_audit.py` 是断的**：
- 默认路径 `bench/_cur8.jsonl` 不存在（历史遗留）
- 要求 request/header 含 tools schema，否则报"无法审计"——真实 dump 只有 tool/call 事件

**修法（四步）**：
1. 修 `tool_audit.py`：默认指向真实 dump、兼容无 schema 格式、加 `--json` 机器可读
2. 实测产出：`1 会话 / 375 唯一调用 / 11 工具 / 前5占90% / 前8占98%`（初版误把8快照当8会话、重复计数成2849，2026-11-21 修正）
3. M5 加结构化 `data_gates`：
   ```yaml
   data_gates:
     - id: P-TOOL-FREQ-AUDIT
       desc: 工具频次审计：1会话(8快照去重)/375调用/11工具/前5占90%;单一会话不足拍板
       status: satisfied
       evidence: tools/tool_audit.py --json
       source: docs/... + archive/session-dumps/_cur*.jsonl
   decision_note: 数据已齐……拍板只需决定砍哪些低频工具，不再是拍脑袋
   ```
4. 科技树 M5 卡显示 `📊1/1` 角标，侧栏显示数据前置 + 决策状态

**结论**：闸门从"空泛拍板"变成"📊数据齐、只差你拍板"——决策成本大幅下降。

---

### 三、通用处理规则（以后照此办理）

遇到"卡在需拍板/需验证"的闸门：

1. **先分类**：指标型 / 数据支撑型 / 外部依赖型 / 阈值待定型
2. **数据支撑型**必须有 `data_gates`（含 id/desc/status/evidence/source）
   - `status: satisfied` 且 evidence 脚本可跑 → 卡上显示 📊N/N
   - 缺数据 → 审计报 VAGUE，禁止声称"只差拍板"
3. **空泛描述回填阈值**：从卡片自己的 `abort_if`/`caveats` 里提取（不硬造）
   - 例：M9 的"中文表现验证" → "中文准确率>=92%"（来自 abort_if）
4. **真无阈值的诚实标"阈值待定"**，不编数字
5. **纯外部/治理决策**标 HUMAN，不要求数据脚本

---

### 四、防回归

`tools/audit_gate_evidence.py --strict` 进门禁：
- 12 条前置逐条分类：6 指标 / 1 数据齐 / 5 人工或待定 / **0 空泛**
- **负对照验证**：删掉 M5 的 data_gates → P-USER-DECISION 立刻变 ✗空泛、审计 FAIL；恢复 → PASS
- 关键设计：`P-USER-DECISION` **不在** HUMAN_DECISION 白名单——它是数据支撑型，缺数据必须报错

`tools/tool_audit.py --json` 也进门禁——数据管道断了会立刻发现。

---

### 附：给用户的实际建议（2026-11-21 晚更正）

**⚠️ 数据不足以拍板砍工具。** 初版统计有严重错误：
- `archive/session-dumps/_cur*.jsonl` 的 8 个文件**不是 8 个会话**，而是同一会话的
  **累积快照**（首 callId 全为 `6Z9glrMOAM`、时间跨度层层递增）；
- 我把重复调用算了 8 遍 → 得出虚假的"2849 次调用"；
- **按 callId 去重后只有 375 次唯一调用、11 种工具、单一任务**
  （"用 SearXNG 写搜索浏览器"——前端/网络调试场景）。

修正后结论：
| 指标 | 修正前（错）| 修正后（实）|
|---|---|---|
| 会话数 | 8 | 1（8 个累积快照）|
| 调用数 | 2849 | 375（去重）|
| 低频工具 | web_fetch 8 / load_workspace 8 / job_kill 16 | web_fetch 1 / load_workspace 1 / job_kill 2 |

**为什么仍不够拍板**：
1. 样本只有 1 个会话、1 类任务（搜索浏览器），低频工具可能只是"这个任务没用到"
2. `job_*` / `web_fetch` 本就禁用/不可用——它们的调用是模型在踩坑，不是需求信号
3. "28 工具"是配置上限，不是实际暴露清单——"17 个零调用"是 28−11 推的，无证据

**拍板前还需要**：覆盖 ≥5 个不同任务类型的会话（系统管理/数据分析/长文档/编码/调研），
按 callId 去重统计；并区分"从未暴露"与"暴露但零调用"。

`tool_audit.py` 已加 callId 去重（输出 duplicate_snapshot_calls），防止再犯。
