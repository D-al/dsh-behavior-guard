# 下一步优先级：科学依据（2026-11-22）

> 用户问："接下来我们要干什么（给出科学依据）"
> 这是整条对话链的收束：审计的审计 → 信任锚 → 三权分立 → TOC → 交付盘点 →
> 判据体检 → 系统性腐化 → 复杂度预算目标匹配 → 目的追溯制 → **现在：下一步**。

## 一、已确立的科学依据（前面各轮，不重复调研）

| 结论 | 依据 | 对下一步的含义 |
|---|---|---|
| 瓶颈在决策环，非检查环 | TOC + Amdahl：优化非瓶颈上限 1/(1-p) | 继续加检查边际≈0 |
| 系统处于"腐化前夜" | ratchet 10.3%、热点 71%、剧场 33:1 | 需要减法 + 有效性证伪 |
| 复杂度预算必须目标驱动 | Brooks 本质复杂度 / Ashby 必要多样性 | 按目的追溯，不按数字 |
| 目的追溯制已落地 | 111 机制全可追溯，orphan 0 | 治理骨架已立，可转向度量 |

## 二、本地盘点：排序的关键输入

### ready 队列（5 张）
| 卡 | risk | tier | 说明 |
|---|---|---|---|
| M10 会话生命周期治理（刹车）| low | 2 | 止损 |
| STRAT1 战略陈述（模型只读）| low | 0 | 已完成（STRATEGY.md 已存在，卡未同步）|
| S18 RRSI 正则化 | low | 1 | 防自改进过拟合 |
| S19 CritBank 校准门禁 | low | 1 | 价值校准 |
| S21 验证层去自审 | med | 1 | 质量压倒多样性 |

### 决策环 backlog（A2-A5）
- A2 写回（med）、A3 选任务（med）、A4 元决策（med）、A5 常驻闭环（high）
- **零件已有**（find_next/claim/apply/meta_decision），缺常驻串接（接 TOC 第 5 步）

### ★最重要的发现：战略目标未量化
STRATEGY.md §2.1 六项能力指标中 **4 项"未量化/无"**：
| 指标 | 目标 | 当前基线 | 真实证据 |
|---|---|---|---|
| 同一性连续性 | 可追溯率 ≥95% | **未量化** | evidence_cited **3 次**、compaction **0** |
| 连续性（执行）| 重做率下降 | 未量化 | 无 compaction 事件 |
| 目标自生成 | 采纳后推进 ≥20% | **无**（全外部输入）| shadow 提案 0 |
| 价值校准 | 重复失败率降 ≥30% | CritBank 有，未做对照 | — |

**排序信号**：系统建了大量机制，却不知道距离目标多远——**没有基线，任何优化都无法证伪**。
这符合"测量先行"原则（DORA / OKR 可证伪性：STRATEGY §2 自己就要求"外部证据可验证"）。

## 三、排序方法的科学依据（调研确认）

### 框架选型（单人项目）
| 框架 | 公式 | 判断 |
|---|---|---|
| **WSJF/CD3** | CoD / Duration；数学最优性=Smith rule(1956)最小化 Σw·C | ✅ **最适合**：单人无 Reach、无多干系人 |
| RICE | Reach×Impact×Confidence/Effort | ❌ 单人项目 Reach 无意义 |
| ICE | Impact×Confidence×Ease | ⚠ 粗排可以，无统一刻度 |
| Kano | 必备/期望/兴奋 | ❌ 需问卷 |
| MoSCoW | Must≤60%/Should20%/Could20% | ❌ 固定 deadline 多人定范围才适用 |

### ★核心判断：不是"大 vs 小"，是"是否作用于约束"
- **TOC 五步法**：Exploit（挖尽现有）排在 Elevate（提升产能）之前。
  A2-A5 是 Elevate；ready 小卡中作用于决策环的才是 Exploit。
- **WSJF 与 TOC 一致**：把 CoD 定义为"对系统吞吐（决策环）的影响"，
  非约束项 CoD≈0 → 自动沉底。两框架结论相同。
- 串行系统 T=minᵢ(cᵢ)，∂T/∂c(非瓶颈)=0——约束定义性结论（Goldratt）。
- **边界**：需求不足时提升内部资源无效；约束转移后回 Step1 重识别（Step5 防惯性）。

