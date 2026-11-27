# 文档地图

> 按 **Diátaxis** 四分法组织：教程（怎么入门）→ 操作指南（怎么做事）→ 参考（是什么）→ 解释（为什么）。
> 再加两类本项目特有：**历史**（怎么走到这）和 **决策**（为什么这么定，不可变）。

## 一、入口层

| 文档 | 类型 | 职责 |
|---|---|---|
| **[../AGENT_BRIEF.md](../AGENT_BRIEF.md)** | **⭐唯一必读** | **11.3KB 决策速查：生产配置/16铁律/已证伪/优先级/已落地机制。读完它才按需读下面这些** |
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
| [OPTIMIZATION_BACKLOG_20261125.md](OPTIMIZATION_BACKLOG_20261125.md) | **活文档/待办** | **优化方向 total backlog：四组深挖的已证伪/未验证/待95%验证方向 + 优先级总表** |
| [MISTAKE_BOOK_RESEARCH_20261127.md](MISTAKE_BOOK_RESEARCH_20261127.md) | 调研/设计 | **错题本可行性：Reflexion/ExpeL/ACE/ReasoningBank 论文实证 + 社区实现 + 项目 60% 骨架 + 可插拔可纠错设计 + P0-P5 落地路径** |
| [REFLECTION_RECALL_GAP_20261127.md](REFLECTION_RECALL_GAP_20261127.md) | 诊断/设计 | **主动反思回忆缺口：代码级证明 12 项机制全被动、工具注册 0 处、反思产物被丢弃；三条补位路线与反面证据** |
| [MIND_GAPS_AND_TRUST_20261122.md](MIND_GAPS_AND_TRUST_20261122.md) | 解释 | 6 路广搜：心智还缺哪些拼图 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 方案 | harness 自进化四阶段（短期①实现路径，2026-11-19）|
| [GPU_ENGINE_GUARD.md](GPU_ENGINE_GUARD.md) | 操作 | 3D/Copy 引擎争抢诊断 + 主动降帧守护（2026-11-19）|
| [COMPACTION_CONTEXT_CADENCE_20261120.md](COMPACTION_CONTEXT_CADENCE_20261120.md) | 数据 | 自动化频次底稿：全部参数 + 5538 行 trace 真实触发数 |
| [COMPACTION_CONTEXT_CADENCE_20261120.md](COMPACTION_CONTEXT_CADENCE_20261120.md) | 解释 | 频次该怎么调：哪些不动、哪些改、社区依据 |
| [COMPACTION_CONTEXT_CADENCE_20261120.md](COMPACTION_CONTEXT_CADENCE_20261120.md) | 诊断 | 压缩触发/重复工作/角色可见性/过程折叠五问实证解答 |
| [MIND_MODEL_CAPABILITY_EVAL_20261121.md](MIND_MODEL_CAPABILITY_EVAL_20261121.md) | 评估 | 大小模型分工：判断类角色证伪 |
| [MIND_MODEL_CAPABILITY_EVAL_20261121.md](MIND_MODEL_CAPABILITY_EVAL_20261121.md) | 评估 | 超小模型当周围神经（感知/路由/反射）：方向成立 |
| [MIND_MODEL_CAPABILITY_EVAL_20261121.md](MIND_MODEL_CAPABILITY_EVAL_20261121.md) | 评估 | 前馈误差放大/NSED/主模型弱点/学生蒸馏三问 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 结果 | Self-Harness P0-P2：白名单/门禁/35B 真提案 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 结果 | 自适应 A/B 实测：token 未降故不开 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 结果 | 0.6B CPU 基准：4-6s，不适合实时外设 |
| [ROADMAP_EVOLUTION_20261120.md](ROADMAP_EVOLUTION_20261120.md) | 规划 | 路线图重定基线：完成盘点 + 重分级依据 |
| [CLASSIFIER_BENCH_SERIES_20261121.md](CLASSIFIER_BENCH_SERIES_20261121.md) | 评估 | 10 类分类器扩展心智模型：可行性+挂载点 |
| [CLASSIFIER_BENCH_SERIES_20261121.md](CLASSIFIER_BENCH_SERIES_20261121.md) | 协议 | 评测三铁律+E核绑定实证 |
| [CLASSIFIER_BENCH_SERIES_20261121.md](CLASSIFIER_BENCH_SERIES_20261121.md) | 结果 | 5候选实测：Horizon胜出93.3%/2.3%/102ms；版本+内存坑 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 维护 | 深度 bug 审计：1 P0 + 7 P1 修复 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 维护 | 完成状态验收：3 缺口修复 + 真实会话验证 |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | 维护 | 周期性 cmd 弹窗根因与修复 |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | 评估 | dsh 开源源码核查：DSH_HOME/插件/卸载机制 |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | 维护 | 平台层整治：插件升级/会话依赖/junction |
| [CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md](CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md) | 验收 | 真实 trace 验收路线图承诺（排除 89% 单测假数据） |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | 复盘/铁律 | 本次平台整治事故的 12 条可复用经验（证据分层/三副本/被证伪方向） |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | 源码核查 | dsh 默认工作区路径：documentsDirectory 正规配置 + 会话归属机制纠错 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 盘点 | 三层长期记忆→心智模型可迁移资产（含硬件可实现性）|
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 评估 | 心智模型"学会自己走路"现状 L1 与三级差距 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 模式/铁律 | 函数外置四段式：默认 import 转发（禁正则/整文件重建/手写转义）+ 反向检验铁律 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 维护/验收 | 反向检验深度维护：时间线错位总根因 + 四卡真完成 + S15 假生效 + 8 项修复 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 战略/源头 | 77轮战略会话完整通读：五阶段演进 + 我们路线缺战略陈述/元治理锁 + 6条启发 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 战略/调研 | 广泛调研定位：我们在harness递归自改进路线B；RRSI正则/Self-MoA质量>多样性/最高杠杆排序 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 架构/实证 | 同会话抗污染：两卡连推实验(第二张更顺)+污染真形态=未折叠噪声+分阶段边界标记方案 |
| [DEPENDENCY_UNLOCK_AUDIT_20261121.md](DEPENDENCY_UNLOCK_AUDIT_20261121.md) | 路线图/审计 | deps与unlocks一致性：8处显式解锁5一致3软解锁;灰实线硬依赖+紫虚线逻辑解锁 |
| [TECH_TREE_CLEANLINESS_20261121.md](TECH_TREE_CLEANLINESS_20261121.md) | 设计原则 | 科技树清爽化：只有阻塞关系才画线;闸门默认隐藏留角标;软关联按需开启;86M五卡处理 |
| [CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md](CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md) | 设计原则 | 闸门证据标准：需拍板≠空泛,数据支撑型闸门必须有data_gates;M5工具拍板实例+tool_audit修复 |
| [PIPELINE_AND_INFRA_BRIDGE_20261120.md](PIPELINE_AND_INFRA_BRIDGE_20261120.md) | 架构决策 | 人读版路线图下线：12条不做迁LADDER.rejected,三副本变两权威一视图 |
| [TECH_TREE_CLEANLINESS_20261121.md](TECH_TREE_CLEANLINESS_20261121.md) | 设计原则 | 科技树清爽化：只有阻塞关系才画线;闸门默认隐藏留角标;软关联按需开启;86M五卡处理 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 方案 | **学会自己走路 6 阶执行阶梯**（用现有器官逐步自主化）|
| [GROWTH_CARD_DESIGN_20261120.md](GROWTH_CARD_DESIGN_20261120.md) | 设计 | 能力阶梯成长卡片：what/why/解锁/好处/代价/坑/反思 |
| [FUTURE_CLAIM_AND_CONSISTENCY_20261120.md](FUTURE_CLAIM_AND_CONSISTENCY_20261120.md) | 事故自审 | GitHub/权威/生产一致性 verdict + 守卫机制 + agent 教训 |
| [GUARD_MANIFEST.yaml](../config/GUARD_MANIFEST.yaml) + `tools/consistency_guard.py` | 工具 | 三处一致性守卫（清单驱动、零 LLM、CRLF 归一化）|
| [BRAIN_PARITY.md](BRAIN_PARITY.md) | 解释 | 人脑功能分区覆盖度盘点（胼胝体/杏仁核等对应与空白）|
| [MIND_GAPS_AND_TRUST_20261122.md](MIND_GAPS_AND_TRUST_20261122.md) | 解释 | 社区对比：先进 / 落后 / 以为先进其实平凡 |
| [MIND_MODEL_CAPABILITY_EVAL_20261121.md](MIND_MODEL_CAPABILITY_EVAL_20261121.md) | 解释 | 同族 35B-A3B / dsh 生态 harness 逐项对标 + 可借鉴清单 |
| [MD_SYSTEM_PLAN.md](MD_SYSTEM_PLAN.md) | 解释 | 文档分层原则（三层体系：执行细节/知识沉淀/导航入口）|
| [MIND_MODEL_CAPABILITY_EVAL_20261121.md](MIND_MODEL_CAPABILITY_EVAL_20261121.md) | 解释 | MCP 等外围能力调研 |
| [USAGE_GUIDE.md](USAGE_GUIDE.md) | 操作 | 新机制怎么用 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 解释 | 架构盘点与优化清单 |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | 历史 | 某次自主作业原始记录（保留，不删）|

