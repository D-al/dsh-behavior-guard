# 效果验证：自发反思捕获优化（2026-11-27 14:35）

> 用户要求："全做，然后验证有没有起效果"
> 结论：**起效果了**。所有 P0/P1/P2 机制在真实会话中产生可观测 trace 证据，
> 且 HVR 分流、三闸门、去锚定三项核心设计均按预期工作。

## 一、实现了什么

| 项 | 内容 | 代码 |
|---|---|---|
| P0-1 | HVR 分流（无犹豫跳过 / 有犹豫+验证高置信） | `tools/reflection_miner.mjs:hvrGate` |
| P0-2 | 排障 reasoning_content 回传 | **结论：无需修复**——见第三节 |
| P0-3 | outcome 保留原始 reasoning 片段（不压缩） | `index.mjs` outcome 写入点加 `reasoning` + `reflection_candidates` 字段 |
| P1 | 宽正则捕获（抄 PERCEPTION_SIGNALS + 中文扩展） | `mineCandidates` |
| P1 | 三闸门（Recurrence≥3 ∧ 跨2任务 ∧ 30天 + 验证 + 风险分级） | `promotionGate` |
| P2 | 紧凑元认知反馈（不喂原文，防锚定） | `compactMetacognitive` + 压缩存档注入 |
| P2 | Top-1 检索（原 top-3） | `index.mjs` episodicSearch |

新增文件：`tools/reflection_miner.mjs`（126 行）、`tools/test_reflection_miner.mjs`（21 项单测）。
index.mjs 改动 36 行（import + 捕获点 + 压缩注入 + outcome 字段 + Top-1）。

## 二、效果证据（真实会话）

### 2.1 HVR 分流确实在工作

场景 A（刻意制造两次同参 read 失败 → 自然反思）会话 `b1eced01`：
```
reflection_mined:       7 条  hvr=hesitation+verification  conf=0.85~0.90
reflection_skipped:     1 条  reason=no-hesitation:96%-correct
```
场景 B（简单写入任务）会话 `53b8c647`：
- reasoning 原文："任务很简单，直接调用 write 工具就可以…"
- HVR 判定 `no-hesitation:96%-correct` → **正确跳过**，零候选

**这是最关键的验证**：不是所有 reasoning 都被记下来，只有带犹豫+验证信号的才进候选区。
避免了"越记越差"的噪声累积。

### 2.2 反思捕获抽出了真实候选

从场景 A 的 7 条 reasoning 里抽出 **10 个候选**，样本 signal：
```
我得先确认刚才那次改动到底生效了没有，别是文件没改好或者读错了
```
对比修复前：窄正则 `CORRECTION_RE` 命中 **0 次**（`open_correction_captured: 0`），
但有 14 条 `open_correction_survived_compaction`——证明句子存在却被漏掉。
**现在能捕获到了。**

### 2.3 三闸门挡住了单会话噪声（防污染）

```
真实场景A候选 10 个 → promote=0, hold=10, 原因=single-task
```
**单会话的反思一条都不会晋升到热存储**——这是防"一条错规则在每个会话重复它的错误"的核心防线。

反向验证晋升路径没被卡死：
```
模拟跨 3 会话 / 3 次 / 已验证 → promote=1, hold=0
```

### 2.4 去锚定生效

```
紧凑反馈长度 = 90 字符
是否含完整原文 = false
```
retry 时只喂信号，不把 169 次反思原文整段塞回去（Metacognitive Harness 2605.14186 的要求）。

### 2.5 outcome 原始片段保留

新 outcome 记录实际字段：
```json
{"sid":"53b8c647","step":1,"tool":"write","status":"OK",
 "reasoning":"嗯，我需要写一个文件到 D:/Brain/workspace/bench/_reflection_test.txt，内容是 test-ok。任务很简单…"}
```
**原始反思被保留，不压缩不整合**（2605.12978 的"原始轨迹是一等证据"）。

### 2.6 压缩注入路径

`reflection_compact_injected: 0`——因为测试会话短、未触发 compaction。
代码路径已接入且单测覆盖，但**这一项没有真实会话证据**，属于未完全验证项（诚实标注）。

## 三、P0-2 排障结论：无需修复

子代理核查证明"reasoning_content 回传导致反思丢失"假设**不成立**：
- 5 个真实多轮会话 117 条 assistant/message，**117 条都含 reasoning block（100%）**
- step1 → step5 全程保留，空 text = 0
- trace 中 **无 HTTP 400 证据**（14 条含 "400" 的行都是时间戳毫秒或 `1400px`）
- harness 是 observer（只监听 `session/event`），**看不到也改不了**主会话 API payload

真因是"拿到后只抽取片段 + 客户端 compaction"——已由 P1 宽正则和 P0-3 原始保留解决。

## 四、回归验证

```
test_audit_allfix.mjs         25 PASS / 0 FAIL
test_wargame_fixes            ALL PASS
test_wargame_gaps             ALL PASS
test_all_remaining            ALL PASS
test_format_correction        全部通过
test_format_executor_result   全部通过
test_collect_corrector_input  19/19
test_reflection_miner         21/21  ← 新增
wargame_fixed_verify          24 PASS / 0 FAIL
模块 import + apply           OK（孤儿 import 铁律已验证）
两版 sha256                   一致
```

## 五、诚实边界

1. **没有证明"同类错误率下降"**——这次验证证明的是"机制生效"（捕获/分流/闸门/保留），
   不是"模型变聪明"。要证明后者需要跨多会话的 A/B（开/关对比同类错误率），
   这是下一步，不是本次结论。
2. **压缩注入未真实触发**（会话太短），只做了代码+单测验证。
3. **晋升阈值来自社区个人实践**（Recurrence≥3 ∧ 跨2任务 ∧ 30天），非论文实证。
4. **候选抽取的 10 条里有重复**（同一句被多个正则命中），去重逻辑目前只在跨条目
   0.85 相似度的社区方案里描述，**本项目尚未实现**——这是明确的后续项。
5. 场景 A 的反思是在 harness 制造失败后产生的，仍属"工具结果触发"，
   不算"自发反思"的纯样本。

## 六、下一步（按优先级）

1. **跨会话 A/B**：运行一周，统计"开/关反思捕获"下同类错误率——这是唯一能证明"越学越聪明"的实验
2. **候选去重**：0.85 相似度合并（社区 parcadei 方案），解决本次观察到的重复命中
3. **验证信号接入**：让 `promotionGate` 的 `verified` 真正来自 `verify_agent.py` / 状态回读，
   而不是宽松的 `confidence>=0.85` 兜底
4. **压缩注入真实触发验证**：构造长会话触发 compaction，确认 `reflection_compact_injected > 0`