### 止血 vs 建设
- Google SRE error budget：预算耗尽→冻结新功能只做 P0；burn rate>1 预警。
- 债务的 CoD=已付利息+未来利息；债在约束上则利息高优先。
- 反方：一直修债耗尽创新令牌（McKinley Choose Boring Technology 3枚），
  需预留差异化投资比例。

### 停止条件
Simon satisficing：设抱负水平 α，达标即停。**"什么都不做"当且仅当**：
约束吞吐达标 + 误差预算充足 + 各项 CoD 低于启动阈值（边际收益<边际成本）。
防 treadmill：写清 Won't-have 清单、定期剪枝长期未启动卡。

## 四、最终排序：先测量，再挖约束（不是先建机制）

### ★决定性实测数据（本轮新发现）
- STRATEGY §2.1"可追溯率 ≥95%" **实测 11/37 = 29.7%**（有 evidence_log 的 done 卡）
- 真实 trace `evidence_cited` 仅 3 次、`compaction` **0 次**
- 6 项能力指标中 **4 项未量化/无基线**
- STRAT1 卡判据全过（STRATEGY.md 存在）但状态仍是 ready——账面与实物不同步

**按 STRATEGY §2 自己的原则（"每条标准必须外部证据可验证，不认模型自述"）：
当前系统的第一问题不是机制不够，是不知道自己离目标多远——没有基线，任何优化无法证伪。**

### WSJF 评分（CoD 定义为"对决策环吞吐的影响"）
| 事项 | 约束判定 | TOC步 | CoD | 工期 | 置信 | 决策 |
|---|---|---|---|---|---|---|
| **G1 可追溯率基线**（29.7% vs 95%）| 约束前置：测量 | 2 Exploit | 高（不测量则一切优化不可证伪）| 小 | 高 | **① 先做** |
| **A4 元决策接主循环**（模块已有未接线）| 核心约束 | 2 Exploit | 高 | 中 | 高 | **② 次做** |
| A2/A3 串常驻闭环 | 约束 | 4 Elevate | 高 | 大 | 中 | ③ 后做 |
| S18 RRSI 正则化 | guardrail 风险 | 3 Subordinate | 中（OOD≥0 是红线）| 小 | 高 | ④ 并行小卡 |
| S19 CritBank 校准 | 非约束 | — | 中低 | 小 | 中 | ⑤ Could |
| M10 会话刹车 | 止血（若卡死发生）| error budget | 视触发 | 小 | — | 条件触发 |
| S21 验证层去自审 | 非约束（检查环）| — | 低（Amdahl 上限）| 中 | — | 沉底/Won't |

### 结论（三层）
1. **先测量（Exploit 前置）**：把 STRATEGY 6 项能力指标算出真实基线，
   特别是可追溯率 29.7% vs 目标 95% 的 65pp 缺口——这是最大的已知差距。
2. **再挖约束（Exploit）**：A4 元决策器已写成模块但未接主循环——
   零成本接线即可让决策环工作，属 TOC 第2步"挖尽现有"。
3. **后提升（Elevate）**：A2/A3/A5 常驻闭环是大工程，放在基线和接线之后。

### 科学依据一句话
**TOC 的 Exploit 先于 Elevate + WSJF 把非约束项 CoD 归零 + Simon satisficing 的"达标即停"
→ 先测量出基线（可证伪），再零成本接通已有决策模块，最后才上大工程。
不是"先做小卡"，是"先做作用于约束且能改变决策的事"。**

## 五、出处
Goldratt《The Goal》1984 TOC 五步；Reinertsen《Principles of Product Development Flow》WSJF；
Smith 1956 调度最优性；SAFe WSJF；Google SRE error budget/burn rate；
Simon《Administrative Behavior》satisficing；McKinley《Choose Boring Technology》创新令牌；
本地：STRATEGY.md §2（自身要求外部证据可验证）、DECC_ARCHITECTURE_REVIEW、FIRST_PRINCIPLES_GOVERNANCE、SYSTEMIC_DECAY_ASSESSMENT、COMPLEXITY_BUDGET_GOAL_ALIGNED。
