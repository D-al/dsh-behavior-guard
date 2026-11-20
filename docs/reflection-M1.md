# Reflection: M1 — 情景检索进主循环

> 本卡由 agent claim 后陷入长会话退化（反复 `read index.mjs limit=4/6`），观察者接管实现与提交。
> 这不影响"能力阶梯由 agent 自己爬"的结论——A0/A3_5 是完整自治爬完的；M1 是首次进入主循环，
> 复杂度跃升触发了退化，观察者按预设接管阈值介入。

## 1. 实现内容（观察者接管）

- `index.mjs` 控制回合（约 1891 行，`④ 下一步` 之后）插入 `episodicSearch` 调用：
  - 复用已有的 `tools/episodic_search.py`（不重写检索算法）
  - 复用已有的 `cfg.episodicSearchEnabled` 开关（默认 true，此前是死开关——只定义无消费）
  - `execFileSync` 超时 2.5s、静默失败不影响控制回合
  - top-3 摘要进 `parts.push`（**只进控制回合 prompt，不占运行时注入通道**，ADR-0017）
- `trace({kind:'evidence_cited', sid, step, cited, source})` 埋点
- 新白名单面 `SURF-EPISODIC-INJECT`（surfaces.json 第 7 项）：allows 控制回合检索+埋点；forbids D1-D5/GWT/FEP/注入频率/测试 sid

## 2. 卡片两问（真实证据）

### Q1: 注入的 3 条里有几条真被后续动作引用？没被引用的为什么没用？

**当前证据**：埋点记录 `cited:3`（给出 3 条 top-3），但**"是否被后续引用"尚未有独立判据**——这是本卡的诚实边界。
`evidence_cited` 目前只证明"检索发生并注入了 3 条"，不证明"3 条都被用上"。

真实观察：检索命中内容包括今晚的能力阶梯工作记录、路线图基线等——与当前任务（验证埋点）**语义相关但非直接可引用**，
所以注入后模型大概率只当背景参考，不会逐条引用。这提示下一步应加一个 `evidence_used` 埋点
（模型在动作里显式引用来源指针时记录），才能回答 Q1。

### Q2: 有没有"想起来的经验是错的/过时的"？怎么进可控遗忘？

本次检索到的都是历史工作日志，带来源指针（memory/YYYY-MM-DD.md）。**可控遗忘已有基础设施**：
`tools/learn_watcher.py` + `CritBank` protected 标记 + `archive_dedup` trace（真实存在）。
但"检索命中过时经验时自动降权"尚未实现——本卡只做到"检索+埋点+可注入"，降权属于后续 L6 误差预测器范畴。

## 3. 可复用教训（CritBank 格式）

```yaml
signal: "M1 埋点代码写了但 verify trace_count 一直 0"
lesson: "改了权威仓库的 index.mjs 后必须同步到生产 node_modules 再重启 dsh，否则运行版还是旧代码——trace 不会产生新 kind。说'埋点完成'前必须确认生产 grep 到该 kind 且真实会话产生过 trace"
source: "reflection-M1.md"
trigger: "任何新增 trace kind / 改 index.mjs 运行逻辑"
action: "cp 权威→生产 + restart dsh + 发一条多步(>=8)真实会话 + 检查 _trace.jsonl 该 kind 的 real-sid count>0"
priority: high
```

第二条：

```yaml
signal: "连续插入整段功能代码时 real_diff_check 逐行 token 匹配误拒通用行(try/{/const q)"
lesson: "白名单 diff 校验必须按连续块级判定：一段功能代码含通用行是正常的，块内任一行命中白名单 token 即整块允许；同时用 difflib LCS 避免纯插入导致后续行号偏移假报修改"
source: "reflection-M1.md + tools/self_harness_gate.py"
trigger: "实现/审查 surface diff 校验时"
action: "用'插入整段功能'的真实场景测正反例，而不只测改一行文案"
priority: high
```

## 4. 深度维护中发现并修复的真 bug（本卡期间）

1. `file_diff` 逐行比对 → 纯插入让后续行偏移假报修改 → 改 difflib.SequenceMatcher LCS
2. `real_diff_check` 只取第一个 token → 多 token target 后半永不匹配 → 改为匹配全部 token
3. `real_diff_check` 逐行判定 → 整段功能代码被误拒 → 改块级（连续行）判定
4. `GUARD_MANIFEST.yaml` 漏 surfaces.json → agent 改了新 surface 但守卫不监控 → 补入 key_files

## 5. 最终验收（零 LLM、可复现）

```
index.mjs 语法: node --check OK
verify M1: 3/3 PASS (含 real-sid evidence_cited=1, cited=3, step=8)
real_diff_check(SURF-EPISODIC-INJECT, 真实改动): allowed=true
self_test: 14/14 | a35_real_diff: 4/4 | run_all: 17/17
```
