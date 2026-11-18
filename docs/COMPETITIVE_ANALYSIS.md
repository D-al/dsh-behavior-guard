# 合成心智 vs 社区主流方案：先进与落后对比

> 数据来源：5 路广搜（docs/MIND_GAPS_RESEARCH.md）+ 第 6 路"先进维度"专项调研。
> 判据：不吹牛、不贬低——每条都给一手链接和具体数字。

## 核心结论（二分法）

**架构理念：我们领先或齐平**（确定性优先、零训练、外置认知、模板层干预）
**工程成熟度：我们明显落后**（社区产品化了 2-3 年，我们 11-18 才起步）

---

## 一、先进的维度（有证据）

### A1 确定性门控的深度和广度

社区：[Harness Engineering (2609.00006)](https://arxiv.org/abs/2609.00006) 解剖 11 个 coding harness，
结论是全部手写循环 + 确定性检索；LivePlan (2608.06701) 的"规则先筛、LLM 再审"是社区 2026 的新提倡。

我们：L0-L3 早收尾 + D1-D5 风险门控 + verify-on-edit + present 深检 + 危险操作分级
——绝大部分 0 LLM，且已跑 30/30 门禁。这比社区的"新提倡"更彻底。

### A2 模板层干预（治本 vs 治标）

我们：直接在 jinja chat template 做 `is_stub` 跳过假完成 assistant + 生成位置锚点。
社区：主流在 prompt 层或 tool_choice=required（我们 A/B 验证后者 0/2 无效）。

### A3 引擎内部信号作零成本风险代理

我们：读 llama-server 的 MTP draft acceptance 率 <0.65 触发审计门控，不额外调用 LLM。
（待专项调研验证是否独创）

### A4 端到端实证文化

我们：decode t/s 伪优化（+37% 但端到端慢 2.4×）、温度 U 形、多审计员无效——
都是自己 A/B 证伪的，不是纸面数字。社区大量方案只有论文自报数字。

---

## 二、落后的维度（有证据）

| 维度 | 社区成熟度 | 我们状态 |
|---|---|---|
| 会话树/rewind | OpenHands/Pi/OpenCode 一等公民 | 今天才做离线脚本 |
| 记忆/技能写回 | Hermes 907 行 review + 审批/归档 | 今天才做审批门 |
| verify-on-stop | Hermes / OpenHands /goal | 今天才加 |
| test-time 自适应 | DART+ARR+BOSS：token -41~76% | 完全没做 |
| 多模态/CUA | 2026 社区重点 | 0 |
| 形式化 eval | 标准 benchmark 套件 | 只有自建 agentlab/projectlab |
| 深度 ToM | BDI/XYBench | 今天才做骨架 |


---

## 第六路专项调研修正（重要：推翻两项"领先"判断）

**一句话总括（调研原文）**：我们的真正护城河是"在极小模型、零训练、纯文本约束下，
把社区公认的正确原则（单 agent + 确定性门控 + 缓存友好 + 实证）用一套权限语义和跨层信号
（spec acceptance）整合到极致"——是**整合与跨层复用**的领先，**不是任何单一技术组件的原创**。

### 原判断被推翻的两项

1. ❌ **"确定性门控深度领先"要降级**：社区 2026 已明确收敛到"确定性 cascade"
   （[Stability Trap 2601.11783](https://arxiv.org/html/2601.11783)、
   [Deterministic vs LLM-Judge 2026](https://futureagi.com/blog/deterministic-vs-llm-judge-evals-2026/)：
   确定性是免费的 30-60% 失败地板）。**方向一致，不领先**——我们只是推得极端。
2. ❌ **"append-only 避免后缀税"完全不新**：这是社区第一指标 + 黄金规则
   （[Manus: KV-cache hit rate is the single most important metric](https://mnemoverse.com/docs/research/agents/kv-cache-context-engineering)）。
   且 8GB 下 llama.cpp prefix cache 是否真命中还需自证。

### 真正领先的 TOP 5（调研判定）

1. **Spec acceptance → 审计门控**：社区用该信号做吞吐/调度，我们跨层复用到语义风险审计，
   零额外 LLM、零 logits 访问——**跨层复用新颖，信号思想不新**
2. **零权重/零并行下的带权限语义多角色控制平面**：单写者+steer+代执行+三态验收，
   ['方向领先/技术平凡']——社区多 agent 已被证伪（MAST 1600+trace/κ=0.88、Google+MIT 180 组
   顺序任务 -39~-70%），我们的选择对了，但 conditioning 技术是 2023 年级基础
3. **极端确定性占比 + is_stub 模板层治本**：少见但社区有更 principled 的约束解码
4. **chat-template 层锚点**：少见切入点，但 hacky、不可移植
5. **证伪驱动的实证文化**：真实亮点，但基准是自设的，外部效度有限

### 我们薄弱/落后的补充发现

- **Critic 与执行者同源**：社区要求异质 verifier 破 self-preference；我们"异质 rubric"不解决模型同源偏差
- 外置记忆能力弱于 Mem0(+26%质量/-91%延迟)/Zep(+18.5%/-90%)/Letta
- spec 阈值 0.65 脆弱：社区典型 acceptance 对话 0.65-0.75/代码 0.55-0.70/创意 0.45-0.60，
  我们的阈值在创意长尾任务可能系统性误触发——**需用 P3/P4/P5 标定，不能拍脑袋**
- template 干预 hacky（社区有 Outlines FSM 97%成功/logit masking 更稳健）
