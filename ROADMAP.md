# 路线图（活文档）

> 这里的目标都**可执行、可验证**——每条带验证方法。完成后勾选并写进 [CHANGELOG](CHANGELOG.md)。
> 骨架在 [README](README.md)，这里展开。更新于 2026-11-18。

## 三波次逻辑（为什么是这个顺序）

> 下面的短/中/长期是**执行节奏**；这三波是**依赖逻辑**。每条目标都属于某一波。

前四层（物质→调优→构建脑→合成心智）造的是**结构**，但很多结构是空的：
CritBank 计数全 0、技能无一来自真实轨迹、spec 阈值拍脑袋、EVENTS.md 未进主循环、Critic 同源。
所以接下来不是"再加第 6 层"，而是**从结构涌现进入功能涌现**。

| 波次 | 主题 | 依赖逻辑 | 对应下方 |
|---|---|---|---|
| **1 回填期** | 给系统装"结果反馈"回路 | 所有后续机制的数据底座——没它，FEP 无从比对、技能进化只能猜 | 短期全部 + 中期①② |
| **2 连接期** | 器官间流动（第 4 层深化）| GWT 状态总线把散落状态缝成单一认知流；技能提炼才能拿到完整证据 | 中期③⑤ + 长期①② |
| **3 进化期** | 心智从经验变聪明（第 5 层延展）| **投毒防御必须先于写回闭环**——SkillJack：80% 攻击删源后仍存活 | 中期④ + 长期③④⑥ |

**双向迭代**：依赖链不只向上——第 4 层的审计需求曾反向复用第 1 层的 spec 日志信号。
判断新工作时多问：它属于哪层？是否需要回头改下层？

**执行铁律**：一波没验收，不开始下一波。

## 🟢 短期（1-2 周）：收口已知风险

- [x] **【波1】标定 spec 阈值 0.65**（v2.10.0）— 社区典型 acceptance 对话 0.65-0.75 / 代码 0.55-0.70 / 创意 0.45-0.60；全局 0.65 在长尾任务可能误触发
  - 做法：`taskTypeOf()` 纯关键词分类（code/creative/dialogue/general）+ `specAcceptanceByType` 分类阈值（0.60/0.50/0.70/0.65），默认关闭、开启后覆盖全局值
  - 验证：`test_short_term_goals.mjs` 证明 creative@0.55 在分类阈值 0.50 下不误触发、全局 0.65 下触发（2/2）
  - 依据：[COMPETITIVE_ANALYSIS](docs/COMPETITIVE_ANALYSIS.md) 薄弱点 4
- [x] **【波1】Critic 去同源化**（v2.10.0）— 同模型 temp=0 conditioning 相同，"异质 rubric"不解决模型同源偏差
  - 做法：Critic 用异质采样 `criticTemperature=0.7`/`criticTopK=20`（callLLMOnce 支持 sampling 覆盖）；
    prompt 强化 AC3 纪律——只拿任务+产物，明确"看不到也不推测执行过程"，绝不喂 s.trail
  - 验证：`test_short_term_goals.mjs` 4/4（异质温度/top_k + prompt 无过程信息）
- [x] **【波1】test-time 自适应原型**（v2.10.0）— DART 双草稿一致性路由（简单题跳过长思考），纯 prompt+控制流
  - 做法：两个零成本信号（MTP acceptance + 无失败）一致性判难度，控制回合注入思考预算提示，trace 记 `adaptive_route`；默认关闭待端到端 token 对照
  - 验证：`test_short_term_goals.mjs` 2/2（高 acceptance → skip-deep-think）；端到端 P3/P4/P5 token 对照待开
  - 依据：[DART 2606.23181](https://arxiv.org/abs/2606.23181)、[BOSS 2610.26383](https://arxiv.org/abs/2610.26383)
- [x] **【波1】真实会话回归**（v2.10.0）— verify-on-stop / 中性心智状态 / 意图漂移跑真实长任务
  - 验证：桥接派 3 个真实任务，`trace_report.py` 看误触发率、有无新循环（见 CHANGELOG v2.10.0）

## 🟡 中期（1-2 月）：从能用 to 可靠

- [x] **【波1】结果反馈捕获（基础设施已装）** — write/edit 后自动记结构化判定到 `_outcome.jsonl`（v2.8.3，测试 6/6）
- [ ] **【波1】技能自进化数据闭环** — 消费 `_outcome.jsonl` 喂 skill_draft（需数据积累 ≥20 条）
  - 验证：攒 20-50 条后 skill_draft 命中后成功率变化
  - 依据：[Reflexion](https://arxiv.org/abs/2303.11366) 8.2→33.8、[ExpeL](https://arxiv.org/abs/2307.11909)
- [ ] **【波1】可控遗忘常态化** — CritBank 状态表从 0 计数变真实 helpful/harmful，月度 `crit_decay.py --apply`
  - 验证：无过时经验被引用（假记忆自检）
- [ ] **【波2】情景检索进主循环** — EVENTS.md + es.exe 从离线脚本接入控制回合自动 top-3 注入
  - 验证：长任务中历史经验被主动引用次数 >0
- [ ] **【波2】工具面裁剪 28→18-20** — 按"单会话实际使用 11 个"的数据裁；**前置：用户拍板**
- [ ] **【波2】会话树实时化** — session_tree.py 从事后分析变 harness 实时写 parent 指针，支持真 rewind

## 🔴 长期（季度级）：架构完整性

- [ ] **【波2】GWT 广播总线** — 8 个认知模块共享确定性状态对象，替代手动搬运（心智状态快照是雏形）
- [ ] **【波2】FEP 预测闭环** — 从"事后验证"升级为"先断言预期结果 → 比对观察 → 偏差驱动学习"
- [ ] **【波3】用户意图 BDI 深化** — 状态卡升级为信念-愿望-意图动态推理，参照 [XYBench](https://ainewstodays.com/ai2-xybench-benchmark-8115-misconception-queries-emnlp-2026) 的"识别≠生成"鸿沟解法
- [ ] **【波3】上游 PR + 撤补丁** — autoparser 两行修复推给 llama.cpp（[#29307](https://github.com/ggml-org/llama.cpp/pull/29307) 合并后撤本地补丁）
- [ ] **【卡脖子】llama.cpp v1.0.0 升级** — FP8 KV + 非阻塞 MoE cache 破显存墙；需重编+重打补丁+全量回归
- [ ] **【波3】标准化 eval** — 自建 P3/P4/P5 迁移到 SWE-bench Verified 子集，提升外部效度

## 明确不做

| 不做 | 理由 |
|---|---|
| 多模态 / CUA | 与纯文本 8GB 环境不匹配，社区主战场但非我们场景 |
| 通用 agent 框架 / 向量检索代码 | [Harness Engineering 2609.00006](https://arxiv.org/abs/2609.00006)：11 个主流 harness 全用确定性循环，无人用 |
| 训练 / 微调模型 | 与"权重零改"的合成路线冲突 |
| 堆更多 judge | [Apple: 9 judge≈2 票](docs/MIND_GAPS_RESEARCH.md)；信号源多样性 >> judge 数量 |
| 强制二选一 / 质疑式干预 | "Are you sure"≈"You are wrong"（JS 散度 0.0186），会让 76.6% 正确答案被推翻（见 [ADR-0014](decisions/0014-reject-forced-choice-injection.md)）|