## 四、历史层（怎么走到这）

| 文档 | 职责 |
|---|---|
| [history/README.md](history/README.md) | 历史说明书总览 + 阶段划分 |
| [history/TIMELINE.md](history/TIMELINE.md) | 按时间的可扫读里程碑 |
| [history/tuning/](history/tuning/README.md) | **调优专题**：硬件/引擎/采样/温度的决策链 |

## 五、专题合并卷（2026-11-25 报告整理）

> 原 136 份主题关联报告已合并为 21 卷；原文件均已删除（可经 git tag `pre-md-consolidation-20261125` 追溯）。

| 卷 | 内容 |
|---|---|
| [PIPELINE_AND_INFRA_BRIDGE_20261120.md](PIPELINE_AND_INFRA_BRIDGE_20261120.md) | 从思考链依赖到落地桥接，再到下一步：IDE 落地机制的完整链条 |
| [GOAL_STATEMENT_EVOLUTION_20261122.md](GOAL_STATEMENT_EVOLUTION_20261122.md) | V2.1→V3→V3.1→最终版，及伴随的落地规划/质量评审/路线重绘 |
| [WALK_EXPERIMENT_SERIES_20261120.md](WALK_EXPERIMENT_SERIES_20261120.md) | 基线 + A1/A3.5/M1/M8 五张卡 + 三份反思，完整实验轨迹 |
| [AUTONOMY_AND_SELF_HARNESS_20261122.md](AUTONOMY_AND_SELF_HARNESS_20261122.md) | 自主化路线/差距/阶段规划与 Self-Harness P0-P2 实证 |
| [CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md](CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md) | 引用审计协议+结果、证据分层标准、闸门证据标准 |
| [COMPACTION_CONTEXT_CADENCE_20261120.md](COMPACTION_CONTEXT_CADENCE_20261120.md) | 压缩与角色诊断、频次审计与重设计、MECHANISM_TRIGGER_AUDIT |
| [FUTURE_CLAIM_AND_CONSISTENCY_20261120.md](FUTURE_CLAIM_AND_CONSISTENCY_20261120.md) | FUTURE_CLAIM_GUARD 设计+分析、一致性设计与裁决、DIAGNOSIS_CORRECTION、GAP_REVIEW |
| [S6_DECISION_WIRE_SERIES_20261122.md](S6_DECISION_WIRE_SERIES_20261122.md) | S6 模型证据审计→真实测试→延迟根因→下侧评估 |
| [S24_VERIFY_LOOP_SERIES_20261122.md](S24_VERIFY_LOOP_SERIES_20261122.md) | 验证/读取回路设计与复测修复 |
| [SKILLS_AB_SERIES_20261122.md](SKILLS_AB_SERIES_20261122.md) | 首轮 A/B 与受控复测 |
| [CLASSIFIER_BENCH_SERIES_20261121.md](CLASSIFIER_BENCH_SERIES_20261121.md) | 评测协议、V3/V4 基线、最终基准、生态调研 |
| [MIND_MODEL_CAPABILITY_EVAL_20261121.md](MIND_MODEL_CAPABILITY_EVAL_20261121.md) | 异构/外设/反馈蒸馏三类评估与科学测量 |
| [MIND_GAPS_AND_TRUST_20261122.md](MIND_GAPS_AND_TRUST_20261122.md) | MIND_GAPS 广搜、六路线调研、信任锚、竞争分析 |
| [MEMORY_AND_REFACTOR_20261120.md](MEMORY_AND_REFACTOR_20261120.md) | 三层记忆→心智模型、重构模式、深度维护两版、完成审计 |
| [PLATFORM_REPAIR_20261120.md](PLATFORM_REPAIR_20261120.md) | dsh 源码核查、平台层修复、弹窗修复、铁律复盘 |
| [ROADMAP_EVOLUTION_20261120.md](ROADMAP_EVOLUTION_20261120.md) | 重定基线→重绘→拆分分析→拆分完成 |
| [ENGINE_V1_RESEARCH_20261123.md](ENGINE_V1_RESEARCH_20261123.md) | v1.0 发布调研→升级部署→性能实测 |
| [ENGINE_OPT_CORE_20261123.md](ENGINE_OPT_CORE_20261123.md) | MoE 卸载优化、缓存与精度、混合精度专家质量 |
| [ENGINE_OPT_DEEP_20261123.md](ENGINE_OPT_DEEP_20261123.md) | Q4_K 预取、源码级优化、显存剖析、mmproj Q8 发现 |
| [ENGINE_OPT_VERIFY_20261124.md](ENGINE_OPT_VERIFY_20261124.md) | 流水线研究/带宽修正→理论极限→MTP/上下文→FA/DFlash→视觉/缓存 |
| [LEVERS_AND_BROAD_RESEARCH_20261124.md](LEVERS_AND_BROAD_RESEARCH_20261124.md) | BFCL 基线→杠杆落地计划→上线清单→广搜（本轮调研入口） |


## 六、决策层（为什么这么定，不可变）

| 文档 | 职责 |
|---|---|
| [../decisions/README.md](../decisions/README.md) | ADR 索引：按主题/状态列出全部决策 |

## 维护规则

1. **决策一旦 accepted 不改原文**——要改就写新 ADR 并 supersede 旧的
2. **历史只追加，不重写**——append-only 日志是本项目的铁律（KV cache 后缀税）
3. **README 保持薄**——超过 200 行就该把细节下沉到 docs/
4. **目标带验证方法**——ROADMAP 里每条都要能判定"做完了没"
