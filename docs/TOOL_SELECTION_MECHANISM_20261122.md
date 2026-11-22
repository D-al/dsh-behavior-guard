# 模型是怎么选工具的：同一权重/引擎，不同 harness 为何选出不同工具（2026-11-22）

> 用户问："调研一下模型是怎么选择工具的？不同 harness 工具集有差异，同一个推理引擎和模型权重到底怎么在工具里面选它认为正确的那个？"

## 一、一句话核心答案
**模型里没有独立的"工具选择模块"——"选工具"就是一次普通的 next-token prediction。**
工具清单以文本形式经 chat template 注入上下文，模型对全词表算概率、采样下一个 token；
被采样的"工具名"只是字符串。**不同 harness 改变这段上下文的文本/顺序/序列化/解码约束，
等于改变了概率分布的输入条件**——"同一套权重"不等于"同一个条件分布"。

## 二、四层机制（子任务调研）

### 2.1 Prompt 层：工具是注入的上下文文本
- API 层 `tools:[...]` 是独立字段，但推理引擎用 `tokenizer_config.json` 的 Jinja2 chat template
  把 schema **渲染进 system prompt**（`# Tools ... - name/description/parameters`）
- 模型只看 token 序列——工具名/描述/schema 都是**输入 token，按 token 计费，占上下文窗口**
- 模型**永远看不到工具代码**，只看名称+描述+schema；system prompt 说有它就当真

### 2.2 Token 层：tool_call 是特殊定界符 + 训练出的输出格式
- 各模型家族用不同标记：Qwen→Hermes 风格 JSON、Mistral→`[TOOL_CALLS]`、DeepSeek→DSML、Llama3.1→JSON
- 必须配对的 `--tool-call-parser`（hermes/qwen3_coder/deepseek_v3/llama3_json/mistral）——
  **配错则"模型输出了调用但引擎识别成普通文本，finish_reason=stop 而非 tool_use"**
- 从模型视角，生成工具调用和普通文本**计算过程完全相同**：Transformer 前向→全词表概率→采样。
  唯一差别是词表多了特殊 token、训练数据多了调用样本。**没有新的推理机制**

### 2.3 训练层：SFT 教"何时/如何调"，RL 管"分寸"
- SFT 数据：`user→tool_calls→tool result→assistant 回答`，外加 tools 字段
  模型学的是"某类问题→某种输出模式"的切换；既学"该调用"也学"直接回答"
- 两层信号：(a) **查询与工具描述的表层语义相似度是真信号**；(b) 但不理解工具实现/因果，
  训练数据里的共现会照单全收（算术题前总调 calculate_sum→每道题都调）
- RL/DPO 补边界（该不该调/选哪个/何时停），但 over-calling 只能部分消除
- **描述质量是核心工程**：Hsieh 2023（arXiv:2308.00675）证明只用工具文档的 zero-shot
  ≈ few-shot 示例（TabMWP 追平 16-shot）；数百真实 API 上文档版显著优于无文档 few-shot

### 2.4 Decoding 层：约束解码管"形式"不管"判断"（最大误解点）
- 链路：HTTP tools 字段 → chat template 渲染 → **constrained decoding**（JSON Schema 编译成 CFG，
  XGrammar MLSys'25 arXiv:2411.15100，把非法 token 的 logit 置 −∞）→ post-processing parser
- "自由生成然后解析" vs "被约束只能生成合法工具名"**两种都存在**，取决于实现/strict/guided decoding
- **但两者都不能替模型做语义决策**："grammar guarantees structure, not semantics——
  model can still choose the wrong tool, it just cannot emit an unparseable one"
- **隐性代价（Pith arXiv:2608.13959）**：约束对"该拒绝调用时拒绝"（abstention）总体负面，
  最差 **−29.5 点**；最小模型韩语下 stop 项 −20.0/enum 项 +19.5/合计 −0.5
  → **约束拿回可读性不是判断力；对小模型尤其危险：可能吃掉"不调用"这个选项**
- 量化先伤格式遵循，所以本地量化模型更需要约束解码——但要显式保留 abstain 选项

## 三、不同 harness 为何选不同工具：六个叠加的差异来源
1. **工具清单文本不同**（数量/名字/描述/schema）→ 注入上下文不同 → 工具名 token 概率不同（最根本）
2. **序列化/模板不同**（Qwen vs Mistral vs DeepSeek DSML）→ token 化结果不同
3. **解码约束不同**（guided decoding 开关、tool_choice=auto/any/none、enum 约束）
4. **system prompt / few-shot / 工具结果回灌格式不同**——都是条件信号
5. **工具顺序不同**——位置偏置，重排 registry 就能改变行为，无需改代码
6. **采样随机性**——条件全同也会选不同；τ-bench 的 pass^k 量化这个

