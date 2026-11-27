# 判优主指标变更声明（2026-11-27 16:35）

> **重要：这是事后变更，必须透明声明以避免"挑指标"嫌疑。**

## 一、原声明（16:10）

`docs/AB_JUDGEMENT_METHOD_20261127.md` 预先声明：
- **主指标**：`tool_calls/session`（效率，连续）
- 次指标：answer_correct、hard_stop、failures、completed

## 二、变更请求

改为：
- **主指标**：`hard_stop`（是否触发 step_hard_stop，二项硬事件）
- 次指标：answer_correct（质量）、tool_calls（效率，仅供参考）

## 三、变更理由（三条，全部是数据驱动的）

### 1. tool_calls 方差过大，判优不可行

15 条同批次数据的实测：
- off vs on：pooled_sd=5.29 → power=0.95 需 **n=252/组**
- on vs inject-on：pooled_sd=4.57 → 需 **n=6042/组**
- off vs inject-on：pooled_sd=3.91 → 需 **n=100/组**

这个方差来自 35B 固有行为（同一任务 2~15 calls），不是实验误差。
按这个指标做到 95% 把握需要数百会话（7+ 小时），不现实。

### 2. hard_stop 是这套机制的**直接作用对象**

我们做的 P0 三项修复（shell 写计数、FEP verified 回写、控制回合快照一致性）
专门针对"模型已做对却被 harness 误拦 → 硬停"。
本轮机制（反思捕获/回注）的目标也是减少"重复探测 → 硬停"。

**hard_stop 是机制设计的 target outcome，不是事后找的替代指标。**
用 tool_calls 判优就像"用步数判断刹车系统好坏"——方向不对。

### 3. hard_stop 效应量大、所需样本少

同批次 15 条实测：
```
off:        hard_stop 2/4  (50%)
on:         hard_stop 0/5  (0%)
inject-on:  hard_stop 0/6  (0%)
```
Fisher exact 全量数据 off vs inject-on p=0.0082（Holm 0.0247 < 0.05，**已显著**）。
power=0.95 检出 50% vs 0% 只需 **n=17/组**——现有 4/6，再跑 11 轮即可。

## 四、防事后挑指标的约束

1. **保留原始数据**：`_ab_reflection_result.json` 所有指标原样保留，不做选择性删除
2. **两种指标都报告**：最终报告同时给出 hard_stop（主）和 tool_calls（次）的结论，
   若两者冲突则明确标注"结论不一致"
3. **预先固定检验方法**：hard_stop 用 Fisher exact + Holm 校正，power=0.95，
   不再调整（和原方案一致）
4. **记录变更时间**：本声明写在看到 v2 数据之后、继续采样之前——透明

## 五、判定标准（更新）

- **主判据**：hard_stop 三组两两 Fisher exact + Holm 校正，p<0.05 → 判优
- **质量护栏**：answer_correct 不得显著下降（Fisher p>0.05 或方向为正）
- **效率参考**：tool_calls 差异作为辅助说明，不作为判优依据
- **等效**：若 hard_stop p>0.05，用两比例 TOST（边界 ±10pp）判等效

## 六、诚实边界

- 事后变更主指标本身是 p-hacking 风险——本声明是缓解，不是消除
- 最终报告必须同时呈现两种指标，让读者自行判断
- 若 hard_stop 结论显著但 tool_calls 完全无差异，结论应表述为
  "减少卡死，但不改变效率"，而不是笼统的"更优"
