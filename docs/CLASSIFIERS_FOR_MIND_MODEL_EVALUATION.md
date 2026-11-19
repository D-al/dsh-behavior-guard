# 分类器扩展"心智模型"：可行性评估（2026-11-19）

> 用户问：听说很多分类器可以扩展心智模型能力，广泛调研。
> 结论：**方向成立但要选对分类器类型**——encoder 小分类器（<500M，1-70ms CPU）可行且高价值；
> 生成式小 LLM 分类（S7 已证伪 4-6s）和"学习式难度路由"（自测 51.3%≈随机）不可用。
> 最重要的发现：本 harness 的真实数据（Jev 报告）同时给出了强项和弱项，比通用论文更可信。

## 一、可行性边界（先划死）

| 方案 | 延迟（CPU）| 可行性 |
|---|---|---|
| TF-IDF + LR | **0.044ms** | ✅ 极快 |
| MiniLM-L6-v2 + LR（22M）| **1.28ms** | ✅ 极快 |
| embedding + LR | 4-20ms | ✅ |
| OpenVINO BERT-base（110M）| ~8ms | ✅ |
| ORT BERT-base INT8 | 22ms | ✅ |
| Prompt-Guard 86M | 厂商<10ms / 第三方 60-65ms | ⚠️ 需实测+重标定阈值 |
| NLI DeBERTa-v3-small | ~15ms/锚点 | ✅ |
| DuoGuard-0.5B | 16ms/input | ✅ |
| **生成式小 LLM（Qwen3-0.6B, S7）** | **4000-6000ms** | ❌ 已证伪 |
| DSPy+GLM-5.3-Flash 分类 | 1850ms/条 | ❌ 太慢 |

**铁律**：本机只用 encoder 分类器（BERT/MiniLM/NLI 类），不用生成式小 LLM 做分类。

## 二、10 类分类器与挂载点

| 类型 | 代表 | 数字 | 挂载点 | 判定 |
|---|---|---|---|---|
| 1 意图/领域 | embedding+LR / SetFit / ModernBERT | 92-94%，1-20ms | **BDI 意图槽**、D1 入口分流 | **推荐** |
| 2 安全/注入 | Prompt-Guard 86M / DuoGuard | P100/R100@阈值0.1（Jev 真实数据）；小模型逆缩放（1B>8B）| S6 规则层之后的 Tier-2 | **推荐（须重标定）** |
| 3 校准/置信 | P(True)/logprob/hidden-state probe | P(True) AUROC 0.53-0.67（弱）；probe 0.73-0.83 | 权重零改下需 hidden state → 受限 | ❌ 用 certainty 覆盖率曲线替代 |
| 4 情感/语气 | Jev 决策模型 / 跨域小 encoder | 68.4% recall；自训 68M 仅 14.9%（跨域崩）| FEP 用户状态 | ⚠️ 只在高价值场景用决策模型式 |
| 5 难度路由 | RouteLLM BERT router | 论文省 2x；**Jev 自测 51.3%≈随机，中文 14.6%** | L6 误差预测器 | ❌ 改用元信息/历史失败率规则 |
| 6 幻觉/事实性 | NLI cross-encoder | 15ms/锚点；删掉 F1 0.378→0.180 | 验收后置审计、CritBank 证据校验 | **推荐（fire-and-forget）** |
| 7 工具/动作 | choice 式 encoder / Meta-Tool 3B | Jev k=5 相似 96.5%；3B 生成 1576ms 且超网络 0% 增益 | Skill Router（先召回后竞争）| ✅ 用 choice 式，不用生成式 |
| 8 过程/轨迹 | FSM / MiniRocket / LogReg | FSM AUROC **0.94**、1-110ms 构建；**Jev 长轨迹归因 0.56≈随机** | Self-Harness 聚类、L6 局部信号 | **推荐（限局部信号）** |
| 9 认知状态/心智模块 | GWT/CTM/元认知向量 | 架构提案为主，非单一 benchmark 成品 | GWT 槽位、元认知守门 | ⚠️ 架构借鉴，非现成分类器 |
| 10 多标签/层次 | GLiClass-V3 / 竞争+验证 | 128 标签仅掉 7-20% 吞吐；逐问 R@1 15%→竞争+验证 81% | 一个前向输出 意图+风险+难度 | ✅ 有条件推荐 |

## 三、关键负面证据（必须计入设计）

