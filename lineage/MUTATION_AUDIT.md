# 反向测试审计：哪些守卫是真的？（2026-11-21）

> 用户："把正在声称发挥功能的全绿反向测试补一下，快速知道哪些是真的发挥作用。"
> 正向全绿只证明"没报错"；反向测试（故障注入）= 破坏机制后行为是否真的改变。

## 0. 为什么必须做（今晚三次血泪）

| 事件 | 正向检查 | 反向测试才暴露 |
|---|---|---|
| listed 假绿灯 | citation_guard 全绿 | listed 只核标题却拿 verified 同样的 PASS |
| 第7维死副本 | run_all 全绿、静态断言 10/10 | 动态触发发现 trace 记 [1-5]（第三副本没同步）|
| ADR 门控判据错 | 构造违规 ADR 后 rc=0 | 判据用文件名而非标题，违规被跳过 |

**结论：静态看代码 + 正向全绿，三次被骗。**

## 1. 已做反向测试的机制（真验证）

| 机制 | 反向方法 | 结果 |
|---|---|---|
| citation_guard 引用门禁 | 构造幻觉引用/错配引用 | FAIL 符合预期 |
| ADR 四字段门控（新） | 构造缺字段 ADR | 首版假绿→修正后 FAIL rc=1、删除 rc=0 |
| A1_7 评审可观测性 | 真实触发 Critic + 检查 trace | 首版 0 条→修第三副本后 6/6；生产 trace 已见 7 维 |
| S11 写后校验 | 旧逻辑 vs 新逻辑对比 | 旧 0/6 → 新 6/6 因果验证 |
| danger guard | 开/关对比（mutation harness）| 开=true 关=false ✅ |
| verify-on-edit | 开/关对比 | 开=true 关=false ✅ |
| turn-guard L3 | 退化场景 | steer=1 ✅（**无 Enabled 开关，不能 mutation，只能验生效**）|

## 2. 子任务独立盘点发现的假绿（尚未修）

测试文件 `tools/test_*.mjs` 的断言强度审计：

| 测试 | 假绿点 | 性质 |
|---|---|---|
| `test_new_guards.mjs:167` | `check('MTP低接受率→触发审计', inj !== null \|\| true, true)` | **恒真断言**——`\|\| true` 让它永远 PASS |
| `test_new_guards.mjs:170` | `check('MTP信号读取正常', true, true)` | **写死 true** |
| G4 confidence=low→UNCERTAIN | 整段只有 emit，零 check | 无断言 |
| `test_injection_budget` | 部分断言 `>=0` | 恒真 |
| CritBank 相关 | 只校验 JSON 内容，没走真实 matchCritbank 检索 | 弱断言 |
| A1_7 | 只有 critic 有动态测试，audit/planner 无 | 覆盖缺口 |

**为什么没立刻修 MTP 那两条**：尝试构造高低接受率对照时测试超时（`SIGTERM`）——
生产 35B 正在占用推理资源，测试里的审计触发真的去调 LLM 卡住了。
凌晨不宜在资源竞争下硬改，**保留为已知弱点**，等空闲时段用 mock fetch 正确重写。

## 3. 生产端到端验证（最强证据）

通过 dsh-session-bridge 向生产 35B 会话发验证消息（session-819eb9bc…），
真实跑了一轮：35B 思考 ~4 分钟 → write → present。

生产 `D:/Brain/workspace/bench/_trace.jsonl` 中的真实记录：
```
review_verdict  critic  critic-v2  [1,2,3,4,5,6,7]
review_verdict  audit   audit-v1   ['A','B','C','D','E']
```

**这是比任何 mock 都强的证据**：真实模型、真实会话、真实 trace，
证明第7维和检查项E不只在代码里，而是真的在生产运行时被加载和使用。

## 4. mutation harness 自身的一个假绿（已诚实处理）

初版 M4 CritBank 断言写成"两边都 false 也算通过"——等于永远 PASS。
已改为：未命中就明确打印 `SKIP`（不算通过），命中才断言开/关差异。

## 5. 结论：当前哪些能声称"真的发挥作用"

| 等级 | 机制 |
|---|---|
| **A 生产实测** | A1_7（7维+E项）、S11（已因果验证）、citation_guard、danger guard、verify-on-edit、turn-guard |
| **B mock 反向验证** | mutation harness 的 M1-M3 |
| **C 仅正向/弱断言** | MTP 信号（恒真断言）、G4 confidence 降级（零 check）、injection_budget 部分、CritBank 检索 |
| **明确不适用** | turn-guard mutation（无开关，只能验生效，不能故障注入）|

> C 类不代表机制是坏的，只代表**我们还没有证据说它真的生效**。
> 按证据纪律：C 类不许自称已验证。
