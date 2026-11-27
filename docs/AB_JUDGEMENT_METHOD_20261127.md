# 判优实验方法学（2026-11-27 16:10）

> 用户："判优实验可以做了，要有 95% 把握"
> 本文记录**实验设计**与**为什么这样设计**。结果见 `AB_JUDGEMENT_FINAL_20261127.md`。

## 一、上一次实验为什么不能判优

三轮分批跑（off n=2 / on n=8 / inject-on n=4），存在三个致命问题：
1. **时序混杂**：三组在不同时间跑，中间重启 3 次
2. **样本不足**：n=2 的 off 组方差估计完全不可靠
3. **第一层是纯观测**：72 次 mining 但回注 0 次，不可能改变行为

## 二、本次设计的三个关键改进

### 2.1 运行时动态开关（消除时序混杂）

新增 `bench/_ab_mode.json`，harness 按 mtime 缓存读取：
- `off`：mining 关、inject 关
- `on`：mining 开、inject 关
- `inject-on`：mining 开、inject 开

**一次重启内交替跑三组**，runner 在每次 create 会话前写模式文件。
预实验验证三组开关全部生效：
```
off        mined=0  inject=0  ✓
on         mined=2  inject=0  ✓
inject-on  mined=4  inject=1  ✓
```

### 2.2 即时回注（让短会话也能触发干预）

上次 inject-on 组 `live_injected=0`——因为回注挂在控制回合（每8步），
而测试会话只有 2-4 步，**干预从未执行**。

修复：mining 后立即回注高置信信号（只喂信号不喂原文、去重、不覆盖守卫注入）。
预实验 inject-on 已能触发 `live_injected=1`。

### 2.3 两组指标（效率 + 质量）

- **主指标**：`tool_calls/session`（效率，连续）
- **质量指标**：`answer_correct`（最终文本是否含正确答案 `C-001`，二项）
- **辅助**：hard_stop、failures、completed

只用 tool_calls 会判反（2 步给错答案 vs 8 步正确完成），所以质量指标是必须的。

## 三、统计方法（95% 把握）

`tools/ab_significance.py`（249 行）：

| 项目 | 方法 |
|---|---|
| 置信度 | alpha=0.05（95% 置信） |
| 把握度 | power=0.95（95% 把握，比常规 0.80 更严） |
| 正态性 | Shapiro-Wilk |
| 主检验 | 正态→Welch t；非正态→Mann-Whitney U；**两种都报**避免选择性报告 |
| 效应量 | Cohen's d + rank-biserial + 10000 次 Bootstrap 95% CI（固定种子） |
| 二项指标 | Fisher exact + OR + 95% CI（零格 Haldane 校正） |
| 多重比较 | Holm-Bonferroni 校正三个族 |
| 等效性 | TOST（边界 ±1 tool_call） |
| 判定 | 判优 / 判等效 / 不确定（附还需样本量） |

## 四、样本量策略（不盲目跑 300 会话）

1. 先用小样本估计效应量（`tools/power_analysis.py`）：
   - off vs on：d=1.27 → n=16/组
   - on vs inject-on：d=−0.72 → n=50/组
   - off vs inject-on：d=0.50 → n=105/组
2. **但 off 组 n=2 的方差不可靠**——所以不直接按这个数跑
3. 跑一批中等样本（每组 8 次）→ 用实测方差重算（`tools/ab_sample_decider.py`）
4. 再决定是否继续加样本

## 五、执行方式

```
python tools/ab_randomized_runner.py 7 20261127 --append
```
- 7 轮 × 3 组 = 21 会话（+ 预实验 3 = 24）
- seed=20261127 打乱顺序，同批次内随机交错
- `--append` 追加到已有 v2 批次
- 每会话增量保存（防中断丢数据）
- 结束自动恢复 `off` 模式（生产安全）

## 六、判据（预先声明，防事后挑指标）

1. **主判据**：三组两两 Holm 校正后 p<0.05 且效应方向一致 → 判优
2. **次判据**：质量指标 answer_correct 的 Fisher exact（Holm 校正）
3. **等效**：若 p>0.05 但 TOST 通过（±1 tool_call）→ 判等效
4. **否则**：报告"不确定"+ 按实测方差算还需样本量

**重要**：不因为"想要某个结论"而换主指标。tool_calls 和 answer_correct 都是预先声明的。

## 七、诚实边界

- 24 会话仍可能不足（若效应量 d<0.5，power=0.95 需 n>100/组）
- 35B 单次方差大（实测同任务 2~10 calls），判优可能最终是"不确定"
- 任务陷阱（路径歧义）是否命中仍有随机性——已通过随机化均衡到三组
- 本实验只回答"这套 harness 机制是否改善行为"，不回答"模型本身能力"
