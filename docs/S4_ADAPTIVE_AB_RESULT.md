# S4 自适应原型端到端 A/B 结果（2026-11-19，实测）

> 目标：验证 `adaptiveThinkEnabled` 是否"token 降且成功率不降"，据此决定默认值。
> 原 DoD 要 P3/P4/P5 各 2 次取中位；本轮只完成 **P3 各 1 次**（P4/P5 单次 10-40 分钟，成本过高），
> 属于**部分完成**，不冒充全量验收。

## 一、方法（不污染生产）

bench 脚本直连 8081（`projectlab.py:32 PL_BASE`），绕过 harness，所以 `adaptiveThinkEnabled` 对 bench 零影响。
故写一个透明代理 `bench/adaptive_proxy.py`（端口 8091），只在 system message 末尾注入 harness 的 ⑦ 提示：

> ⑦ 思考预算：两个独立信号一致显示这是简单步（生成顺畅+无失败）——直接执行下一步，不必展开长链推理。

- 对照组：`ADAPTIVE_MODE=off`（透明转发）
- 实验组：`ADAPTIVE_MODE=on`（注入 ⑦）
- 命令：`PL_BASE=http://127.0.0.1:8091/v1/chat/completions QL_TEMP=0.6 python bench/projectlab.py P3`

## 二、结果（P3 单次）

| 组 | 结果 | 步数 | 耗时 | 生成 token | 画像 |
|---|---|---|---|---|---|
| off（对照）| **FAIL** — config.py 没生成（FAKEOK）| 11 | 189.1s | 4172 | DELIVER=FAIL |
| on（adaptive）| **PASS** | 13 | 300.6s | 4168 | DELIVER=OK, RECOVER=WEAK |

## 三、解读（关键，别读反）

1. **token 没降**：4172 → 4168（基本持平）。DoD 是"token 降且成功率不降才开"——**按此标准不能开**。
2. **行为变了**：off 组在 step10 假装完成（FAKEOK），on 组在 step11 真的写了 config.py 并跑通测试。
   ⑦ 提示的作用是"继续执行、别过早收工"，不是"少想"。
3. **耗时反而增加**：189s → 301s（多 2 步），因为 on 组多做了一步写入+验证。
4. **单次噪声**：项目既有铁律"单次 ±10%，判优至少 2 次"。本轮各 1 次，
   FAIL→PASS 是强信号但**不能排除随机性**（off 组历史也有 PASS 记录）。

## 四、结论与决定

- **保持 `adaptiveThinkEnabled: false` 默认值不变**——token 未降，不满足开启条件。
- 但记录一个有价值的观察：⑦ 提示可能降低 FAKEOK（提前假装完成）。这与我们 D4 交付闸门
  和 verify-on-stop 关注的问题同源，值得用更多次数验证（列 L7 探索）。
- **不把单次 PASS 当成机制有效**——按 DoD 诚实判为"未达开启标准"。

## 五、未完成部分（诚实记录）

- P4/P5 各 2 次未跑：单次耗时 10-40 分钟，4 次合计数小时，超出本轮合理预算。
- 机制本身的单测已覆盖（`test_short_term_goals.mjs` ③：双信号一致→skip-deep-think，
  trace 记 adaptive_route）。

## 六、产物
- 代理脚本：`bench/adaptive_proxy.py`
- 调用日志：`bench/_adaptive_proxy.jsonl`（含每组 prompt/completion token）
- 原始输出：见 background task 日志（P3 off 189.1s FAIL / on 300.6s PASS）

> 遵循知识资产沉淀规则：正结果、反结果、未完成部分、决定理由都留档。
