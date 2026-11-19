# 文档地图

> 按 **Diátaxis** 四分法组织：教程（怎么入门）→ 操作指南（怎么做事）→ 参考（是什么）→ 解释（为什么）。
> 再加两类本项目特有：**历史**（怎么走到这）和 **决策**（为什么这么定，不可变）。

## 一、入口层

| 文档 | 类型 | 职责 |
|---|---|---|
| [../README.md](../README.md) | 入口 | 定位 + 路线骨架 + 导航（薄，不放细节）|
| [../ROADMAP.md](../ROADMAP.md) | 参考/活文档 | 短中长期目标，每条带验证方法 |

## 二、操作层（怎么做事）

| 文档 | 类型 | 职责 |
|---|---|---|
| [MANUALS.md](MANUALS.md) | 操作指南集合 | 一键开箱 / 生产参数 / 工具速查 / 论文速查 / 升级 / 故障排查 / 心智拼图 |

## 三、参考层（是什么 / 为什么）

| 文档 | 类型 | 职责 |
|---|---|---|
| [MIND_GAPS_RESEARCH.md](MIND_GAPS_RESEARCH.md) | 解释 | 6 路广搜：心智还缺哪些拼图 |
| [SELF_HARNESS_PLAN.md](SELF_HARNESS_PLAN.md) | 方案 | harness 自进化四阶段（短期①实现路径，2026-11-19）|
| [GPU_ENGINE_GUARD.md](GPU_ENGINE_GUARD.md) | 操作 | 3D/Copy 引擎争抢诊断 + 主动降帧守护（2026-11-19）|
| [CADENCE_AUDIT.md](CADENCE_AUDIT.md) | 数据 | 自动化频次底稿：全部参数 + 5538 行 trace 真实触发数 |
| [CADENCE_REDESIGN.md](CADENCE_REDESIGN.md) | 解释 | 频次该怎么调：哪些不动、哪些改、社区依据 |
| [COMPACTION_AND_ROLES_DIAGNOSIS.md](COMPACTION_AND_ROLES_DIAGNOSIS.md) | 诊断 | 压缩触发/重复工作/角色可见性/过程折叠五问实证解答 |
| [HETEROGENEOUS_MODELS_EVALUATION.md](HETEROGENEOUS_MODELS_EVALUATION.md) | 评估 | 大小模型分工：判断类角色证伪 |
| [PERIPHERAL_MODELS_EVALUATION.md](PERIPHERAL_MODELS_EVALUATION.md) | 评估 | 超小模型当周围神经（感知/路由/反射）：方向成立 |
| [FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md](FEEDBACK_LOOP_AND_DISTILLATION_EVALUATION.md) | 评估 | 前馈误差放大/NSED/主模型弱点/学生蒸馏三问 |
| [S1_SELF_HARNESS_P0P1_RESULT.md](S1_SELF_HARNESS_P0P1_RESULT.md) | 结果 | Self-Harness P0-P2：白名单/门禁/35B 真提案 |
| [S4_ADAPTIVE_AB_RESULT.md](S4_ADAPTIVE_AB_RESULT.md) | 结果 | 自适应 A/B 实测：token 未降故不开 |
| [S7_SMALL_MODEL_BENCH_RESULT.md](S7_SMALL_MODEL_BENCH_RESULT.md) | 结果 | 0.6B CPU 基准：4-6s，不适合实时外设 |
| [ROADMAP_REBASELINE_20261119.md](ROADMAP_REBASELINE_20261119.md) | 规划 | 路线图重定基线：完成盘点 + 重分级依据 |
| [CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md](CLASSIFIERS_FOR_MIND_MODEL_EVALUATION.md) | 评估 | 10 类分类器扩展心智模型：可行性+挂载点 |
| [DEEP_MAINTENANCE_20261119.md](DEEP_MAINTENANCE_20261119.md) | 维护 | 深度 bug 审计：1 P0 + 7 P1 修复 |
| [COMPLETION_AUDIT_20261119.md](COMPLETION_AUDIT_20261119.md) | 维护 | 完成状态验收：3 缺口修复 + 真实会话验证 |
| [POPUP_CONSOLE_FIX_20261119.md](POPUP_CONSOLE_FIX_20261119.md) | 维护 | 周期性 cmd 弹窗根因与修复 |
| [DSH_SOURCE_AUDIT_20261119.md](DSH_SOURCE_AUDIT_20261119.md) | 评估 | dsh 开源源码核查：DSH_HOME/插件/卸载机制 |
| [DSH_PLATFORM_REPAIR_20261120.md](DSH_PLATFORM_REPAIR_20261120.md) | 维护 | 平台层整治：插件升级/会话依赖/junction |
| [REAL_TRACE_ACCEPTANCE_20261120.md](REAL_TRACE_ACCEPTANCE_20261120.md) | 验收 | 真实 trace 验收路线图承诺（排除 89% 单测假数据） |
| [BRAIN_PARITY.md](BRAIN_PARITY.md) | 解释 | 人脑功能分区覆盖度盘点（胼胝体/杏仁核等对应与空白）|
| [COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md) | 解释 | 社区对比：先进 / 落后 / 以为先进其实平凡 |
| [PEER_HARNESS_BENCHMARK.md](PEER_HARNESS_BENCHMARK.md) | 解释 | 同族 35B-A3B / dsh 生态 harness 逐项对标 + 可借鉴清单 |
| [MD_SYSTEM_PLAN.md](MD_SYSTEM_PLAN.md) | 解释 | 文档分层原则（三层体系：执行细节/知识沉淀/导航入口）|
| [PERIPHERAL_CAPABILITIES.md](PERIPHERAL_CAPABILITIES.md) | 解释 | MCP 等外围能力调研 |
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | 操作 | 新机制怎么用 |
| [BRAIN_AUDIT_20261118.md](BRAIN_AUDIT_20261118.md) | 解释 | 架构盘点与优化清单 |
| [MORNING_REPORT_20261118.md](MORNING_REPORT_20261118.md) | 历史 | 某次自主作业原始记录（保留，不删）|

## 四、历史层（怎么走到这）

| 文档 | 职责 |
|---|---|
| [history/README.md](history/README.md) | 历史说明书总览 + 阶段划分 |
| [history/TIMELINE.md](history/TIMELINE.md) | 按时间的可扫读里程碑 |
| [history/tuning/](history/tuning/README.md) | **调优专题**：硬件/引擎/采样/温度的决策链 |

## 五、决策层（为什么这么定，不可变）

| 文档 | 职责 |
|---|---|
| [../decisions/README.md](../decisions/README.md) | ADR 索引：按主题/状态列出全部决策 |

## 维护规则

1. **决策一旦 accepted 不改原文**——要改就写新 ADR 并 supersede 旧的
2. **历史只追加，不重写**——append-only 日志是本项目的铁律（KV cache 后缀税）
3. **README 保持薄**——超过 200 行就该把细节下沉到 docs/
4. **目标带验证方法**——ROADMAP 里每条都要能判定"做完了没"
