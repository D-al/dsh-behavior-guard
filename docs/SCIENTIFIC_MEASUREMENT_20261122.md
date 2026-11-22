# 科学测量方法论：STRATEGY 六项能力指标基线（2026-11-22）

> 用户问："测量的时候要有科学依据"，并指出"还有推卡的时候产生的会话"。
> 这两点都直接改变了测量方案。

## 一、方法论依据（调研确认）

### 1. GQM（Basili & Weiss 1984, IEEE TSE）
Goal（对象/目的/质量焦点/视角/上下文）→ Question → Metric → Data。
每个数据点必须可向上追溯到目标，**无目标归属的指标应退役**。
ISO/IEC 15939:2017 要求"判定分析结果有效性"；ISO 25010 给质量模型。

### 2. 构念效度（Cronbach & Meehl 1955）
代理指标 ≠ 目标构念本身。有效性需验证：
内容效度（覆盖构念域）、聚合/区分效度（MTMM）、效标关联、已知群体区分度。
**这是本轮最重要的一课**：我上一轮说的"可追溯率 29.7%"是
`evidence_log 字段比例`，而 STRATEGY 要的是"跨会话目标/决策/约束可追溯率"——
**代理指标，构念效度未验证**，不能当基线。

### 3. 统计严谨性
- 分布 > 点值：Wilson 95%CI（小样本比例，优于 Wald，k=0 时仍有效）
- 噪声地板：项目已实测 σ≈10%；RCI = 1.96·SEM·√2
- 样本量 `n ≥ 2(zσ/δ)²`：σ=10%、检测 10% 变化需 n≥16
- 回归均值 E[复测]=μ+r(x−μ)：r=0.6、观测 25 → 复测期望 35（+10 纯回归假增益）
- Simpson 悖论：分层与合并趋势可反向 → 必须分层报告

### 4. Goodhart / Campbell
指标越用于决策越被腐蚀。对策：指标多样、隐藏集、与奖惩脱钩、过程优于输出。

### 5. 测基线的依据（出处订正）
"If you can't measure it, you can't improve it" **在 Drucker 著作中查无实据**，
源出 Lord Kelvin 1883 ICE 演讲（Thomson 1889 p.73）；
Deming《The New Economics》1993 斥严格版为 "a costly myth"。
无基线即无效应量、无法做功效分析。

## 二、用户指出的关键修正：推卡会话必须分层

用户："还有推卡的时候产生的会话"——完全正确。

实测 8 个 sid：
| 层 | sid | 数量 | 特征 |
|---|---|---|---|
| synthetic | s1 | 1（9600条）| 单测假数据，必须隔离 |
| **probe** | **budget-3 / budget-4** | **2（各360条）** | **推卡探针：只有 tool_call/injection_hit/tool_result，无高级证据** |
| task | f429de9d / f56ec374 / 16ebf7b1 / 7d712f92 / s2 | 5 | 真实任务会话，有 review/evidence/control |

**如果混在一起算**：probe 会话的 0 证据会稀释分母 → 系统性低估（典型 Simpson 风险）。
测量器只在 **task 层**计算能力指标。

## 三、科学基线实测结果（`tools/baseline_metrics.py`）

| 指标 | 状态 | 实测 | 95%CI | 判断 |
|---|---|---|---|---|
| G1 同一性连续性 | **PROXY_ONLY** | evidence_cited=3 / 5会话 | [0.231, 0.882] | 代理指标，构念效度未验证 |
| G2 连续性执行 | **NOT_INSTRUMENTED** | compaction=0 | — | 没埋点，不是分为0 |
| G3 目标自生成 | **NOT_INSTRUMENTED** | goal_proposal=0 | — | 没埋点 |
| G4 价值校准 | **PROXY_ONLY** | crit_hit=4 / 5会话 | [0.376, 0.964] | 命中≠失败率下降，需对照 |
| G5 经验进化 | **NOT_INSTRUMENTED** | delta_rule=0 | — | 没埋点 |
| G6 开放环境适应 | **PROXY_ONLY** | gate_created=0 | — | git有记录但无法区分触发原因 |

**结论：可测 0 / 代理 3 / 未埋点 3 —— 当前不具备科学测基线条件。**
样本量 task=5 < 16，只能检测 >12.4% 的相对变化；G1 的 CI 宽 0.65，几乎没有信息量。

## 四、核心诚实原则（写入工具，不可违背）

1. ★ 不把"测不了"伪装成"测出来很低"
2. ★ 不把"代理指标"伪装成"目标构念本身"
3. ★ 单点数值必须带置信区间和样本量警告
4. ★ 每项标注 MEASURABLE / PROXY_ONLY / NOT_INSTRUMENTED
5. ★ 按会话类型分层报告（synthetic/probe/task）

## 五、自证（防"假精确"）
- 未埋点指标正确标 `NOT_INSTRUMENTED`（3项）而非给出假分数
- 分层正确：probe=2、synthetic=1、task=5（断言验证）
- G1 代理指标 CI 宽度 0.65（诚实暴露不确定性，不假装精确）
→ 三项自证通过

## 六、下一步（基于测量的科学判断）
不是"优化代理指标"，而是：
1. **给 NOT_INSTRUMENTED 的三项埋点**（compaction / goal_proposal / delta_rule）
2. **验证代理指标的构念效度**：人工抽样对齐 evidence_cited 与真实可追溯性（一致性 80-85% 才采信）
3. **凑够样本量**：≥16 个 task 会话才能检测 10% 变化
4. **建立 hold-out 对照**（G4 因果测量必需）

## 七、出处
Basili & Weiss 1984（GQM）；ISO/IEC 15939:2017；ISO 25010:2023；
Cronbach & Meehl 1955（构念效度）；Wilson 1927（CI）；
Goodhart 1975 / Campbell 1976 / Manheim-Garrabrant 五型；
Campbell & Stanley 1963（前后测八威胁）；Lord Kelvin 1883 ICE；
Deming 1993；KTH arXiv:2602.07150（pass@1 波动 2.2-6.0pp）。
