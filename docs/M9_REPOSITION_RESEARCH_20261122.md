# M9 定位复核 + 长/短任务分类器调研（2026-11-22）

> 用户问："M9的定位是不是也得变，调研一下有没有可以一开始就区分是个长任务还是短任务的分类器"

## 一、M9 现状与为什么要变
M9 卡（CAPABILITY_LADDER.yaml）当前：
- title "意图分类器"，`what: 用意图分类器填 BDI 意图槽，高置信直接用、低置信交三角色`
- `deps: [M3]`、`status: backlog`、`autonomous: false`、`manual-blocked`
- `abort_if: 86M CPU 延迟>500ms 或中文准确率不达92%`

**定位已经站不住**：
1. 它要填的 BDI 槽今晚被证伪——6/6 锚点是 P0 存档 initial 原文子串，零增量，LLM 抽锚点 15-16s 不值得（docs/M3_ANCHOR_COST_BENEFIT_20261122.md）
2. `deps: [M3]` 依赖一个核心目标已撤销的卡
3. 本地 `taskProfile`（tools/task_profile.mjs）注释明确写"猜语义是 M9 分类器的事，需独立标签，未满足前提"——M9 的旧定位是"补 taskProfile 的语义盲区"

## 二、本地实证：开局判长短，零成本规则已经够用
用 54 个有工具调用的真实会话测（首条真实用户指令 → 实际工具调用数）：

| 指标 | 结果 |
|---|---|
| 短任务（≤3 calls）| 23 个，首指令平均 189 字 |
| 长任务（≥20 calls）| 21 个，首指令平均 857 字 |
| **首指令长度** | 有相关但不可靠："发生了什么？"（6字）→ 23 calls 长任务 |
| **关键词规则**（长：自主推卡/新会话任务/爬X/完整走完/claim/验收；短：只做一个动作/只读/直接告诉/不要写文件）| 35 条可判定样本 **TP=16 FP=2 TN=17 FN=0，准确率 94.3%，零漏判长任务** |

**结论**：在本机场景下，"开局判长短"用零成本正则就有 94.3% 准确率——
上分类器需要证明它能显著超过这个基线，否则是过度工程。

## 三、社区/论文调研（社区部分实证）

### 3.1 核心答案：**"仅凭首条指令预测执行长度/难度"学术和工程上都被认为不可靠**
- **IBM Research（HF Blog, 2025-2026）**：*"difficulty is often invisible at routing time.
   A request like 'summarize this contract' looks simple, but might trigger retrieval, compliance
   checks, tool use, and multiple rounds of refinement"*——**常常要等执行起来才知道难不难**。
  他们的路由因此从"分类问题"改成"系统优化问题"（同时权衡 cost/latency/quality），
  在 AppWorld 417 任务上 84% accuracy / $93（比单跑 Opus 省 21% 成本、9% 延迟），
  路由本身仅 ~6ms / 2KB
- **Mercor（工程博客）**：query-classification routing "**only works when the request contains
  enough information to predict how hard**"——难度方差大的 workload 才需要路由，
  且必须先有 eval suite 定义"好"，否则省 token 可能只是"跳过了工作"
- **Model Routing 综述（papercompute）**：RouteLLM（LMSYS/Anyscale, ICLR 2025, arXiv:2406.18665）
  用小型 learned judge 在强/弱模型间路由，报的是**成本下降**，不是"预测任务长度"
- **DAAO（Difficulty-Aware Agentic Orchestration, 2025-09）**：用 VAE + difficulty head
  给 query 打 d∈(0,1) 分，据此调 workflow 深度/operator/模型——**但这是"难度分"不是"步数预测"**，
  且没有独立验证数字

### 3.2 关键区分：难度分 ≠ 长度预测
社区方案几乎全是**按 query 难度路由模型/算力**（RouteLLM/DAAO/IBM），
**没有找到"预测这个 agent 任务会跑多少步/多少 token"的成熟分类器**。
原因：执行长度由**环境反馈**（工具结果、失败重试、用户新指令）决定，不只是输入难度。

### 3.3 与本地数据的呼应
- 本地"发生了什么？"（6字）→ 23 calls：说明**短指令可能是诊断类长任务**，
  跟 IBM 的 "summarize this contract" 例子同构
- 本地关键词规则 94.3% 高准确率，是因为样本里"长任务"几乎全是
  "自主推卡/新会话任务/爬卡"这类**显式标记了长的指令**——不是真正预测难度，
  是读到了用户自己写的标签
- 一旦有新任务类型（用户不写标签），规则就失效——这解释了为什么学术上不看好这条路线

## 三·补 学术子任务深度调研（2026-11-22）

### 3.4 直接答案：没有现成的"指令→步数"分类器，且作为精确预测学术上不成立
调研了 11 篇相关工作，**没有任何一篇的预测目标是"agent 会跑多少步"**——都是相邻目标
（IRT 难度 β / 成功率 AUC / token 消耗 / 推理 token / 模型路由）。