## 四、工具集差异的影响（数字，注明出处可信度）
| 来源 | 设置 | 结果 | 可信度 |
|---|---|---|---|
| RAG-MCP 2025 | 10→100+ 工具全塞 prompt | 选对率 78%→**13.62%**，加检索回 43.13% | preprint 未评审 |
| BFCL 日历调度 | 4→51 工具 | 43%→**2%** | 二手转引需核 |
| Chance-Corrected 2026 | BFCL 370 工具 | 看 50 个 60.9% → 收窄 ~7 个 **76.8%** | 预印本方向可信 |
| Less is More (DATE 2025) | 小模型边缘硬件 | 减工具显著提升，执行时间最多 −70% | 会议论文 |
| "Rethinking MCP-Augmented LLMs" | 3域6模型接 MCP | 平均**下降 9.5%**（接了反而差）| 论文 |
| ToolHop (ACL 2025) | 995 query/3912 工具/3-7跳 | GPT-4o 自由选择 47.74%；**详细反馈 47.87% vs 简单错误 24.47%（−23.4点）** | 会议论文 |
| τ-bench (ICLR 2025) | pass^k | Claude3.5 retail pass@1 69.2%→pass^4 46.2% | 论文 |

⚠ 绝对百分比不可跨来源比较（benchmark/模型/distractor 密度不同）；可复现的只有**形状**：浅缓降（≤25）、中度（~50）、断崖（≥50-75）。
**厂商 guidance**：OpenAI <20 函数/轮、Anthropic 30-50 开始退化、Gemini 活跃 10-20（均二手转引）。

## 五、Bias 证据：模型"认为正确"的依据
- **BiasBusters（2025，7 模型含 Qwen）**：功能等价工具轮换顺序 → 全面偏向**更靠前**的工具；
  **最强预测因子是 query 与工具描述的表层语义相似度**（改描述彻底重排偏好，改名字影响小）；
  预训练曝光会烘焙 bias 进权重；跨模型家族偏好同一批 API；combined bias 0.3-0.4；
  filter-then-sample 缓解 GPT-4.1 mini 0.380→0.094 且精度仍 0.996
- **ToolTweak（攻击论文）**：优化工具元数据把 DeepSeek 20.2%→**81.6%**、GPT-OSS 19%→73.6%；
  **名字和描述一样重要**，连数字后缀都偏向索引1
- 调和：BiasBusters 测自然偏置（语义>名字），ToolTweak 是对抗说服性元数据（名字也重要）
- MetaTool（ICLR 2024）：相似工具任务上多数模型仍难选对；Anthropic 建议用共同前缀分组

## 六、本地 dsh 实证（补充子任务）
- **工具集来源**：真实 `request/header` 事件里 `tools` 是结构化数组（15 个，含 name/description/parameters）
- **排列方式**：字母序（ask_user_question→write），不是频率/重要性序
- **描述长度差异**：pwsh 2007 字 vs write 42 字（**47 倍**）
- **15 工具面 2160 次调用分布**：read 32.6% / pwsh 31.8%（两者合计 64.4%）、
  todo_write 7.4%、glob 7.2%、edit 6.6%、write 6.5%、grep 4.8%；
  plugin_manager/skill/read_image 接近 0
  → **没有明显的字母序位置偏好**（最前的 ask_user_question 仅 0.4%，最后 write 6.5%），
  选择由**任务类型**驱动（读/执行占绝大多数），与 BiasBusters"语义相似度是主信号"一致

## 七、对本地 35B / dsh 的启示
1. **先对齐 template 和 parser**，再谈效果——本地 Qwen3.6 必须 `apply_chat_template(tools=...)`，
   配错 parser 是最容易被误判成"选错工具"的假故障
2. **约束解码是刚需但要保留 abstain**——量化先伤格式遵循；用 free/stop/stop+grammar 三条件自测
   "选对"和"该拒时拒"两件事（两条件对比会掩盖一损一得）
3. **工具数控制 10-20 活跃集**，按意图分池——本地已从 36 降到 15，方向对；别信 API 128 上限
4. **描述当代码写**：硬约束（枚举/格式/实体类型）写进 **schema 而非 description**
   （Singh 消融：写 schema 4/4 模型有效，写 description 仅 2/4）；"工具做什么"决定选哪个
5. **固定工具顺序，重排当变更回归**——位置偏置在语义不分伯仲时最大
6. **评估测三件事**：首调准确率、错调分解（定位改哪条描述）、**不调用率**（随工具集增长悄悄上升）；
   多轮用 pass^k 而非 pass@1
7. **别假设接工具更强**——MCP 增强 −9.5% 反例在前；先做有/无工具 A/B
8. **反馈要详细**——ToolHop 详细反馈 vs 简单错误差 23.4 点

## 八、诚实标注
- 机制四层（template/CFG/parser）是代码确证；数字多来自 preprint/二手转引，已逐条标注
- "dsh"在本报告按本地自部署 35B + dsh harness 理解（真实 request header 已验证工具注入形式）
- 本地 2160 次调用是历史会话统计，非受控实验；"无明显位置偏好"是观察不是证明
- 约束解码的 abstention 代价（Pith）基于 mention-based scoring，作者自认可能有 scoring artifact
