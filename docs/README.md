# 文档地图

> 按 **Diátaxis** 四分法组织：教程（怎么入门）→ 操作指南（怎么做事）→ 参考（是什么）→ 解释（为什么）。
> 再加两类本项目特有：**历史**（怎么走到这）和 **决策**（为什么这么定，不可变）。

## 一、入口层

| 文档 | 类型 | 职责 |
|---|---|---|
| [../README.md](../README.md) | 入口 | 定位 + 路线骨架 + 导航（薄，不放细节）|
| [../TECH_TREE.html](../TECH_TREE.html) | 活视图 | 交互科技树：依赖/完成/ROI/上下游高亮 |
| [../ROADMAP_GRAPH.md](../ROADMAP_GRAPH.md) | 机器权威 | 状态/依赖/preconditions |

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
| [CLASSIFIER_EVAL_PROTOCOL_20261121.md](CLASSIFIER_EVAL_PROTOCOL_20261121.md) | 协议 | 评测三铁律+E核绑定实证 |
| [CLASSIFIER_BENCH_FINAL_20261121.md](CLASSIFIER_BENCH_FINAL_20261121.md) | 结果 | 5候选实测：Horizon胜出93.3%/2.3%/102ms；版本+内存坑 |
| [DEEP_MAINTENANCE_20261119.md](DEEP_MAINTENANCE_20261119.md) | 维护 | 深度 bug 审计：1 P0 + 7 P1 修复 |
| [COMPLETION_AUDIT_20261119.md](COMPLETION_AUDIT_20261119.md) | 维护 | 完成状态验收：3 缺口修复 + 真实会话验证 |
| [POPUP_CONSOLE_FIX_20261119.md](POPUP_CONSOLE_FIX_20261119.md) | 维护 | 周期性 cmd 弹窗根因与修复 |
| [DSH_SOURCE_AUDIT_20261119.md](DSH_SOURCE_AUDIT_20261119.md) | 评估 | dsh 开源源码核查：DSH_HOME/插件/卸载机制 |
| [DSH_PLATFORM_REPAIR_20261120.md](DSH_PLATFORM_REPAIR_20261120.md) | 维护 | 平台层整治：插件升级/会话依赖/junction |
| [REAL_TRACE_ACCEPTANCE_20261120.md](REAL_TRACE_ACCEPTANCE_20261120.md) | 验收 | 真实 trace 验收路线图承诺（排除 89% 单测假数据） |
| [POSTMORTEM_20261120.md](POSTMORTEM_20261120.md) | 复盘/铁律 | 本次平台整治事故的 12 条可复用经验（证据分层/三副本/被证伪方向） |
| [WORKSPACE_PATH_AUDIT_20261120.md](WORKSPACE_PATH_AUDIT_20261120.md) | 源码核查 | dsh 默认工作区路径：documentsDirectory 正规配置 + 会话归属机制纠错 |
| [MEMORY_TO_MIND_MODEL_20261120.md](MEMORY_TO_MIND_MODEL_20261120.md) | 盘点 | 三层长期记忆→心智模型可迁移资产（含硬件可实现性）|
| [AUTONOMY_GAP_20261120.md](AUTONOMY_GAP_20261120.md) | 评估 | 心智模型"学会自己走路"现状 L1 与三级差距 |
| [REFACTOR_PATTERN_20261121.md](REFACTOR_PATTERN_20261121.md) | 模式/铁律 | 函数外置四段式：默认 import 转发（禁正则/整文件重建/手写转义）+ 反向检验铁律 |
| [DEEP_MAINTENANCE_20261121.md](DEEP_MAINTENANCE_20261121.md) | 维护/验收 | 反向检验深度维护：时间线错位总根因 + 四卡真完成 + S15 假生效 + 8 项修复 |
| [STRATEGIC_SESSION_ANALYSIS_20261121.md](STRATEGIC_SESSION_ANALYSIS_20261121.md) | 战略/源头 | 77轮战略会话完整通读：五阶段演进 + 我们路线缺战略陈述/元治理锁 + 6条启发 |
| [ROUTE_POSITION_AND_EVOLUTION_20261121.md](ROUTE_POSITION_AND_EVOLUTION_20261121.md) | 战略/调研 | 广泛调研定位：我们在harness递归自改进路线B；RRSI正则/Self-MoA质量>多样性/最高杠杆排序 |
| [SINGLE_SESSION_ANTI_POLLUTION_20261121.md](SINGLE_SESSION_ANTI_POLLUTION_20261121.md) | 架构/实证 | 同会话抗污染：两卡连推实验(第二张更顺)+污染真形态=未折叠噪声+分阶段边界标记方案 |
| [DEPENDENCY_UNLOCK_AUDIT_20261121.md](DEPENDENCY_UNLOCK_AUDIT_20261121.md) | 路线图/审计 | deps与unlocks一致性：8处显式解锁5一致3软解锁;灰实线硬依赖+紫虚线逻辑解锁 |
| [TECH_TREE_CLEANLINESS_20261121.md](TECH_TREE_CLEANLINESS_20261121.md) | 设计原则 | 科技树清爽化：只有阻塞关系才画线;闸门默认隐藏留角标;软关联按需开启;86M五卡处理 |
| [GATE_EVIDENCE_STANDARD_20261121.md](GATE_EVIDENCE_STANDARD_20261121.md) | 设计原则 | 闸门证据标准：需拍板≠空泛,数据支撑型闸门必须有data_gates;M5工具拍板实例+tool_audit修复 |
| [HUMAN_VIEW_RETIRED_20261121.md](HUMAN_VIEW_RETIRED_20261121.md) | 架构决策 | 人读版路线图下线：12条不做迁LADDER.rejected,三副本变两权威一视图 |
| [TECH_TREE_CLEANLINESS_20261121.md](TECH_TREE_CLEANLINESS_20261121.md) | 设计原则 | 科技树清爽化：只有阻塞关系才画线;闸门默认隐藏留角标;软关联按需开启;86M五卡处理 |
| [WALKING_PLAN_20261120.md](WALKING_PLAN_20261120.md) | 方案 | **学会自己走路 6 阶执行阶梯**（用现有器官逐步自主化）|
| [GROWTH_CARD_DESIGN_20261120.md](GROWTH_CARD_DESIGN_20261120.md) | 设计 | 能力阶梯成长卡片：what/why/解锁/好处/代价/坑/反思 |
| [CONSISTENCY_VERDICT_20261120.md](CONSISTENCY_VERDICT_20261120.md) | 事故自审 | GitHub/权威/生产一致性 verdict + 守卫机制 + agent 教训 |
| [GUARD_MANIFEST.yaml](../config/GUARD_MANIFEST.yaml) + `tools/consistency_guard.py` | 工具 | 三处一致性守卫（清单驱动、零 LLM、CRLF 归一化）|
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
| [QWEN36_35B_WEAKNESSES_20261122.md](QWEN36_35B_WEAKNESSES_20261122.md) | 调研 | 35B-A3B弱点:单次工具调用不弱(UD-Q4_K_XL保98.8%)/弱在长链路;分类器不能补工具能力;排查优先级 |
| [CRITIC_GATE_FEASIBILITY_20261122.md](CRITIC_GATE_FEASIBILITY_20261122.md) | 验证 | Critic卸载到分类器不可行:历史35次Critic全PARSE_FAIL且无产物文本;假数据坑(ms:0);扩展样本召回0/8 |
| [TOOL_SURFACE_EVIDENCE_20261122.md](TOOL_SURFACE_EVIDENCE_20261122.md) | 证据 | 全量37会话1959调用/17工具;前7占95.7%;低频≠可砍;zstd多帧与bridge cursor坑 |
| [AUTOCARD_POSTMORTEM_20261122.md](AUTOCARD_POSTMORTEM_20261122.md) | 复盘 | 两轮自动推卡的9个阻碍+5个盲区;门禁覆盖仅8%(12个py测试1个在门禁);8类教训科技树覆盖审计(0全/5部分/3空白);A6加固卡建议 |
| [VERIFICATION_SOP_AND_BEHAVIOR_ASSERTIONS.md](VERIFICATION_SOP_AND_BEHAVIOR_ASSERTIONS.md) | 规范 | A6判据4/5:独立核验四步(门禁/判据/sha/git真验)+行为断言三级(强调用/弱grep/伪MockState重写)+退出码真实 |
| [FOUNDATION_GUARD_DESIGN_20261122.md](FOUNDATION_GUARD_DESIGN_20261122.md) | 设计 | 地基自动维护:社区调研(适应度函数/元测试/RRSI/持续验证/error budget)+6条不变量+Foundation Guard编排;58/58;挂LearnWatchDaemon每10min巡检 |