**最强的负面证据**：
- **CoderForge（arXiv:2608.18280）**：54 特征 XGBoost 预测软件任务成功率——
  **prompt-only AUC 0.599、R²=0.025（近随机）**；patch-only 0.846、repo-only 0.839。
  `prompt_len_bpe` 在 54 特征里排第 20，SHAP 仅最强特征 1/9。→ **只看指令几乎无信号**
- **Bai et al.（arXiv:2604.22750）**：8 个前沿模型自预测 token 消耗，
  Pearson 最高仅 **0.39 且系统性低估**；**同一任务不同 run 差最多 30×**；
  人类专家难度 rating 与真实 token 仅弱相关。→ **开局精确判长短根本不成立**
- **Predicting Task Difficulty（arXiv:2608.05797）**：长度基线 ρ≈0.09；
  full 特征跨 benchmark LOBO 骤降到 ρ=0.225；明确点名 **AUC 误导——常数预测器也有 0.715**
- **三篇系统论文独立共识**：Heddle（2603.28101）明写静态开局预测 *"ineffective for precise
  agentic trajectory prediction"*；TokenCast（2609.35760）称 prompt-only 估计 *"highly uncertain"*；
  Libra 同样结论。长度由工具返回/环境反馈决定，长尾，**必须逐步更新**

**仅有的可行信号**（都不是开局分类器）：
- **Heddle：第一步执行计划是强语义指示器**——比原始指令强得多，且只晚一步、成本可忽略
- Predictive Scheduling（2602.1237）：1.5B LoRA 三分类 66.3%（medium 类最差），
  few-shot 仅 41.6%；标签构造需每题 100 条 trace，离线成本极高
- EffGen（2602.00887）：纯启发式词数阈值，无独立验证、无标准准确率
- token-level entropy 轨迹是单类特征里最强的（Predicting Task Difficulty）

### 3.5 学术结论映射到本地
| 本地观察 | 学术对应 |
|---|---|
| 关键词规则 94.3% | 不是"预测难度"，是读用户写的显式标签（对应 CoderForge 的 gold 信息）；换任务类型即失效 |
| 6字→23calls 反例 | 对应 Bai 的 30× run 波动 + IBM 的 "summarize contract" |
| 首指令长度 189 vs 857 字 | 对应 prompt_len_bpe 排第20、贡献 1/9——弱信号 |
| 想开局判长短上分类器 | 三篇系统论文判定无效 + prompt-only AUC 0.599 近随机 |

**新方向（学术支持、本地可落地）**：**"第一步后判"** ——让 agent 先输出一步计划，
再据此决定是否启用重型机制；比纯开局分类靠谱得多，成本可忽略。
但这属另一条研究线，且本地已有 `taskProfile` 做运行中判定（只读 vs 有产物），
二者需先厘清分工再谈实现。

## 四、M9 新定位判断

### 4.1 候选评估
| 候选 | 判断 | 依据 |
|---|---|---|
| A. 开局长短分类器 → 路由重型机制 | **不建议（学术强否定）** | ① prompt-only AUC 0.599/R²=0.025 近随机、自预测 r≤0.39 且 30× 波动、三篇系统论文判静态预测无效；② 本地零成本规则已 94.3%（读标签非预测）；③ 无现成"指令→步数"分类器 |
| B. "第一步后判"（Heddle 式）→ 动态调 workflow | **更可行但属另一条线** | 第一步执行计划是强语义指示器，比开局分类靠谱且成本可忽略；但本地已有taskProfile做运行中判定，需先厘清分工 |
| C. **rejected / 合并到 L1 的产物内容断言** | **推荐** | 旧定位(BDI槽)已证伪；开局长短不需要分类器；L1 的"产物内容满足what"才是真正未解的问题（goal_verify 已有三态雏形）|

### 4.2 推荐动作
1. **M9 标 rejected**，理由："填 BDI 槽已证伪（P0 initial 原文零增量）+ 开局长短用零成本规则已 94.3%，分类器无独立价值"
2. **L1 的 deps 去掉 M9**（L1 核心是产物内容断言，与意图/长短分类无关），改为 deps=[M1] + 新增"产物内容判据"前置
3. **把"开局长短规则"作为独立小工具落地**（如果还需要）——零成本、已有规则、不需要卡位；但**必须标注它是"读用户写的标签"而非"预测难度"**，避免误导
4. 若将来真要做复杂度路由：先建 eval suite（Mercor 教训），再谈分类器

### 4.3 诚实边界
- 本地 94.3% 是**事后拟合 + 样本偏斜**（长任务几乎全是显式标注的推卡任务），不代表通用能力
- 无法排除"某个轻量分类器在新任务类型上显著超过规则"的可能——但**当前没有证据支持做这个投入**
- M9 的 `abort_if`（86M 延迟>500ms / 中文准确率<92%）是针对旧定位的判据，rejected 后自然失效

## 五、诚实标注
- 本地 35 条样本来自单一项目（路线图推卡 + 验证任务），分布偏斜，不能外推
- 关键词规则是**事后拟合**这些样本，94.3% 有 overfit 嫌疑——需留出集或新样本验证
- "首指令长度"与任务长度相关性弱（6字→23 calls 的反例）
