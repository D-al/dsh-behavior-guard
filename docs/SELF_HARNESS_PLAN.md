# Self-Harness 落地方案（2026-11-19）

> 来源：[Self-Harness: Harnesses That Improve Themselves](https://arxiv.org/abs/2606.09498)（arXiv 2606.09498v3，上海 AI Lab）
> + 官方仓库 [qzzqzzb/Self-Harness](https://github.com/qzzqzzb/Self-Harness)。
> 本文是**执行方案**，定位为 ROADMAP 新短期①「技能自进化数据闭环」的具体实现路径；决策依据见 [ADR-0018](../decisions/0018-self-harness-two-stage.md)。

## 一、论文要点（只取与我们相关的）

Self-Harness 定义：固定模型 `M` 与评估器 `ℰ`，只改进非参数化脚手架 `h`；一个三步闭环：

1. **Weakness Mining**：在 held-in 任务上跑当前 harness → 从 trace 里抽失败签名 `φ(r) = (terminal_cause, criticality, agent_mechanism)` → **精确匹配聚类**（不用 embedding）→ 产出 evidence bundle（按 support × actionability 排序）。
2. **Harness Proposal**：同一个模型 `M` 在 proposer role 下生成 K 个互不相同的候选修改，每个绑定一个失败机制 + 一个**可编辑面**，最小改动；允许明确 `decline`。
3. **Proposal Validation**：baseline 与候选同时在 held-in / held-out 上评估（仓库默认 `repeats=2`），接受规则是「任一 split 不退化且至少一个提升」；通过的合并进 `h(t+1)`，否则保持 `h(t)`。

数字：Qwen3.5-35B-A3B 在 Terminal-Bench-2.0 上 held-in 15.1→36.0、held-out 23.8→38.1（README 总表 18.0→36.7）；九个模型×benchmark 组合全部提升，最大 +40.6pp / +132% 相对。仓库默认 `--route-count=4`、`--max-candidates=1`、split 43 train / 21 heldout。

**它给 Qwen3.5 找到的改进**（提前查依赖、打断重复失败命令、跳出无休止探索、工具出错后仍产出产物）与我们 CritBank 的教训高度重合——既验证方向，也说明这些机制可以被自动发现。

## 二、与我们的对照：已经有的一半

| 论文要素 | 我们已有 | 真缺口 |
|---|---|---|
| 执行轨迹 + verifier 结果 | `_trace.jsonl` 3300+ 行、`_outcome.jsonl` 60+、CritBank 9 条真实命中 | 没有 verifier-grounded 失败签名与聚类 |
| 可编辑面（editable surfaces） | index.mjs 2000 行 / 40+ 开关 + skills + 配置 | **没有白名单**，不能让模型自由改代码 |
| proposer | 目前由 WorkBuddy agent 手工做——即论文的 **Meta-Harness** 阶段 | 35B 自己当 proposer 的闭环未建 |
| 回归门禁 | `regression_check.py` 30/30 静态门禁 | 不是 baseline vs candidate 的**双 split pass-rate** 判定 |
| 评测任务集 | `agentlab.py` 7 任务 / `projectlab.py` P1-P5 | 太小，撑不起 train/heldout × 2 repeats |

## 三、四阶段执行方案

### P0 · 可编辑面白名单 + 评测台（地基，先做）

**产出**：`surfaces.json` + `tools/self_harness_eval.py` + acceptance gate 单测。

- 允许改：prompt 措辞（控制回合 / Critic / verify-on-stop）、阈值类 runtime control（`specAcceptanceByType` / `adaptiveSimpleThreshold` / `mindStateLoopThreshold`）、技能草稿文件、受限 middleware 模板。
- **禁止改**：权限预设、approval-delegate、L0-L3 硬规则、verify 闸门、GWT/FEP 通道——这些是安全边界，不是搜索空间。
- 每个候选**只改一个 surface**，结构化替换，改完必须 `node --check` + 30/30 门禁通过。
- 候选写到独立目录（`SELF_HARNESS_CANDIDATE_WORKSPACE` 模式），**不碰运行版**，用环境变量切换评测对象。
- 评测任务集扩到 ~24 个可验证任务（train 16 / heldout 8，2 repeats）；先测基线噪声 <10%，否则任何提升都不可信。

**验证**：同一 harness 跑两次的 pass-rate 方差 <10%；acceptance gate 单测覆盖 accept / reject / no-op 三个分支。

### P1 · 弱点挖掘接我们的 trace

从 `_trace.jsonl` + `_outcome.jsonl` 抽失败事件（`crit_hit` harmful、D1-D5 注入、`verify_on_stop`、`fep_cycle` 偏差、tool FAIL、Critic 拒收），用评估器给 `(terminal_cause, criticality, agent_mechanism)` 三元组，精确匹配聚类，产出 `evidence_bundle.json`。

**特有的一类**：`recovered_friction`——「上下文不堪但靠 harness 救回来」的案例（如监测插件会话的承接）。按论文源码的处理，它是**要保护的 passing behavior**，不是修复对象；写进 evidence bundle 的 protected 段。

**验证**：拿监测插件会话的真实 trace 离线跑一遍，看重复探测 / 路径解析 / 权限等待是否被分到不同 cluster。

### P2 · 最小闭环（先由 WorkBuddy 离线跑通协议）

本地 35B 作 proposer，`route-count=4`、单 surface 最小改动、strict JSON 且允许 `decline`。候选跑评测台，acceptance gate 按「任一 split 不退化且至少一个提升」判定。通过的先生成 patch + **人工确认后部署**——这道人确认先保留，稳定后再讨论自动写回（ADR-0015 的审批原则不外推到 harness 自身）。

**验证**：人为注入一个已知弱点（例如临时关闭 `verifyOnStopEnabled`），看闭环能否重新发现并提一个恢复它的候选。

### P3 · 常态化（可选，需 P0-P2 验收后才启动）

与 `learn_watcher` 合并成旁路夜间循环；accepted edit 沉淀成 CritBank 条目或技能草稿；监控 held-in/held-out 曲线、接受率、每轮成本。

## 四、边界与成本

- **不跳步**：论文成功前提是 bounded surfaces + 强 evaluator + 双 split；我们的 evaluator 比它弱，P0 不扎实则后面全是噪声。
- **两步走**：先 Meta-Harness（我离线跑通协议）→ 再 Self-Harness（35B 自己当 proposer）。直接跳第二步，35B 大概率只产出 decline 或垃圾改动。
- **成本**：本地 27 t/s、单任务 1-3 分钟；24 任务 × 2 repeats ×（基线+候选）≈ 96 次运行、2-4 小时/轮。原型先用 8+4 任务，跑通再扩。
- **噪声防线**：单次结果 ±10%，必须 ≥2 repeats；heldout 定期轮换防止被优化过拟合。
- **decline 是合法结果**：35B 若判断无安全可复用改动，返回 decline 不算失败。

## 五、与现有机制的关系

- 是短期①「技能自进化闭环」的**实现路径**，不新增并列目标。
- 给中期「情景检索」提供 evidence bundle（检索对象从散落 trace 升级为结构化失败模式）。
- 与 FEP 分工：FEP 做单步「预期→观察→偏差」，Self-Harness 做跨步「偏差聚类→改 harness→双 split 验证」。
- 学习信号仍只进 trace / 学习队列，**不占运行时注入通道**（ADR-0017 红线不变）。

相关：[ROADMAP](../ROADMAP.md) · [ADR-0017](../decisions/0017-gwt-first-then-fep.md) · [ADR-0018](../decisions/0018-self-harness-two-stage.md) · [MIND_GAPS_RESEARCH](MIND_GAPS_RESEARCH.md)
