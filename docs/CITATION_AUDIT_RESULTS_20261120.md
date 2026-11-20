# 全项目引用核实结果清单（2026-11-20）

> 用户要求：①逐一核实所有论文/社区引用是否为真 ②依赖证据的决策是否严格成立
> ③梳理清单 ④说明如何确保核实正确性。本文是①②③，④见 `CITATION_AUDIT_PROTOCOL_20261120.md`。

## 0. 总览

| 项目 | 数值 |
|---|---|
| arXiv 编号（去重） | **86**，官方 API 全部返回（86/86，无 404）|
| GitHub issue 引用 | 9 个（第5路核实：真实一致为主，5 处小偏差需修正）|
| 社区 URL | 主核实 15 项：12 真实一致、0 幻觉、5 处小偏差 |
| 台账总条目 | **99**（config/citation_ledger.json）|
| 判定分布 | verified 7 / listed 67 / partial 6 / hallucinated 18 / pending 1 |

## 1. 幻觉引用清单（18 篇，❌禁止引用）

**特征**：arXiv 编号真实存在（过 L1），但项目编号对应的**真实论文主题与项目声称完全无关**，或数字方向相反。

### 1.1 已清除且写进更正声明的 7 篇（ADR-0014 相关）
| 编号 | 项目曾声称 | 真实论文 |
|---|---|---|
| 2605.01403 | Answering Questions with Confidence / JS散度0.0186 | 多标签节点分类 GNN |
| 2605.11705 | Overthinking trope / -20.4pp | CAST 多模态数据选择 |
| 2605.14729 | Don't Think Twice / 二次思考降性能 | 宇宙学真空应力张量 |
| 2504.09864 | Re-Examination Prompt / 重查变差 | 平行板蒸发制冷 |
| 2605.00631 | System1/2 不是推理量 | H-RAG SemEval |
| 2606.05256 | Reasoning-Reflection-Doubt / 质疑伤小模型 | Reddit LLM 说服策略 |
| 2604.09715 | RSD / 自我怀疑致保守 | MuPPet 3D 姿态估计 |

### 1.2 本次新增 11 篇（MIND_GAPS_RESEARCH.md，已逐条标注作废）
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

## 2. 真实但误用（6 篇，⚠️部分成立，仅作背景）

| 编号 | 真实论文 | 误用点 |
|---|---|---|
| 2310.01798 | LLMs Cannot Self-Correct Reasoning Yet | 研究 intrinsic（无外部反馈）自纠错，**不支持**"质疑式措辞有害" |
| 2606.09498 | Self-Harness: Harnesses That Improve Themselves | 真且高度相关，但 +18.7pp 摘要无（正文未核），不作 ADR-0018 唯一依据 |
| 2608.29168 | JudgePanel（紧凑 judge 达多 agent 审议，14B>70B）| 项目称"否决多 judge 投票"——论文其实**支持**用好 judge |
| 2510.12487 | Diff-XYZ | 摘要支持"小模型换格式收益小"，但项目补充"对精确锚点依赖度高"是推断非论文结论 |
| 2504.19413 等见上 | — | — |
| url:harnessrouter-hashline | Thin Model Thick Harness | 数字对但 comparator 错（原文 beat patch 14/16，项目写 ≥str_replace）|
| url:chroma-context-rot | Context Rot | 内容真，原文"non-uniform 含局部峰值"，项目写"单调"略夸大 |

## 3. 真实且一致（verified，可作决策依据）

- **arXiv:2607.16072** Frontier LMs Struggle to Copy — S14 编辑协议根因（主代理 WebFetch 核实摘要）
- **arXiv:2510.12487** Diff-XYZ — S14 小模型结论
- **arXiv:2609.38108** Plan Declaration-Execution Gap — AGENTS.md 路由表（22-45%保真率、0.48→0.92）
- **arXiv:2609.00006** Harness Engineering — ROADMAP §8（11 系统、无 vector retrieval）
- **url:anthropic-advanced-tool-use** — M5 工具面（10+ tools、72→90%、49→74%，四组数字原文核实）
- **url:aider-wiki** — S14（GPT-4 26→59%，原文 December 2023）
- **github:claude-code#26996** — S14（tab→空格 6 次 Edit 失败）
- **arXiv:2307.03172** Lost in the Middle 等 67 篇 `listed`（L1-L2 通过，未做 L3-L4）

## 4. 决策链审查（用户最关心：证据假，决策是否严格成立）

### 4.1 已被幻觉污染但已修正的决策
- **ADR-0014 撤销强制二选一**：原 7 篇幻觉证据已清除；决策结论**保留但降级为"未验证工程判断"**——
  依据改为现场症状 + 谨慎表述，**不再声称论文证明**。理由：假证据只能说明"原推理链断了"，
  不能证明结论相反；但也没有真证据能证明它最优，所以降级而非保留"正确"标签。

### 4.2 幻觉只停留在调研文档、未进入决策（本次核实的好消息）
- 11 篇新增幻觉**全部只在 `MIND_GAPS_RESEARCH.md`**，已标注作废
- 核查 `decisions/0015-*`（技能审批）、`config/critbank.json`、`config/AGENTS.md`：
  **均未引用这些幻觉编号**——即"技能审批/critbank/编辑协议"等机制不是建立在假证据上
- 结论：这些机制的依据需另行核实（本轮没有发现它们引用幻觉），但**未被本次幻觉污染**

### 4.3 真论文误用方向的决策（需修正）
- **ROADMAP §8 "否决多 judge"** 引用 JudgePanel（论文其实支持紧凑 judge）→ 待修正表述
- **M5 工具面** 依据 Anthropic 官方博客：真实一致，决策严格成立 ✅
- **S14 编辑协议** 依据 RoPE 复制论文 + Diff-XYZ：真实一致，决策严格成立 ✅
- **AGENTS.md 路由表** 依据 Plan Declaration-Execution Gap：真实一致，决策严格成立 ✅

## 5. 必须修正的小偏差（社区/GitHub）
- OpenHands #6277 → 应写完整 `OpenHands/software-agent-sdk#6277`（裸号指向错误 repo）
- hashline "14/16 ≥ str_replace" → 原文是 "beat patch format for 14/16"
- Context Rot "单调下降" → 原文 "non-uniform with local peaks"
- Claude Code #26996 "6+ 分钟" → 原文是"连续 6 次 Edit 调用"

## 6. 架构级机制（已落地，确保未来决策与引用对应）

1. **`config/citation_ledger.json`**：99 条引用台账，每条带 status/真实标题/决策用途
2. **`tools/citation_guard.py`**：机器守卫——决策文档引用 hallucinated/missing/pending → FAIL；
   partial → WARN；`decision_uses` 非空必须 verified/n-a。已接入，`--quiet` rc=0
3. **`decisions/_ADR-TEMPLATE.md` 新增 Evidence 段**：未来 ADR 必填引用台账 ID + 核实状态清单
4. **本项目文档**：核实协议 + 本结果清单，均进仓库

**用户要求的固化达成**：存量已对应（幻觉清除/标注、真证据登记），未来由模板 + guard 强制对应。
