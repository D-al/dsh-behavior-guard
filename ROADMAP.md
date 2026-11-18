# 路线图（活文档）

> 这里的目标都**可执行、可验证**——每条带验证方法。完成后勾选并写进 [CHANGELOG](CHANGELOG.md)。
> 骨架在 [README](README.md)，这里展开。更新于 2026-11-18（v2.11.0 地基收口后重排）。

## 当前位置（先读这一段）

短期四目标（spec 分类 / Critic 去同源 / 自适应原型 / 真实回归）与长期地基①②（GWT 总线 / FEP 闭环）
**均已完成**。系统现在处于「**骨架已立、血肉待长**」阶段：数据底座（outcome 63+/trace 3200+/CritBank 真实命中）
与共享状态总线都已就位，接下来是从结构涌现进入功能涌现。

**执行顺序已调整**（ADR-0017）：先建结构性地基（已完成）→ 再积累数据型目标（新短期）→
最后做需要世界模型/外部基准的目标（新长期）。独立轨道（上游 PR / v1.0.0 / 工具面裁剪）不插队。

## 四波次逻辑（依赖方向，不随时间变）

> 短/中/长期是**执行节奏**（会随进度重排）；这四波是**依赖逻辑**（稳定不变）。判断新工作先问"它属于哪波"。

| 波次 | 主题 | 依赖逻辑 | 状态 |
|---|---|---|---|
| **0 地基期** | 数据底座 + 共享总线 | 没 outcome 无从比对、没 GWT 只能手动搬运状态——是所有后续机制的前提 | ✅ 已完成（v2.8~v2.11）|
| **1 回填期** | 把积累的数据变成能力 | FEP 偏差流 + outcome 已攒够，现在能喂技能进化与遗忘 | 🟢 当前短期 |
| **2 连接期** | 器官间流动（第 4 层深化）| GWT 已立，情景检索/会话树可以进主循环；BDI 有状态卡可依 | 🟡 中期 |
| **3 进化期** | 心智从经验变聪明（第 5 层延展）| **投毒防御必须先于写回闭环**——SkillJack：80% 攻击删源后仍存活 | 🔴 长期 |

**双向迭代**：依赖链不只向上——第 4 层的审计需求曾反向复用第 1 层的 spec 日志信号；
FEP 的注入曾挤掉 D5 审计额度，反向促成"学习信号不占运行时注入通道"的边界（ADR-0017）。
判断新工作时多问：它属于哪波？是否需要回头改下层？

**执行铁律**：一波没验收，不开始下一波。

---

## ✅ 已完成（归档，不再占用短中长期位置）

| 目标 | 版本 | 验证 |
|---|---|---|
| spec 阈值分类标定 | v2.10.0 | `test_short_term_goals.mjs` 2/2 |
| Critic 去同源化（异质采样 + AC3）| v2.10.0 | 同上 4/4 |
| test-time 自适应原型 | v2.10.0 | 同上 2/2（端到端 token 对照待开）|
| 真实会话回归 | v2.10.0 | 桥接派真实任务，verify-on-stop 验证链成立 |
| 权限弹窗代劳（full-access 预设 + answerer）| v2.10.1 | 新会话 0 次 `approval/asked` |
| **GWT 共享状态总线**（胼胝体）| v2.11.0 | `test_gwt_fep.mjs` 9/9 |
| **FEP 预期闭环**（小脑）| v2.11.0 | 同上 7/7；真实 dsh trace 出现 `fep_cycle` |
| 结果反馈捕获 / 各类确定性门控 / 三角色 / P0-P2 心智拼图 | v2.0~v2.9 | 见 CHANGELOG 全文 |

完整历史见 [CHANGELOG](CHANGELOG.md) 与 [时间线](docs/history/TIMELINE.md)——**历史只追加，不重写**。

---

## 🟢 短期（1-2 周）：把数据变成能力

