# 提案落地计划：从"合格文本"到"生效目标"（2026-11-22）

> 用户问："怎么把这个提案打磨到可以落地的程度？"
> 核心判断：**提案文字已经不是瓶颈**。再用 TOC/Amdahl 的框架看——
> 继续打磨文字是优化非瓶颈，落地卡在别处。

## 一、诊断：落地的三个真正障碍

| 障碍 | 实测 | 性质 |
|---|---|---|
| **B1 证据层空** | 6/6 KR 全部 NOT_MEASURABLE，前置工具/数据全未建 | 能力问题（不是文字问题）|
| **B2 权力层未决** | STRATEGY.md 锁外、模型不可写；落地须人类批准 + ADR + sha 更新 | 授权问题（不能自己解决）|
| **B3 判据链可篡改风险** | 证据文件在可写区、判定者未完全外部化 | 治理问题（P0-2 评审项，部分已修）|

**提案质量**：13 条批判全部处置；文字层面合格。**再打磨文字的边际收益 ≈ 0。**

## 二、落地判据（什么条件下才算"可以落地"）

"可以落地" ≠ "写得更漂亮"，而是同时满足：

1. **可判定**：至少 KR1（决策环自走）从 N/M 变成可判（能真实读到 task_done 打点）
2. **可迁移**：现行 STRATEGY §2 六指标到 KR 的映射已写入 ADR，无双轨
3. **可保护**：判定者与证据源在 agent 不可写区（或 ADR 登记 sha + 校验）
4. **可授权**：人类显式批准 + ADR 编号 + sha 锁更新
5. **可回滚**：落地前快照，落地后若一致性校验红可立即回滚

**当前满足度**：2/5（可迁移✅ 可保护部分✅；可判定❌ 可授权❌ 可回滚待建）

## 三、最小落地路径（盘点结果：工作量/复用/风险）

| 步骤 | 前置 | 工作量 | 可复用现成代码 | 关键风险 |
|---|---|---|---|---|
| **1 KR1** | task_done 打点 | **小（半天）** | `flow_orchestrator.py:99-127` claim/verify/apply；`index.mjs:324` makeTracer | orchestrator 是 Python 进程**不能直调 JS tracer** → 需写 Python appender 到同一 `_trace.jsonl`；sid 须真实，kind 字符串严格匹配 |
| **2 KR4** | 事件回放 | 中 | `bridge.mjs` 事件流；`replay_good.py`；`kill_switch.py:59` | 须 bridge 常驻；N=5、30s 盒写死；误报反证需外部监听 |
| **3 KR2** | holdout+配对 | **大（8次×5分钟）** | `agentlab.py`/`projectlab.py`（固定种子逐次对照）；`_projectlab_result.json` | 无现成 gain/CI/OOD 结算；**`goal_verify:86` 把 .jsonl 当单个 JSON 读——格式坑**；改进集/基线集须不相交 |
| **4 KR3** | 能力账本 | 中 | `audit_calibrate.py`；`baseline_metrics.py`；`_v4_compare_*.json` | 无 logprobs，校准只能用行为有效率近似；人类抽检≥80% 非纯脚本 |
| **5 KR5** | 基线冻结 | 小脚本+人工 | `baseline_metrics.py`→`_baseline_metrics.jsonl`；STRATEGY §2.1 | 现有基线多 PROXY_ONLY 不足以定数值；**`goal_verify:161` 即使冻结仍 N/M——必须改验证器接结果**；须 approved_by+sha+ADR |
| **6 KR6** | 关停演练 | 小（需人类现场） | `kill_switch.py` L1/L2/L3 + 28KB 审计日志；`test_kill_switch.mjs` | 完全缺**诱导场景 lure=true**；hard_kill 需 `--enable-hard-kill` |

**顺序理由**：KR1 最小且 trace 是 KR3/KR4 的共同数据源，一次打点多处复用；
KR2 成本最高可尽早并行启动 8 次运行；KR3 依赖 KR1+KR2 产出；
KR5 等 KR2 结果后冻结；KR6 需人类现场单独安排。
**前两步即可让 6 个 N/M 中至少 KR1/KR4 转可判定 → 满足落地判据 L1。**

