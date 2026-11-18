# dsh-agent-harness

> **DeepSeek Harness（dsh）的 agent harness 聚合插件**——用确定性代码和结构化角色，为一个本地 8GB 显存上的 35B MoE 模型分担负担、拓展能力边界。
>
> 仓库名沿用历史名 `dsh-behavior-guard`；npm 包名与插件 id 为 `dsh-agent-harness`（v2.0.0 起）。
> 当前版本 **v2.2.1**（2026-11-18）。

---

## 导航：怎么读这篇文档

这篇 README 不只是"功能说明"，而是**一份完整的工程决策档案**——记录我们碰到什么瓶颈、搜了哪些论文、做了什么决定、拿到什么效果、又发现了什么新问题。

| 你是谁 | 建议读法 |
|---|---|
| **只想用** | 跳到 [Part 5：现状与成本](#part-5现状与运行期成本) + [Part 6：配置](#part-6配置与注意事项) |
| **想借鉴方法** | 读 [Part 1 时间线](#part-1主干时间线) → [Part 2 五条分支线](#part-2五条分支线) |
| **想继续研究** | 重点读 [Part 3 论文索引](#part-3论文索引完整带链接) + [Part 4 失败清单](#part-4失败与放弃负面资产) + [Part 7 给后来者](#part-7给后来者人或-ai的探索指南) |
| **AI 接手** | 从头读，尤其注意每个决策节点的"为什么"和 [Part 4](#part-4失败与放弃负面资产)——**别重试已证伪的路** |

**核心命题**：*模型不是瓶颈，harness 是。* 同一模型换 scaffold 实测 +15.6pp（SWE-bench Hard）、+26pp（9B）；
Meta 的 [Thinking Before Thinking, arXiv 2609.38147](https://arxiv.org/abs/2609.38147) 在 ProgramBench 上 +13.5pp。
我们做的是把"能由系统可靠完成的事"从模型肩上卸下来，让它只专注决策。

**目标函数**：**一次做对 > 快速但反复修改**。三次顺序迭代 ≈ 单次生成，返工才是真成本。

---

## Part 0：起点——我们在什么约束下做事

### 硬件与模型（不可突破的边界）

| 项 | 值 |
|---|---|
| CPU / 内存 | i7-12650H (10C/16T) / DDR4-3200 64G |
| GPU | RTX 4060 Laptop **8G**（无核显，MUX 直连） |
| 模型 | Qwen3.6-35B-A3B **Q4_K_XL**（21.28 GiB），41 层 / 256 专家 top8 / 31 层 DeltaNet + 10 层吃 KV / 带 MTP 头 |
| 引擎 | 自编 llama.cpp **b12244**（含 autoparser 2 行补丁） |
| 速度 | 20K decode **27.2 t/s**、prefill **800 t/s**；显存余量常被压到 <450 MiB |
| 上下文 | 96K（压缩触发 54K）；`CTX_CHECKPOINTS=2` 是承重墙 |

三条硬约束贯穿所有决策：**① 显存空闲 ≥450 MiB**（186 必卡，WDDM 换页→1~2 t/s）；
**② 27 t/s decode 意味着一次 LLM 审计 10~20s**；**③ 改写历史会让 KV cache 后缀失效，20K 重预填充 25~44s**。
——每一条都把"加一层 LLM 调用"从"免费"变成"昂贵决策"。

### 最初的痛点（2026-11-07 起）

本地小模型在长 agent 会话里会以**可预测的方式退化**：

1. **"只输出好"回路**：同一现场 7 次异常 tool_result 后，模型连续回「好」然后 EOS（6/7 紧跟无信息工具结果）。
2. **路径复述崩塌**：13 字符路径 5/5 准确，20 字符 1/5，73 字符完整 Windows 路径 **0/5**。
3. **计划说了不做**：模型声明的计划只有 22~45% 在执行中被遵守（[Plan Declaration-Execution Gap, arXiv 2609.38108](https://arxiv.org/abs/2609.38108)）。
4. **虚假完成**：小模型任务完成声明里 ~13% 是假的，**自检只能从 12.7% 降到 11.8%**（同一盲区）。

这四条对应后来的四条主线（L0-L3 / 短路径 / P1 闹钟 / D4 验收闸门）。

---

## Part 1：主干时间线

> 每个节点的格式：**瓶颈 → 论文/搜索 → 决定 → 效果 → 新发现**。

### 2026-11-07～11-10：先堵"行为漏洞"

| 日期 | 瓶颈 → 依据 → 决定 → 效果 |
|---|---|
| **11-07** | **瓶颈**：「只输出好」回路。**决定**：chat 模板 `is_stub` 跳过「确认词 + 无 tool_calls + 非最后一条」的 assistant（治本），外加插件 L0-L3 三层判定。**效果**：现场回路消失；A/B 显示删历史「好」/屏蔽 token/`tool_choice=required` 全部 0/2（都无效），证明只有"渲染时跳过"治本。**新发现**：唯一有效的中文思维链锚点是自述句 `{{- '嗯，' }}`——祈使句会让模型回「好」后 EOS。 |
| **11-10/11** | **瓶颈**：Q3/Q4 该用哪个、温度多少。**决定**：端到端扫描 P3/P4/P5（不是看 decode t/s）。**效果**：Q4@0.7 是唯一在三项上 2/2 且最快的配置（193/355/418s）；温度是主导变量，曲线 U 形（0.1 想完不干、0.9 草率收工）。**新发现**：真正的主导变量是温度不是量化档位——[详见失败清单](#f2-温度极端值)。 |
| **11-11** | **瓶颈**：decode t/s 显示 `moe-cache-cpu-share=1.0` 快 37%。**论文/方法**：坚持 P5 端到端验证。**决定**：否掉，生产 `share=0`。**效果**：端到端反而慢 **2.4 倍**（每步增量 prefill 慢 4-5 倍、生成 token 翻倍）。**新发现**：**decode t/s 是误导性指标**——写进了项目的第一条铁律。 |

### 2026-11-15～11-17 上午：路径、记忆、前额叶外置

| 日期 | 瓶颈 → 依据 → 决定 → 效果 |
|---|---|
| **11-15/16** | **瓶颈**：长路径复述 0/5。**论文**：[Frontier LMs Struggle to Copy, arXiv 2607.16072](https://arxiv.org/abs/2607.16072)（1D RoPE 局部匹配偏置）、[In-context Superposition, arXiv 2604.09670](https://arxiv.org/abs/2604.09670)（记忆项纠缠编码）、[Copying Under Repetition, arXiv 2610.26722](https://arxiv.org/abs/2610.26722)、[CopyGen (NeurIPS 2026), arXiv 2610.28393](https://arxiv.org/abs/2610.28393)（精确复制是 decoding-time control problem）。**决定**：一律短相对路径（`p/ bench/ memory/`），禁止 70+ 字符绝对路径。**新发现**：逐级导航方向对（文件名段 8/8），但**纯 prompt 模拟不够**（0/8）——必须配真实 `list_dir` + 约束输出，见 [失败清单](#f8-逐级路径纯-prompt-模拟)。 |
| **11-17 08:42** | **瓶颈**：会列清单但不会用（23 步重述 14 次）。**论文**：[Plan Declaration-Execution Gap, arXiv 2609.38108](https://arxiv.org/abs/2609.38108) + CoPE (ICML 2026) + Claude Code TodoWrite 社区实践。**决定**：前额叶外置——AGENTS.md 引导层 + 插件闹钟强制层（≥4 步无单提醒 / ≥5 步停滞提醒）。**效果**：离线回放 3/3 命中，真实会话中闹钟把模型从纯搜索拉回执行。 |
| **11-17 上午** | **瓶颈**：单 agent 自己审自己。**论文**：[Three Roles, One Model, arXiv 2604.11465](https://arxiv.org/abs/2604.11465)（同一 8B 权重三种 conditioning，AppWorld 5.4%→8.9%，超过 33B）。**决定**：三角色协作——审计员（无历史）+ 纠正器（环境证据算参数）+ 验收员（独立三态）。**效果**：子智能体验收员生产级落地（10 步逐项核验后回注 PASS）。 |

### 2026-11-17 22:00～23:30：验证与门控

| 日期 | 瓶颈 → 依据 → 决定 → 效果 |
|---|---|
| **11-17 22:52** | **瓶颈**：虚假完成 + 状态回卷。**论文/实践**：IOV Labs（896 任务，自检无效）、verify-gate（开源 MCP，`E_SELF_VERIFY` 硬拒自签）、[StateForge, arXiv 2609.32520](https://arxiv.org/abs/2609.32520)（意图漂移 0.476→0.384）、U-Fold（摘要+todo+工具关键行）、ARC (ACL 2026)（每轮反应优于延迟反射）。**决定**：D4 present-gate（"做的人不能自己签字"）+ P1.5 todo 回灌（Manus recitation）。**效果**：测试 10/10 + 26/26 + 门禁 27/27。 |
| **11-17 23:00** | **瓶颈**：每 8 步一次完整 LLM 审计 10-20s，且实测有时**有害**（纠正器猜错路径那次注入后模型进入重问循环）。**论文**：**SAG (SKKU/Soongsil, 2026-10)**——gated critique 只在决策风险高时触发，算力 **-66%**、成功率 **3 倍**，"precision intervention > constant supervision"。**决定**：D5 从固定周期改为**风险门控**（连续失败≥2 / 无进展≥6 / present 前 / 压缩后）。**新发现**：审计的**误判风险 > 漏审风险**——错误路径作为失败信息进上下文会变成干扰源。 |

### 2026-11-17 23:30～11-18 02:00：MTP、审计质量、角色架构

| 日期 | 瓶颈 → 依据 → 决定 → 效果 |
|---|---|
| **11-17 23:30** | **问题**：MTP draft 头做 surprisal 值不值。**论文**：[SU: How to Speculate about Uncertainty in Agentic Coding?, arXiv 2609.05274](https://arxiv.org/abs/2609.05274)（EMNLP 2026 Industry，用 draft cross-likelihood 做失败预测，执行错误 -6~8pp、token -14~19%）。**决定**：只算运行期成本后发现边际成本 ≈0（MTP forward 已付），但 **dsh 不暴露 logits** → 改用**零改动代理**：读 llama-server 已经在打印的 `draft acceptance = 0.89 (162 accepted / 191 generated)`。**效果**：接受率 <0.65 作为 D5 第五信号上线。**新发现**：全局预算 4096 与 INI 的 -1 冲突（真隐患），已对齐。 |
| **11-17 23:50** | **问题**：多审计员能不能用 MTP 类方法解决？**论文**：**Apple《Nine Judges, Two Effective Votes》(2026-06)**——9 个 judge ≈ 2 个独立投票（共享训练/RLHF/架构先验→错误高度相关）；[JudgePanel, arXiv 2608.29168](https://arxiv.org/abs/2608.29168)（14B 蒸馏 panel 能力，单模型推理成本）；PoLL（3 跨家族小模型 > GPT-4，便宜 7-8×）。**决定**：**不做多审计员**，改用"MTP 信心 × 审计判定"双信号交叉（零成本）：低 MTP+ISSUE=高可信干预；高 MTP+ISSUE=矛盾→抑制干预降误报。**新发现**：信号源多样性 >> judge 数量多样性。 |
| **11-18 00:15** | **问题**：还能不能零成本提质。**论文**：[Post-Reasoning, arXiv 2605.06165](https://arxiv.org/abs/2605.06165)（NTU，"先给结论再论证"，117 组合 88% 有效）；few-shot 变异性 -52%。**决定**：审计 prompt 加 3 个实例（UNCERTAIN 放最后）+ 正例表述替代否定句（"路径照抄证据原文"替代"不要猜路径"）。**效果**：纠正器猜路径类干扰被抑制。 |
| **11-18 00:45** | **问题**：Critic/审计规则写死在代码里，改标准要改代码。**论文**：社区 rubric-as-code 实践（版本化 rubric + 判决记 `rubric_version` + prompt 从 rubric 生成）。**决定**：`bench/rubrics/*.json` 外置，prompt 从 rubric 生成，判决记版本；审计 rubric 的 `deterministic` 字段标注"已由 D1/D2 覆盖"——**外置规则与代码门控联动**。**新发现**：这让审计员"宏观知道自己审什么"且不重复劳动。 |

### 11-18 01:00～02:20：控制回合、合并、社区缺口

| 日期 | 瓶颈 → 依据 → 决定 → 效果 |
|---|---|
| **01:05** | **问题**：用户观察到云端模型"先快速准备再正式思考"是什么。**论文**：[Thinking Before Thinking, arXiv 2609.38147](https://arxiv.org/abs/2609.38147)（Meta——**agentic meta-reasoning**：Worker 干活，Controller 固化已知/探索选项/评估价值/派发；+13.5pp）；[Tyler, arXiv 2606.16360](https://arxiv.org/abs/2606.16360)（O_g 全局定向算子）；PAM (ACL 2026)（Flavell 元认知框架）。**决定**：v2.1.0 每 8 步注入**控制回合**（零 LLM）：已确立/当前项/已排除/列 2-3 候选。**新发现**：我们的 harness 本来就承担 Controller 四件事中的三件——方向被论文印证。 |
| **01:25** | **问题**：用户问"思考替换"（改写历史思维链）的收益/代价。**论文**：[Why Pay for Long Reasoning When Rewrite Do Trick?, arXiv 2611.03852](https://arxiv.org/abs/2611.03852)（紧凑历史使后续推理变短 83~100%）；[Think or Remember, arXiv 2611.10982](https://arxiv.org/abs/2611.10982)（**丢弃**早期推理 → HotpotQA -9~23pp，且服务端缓存复用时"丢弃"成本是"保留"的 1.74×）。**决定**：**不改写历史**——本机 20K 后缀税 25~44s 远大于收益；我们的 append-only 注入天然规避。 |
| **00:52** | **决定**：合并 `dsh-behavior-guard` + `dsh-task-continuity` → 单包 `dsh-agent-harness` v2.0.0（事件面相同、共享状态、预算需统一；曾双挂载导致注入成对）。**新发现**：测试抓到 state 漏初始化 `todoCalls` → P1 闹钟永不触发。 |
| **01:25～02:20** | **问题**：社区 harness 清单还缺什么（Keyhole 白皮书 / Praison 10 组件 / guibai 5 模块）。**决定**：v2.2.0 补四项——**per-step trace**（`_trace.jsonl` + `trace_report.py`）、**JSON 解析重试**、**Skills 渐进披露**、**危险操作分级**。**效果**：26+38 测试、29 门禁、P4/P5 长任务双 PASS。 |

---

## Part 2：五条分支线

主干时间线按"何时做"组织，这里按"解决什么问题"重组——五条线相互独立又互相喂养。

### 分支 A：行为治理线（防退化）

```
"只输出好"回路  →  L0-L3 早收尾  →  D1/D2/D3 确定性信号  →  D5 风险门控审计  →  MTP 信心 + rubric 外置
   (11-07)          (11-07)           (11-17 上午)            (11-17 23:00)         (11-17 23:30～11-18 00:45)
```

- **核心洞察**：绝大多数失败不需要 LLM 判断，用确定性代码即可——L0-L3 是 0 LLM，D1-D3 是 0 LLM，深检是 0 LLM。
- **贵的留给刀刃**：D5 审计 10-20s，只在风险点触发（SAG 同派）。
- **审计员也要被约束**：只读 + steer + 预算 + 白名单；纠正器只能"照抄证据"，不能拼路径——这是被实证坑出来的。

### 分支 B：上下文 / 记忆线（防遗忘）

```
短路径约定  →  P0 压缩存档  →  P1.5 todo 回灌  →  压缩策略向截断倾斜  →  已排除清单
 (11-15)       (11-17)          (11-17 22:52)       (11-16)                 (11-18 00:20)
```

- **论文支柱**：[MemGPT, arXiv 2310.08560](https://arxiv.org/abs/2310.08560)（分层记忆）、[Hippo, arXiv 2610.24453](https://arxiv.org/abs/2610.24453)（防污染：只存用户真实指令）、[StateForge, arXiv 2609.32520](https://arxiv.org/abs/2609.32520)、U-Fold、ARC (ACL 2026)。
- **关键决定**：用户约束**逐字钉住不转述**；P0 加【已排除】——被拒绝的方案是"最贵的信息"，叙事式摘要最先丢它。
- **压缩触发点 0.55（54K）**：社区建议 60-70%，我们保守地更早——因为实测 68.8K 时模型进入"复读退化"（连续 4 步重述同一份计划，最后只写计划不发工具就 EOS）。

### 分支 C：角色 / 元认知线（防短视）

```
三角色协作  →  Critic + Planner  →  角色专属 AGENTS.md  →  控制回合  →  确定性检查密度
 (11-17 上午)    (11-18 00:45)       (11-18 00:50)         (01:05)        (01:00 verify-on-edit)
```

- **四角色标准**：Planner（出 spec + 成功标准）/ Executor / **Critic（主观评审）** / **Verifier（确定性检查）**——Critic 与 Verifier 不是同一个东西。
- **我们的角色**：执行者（唯一写权限）+ 审计员（只读+steer）+ 纠正器（只读代执行）+ Critic（只读产物）+ 验收员（三态）。
- **角色专属上下文**：审计/纠正/评审是独立 LLM 调用，**只收各自 prompt，不收 AGENTS.md**——天然干净。社区 role isolation 证实这是对的。
- **verify-on-edit**：写文件后 80-150ms 确定性语法检查——Qwen3.5-35B 的实测 +15.6pp，是**整个项目性价比最高的质量杠杆**。

### 分支 D：质量 / 验证线（防虚报）

```
verify-gate  →  D4 present-gate  →  独立验收员  →  深检 + 配置一致性  →  per-step trace
 (11-17 22:52)   (11-17 22:52)     (11-17 上午)    (11-18 00:40/00:50)   (11-18 01:25)
```

- **承重角色**：[MAST, arXiv 2503.13657](https://arxiv.org/abs/2503.13657) 分析 1642 个多智能体失败，**21.3% 是验证缺口**；PwC 报告结构化验证回路 10%→70%（7×）。
- **自验证有害**：AI Office（522 会话）实测单 agent 60% → 多 agent 90%，而**自验证让准确率低于 60%**。
- **深检清单**：import 可解析（`importlib.util.find_spec`，不执行模块）、占位符、空文件、BOM/GBK、重复段落、路径引用、未完成 [VERIFY] 项。`config_check.py` 比对 `.env` 与 INI 的 23 个键——**上线即抓到 2 处真不一致**。

### 分支 E：能力边界线（防膨胀）

```
工具面裁剪  →  知识层调研  →  MCP 否决  →  Skills 渐进披露  →  预算分离受限
 (11-16/17)     (11-18 00:45)   (11-18 01:45)  (11-18 01:30)      (11-18 01:05)
```

- **工具面 28 个、单会话只用 11 个**（17 个零调用）；工具一多准确率是**崩塌不是缓降**：BFCL 日历排程 4→51 工具 **43%→2%**、RAG-MCP 压力测试 10→100+ 工具 **78%→13.62%**，且 38% 错误是**参数填错**（见 [工具选择崩塌曲线综述](http://quidproquo.cc/posts/ai/2026-06-04-tool-selection-at-scale-en)，原始实验见 [RAG-MCP](https://arxiv.org/abs/2505.03275)）。
- **MCP 三重否决**：① dsh 不支持；② 工具面已满，加 MCP 直接越线（GitHub MCP 默认 42 工具）；③ 本地量化模型更怕工具膨胀（选错工具/编参数/循环）。详见 [PERIPHERAL_CAPABILITIES.md](https://github.com/D-al/dsh-behavior-guard/blob/main/PERIPHERAL_CAPABILITIES.md)。
- **正确的替代**：Skills——只在相关时加载的过程性知识，不占工具面，是 AGENTS.md 4K 容量之外的出口。
- **元认知不可用**：[Confident Fools or Careful Searchers?, arXiv 2610.41124](https://arxiv.org/abs/2610.41124)——400 题基准，Mistral Small 只搜 20% 该搜的，且作者明说"测的是产品搜索触发，不是严格元认知"。[MARTA, arXiv 2610.05223](https://arxiv.org/abs/2610.05223)（Retrieve-Always = 诱导性失忆）、FlyBy (KAIST 2026-09)（执行瓶颈 vs 知识瓶颈）。**结论**：用规则代替感觉——"不确定就搜"写进 AGENTS.md。

---

## Part 3：论文索引（完整，带链接）

> 每条含 **arXiv 编号 + 链接 + 一句话 + 我们从中拿了什么**。编号格式统一为 `arXiv XXXX.XXXXX`。

### A. 失败预测 / 风险门控 / 不确定性

| 论文 | 我们的用法 |
|---|---|
| [arXiv 2609.05274](https://arxiv.org/abs/2609.05274) — *How to Speculate about Uncertainty in Agentic Coding? A Draft-Model Gate Method* (SU, EMNLP 2026) | MTP 信心信号的理论来源；零改动版 = 读 draft acceptance |
| **SAG (SKKU/Soongsil, 2026-10)** — gated critique，算力 -66%、成功率 3× | D5 风险门控的直接依据："precision intervention > constant supervision" |
| [arXiv 2608.23651](https://arxiv.org/abs/2608.23651) — *Feedback That Backfires* | D1 重复探测：失败记录使重复概率 0.06→0.54 |
| [arXiv 2608.27167](https://arxiv.org/abs/2608.27167) — *Calibrated to Act* | 审计员自校准闭环（判决后 3 步结算有效性） |
| [arXiv 2610.41124](https://arxiv.org/abs/2610.41124) — *Confident Fools or Careful Searchers?* | 证明小模型不会自知知识边界 → 规则驱动 |
| [arXiv 2610.05223](https://arxiv.org/abs/2610.05223) — *MARTA* | "look before you leap"，检索要按不确定性触发 |

### B. 验证 / 评审 / 多 agent 失败

| 论文 | 我们的用法 |
|---|---|
| [arXiv 2503.13657](https://arxiv.org/abs/2503.13657) — *MAST: Why Multi-Agent Systems Fail* | 21.3% 失败是验证缺口 → D4/D5 承重 |
| [arXiv 2410.10934](https://arxiv.org/abs/2410.10934) — *Agent-as-a-Judge* | 审计员主动取证（NEED_EVIDENCE）——限预算、早停、说不确定 |
| [arXiv 2608.29168](https://arxiv.org/abs/2608.29168) — *JudgePanel* | 单模型蒸馏 panel 能力（否决"多 judge 投票"） |
| **Apple《Nine Judges, Two Effective Votes》(2026-06)** | 9 judge ≈ 2 票 → 拒绝多审计员，改异质 rubric |
| **PoLL: Replacing Judges with Juries** (Cohere) | 跨家族小模型 > 单大模型（依据"多样性不在数量"） |
| [arXiv 2605.06165](https://arxiv.org/abs/2605.06165) — *Post-Reasoning* (NTU) | 先给判定再论证（117 组合 88% 有效） |
| **SLEIGHT-Bench** (Anthropic Fellows, 2026-05) | omission/N-hops 类盲点 0% 检出 → 审计加 D 类遗漏检查 |
| **IOV Labs (896 任务)** + **verify-gate** (MCP) | 小模型虚假完成 13%、自检无效 → D4 present-gate 硬门槛 |
| **PROCTOR / Demote the LLM Judge** | 确定性护栏 > LLM judge；judge 也要被硬约束 |

### C. 角色 / 编排 / 元推理

| 论文 | 我们的用法 |
|---|---|
| [arXiv 2604.11465](https://arxiv.org/abs/2604.11465) — *Three Roles, One Model* | 三角色协作的骨架（8B 超过 33B 的实证） |
| [arXiv 2609.38147](https://arxiv.org/abs/2609.38147) — *Thinking Before Thinking* (Meta) | 控制回合：Controller 四动作（consolidate/explore/assess/dispatch） |
| [arXiv 2606.16360](https://arxiv.org/abs/2606.16360) — *Tyler: Typed Latent Reasoning* | "全局定向"是独立算子 → 定向值得显式做 |
| **PAM** (ACL 2026, Flavell 元认知框架) | 先识别任务性质再推理 |
| **MetaGPT** (arXiv 2308.00352) / **ChatDev** (arXiv 2307.07924) | SOP 角色化 + 交流式去幻觉（缺细节先问） |
| [arXiv 2609.38108](https://arxiv.org/abs/2609.38108) — *Plan Declaration-Execution Gap* | P1 闹钟：计划只有 22~45% 被遵守 |
| **CoPE** (ICML 2026) | plan-deviated trajectories 是长任务失败主因 |

### D. 记忆 / 上下文 / 压缩

| 论文 | 我们的用法 |
|---|---|
| [arXiv 2310.08560](https://arxiv.org/abs/2310.08560) — *MemGPT* | 分层记忆 → P0 存档 |
| [arXiv 2610.24453](https://arxiv.org/abs/2610.24453) — *Hippo* | 防污染：只存用户真实指令，不存模型自我总结 |
| [arXiv 2609.32520](https://arxiv.org/abs/2609.32520) — *StateForge* | 显式维护活动需求列表（意图漂移 0.476→0.384） |
| **U-Fold** (浙大/阿里 2026) / **ARC** (ACL 2026) | 摘要+todo+工具关键行重建上下文；每轮反应优于延迟反射 |
| [arXiv 2508.21433](https://arxiv.org/abs/2508.21433) — *The Complexity Trap* (JetBrains) | observation masking 优于纯摘要（-52% 成本 / +2.6% solve rate） |
| [arXiv 2611.03852](https://arxiv.org/abs/2611.03852) — *Why Pay for Long Reasoning When Rewrite Do Trick?* | 改写历史使后续推理变短 83~100%——但本机后缀税更大，**不采用** |
| [arXiv 2611.10982](https://arxiv.org/abs/2611.10982) — *Think or Remember* | 丢弃早期推理 HotpotQA -9~23pp；缓存复用时"丢弃"反而贵 1.74× |
| [arXiv 2604.09670](https://arxiv.org/abs/2604.09670) / [arXiv 2607.16072](https://arxiv.org/abs/2607.16072) / [arXiv 2610.26722](https://arxiv.org/abs/2610.26722) | 解释路径复述崩塌 → 短路径约定 |

### E. 工具 / 效率 / 能力边界

| 论文 | 我们的用法 |
|---|---|
| **Qwen3.5-35B scaffold 实验** (r/LocalLLaMA) + **Qwen3.6 35B little-coder** | verify-on-edit +15.6pp；scaffold > 模型选择 |
| [arXiv 2602.7213](https://arxiv.org/abs/2602.7213) — *Adaptive Retrieval helps Reasoning… but mostly if it's not used* | 检索频率随难度上升，但"不用检索"反而标志好性能 → 谨慎检索 |
| **FlyBy** (KAIST 2026-09) / **AdaSearch** (台大) | 执行瓶颈 vs 知识瓶颈；自知识意识 F1——本机不可训练，走规则 |
| **BFCL 工具选择崩塌** + [RAG-MCP, arXiv 2505.03275](https://arxiv.org/abs/2505.03275) | 工具面预算 → 不加 MCP（详见 [工具选择崩塌曲线综述](http://quidproquo.cc/posts/ai/2026-06-04-tool-selection-at-scale-en)）|
| **JetBrains / mcptrove / Keyhole harness 白皮书** | 本地 MCP 短名单；harness 六层组件清单 |

---

## Part 4：失败与放弃（负面资产）

> **这一节的价值不亚于成功清单**——它记录"为什么不做"，避免后来者重蹈覆辙。

### F1. `--moe-cache-cpu-share` 伪优化
- **看起来**：decode 20.30 → 27.90 t/s（+37%）。
- **实际**：P5 端到端 share=0 均值 418s、share=1.0 **1013s（慢 2.4×）**，生成 token 翻倍、每步 prefill 慢 4-5×。
- **结论**：agent 多轮场景必须 `share=0`。**decode t/s 是误导性指标。**

### F2. 温度极端值
- Q4@0.1：1/2 概率"想完不干"（683 字计划后直接 EOS）；Q4@0.9：3 步草率收工、P5 0/1。
- **结论**：Q4 最优 0.7，曲线 U 形；±0.1 之外明显退化。

### F3. `nmax 7` / `-t 6/10/16` / 电源计划 / `-lm` 大页 / KV q8_0 / ignore_eos
- 全部实测无收益或负收益（nmax 7：26.73 < 27.31 且 +153MiB；KV q8_0 显存不够）。

### F4. 思考预算硬切 / 改写历史思维链
- 硬切（切在半句）→ 思考与正文脱节；改写历史 → KV cache 后缀税（本机 20K 重预填充 **25~44s**）。
- **结论**：改用 `--reasoning-budget-message` 软引导 + append-only 注入。

### F5. apply_patch / edit 工具切换 / 工具结果去重
- A/B 无稳定收益。保留 `edit`，不去重。

### F6. 独立 Planner 进程 / 多审计员 panel / 自验证循环
- 独立 Planner：AI Office 显示轻量 orchestrator 规划即可，全 LLM 角色是反模式。
- 多审计员：Apple 9 judge ≈ 2 票，同家族相关性最高。
- 自验证：AI Office 实测让准确率 <60%。

### F7. 知识层概念/论点分层 / 成本硬预算 / 向量库记忆
- 知识层建设成本（每文档交叉引用更新概念/论点）远高于通用任务收益。
- 成本硬预算与"一次做完"目标冲突，且 D1/D2 已覆盖死循环。
- 向量库记忆：35B 的检索判断力撑不起 embedding 检索的质量门槛。

### F8. 逐级路径纯 prompt 模拟
- 六级逐段独立调用 0/8、五级"选择题"模拟整条 0/8。
- 论文方向对（IOP 六层逐级导航"eliminates hallucination by construction"），但**必须配真实 `list_dir` + 约束输出**；纯 prompt 模拟模型会自加解释、拼 cd 命令、合并多级。

### F9. MCP（当前不接）
- 三重否决见 [分支 E](#分支-e能力边界线防膨胀)。**若将来要做**：需 dsh 支持 + 工具面先降到 ≤20 + 只接 ≤2 工具的薄服务器 + schema 延迟注入。

### F10. 模板目标锚定（tc.n>=3 重申本轮要求）
- A/B 实测 -0.7%（噪声内），且被 P0 存档超集覆盖 → 删除该 `{% if %}`。

---

## Part 5：现状与运行期成本

### 机制清单（17 项）

**行为治理**：L0 空手收尾 / L1 文件声明校验 / L2 贴代码检测 / L3 短确认词 / D1 重复探测 / D2 同参双败 / D3 冗余 todo / D4 交付闸门 / **D5 风险门控审计**（含 MTP 接受率 <0.65）/ 纠正器 + 只读代执行 / Critic 产物评审 / Planner 验收标准检查 / verify-on-edit / present 深检 / 控制回合 / Skills 技能卡 / 危险操作分级 / per-step trace / JSON 解析重试。

**任务连续性**：P0 压缩存档（合同/决策/开放项/已排除/三问）/ P1.5 todo 回灌 / P1 todo 闹钟。

### 运行期成本账（本机 800 t/s prefill / 27 t/s decode）

| 机制 | 成本 |
|---|---|
| L0-L3 / D1-D3 / MTP / verify-on-edit / 深检 / 控制回合 / Skills / 危险操作 / trace | **≈0**（确定性代码，无 LLM） |
| D5 审计 | 10-20s/次，风险点触发（每会话 2-5 次） |
| Critic | 13-20s/次，present 前 ≤2 次 |
| Planner | ~11s/任务 |
| **合计** | **+5~10% 会话时长，换掉反复修改的 20~40% 返工风险** |

### 实测（2026-11-18）

| 项 | 结果 |
|---|---|
| 单元测试 | 26/26 + 38/38 |
| 门禁 | 29/29；`config_check.py` 一致 |
| agentlab（7 小任务） | 5/7 首轮 → 复跑通过（模型随机性，非回归） |
| **P5 交付级** | **PASS**，17 步 / 551.8s / 六维画像全 OK |
| **P4 长链路** | **PASS**，11 步 / 300.0s（比历史 486.7s 快 38%） |
| 显存 | 长任务余量掉到 107~113 MiB（<450 安全线）→ **跑长任务前重启** |

---

## Part 6：配置与注意事项

- 全部默认值在 [`cordis.patch.yml`](cordis.patch.yml) 的 agent-harness config。
- **换机器必须改**：`verifyScript` / `pythonPath` / `allowedRoots` / `specLogPath` / `critbankPath` / `ledgerPath` / `skillsDir` / `tracePath`。
- 外部依赖（可选，缺失用内置默认）：`bench/critbank.json`（9 条教训）、`bench/rubrics/*.json`、`bench/skills/*.md`（7 个）、`_trace.jsonl`。
- 发布流程见 skill `release-plugin.md`；调试见 `harness-debug.md`。

**相关文档**：
- [PERIPHERAL_CAPABILITIES.md](https://github.com/D-al/dsh-behavior-guard/blob/main/PERIPHERAL_CAPABILITIES.md) — MCP/连接器调研
- [USAGE_GUIDE.md](https://github.com/D-al/dsh-behavior-guard/blob/main/USAGE_GUIDE.md) — 新注入标签与调节旋钮
- [MORNING_REPORT_20261118.md](https://github.com/D-al/dsh-behavior-guard/blob/main/MORNING_REPORT_20261118.md) — 一次完整的自主作业报告

---

## Part 7：给后来者（人或 AI）的探索指南

### 7.1 方法论（我们踩出来的规则）

1. **任何"加速"必须用 P4/P5 端到端验证**，不看 decode t/s。
2. **暖态口径**：warmup 2-3 次 + 测 5 次取中位——冷态→暖态差 ~7%（MoE cache 按需增长）。
3. **单次 ±10%**，判优至少 2 次。
4. **每次调引擎参数后看日志的 `args[upstream]` 行**——`.env` 覆盖 INI，`config_check.py` 查一致性。
5. **测试台覆盖不到"20+ 轮后遇失败工具结果"**——改守卫前先过回放现场。

### 7.2 开放问题（值得继续挖）

| 问题 | 现状 | 下一步 |
|---|---|---|
| MTP 阈值的概率校准 | 0.65 是经验值 | 用 `_trace.jsonl` + `auditor_metrics.py` 做 ROC |
| 审计员有效率 | `_audit_feedback.jsonl` 已记 | 按门控类型统计，砍掉"有害"的门控 |
| 工具面裁剪 | 28→目标 18~20 | 先跑一周 trace，确认零调用再静态 disable |
| Planner 输出 schema 强制 | 靠 AGENTS.md 自觉 | 代码层校验"计划是否含完成标准" |
| 思考预算 per-request | dsh 不传字段（llama.cpp 其实支持 `reasoning_budget_tokens`） | 等 dsh 上游支持 |
| 事实性错误 / 参数语义错误检测 | 审计员盲区 | 需外部证据源或更聪明的 rubric |

### 7.3 别重试的清单一句话版

`moe-cache-cpu-share=1.0` / 温度 0.1 或 0.9 / nmax 7 / 硬切思考 / 改写历史 /
apply_patch 切换 / 工具结果去重 / 多审计员 / 自验证 / MCP / 向量库记忆 / 成本硬预算 / 逐级路径纯 prompt 模拟。

---

## 版本历史

| 版本 | 日期 | 关键变更 |
|---|---|---|
| v1.x | 11-07～11-17 | L0-L3、D1-D5、三角色、任务连续性、MTP 信号（behavior-guard 与 task-continuity 两个仓库） |
| **v2.0.0** | 11-18 00:52 | 两仓合并为单包 `dsh-agent-harness` |
| **v2.1.0** | 11-18 01:35 | 控制回合（meta-reasoning controller） |
| **v2.2.0** | 11-18 02:25 | 四项社区缺口：trace / JSON 重试 / Skills / 危险操作分级 |
| **v2.2.1** | 11-18 03:35 | planner rubric 外置接入 |

## License
MIT
