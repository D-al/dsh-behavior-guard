# 路线图（活文档）

> 这里的目标都**可执行、可验证**——每条带验证方法。完成后勾选并写进 [CHANGELOG](CHANGELOG.md)。
> 骨架在 [README](README.md)，这里展开。更新于 2026-11-18。

## 🟢 短期（1-2 周）：收口已知风险

- [ ] **标定 spec 阈值 0.65** — 社区典型 acceptance 对话 0.65-0.75 / 代码 0.55-0.70 / 创意 0.45-0.60；全局 0.65 在长尾任务可能误触发
  - 做法：P3/P4/P5 三任务各测，改分类阈值而非全局值
  - 验证：审计误触发率 <10%，且真阳性不降
  - 依据：[COMPETITIVE_ANALYSIS](docs/COMPETITIVE_ANALYSIS.md) 薄弱点 4
- [ ] **Critic 去同源化** — 当前同模型 conditioning，"异质 rubric"不解决模型同源偏差
  - 做法：Critic 强制只看产物+证据、不看执行者推理（AC3 结论）；或不同 temperature/preset
  - 验证：Critic 独立发现率对照
- [ ] **test-time 自适应原型** — DART 双草稿一致性路由（简单题跳过长思考），纯 prompt+控制流
  - 验证：P3/P4/P5 token 下降且成功率不降
  - 依据：[DART 2606.23181](https://arxiv.org/abs/2606.23181)、[BOSS 2610.26383](https://arxiv.org/abs/2610.26383)
- [ ] **真实会话回归** — v2.8.0 新机制（verify-on-stop / 中性心智状态 / 意图漂移）跑 3-5 个真实长任务
  - 验证：`trace_report.py` 看误触发率、有无新循环

## 🟡 中期（1-2 月）：从能用 to 可靠

- [ ] **技能自进化数据闭环** — 每轮 write/edit 后追加结构化成功/失败判定（现在缺证据）
  - 验证：攒 20-50 条后 skill_draft 命中后成功率变化
  - 依据：[Reflexion](https://arxiv.org/abs/2303.11366) 8.2→33.8、[ExpeL](https://arxiv.org/abs/2307.11909)
- [ ] **可控遗忘常态化** — CritBank 状态表从 0 计数变真实 helpful/harmful，月度 `crit_decay.py --apply`
  - 验证：无过时经验被引用（假记忆自检）
- [ ] **情景检索进主循环** — EVENTS.md + es.exe 从离线脚本接入控制回合自动 top-3 注入
  - 验证：长任务中历史经验被主动引用次数 >0
- [ ] **工具面裁剪 28→18-20** — 按"单会话实际使用 11 个"的数据裁；**前置：用户拍板**
- [ ] **会话树实时化** — session_tree.py 从事后分析变 harness 实时写 parent 指针，支持真 rewind

## 🔴 长期（季度级）：架构完整性

- [ ] **GWT 广播总线** — 8 个认知模块共享确定性状态对象，替代手动搬运（心智状态快照是雏形）
- [ ] **FEP 预测闭环** — 从"事后验证"升级为"先断言预期结果 → 比对观察 → 偏差驱动学习"
- [ ] **用户意图 BDI 深化** — 状态卡升级为信念-愿望-意图动态推理，参照 [XYBench](https://ainewstodays.com/ai2-xybench-benchmark-8115-misconception-queries-emnlp-2026) 的"识别≠生成"鸿沟解法
- [ ] **上游 PR + 撤补丁** — autoparser 两行修复推给 llama.cpp（[#29307](https://github.com/ggml-org/llama.cpp/pull/29307) 合并后撤本地补丁）
- [ ] **llama.cpp v1.0.0 升级** — FP8 KV + 非阻塞 MoE cache 破显存墙；需重编+重打补丁+全量回归
- [ ] **标准化 eval** — 自建 P3/P4/P5 迁移到 SWE-bench Verified 子集，提升外部效度

## 明确不做

| 不做 | 理由 |
|---|---|
| 多模态 / CUA | 与纯文本 8GB 环境不匹配，社区主战场但非我们场景 |
| 通用 agent 框架 / 向量检索代码 | [Harness Engineering 2609.00006](https://arxiv.org/abs/2609.00006)：11 个主流 harness 全用确定性循环，无人用 |
| 训练 / 微调模型 | 与"权重零改"的合成路线冲突 |
| 堆更多 judge | [Apple: 9 judge≈2 票](docs/MIND_GAPS_RESEARCH.md)；信号源多样性 >> judge 数量 |
| 强制二选一 / 质疑式干预 | "Are you sure"≈"You are wrong"（JS 散度 0.0186），会让 76.6% 正确答案被推翻（见 [ADR-0014](decisions/0014-reject-forced-choice-injection.md)）|
