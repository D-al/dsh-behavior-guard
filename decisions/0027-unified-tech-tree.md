# ADR-0027：科技树统一视图——根系骨架 + 器官分支 + 目标归属

- 状态：accepted
- 日期：2026-11-22
- 决策者：用户（显式批准："按层级和按KR视图都太乱了…重绘科技树，让它成为一张真正的科技树"；"速度/交互卡也算体系智能"；"决定走A"）
- 决策层级：重要决策 I（信息架构，不改变判据）
- 支撑决策：ADR-0023（双轴）、ADR-0024（三层归一）、ADR-0026（KR1阈值16）

## Context（背景）
科技树先按 tier（层级）组织，后加 KR 视图，用户反馈"两个视图都太乱"——根因是
**tier/category/KR 是三套互不相干的扁平标签**，每套只显示一个切面，且缺"这卡在体系里扮演什么角色"的纵轴。
用户进一步指出：
- 改善交互体验/速度的卡（想得快、不被无关因素卡住）**也是体系智能**——它们应进树
- 卡有"组装那个脑时提出"vs"优化脑时提出"的区别——谱系来源应可见

核实发现：调优期（第2层，性能/显存/解码）**根本不在科技树里**——只在 `docs/history/tuning/` 谱系叙事中。

## Options
| 方案 | 做法 | 结论 |
|---|---|---|
| A 加个分类字段 | 现有视图上加标签/筛选 | ❌ 用户明确说"太乱"——没解决结构问题 |
| B 只把速度卡归evolution_path | 小改KR映射 | ❌ 调优层证据仍不在树里 |
| C 统一视图（选中）| 根系骨架+器官分支+KR归属+状态,调优节点入树 | ✅ 一张树回答四个问题 |

## Decision
1. **四正交坐标**替代三套扁平标签：
   - `root_stage` 根系（谱系阶段）：tuning→assembly→optimization→governance→evolution
   - `organ` 器官（功能角色）：foundation/perception/memory/reasoning/action/validation/guardrail/evolution
   - `kr` 目标归属：KR1-6 / evolution_path / null
   - `status` 状态：done/ready/backlog/rejected + KR判据状态
2. **统一视图**：根系为列（纵向依赖骨架），列内按器官分组（带小标题），节点显示器官配色 +
   KR 归属徽章 + 状态。旧 tier/KR 视图保留可切换（三态按钮）。
3. **调优期入树**：从 `docs/history/tuning/DECISIONS.md` 提取 14 个决策节点（TUNE-01~14，
   带真实证据与铁律）作为 tuning 根系。用户判断"想得快/不被卡住也是智能"纳入——
   TUNE-05 温度0.7→KR2，TUNE-07 CTX_CHECKPOINTS→KR4，其余 null。
4. **73 张卡标注** root_stage/organ（子任务语义映射+人工审核 8 张边界卡）。
   **谱系阶段按"何时为何造"判定，不按当前 KR 归属**——M3/M9/M2 虽现归 evolution_path，
   但是组装脑时期造的器官，归 assembly；S20 ACE 经验编译归 evolution。
5. 数据写在语义镜像 CAPABILITY_LADDER.yaml；生成器 tech_tree.py 自动生成 HTML，不手改。

## Counter-evidence（反证）
- **最强反对**：把 tuning 历史决策塞进科技树会稀释"卡片=可做的工作单元"的语义——节点不再是行动项。
  对冲：tuning 节点 `kind='tuning'`，与 `kind='card'` 区分；它们代表"地基已铺"的证据而非待办。
- **第二反对**：四坐标认知负荷高，用户可能更困惑。
  对冲：三态切换保留旧视图；统一视图用列+分组+徽章渐进披露，颜色只编码器官（1个ramp集）。
- **翻案条件**：若用户实际使用中发现统一视图仍不好用，回退到三视图分离，重开 ADR。

## Consequences
- 正面：一张树回答"从哪来/干什么/服务什么/到哪了"；调优期地基可见；组装期vs优化期可分。
- 负面：标注 73 卡有主观性（已审核边界卡）；HTML 从 60KB 增到 70KB。
- 验证：104 节点（90+14 tuning），root 五阶段齐全，JS 语法自检+门禁 67/67。