- [ ] **技能自进化数据闭环** — 消费 `_outcome.jsonl` + `fep_cycle` 偏差喂 skill_draft，数据已 ≥20 条
  - 做法：B 段 watcher 把 FEP 偏差归入 skill 草稿的证据字段；`promote_skills` 仍人工审批（ADR-0015）
  - 验证：草稿命中后同类任务成功率变化；投毒防御（provenance + lineage）先于自动写回
  - 依据：[Reflexion](https://arxiv.org/abs/2303.11366) 8.2→33.8、[ExpeL](https://arxiv.org/abs/2307.11909)
- [ ] **可控遗忘常态化** — CritBank 从 0 计数变真实 helpful/harmful，月度 `crit_decay.py --apply`
  - 做法：FEP 偏差 + crit_hit 命中后 3 步内是否再失败 → 结算 helpful/harmful；过时教训 retire/supersede
  - 验证：无过时经验被引用（假记忆自检），状态表里有真实非零计数
- [ ] **自适应原型端到端对照** — 开启 `adaptiveThinkEnabled`，P3/P4/P5 各跑 2 次取中位
  - 验证：token 下降且成功率不降；若不达标就保持默认关闭（不硬上）

## 🟡 中期（1-2 月）：器官间流动

- [ ] **情景检索进主循环** — EVENTS.md + es.exe 从离线脚本接入控制回合自动 top-3 注入
  - 依赖：GWT 快照提供 goal/todo/evidence，检索结果写回快照的 evidence 字段
  - 验证：长任务中历史经验被主动引用次数 >0
- [ ] **会话树实时化** — session_tree.py 从事后分析变 harness 实时写 parent 指针，支持真 rewind
  - 依赖：GWT 快照加 `parentId`；写入 append-only（ADR-0013）
  - 验证：能从任一节点 fork 且不改写历史、不付 KV 后缀税
- [ ] **用户意图 BDI 深化** — 现有 `s.bdi` 单槽升级为 belief/desire/intention 三槽动态推理
  - 依赖：GWT 快照已有 bdiGoal；FEP 偏差可作为 belief 修正信号
  - 验证：用户约束跨压缩不丢，意图漂移检测有状态可依
  - 依据：[XYBench](https://ainewstodays.com/ai2-xybench-benchmark-8115-misconception-queries-emnlp-2026) 的"识别≠生成"鸿沟

## 🔴 长期（季度级）：架构完整性与外部效度

- [ ] **FEP 深化：从偏差检测到世界模型** — 现有 FEP 只判"产物是否存在"，下一步断言"产物内容应满足 what"
  - 依赖：情景检索（提供历史模式）+ BDI（提供意图）
  - 验证：预期断言的精度与召回；误报不侵占注入通道（ADR-0017 红线）
- [ ] **标准化 eval** — 自建 P3/P4/P5 迁移到 SWE-bench Verified 子集，提升外部效度
  - 验证：与社区同基准可比，不再只靠自建短任务
- [ ] **统一脑功能分区对照** — 按人脑分区盘点覆盖度，优先补空白区（眶额价值/脑干稳态）
  - 依据：Foundation Agents 综述（2504.01990）七模块蓝图；Karpathy 指出杏仁核/海马"几乎缺失"
  - 状态：调研已完成（2026-11-18），待决定是否落 ADR
- [ ] **独立轨道（不插队，与脑结构无关）**：autoparser 上游 PR + 撤补丁（[#29307](https://github.com/ggml-org/llama.cpp/pull/29307)）；llama.cpp v1.0.0 升级（FP8 KV + 非阻塞 MoE cache 破显存墙）；工具面 28→18-20（**前置：用户拍板**）

## 明确不做

| 不做 | 理由 |
|---|---|
| 多模态 / CUA | 与纯文本 8GB 环境不匹配，社区主战场但非我们场景 |
| 通用 agent 框架 / 向量检索代码 | [Harness Engineering 2609.00006](https://arxiv.org/abs/2609.00006)：11 个主流 harness 全用确定性循环，无人用 |
| 训练 / 微调模型 | 与"权重零改"的合成路线冲突 |
| 堆更多 judge | [Apple: 9 judge≈2 票](docs/MIND_GAPS_RESEARCH.md)；信号源多样性 >> judge 数量 |
| 强制二选一 / 质疑式干预 | "Are you sure"≈"You are wrong"（JS 散度 0.0186），会让 76.6% 正确答案被推翻（见 [ADR-0014](decisions/0014-reject-forced-choice-injection.md)）|
| FEP 偏差走运行时注入通道 | 实测会挤掉 D5 审计额度（ADR-0017）——学习信号只进 trace/学习队列 |
