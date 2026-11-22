# DECision-Execute-Check-Correct 循环架构复盘（2026-11-22）

> 用户问：回顾"决策-执行-检查-纠正"循环，架构上是否完整？有何改进？
> 用户补充：这个问题问过，但现在情况不同了。
> 对照：docs/AUTONOMY_GAP_20261120.md（当时结论 L1，6 环节缺 3）

## 一、新旧对比（回答"现在不同了"）

| 环节 | 2026-11-20 评估 | 2026-11-22 现状 | 变化 |
|---|---|---|---|
| ① 读路线图选任务 | ❌ 完全缺失 | ❌ A2/A3 仍 backlog | **未变** |
| ② 自主执行 | ✅ 强 | ✅ S1/S17 done，工具面成熟 | 更强 |
| ③ 自主验证 | ✅ 已具备但没绑定路线图 | ✅✅ A1/A1_5/A6/A0 + 59 门禁 + 7 不变量 + 规则包钉住 | **质变**：检查环向上推了 3 层 |
| ④ 写回路线图 | ❌ 完全缺失 | ❌ A2 仍 backlog | **未变** |
| ⑤ 决定下一步 | 🟡 prompt 软反思 | 🟡 A4 仍 backlog；新增 STRAT1 ready | 微进 |
| ⑥ 常驻循环 | ❌ 自进化未启动 | ❌ A5 仍 backlog；但 LearnWatchDaemon 常驻（只学习不决策）| **未变** |

**结论：这两天的所有工作都集中在"检查环"（③），把它从"能验"做到"审计的审计 + 地基守护 + 权力分立"。
而①④⑤⑥四个决策/循环环节原地不动。架构从"L1"变成"检查环世界级、决策环 L1"的跛脚状态。**

## 二、社区调研：真正缺的是 Observe + Orient

DECC ↔ OODA 映射：D/E/C/C ≈ Decide/Act/Reflect，**Observe、Orient 被默认"已发生"**——这是最常见的结构性缺失。
Orient 是认知核心与主失败点（ Boyd 递归反馈中枢；n1n 2026）；Schneier & Raghavan（Berkman 2025-10）
指出"把现实压缩成模型可处理形式"是核心难题，压缩失真即错误与对抗注入入口。

### 完整性 checklist（6 项）
1. **Observe** 多源感知（选择性注意本身是推理）
2. **Orient** 显式信念状态 + 目标/约束对齐 ← **我们最该补**
3. **Decide** 候选生成 + 外部验证门（不让 LLM 自评计划）
4. **Execute** 受约束调用 + 审计 ← 已有
5. **Check / Correct** ← 已做透（本次全部工作）
6. **Meta / 常驻循环** 预算、终止条件、放弃/升级、漂移监控 ← backlog A4/A5

### 常见缺失
- Orient 隐式化（我们有零件但无硬判据）
- LLM 自验证代替外部校验：Kambhampati ICML 2024 约 1/10 计划可执行；ICLR 2024 无外部反馈时自纠反而变差
- 终止条件是事后补丁而非架构组件（Anthropic 2024-12 / Google Cloud 2025-11 共识）
- goal drift 长期无监测；Arike AIES 2025（arXiv:2505.02709）证实所有模型均漂移，长上下文下 pattern-matching 易感性正相关
- 混合架构层间仲裁/升级规则缺失（协调故障多于层内故障）

## 三、我们的 Orient 零件盘点（关键发现：不是没有，是"软"）

| 零件 | 位置 | 状态 | 缺口 |
|---|---|---|---|
| BDI 状态卡（goal/belief/preference） | index.mjs:560/874/944 `bdiEnabled` | 有 | 只在控制回合软注入，无一致性判据 |
| frame（role/goal/evidence/provenance/trust） | index.mjs:159/868 `frameEnabled` | 有 | 记录但不校验 goal 漂移 |
| mind_state（跨步重复中性注入） | index.mjs:179 | 有 | 中性事实，无决策路径 |
| intent_drift（意图漂移检测） | learn_watcher.py:219（每20轮） | 有 | 仅 append_feedback，不改行为、不阻断 |
| 控制回合 | 实测 trace 大量 | 有 | prompt 反思，代码无 abandon/skip 分支（A4）|

**精确判断：Orient 的"感知与记录"有，"对齐判定与决策输出"无——它是观测仪表盘，不是方向盘。**

## 四、架构完整度结论

**不完整，且是结构性偏科**：
- 检查/纠正环：✅ 世界级（多层 + 元验证 + 地基 + 权力边界）
- 执行环：✅ 强
- 决策环（Observe/Orient/Decide）：⚠️ 有零件无判据，A4/A5 backlog
- 循环闭合（写回/下一步/常驻）：❌ A2/A3/A5 backlog，靠人

**最值得补（按性价比）**：
1. **把 Orient 从软提示升级为硬判据**——goal 漂移检测：行为 vs 原目标一致性
   （`s.bdi.goal` / `s.frame.goal` / 当前 tool_calls 三者比对），漂移则触发 A4 式 meta_decision，
   不是只写日志
2. **元决策一等公民（A4）**——停/跳/换/升级人配阈值与预算，这是常驻循环不空转的关键
3. **执行前外部验证门**——计划由确定性规则校验（我们已有 in-toto 式思路，但没用在 plan 上）
4. **写回与选任务（A2/A3）**——最后拼图，但依赖 1-3 先立住，否则自动化了一个跛脚循环

## 五、诚实边界
- 这不是"推倒重来"——检查环的投入不浪费，它是任何自主循环的必备底座
- 但**继续加固检查环的边际收益已递减**（已经 7 层），下一份投入该转向 Orient + 元决策
- 社区共识：终止/升级是架构组件而非补丁；我们的 D5 门控是检查层的终止，不是循环层的

## 六、出处
docs/AUTONOMY_GAP_20261120.md（本地上次评估）；arXiv:2506.01839（OODA 综述 2025）；
arXiv:2505.02709（AIES 2025 目标漂移）；n1n Emergent Loop 2026-03；Schneier & Raghavan 2025-10；
Kambhampati ICML 2024 / ICLR 2024「LLMs Cannot Self-Correct」；Anthropic Building Effective Agents 2024-12；
Google Cloud 2025-11；Zenodo 17676269；PhilArchive CBA 2025-11。