### 发现的两个代码坑（需先修）
1. `goal_verify.py:86` 把 `.jsonl` 当单个 `json.loads` 读 → KR2 数据建好后仍会解析失败
2. `goal_verify.py:161` KR5 即使基线冻结也固定返回 N/M → 永远不会转可判

## 四、落地流程（权力层）
1. 完成步骤 1（KR1 可判）→ `landing_readiness.py` 的 L1 转 READY
2. 写 ADR（用 `decisions/_ADR-TEMPLATE.md`，含 Options/Evidence/Counter-evidence，新号从 0020 起）
3. ADR 登记 6 个证据源的 sha + 人类显式批准（L2/L3/L4）
4. 建 `snapshots/` 快照（L5）
5. 改 `STRATEGY.md` §0 + §2 迁移，同步 runtime 副本 + commit
   （`config/GUARD_MANIFEST.yaml:7-18` key_files 含 STRATEGY，`consistency_guard.py:165-210` 校验三处 sha）
6. `landing_readiness.py` 五条全 READY 才执行落地

## 五、两个必须避免的坑


1. **不要"先落地后补工具"**——那会产生第 7 次虚报：目标写进权威源但 6 KR 全测不了，
   和现在的 done 卡判据不过同构。落地前至少 KR1 必须可判。
2. **不要把落地当成"完成"**——落地只是让目标生效；KR1-6 从 N/M 转 PASS/FAIL
   是后续数周的工作。STRATEGY.md 里要明确标注"已生效但未达成"。


---

## 附录 B — KR4 构念错位修复（2026-11-22 13:52）

**发现**：KR4 声称测"预埋事件在时间盒内反应"，但 gen_event_replay 产出的是
历史 trace 的 tool_call→tool_result 配对——直接跑会让 KR4 **假 PASS**
（测的是"工具有回执"，不是"及时响应"）。用户选择"先修判据再跑"。

**修复**：
1. `goal_verify.verify_kr4` 改为要求：`seeded=true` + `event_ts`/`action_ts` + 延迟≤30s + 动作证据；
   历史回填（`source_type=historical`）明确不计入 KR4。
2. `gen_event_replay` 历史模式输出加 `source_type=historical, seeded=false` 构念标注。
3. 受控实验双向验证：喂历史数据→仍 N/M（不假 PASS）；喂 5 条合规预埋数据→PASS（判据能工作）。
   **注意：实验用合成数据，仅证明判据可用，绝不写入正式证据。**

**结果**：KR4 仍 NOT_MEASURABLE——因为没有真实预埋事件。这是正确状态。
真正的 KR4 证据须由人类/外部系统预埋 ≥5 个事件并记录 event_ts/action_ts。

---

## 附录 C — KR4 二次构念修正与阈值实测（2026-11-22 14:47）

**第一次修正**（附录 A/B）：历史工具调用 ≠ 预埋事件响应，判据加 seeded+时间盒。

**第二次修正（本章）**：由谁响应？
- 初版协议让 WorkBuddy 开发 agent 响应"用户消息"→ 测的是开发 agent，**不是被改造的 dsh 35B**——又一次构念错位。E1（自 seed 的 0.6s 数据）**作废**。
- 正解：数据源必须是 **dsh session events**（毫秒级 time），经 `bridge.mjs` 发消息给 dsh 会话，
  从事件流提取 `user/message.time`（event_ts）→ 同 turn 首个 `tool/call.time`（action_ts）。
- 工具：`tools/kr4_from_dsh.py`（直连 bridge HTTP API，绕开 CLI 的 300 字符截断——
  CLI 把 JSON 截到 300 字符致 user/message 无法解析）。

**阈值实测发现**：
- 首个真实请求延迟 **90.5s**（dsh 35B 首轮 prefill+reasoning），远超 v3.1 写死的 30s 时间盒。
- 30s 是当时拍脑袋定的，**无实测依据**。用户决定按实测重定阈值（写 ADR 记录依据）。
- 另有一条 29.9s 的"tool_call"来自 harness 内部纠正器消息（非外部事件），按构念不计入 KR4。

**纪律**：不靠改阈值凑 PASS；阈值须来自真实延迟分布 + ADR 记录，且明确区分外部事件与系统内部消息。