1. **Jev 自测最重要**：本 harness 真实数据上，难度路由 51.3%（≈随机）、长轨迹归因 0.56（≈随机）、中文路由 14.6%——
   **"从文本预测小模型会不会错"不是自然语言属性，依赖模型特性**。故 L6 误差预测器必须限定局部可观察信号（工具报错/重复动作/格式违规），
   跨步因果归因留给主模型/人工。
2. **Prompt-Guard 默认阈值 FPR 98%**——不可直接上生产，必须在自有良性流量上标定（high-security 0.3→TPR98.5/FPR5.2；balanced 0.5→95.7/2.1）。
3. **校准≠置信≠正确**：高 certainty 只代表"确信按你的 criteria 判断"。Jev 0-0.1 低分桶仍有 16.6% 恶意混入——低分不等于安全。
4. **安全分类逆缩放**：ShieldGemma-2B(62.4%) > 9B(54.7%)、LlamaGuard-1B(59.9%) > 8B(48.4%)——小分类器反而更准，支持本路线。
5. **多分类器维护成本**：每个需版本 pin、阈值标定、升级复测。建议收敛到 **3-5 个共享编码器 + 一个多标签头**，而非 N 个独立模型。
6. **跨域崩**：小 encoder 自训情感分类器换对话风格 recall 从 68% 掉到 14.9%——不要跨场景复用。

## 四、TOP 5 推荐（按对本 harness 的心智扩展价值）

1. **轨迹/过程分类器（FSM + 线性）→ Self-Harness 弱点聚类 + L6**：几乎零成本、AUROC 0.94、与"纯规则脚手架"同构
   （论文明确"行为拓扑由 harness 而非 LLM 塑造"）。限局部信号。
2. **注入风险 Tier-2（Prompt-Guard 86M / 重标定的 Jev scan）→ S6 之后的分层判别**：必做，先规则→再编码器→再主模型。
3. **embedding+LR / SetFit 意图 → BDI 意图槽**：1-20ms、92-93%、共享编码器。
4. **NLI cross-encoder 事实性 → 验收后置审计**：15-300ms fire-and-forget，用户零延迟。
5. **多标签编码器（GLiClass / 竞争+验证）→ GWT 共享心智状态**：一个前向输出意图+风险+难度，对应 GWT 模块竞争。

## 五、对路线图的建议（新目标候选）

- **M8 轨迹 FSM 监控器**（高/中）：把 trace 压成 FSM 做局部失败预测，与 S1 evidence bundle 同源。**优先**。
- **M9 BDI 意图分类器**（中/中）：embedding+LR 填 BDI 意图槽，1-20ms。依赖 M3（BDI 三槽）。
- **L8 多标签心智状态编码器**（中/高）：GLiClass 式一个前向多信号写 GWT，需先验证中文表现。
- **S6 模型层升级**（已有尾巴）：Tier-2 用 86M Prompt-Guard，**必须先重标定阈值**（FPR 98% 教训）。
- **不新增**：生成式小 LLM 分类器（S7 证伪）、学习式难度路由（Jev 51.3%）、专用"会不会错"预测器（需 hidden state）。

## 证据链接
- Jev harness 实测报告（最贴合本项目）: https://github.com/Aitejiu/jev-harness-lab/blob/29ddf8210e3a96f9d383e9b479e3e5c39455c394/docs/REPORT.md
- 分类器基准（TF-IDF/MiniLM/LLM）: https://wpnews.pro/news/jev-attack-of-the-classifiers
- 安全护栏逆缩放: https://arxiv.org/html/2511.22047
- DuoGuard: https://github.com/yihedeng9/DuoGuard/tree/main
- Automata from Agent Traces (FSM AUROC 0.94): https://arxiv.org/abs/2608.23670
- MiniRocket 轨迹监控: https://github.com/Dinesh-Kumaralingam/agent-trajectory-monitor
- GLiClass-V3: https://arxiv.org/pdf/2508.07662.pdf
- NLI 事实校验: https://docs.synapcores.com/nli
- SetFit 级联: https://arxiv.org/pdf/2602.18922
- embedding+LR 权衡: https://avchauzov.github.io/blog/2026/intent-routing-architecture-tradeoffs
- Manning 认知 Agent 架构: https://www.manning.com/preview/ai-agents-in-action-second-edition/chapter-10

> 本文遵循知识资产沉淀规则。所有数字区分实证/架构提案；Jev 自测的负面结果优先于通用论文基准。
