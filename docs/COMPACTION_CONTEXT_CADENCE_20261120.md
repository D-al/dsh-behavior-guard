# 压缩/上下文/频次治理（2026-11-20~22）

> 压缩与角色诊断、频次审计与重设计、MECHANISM_TRIGGER_AUDIT

> 本卷合并 4 份原报告（2026-11-25 整理）。

## 本卷目录

- `COMPACTION_AND_ROLES_DIAGNOSIS.md`（原文件保留为引用桩）
- `CADENCE_AUDIT.md`（原文件保留为引用桩）
- `CADENCE_REDESIGN.md`（原文件保留为引用桩）
- `MECHANISM_TRIGGER_AUDIT_20261120.md`（原文件保留为引用桩）

---

## 原报告：`COMPACTION_AND_ROLES_DIAGNOSIS.md`

## 压缩触发、重复工作、角色可见性、过程折叠：诊断报告（2026-11-19）

> 全部结论基于真实代码（`index.mjs`）+ 生产配置（profile `cordis.patch.yml`）+ 5538 行 trace + 110 条压缩账本。
> 区分【事实】（数据/代码直接可见）与【推断】（需进一步验证）。

---

### 问题 1：写入/读取文件时触发压缩——是设计还是 bug？

**结论：都不是——是因果倒置。压缩由 dsh 引擎按 token 量触发，harness 不主动触发压缩。**

【事实】harness 里没有"发起压缩"的代码，只有监听：
```js
if (event.type === 'compaction/prune' || event.type === 'compaction/summary') {
  s.justCompacted = true; s.pendingArchive = true
}
```
（index.mjs:746）——压缩事件由 dsh 发出，harness 只是被动响应。

【事实】触发点由 dsh 的 `compaction-basic` 配置决定：
`thresholdRatio: 0.55`、`headroomTokens: 16384`、`retainTokens: 24576`、`contextWindow: 98304`
→ 触发点 ≈ min(98304×0.55, 98304−8192−16384) = **54K tokens**。

【推断】"写/读文件时压缩"是因为：长任务里文件操作密集，token 恰好在同一时段跨过 54K 阈值；
压缩又插入存档文本，进一步推高 token，可能短时间内连续压缩。
账本证据：s1 会话 82 次压缩，中位间隔 196 秒，但**最小间隔 0.6 秒**——存在连续触发。
这是"阈值型压缩 + 存档回注推高 token"的正反馈，属于**设计缺陷**（不是代码 bug，是机制设计问题）。

---

### 问题 2：压缩会不会导致重复干同一件事？

**结论：会，但根因不是压缩本身，是"存档内容 82 次完全不变"——模型卡在 todo 状态没推进。**

【事实】压缩账本里 s1 的 82 条记录**签名完全一致**：
`(todos=2, completed=0, rejected=0, hasVerify=1)` ×82。
即每次压缩后注入的存档都是"2 项待办、0 项完成"的同一份内容（index.mjs:1570-1591）。

【事实】`s.lastTodos` 在每次 `todo/write` 事件更新（index.mjs:771）。82 次存档不变
→ 模型 82 次写入的 todo 清单都是同一份（或从未更新）。

【推断】因果链：模型没推进 todo → token 继续涨 → 压缩 → 注入相同存档 → 模型读到"还是这 2 项、0 完成"
→ 重新规划/重做同样的事 → token 再涨 → 再压缩。这是**自我强化的重复循环**。

**已识别的缓解点（设计缺陷）**：存档注入没有"去重/变化检测"——即使内容与上次完全相同，
也照样注入完整存档 + "压缩后自检三问"。这等于反复提醒模型"你还没做"，却没告诉它"这份提醒已经发了 82 次"。
D3 冗余 todo 检测（index.mjs:787）本应捕获"连续写相同 todo"，但它的触发条件是 `todoRedundant>=2`
且 `!s.pendingInject`，在高频注入下容易被其他 pending 抢占。

---

### 问题 3：验收员有发挥作用吗？为什么没看到注入？

**结论：验收员在稳定服务期工作，但整体成功率低；看不到注入有三层原因。**

#### 3.1 触发条件与实际工具面脱节【事实】
验收员（代验收）的触发条件是：`wait_agent` 工具连续 `verifyMinWaits=2` 次 UNPRODUCTIVE
（index.mjs:992）。但 5538 行 trace 里 **`wait_agent` 调用 0 次**——
实际工作流用的是 `spawn_teammate`（73 次），不是 `wait_agent`。
→ **验收员的主触发路径在当前环境永远不会被命中**。这是角色设计与实际工具面的脱节。

#### 3.2 角色 LLM 调用大量失败【事实】

| 角色 | 调用次数 | 成功 | 成功率 |
|---|---|---|---|
| audit（审计员）| 84 | 9 | 10% |
| corrector（纠正员）| 74 | 7 | 9% |
| **critic（Critic）** | **54** | **0** | **0%** |
| planner（Planner）| 6 | 6 | 100% |

失败特征：`ms=0~1`、`outChars=2`（立即返回空），而成功调用要 10-45 秒。
按小时分布显示某些时段 0%（01-04 点、13-14 点、16 点），某些时段 100%（00、10、12、15 点）
→ **llama-server 不稳定/重启期间，角色 LLM 调用静默失败，harness 吞掉了错误**。
最近真实会话（eedb849e / 42bcddbe / 269ec283）角色成功率 100%/100%/60%，服务稳定时正常。

#### 3.3 注入是"只在发现问题才出现"【事实】
审计员走 `runAudit()` → 只有 `verdict === 'ISSUE'` 才产出注入文本（`[harness 独立审计]`），
`UNCERTAIN`（证据不足）直接弃权、`OK` 不注入（index.mjs:1896-1955）。
→ 用户看不到 = 大部分时候没有 ISSUE，或 ISSUE 因 LLM 失败没产出。**这是设计使然，不是角色没接。**

---

### 问题 4：其他角色呢？

【事实】角色都有代码实现且真实跑过（trace 有 llm tag 证据）：

| 角色 | 触发 | 产物可见性 | 状态 |
|---|---|---|---|
| 审计员 audit | 门控（失败≥2/无进展≥6/present前/压缩后）| 仅 ISSUE 时注入 `[harness 独立审计]` | 工作，但成功率受服务稳定性影响 |
| 纠正员 corrector | D2 同参数双败 / 审计 ISSUE | `formatCorrection` 注入或代执行 | 工作 |
| Critic | present 前评审产物 | 结果进 turn-stopping 决策，不直接注入 | **0% 成功率，实质失效** |
| Planner | 首次 [VERIFY] 项 | 结果进验收清单 | 工作（6/6）|
| 执行者 executor | corrector 产出只读 action | `formatExecutorResult` 注入 | 工作 |
| 验收员 verifier | `wait_agent`×2 超时 | `[harness 代验收]` 注入 | **触发路径脱节，从未命中** |

【推断】Critic 0% 成功率是最大的实质问题——54 次调用全部空返回，且它只在 present 前触发，
可能当时服务恰好都不稳定；也可能是 prompt 太长（inChars 大）导致模型不稳定。
需要单独复现验证（建议用稳定期手动触发一次 Critic）。

---

### 问题 5：每次答完能不能把中间过程折叠起来？

**结论：能，dsh 已支持且我们已开了 compact，但有两个配置没调到最激进。**

【事实】官方 `ui-chat` 有三个配置（chat-settings.ts）：
- `transcriptView`: compact / standard / detailed / verbose —— profile 已设 **compact** ✅
- `collapseTiming`: completion（完成时折叠）/ next-input（下次输入才折叠）—— **未设**，默认 completion ✅
- `foldedReplies`: all（保留所有 assistant 回复）/ final（只留最终回答）—— **未设，默认 all** ❌

【事实】官方折叠规则（2026-08-14 设计文档）：compact 模式下，轮次打开时全展开；
`turn/end` 时若最后一步是"面向用户的 Assistant 回复且不含工具调用"，前面的注入/推理/早期回复/工具行
统一收进一个过程 disclosure。**系统提示词、用户消息、steering 消息永远独立不折叠。**

【推断】用户看到的"一堆中间过程"可能是因为：
① 默认 `foldedReplies=all` 保留了所有 assistant 中间回复；
② 很多轮次最后一步是工具调用而非正文 → 不满足"最终正文边界"条件 → 整个轮次不折叠（官方："没有最终正文的轮次保留全部过程证据"）。

**可改**：在 profile 的 `ui-chat` config 加 `foldedReplies: final`（只留最终回答）。
②是官方设计，无法配置绕过——要确保模型答完时最后一步是纯正文回复（verify-on-stop 已经有类似约束）。

---

### 建议的修复动作（按优先级）

| # | 动作 | 位置 | 风险 |
|---|---|---|---|
| 1 | 存档去重：相同 todo 签名的存档只注入一次，后续改为简短"存档未变化+N次"提示 | index.mjs P0 存档段 | 低（纯文本逻辑）|
| 2 | `foldedReplies: final` 加到 profile ui-chat config | profile cordis.patch.yml | 低（UI 配置，需重启 dsh）|
| 3 | 验收员触发从 `wait_agent` 扩展到 `spawn_teammate` 的完成检测 | index.mjs | 中（需理解 spawn 事件语义）|
| 4 | 角色 LLM 失败时记录明确 trace 字段（error/code），不再静默 | callLLMOnce | 低 |
| 5 | Critic 0% 成功率根因调查（手动触发复现） | 专项 | 中 |

本文为诊断；修复实施见后续 commit。

---

### 补记（2026-11-21）：受控单卡试跑实证 —— S23 自主推卡

**设置**：新会话 `session-501ca858`，投递一条受控指令"推进当前卡 S23"，全程旁站，不改状态、不干预。
**结果**：✅ **成功**。35B 自己创建 `tools/prefix_stability_probe.py`（145行）+ `tools/test_prefix_stability.py`（78行），
自跑 `--dry-run` 后 S23 判据全绿（file_exists + test_pass PASS=3）。耗时约 10 分钟，115 个事件序列。

**事件流里观察到的污染/纠正模式（一手数据）**：
- step 5-7：模型连续 3 步卡在"找 S23 定义"——路径记错、参数写错，反复 grep/read 同一文件
- step 7：harness **独立纠正器**介入（`[harness 系统修正] ... 请原样调用`），把它拉回正确工具调用
- step 8：**控制回合**触发（"你现在处在第 8 步，先做元决策"），注入 ①已确立 ③已排除 ④下一步
- step 9：**状态复述**注入 todo 清单 → 模型立刻停止探测，开始写文件，之后一路完成

**结论**：
1. **单会话内的主要污染源不是"旧历史"，而是"当前任务内的重复探测循环"**。即使全新会话也会自制造噪声。
2. **有效的干预是结构化的、确定性的**：复述 todo / 排除项 / 下一步 > 让它自己"想一想"。
   这与记忆里"别依赖模型元认知，用规则驱动"完全一致。
3. 现有 harness 的纠正器 + 控制回合 + 状态复述三件套已经起了作用——**不需要开新会话来治这个病**，
   需要的是把这三件套的触发更快、更省 token（step 5 就该介入，而不是 step 7）。

---

## 原报告：`CADENCE_AUDIT.md`

## 自动化频次审计（数据底稿，2026-11-19）

> 本文只记录**可核验的事实**（代码当前值 + `_trace.jsonl` 真实触发数）。
> 科学依据与调整建议见 [CADENCE_REDESIGN.md](#原报告CADENCE_REDESIGN)（等社区/论文调研合并后写）。
> 数据来源：`index.mjs` DEFAULTS、10 个会话的 `_trace.jsonl`（5538 行，2026-11-17 17:26 ~ 11-18 16:41）。

### 一、代码里的全部频次参数（现状）

#### 运行时注入类（有 token 成本）

| 参数 | 当前值 | 触发条件 | 会话上限 |
|---|---|---|---|
| `controlEverySteps` | 8 | 每 8 步 | `maxControlPerSession=24` |
| `mindStateLoopThreshold` | 3 | 跨步重复 3 次 | `maxMindStateInjections=6` |
| `verifyOnStop` | 写后无验证 | 每轮最多 | `maxVerifyOnStopSteers=2` |
| `feedbackMaxInjectPerSession` | 2 | 学习回注 | 2 |
| `maxSkillCardsPerSession` | 2 | 技能卡 | 2 |
| `dangerGuardMaxPerSession` | 5 | 危险操作 | 5 |
| `maxTodoInjectionsPerSession` | 4 | todo 闹钟 | 4 |
| `maxPresentGatePerSession` | 2 | 交付闸门 | 2 |
| `noTodoStepThreshold` / `staleStepThreshold` | 4 / 5 | 无 todo / todo 陈旧 | — |
| `maxInjectionsPerTurn` / `maxInjectionsPerSession` | 1 / 4 | 全局注入预算 | 4 |
| `sharedMaxPerTurn` | 3 | 每轮共享预算 | — |

#### LLM 调用类（有金钱/时间成本，每次 10-20s）

| 参数 | 当前值 | 触发条件 | 会话上限 |
|---|---|---|---|
| `auditEverySteps` | 8 | 每 8 步 | — |
| `auditEveryStepsAnomaly` | 4 | 异常时每 4 步 | — |
| `auditEvidenceRounds` | 2 | 审计证据轮数 | — |
| `maxCriticPerSession` | 2 | present 前 | 2 |
| `maxPlannerCheckPerSession` | 1 | 规划检查 | 1 |
| `jsonRetryTimes` | 1 | JSON 解析失败 | — |

#### 旁路类（零运行时 token）

| 机制 | 频率 | 说明 |
|---|---|---|
| `learn_watcher.py` | `INTERVAL=30s`；低频诊断每 30 轮≈15 分钟 | 心跳日志每 30s 一条 |
| `freeze_watch.py` | `POLL=8s`、`STUCK_SEC=120s`、`COOLDOWN=300s` | 真冻结才重启 |
| `gpu_engine_guard.py` | `GG_POLL=1.5s`、`SUSTAIN=3`、`COOLDOWN=20s` | 引擎争抢时降帧 |
| 压缩 | `thresholdRatio=0.55`（54K） | retain 16384 + headroom 16384 |

### 二、真实触发数据（5538 行 trace）

全局分布：

| 机制 | 次数 | 占比 | 有无 LLM |
|---|---|---|---|
| tool_call | 3249 | 58.7% | — |
| tool_result | 1457 | 26.3% | — |
| fep_cycle | 325 | 5.9% | 无（只记 trace）|
| llm | 212 | 3.8% | **有** |
| control_turn | 139 | 2.5% | 无（零 LLM）|
| skill_card | 71 | 1.3% | 无 |
| mind_state | 43 | 0.8% | 无 |
| verify_on_stop | 21 | 0.4% | 无 |
| crit_hit | 13 | 0.2% | 无 |
| learn_feedback | 8 | 0.1% | 无 |

LLM 调用按用途：audit 82、corrector 72、critic 52、planner 6 —— **共 212 次**。

#### 重点会话 s1（3057 步，占全部工具调用的 94%）

| 机制 | 次数 | 折算频次 | 观察 |
|---|---|---|---|
| LLM 调用（audit 71 + corrector 65 + critic 52）| **188** | **每 16 步一次** | 长会话最重成本 |
| control_turn | 126 | 1/24 步 | ⚠ **注意**：trace 的 `step` 每轮 turn/start 重置（实测在 0-8 循环），`controlTotal` 是 state 级会话累计；此 126 次可能是同一 sid 多轮/旧 sid 复用所致，**不能据此推断上限掐断** |
| fep_cycle | 314 | 1/9 步 | 最高频，但零 LLM |
| mind_state | 40 | 1/76 步 | — |
| skill_card | 63 | 1/48 步 | — |
| verify_on_stop | 19 | 1/160 步 | — |
| learn_feedback | 0 | — | 长会话期间学习回注未命中（旁路 watcher 去重/无新沉淀）|

### 三、从数据直接可见的问题（不含外部理论）

1. **（已排除）控制回合上限掐断**：初看 s1 的 126 次 control_turn 恰好 = 上限 24 的倍数，怀疑被掐断；核实后 `step` 每轮重置、`controlTotal` 按 state 累计，126 次是"多轮累计"而非单会话超限。**此项不是问题**，但暴露 trace 缺少 `turn` 字段，无法从数据直接区分"跨轮"与"跨会话"——建议后续补记。
2. **LLM 审计密度过高**：188 次 audit/corrector/critic 对 3057 步 = 每 16 步一次，每次 10-20s。若按 15s/次算，s1 仅 LLM 机制就花 ~47 分钟。需要核实这些调用的边际收益。
3. **`auditEverySteps` 与 `auditEveryStepsAnomaly` 双轨**（8 / 4）但 trace 里 audit 82 次集中在 s1——尚无法区分是正常轨还是异常轨触发，需要加 trace 字段才能判断。
4. **学习回注在最长会话里 0 次**：`learn_feedback` 全局仅 8 次且不在 s1——学习闭环对正在跑的长任务**没有实时反馈**，只有跨会话的沉淀。
5. **FEP 每 9 步一次但只记 trace**：符合 ADR-0017"学习信号不占注入通道"的设计，但需确认 B 段 watcher 真的消费了这 325 条（目前 `new_hits=0 new_outcomes=0`，说明是消费后的稳定态）。

> 待调研合并：社区/论文对反思、审计、巩固、压缩、注入频率的实验数据，见 [CADENCE_REDESIGN.md](#原报告CADENCE_REDESIGN)。

---

## 原报告：`CADENCE_REDESIGN.md`

## 自动化频次重设：结论与依据（2026-11-19）

> 数据底稿见 [CADENCE_AUDIT.md](#原报告CADENCE_AUDIT)（代码当前值 + 5538 行 trace 的真实触发数）。
> 本文给出**哪些该改、哪些不该动**，每条注明是"实测数据"还是"社区依据"还是"设计权衡"。

### 一、总原则：按"成本 × 边际收益"分层，不是拍脑袋定数字

自动化机制分三类，**频次策略完全不同**：

| 类别 | 例子 | 成本 | 频次策略 |
|---|---|---|---|
| **零成本确定性** | fep_cycle 记录、crit_hit 命中、tool trace | 0 LLM，仅 IO | 可以高频（每步），但**只进 trace/队列，不占注入通道** |
| **零 LLM 注入** | control_turn、mind_state、todo 闹钟、skill_card | 消耗 token/注意力 | 中频 + 会话上限；**按 token 预算而非次数**更科学 |
| **有 LLM 调用** | audit、critic、corrector、planner | 10-20s + 钱 | 低频 + 门控触发；**只在边际收益高于成本时调用** |

社区共识（Generative Agents / Reflexion / ExpeL / Letta）：**事件驱动的巩固 + 低频周期性反思**，
而非固定每 N 步无差别触发。我们大部分机制已符合，问题集中在几处。

### 二、审计结论：不该动的（有依据，别手贱改）

| 参数 | 现值 | 结论 | 依据 |
|---|---|---|---|
| `controlEverySteps` | 8 | ✅ 合理 | 每 8 步元决策是社区常见节奏；零 LLM，成本低 |
| `maxControlPerSession` | 24 | ✅ 合理 | 实测 s1 的 126 次是**跨轮累计**（step 每轮重置），非单会话超限；24 覆盖 3 个 8 步轮次 |
| `auditEverySteps` / `Anomaly` | 8 / 4 | ✅ 保留 | 异常时加密是真门控语义；trace 里 audit 82 次说明触发正常 |
| `maxCriticPerSession` | 2 | ✅ 合理 | Critic 有 LLM 成本；present 前 ≤2 次是成本-收益平衡点 |
| `verifyMinWaits` | 2 | ✅ 合理 | 二次升级拦截已被真实验证（write→运行→读回链） |
| `mindStateLoopThreshold` | 3 | ✅ 合理 | 3 次重复才算循环，避免误报；实测 mind_state 仅 43 次（0.8%）|
| `specAcceptanceMin` | 0.65 + 分类阈值 | ✅ 合理 | 分类阈值已按任务类型细化（对话 0.70/代码 0.60/创意 0.50）|
| `jsonRetryTimes` | 1 | ✅ 合理 | 解析失败重试 1 次是社区标准，多了徒增延迟 |
| 压缩 `thresholdRatio` | 0.55 | ✅ 合理 | 54K 触发 + retain 16384 + headroom 16384，`CTX_CHECKPOINTS=2` 是承重墙（实测降到 1 → +23% 耗时）|
| `freeze_watch` POLL/STUCK | 8s / 120s | ✅ 合理 | 真冻死才重启；COOLDOWN 300s 防抖 |

### 三、该改的（3 项，按 ROI）

#### 1. `learn_watcher.py`：每 30s 全量巩固 → 三层频率（**已改**）

**问题**：原实现每 30s 跑全部 8 个脚本（skill_draft / crit_revision / trace_timeline / session_tree /
episodic_index / intent_drift / mind_state / crit_decay），但心跳日志常见 `new_hits=0 new_outcomes=0`——
**无新数据时纯属空转**。记忆巩固的社区惯例是"事件触发 + 周期性离线巩固"，不是每 30s 全量重跑。

**改造**（2026-11-19，本版本）：
- **心跳层**（30s）：只查 `_pending_learn.jsonl` / `_outcome.jsonl` 的 offset，零新数据几乎零成本。
- **事件驱动层**（有新数据才跑）：`settle_crit_hits` + 轻量沉淀（skill_draft / crit_revision / trace_timeline）。
- **巩固层**（每 20 轮 ≈ 10 分钟）：`session_tree` / `episodic_index` / `intent_drift` / `mind_state`——
  这些扫全部会话根、无新数据时结果不变，每 30s 跑是浪费。
- 常量：`CONSOLIDATE_EVERY=20`（可用环境变量覆盖，预留）。

**验证**：语法 OK；心跳日志应继续按 30s 输出，但 `[deep]` 标记每 20 轮才出现一次。

#### 2. 注入预算从"次数"升级为"token 感知"（**建议，未实施**）

**问题**：`maxInjectionsPerTurn/Session` 按**次数**计数，但一条 200 token 的 skill_card 和一条
1500 token 的控制回合摘要花同样的"1 次预算"——预算与真实成本脱节。社区（token-aware parsing,
llama.cpp #29307 未合并）方向是按 token 计量。

**建议**：在 `workspaceSnapshot` 里加 `injectionTokensUsed`，每次注入按 `estimateTokens(text)` 累加，
预算改为 `maxInjectionTokensPerTurn`（如 800）。**但**：这需要在 apply 层改注入路径，风险中等，
且需端到端验证不误挡 verify-on-stop 这类安全注入——列为中期目标，不急着做。

#### 3. trace 补 `turn` 字段（**建议，未实施**）

**问题**：审计频次时无法从 trace 区分"同一会话跨 16 轮"与"单会话跑 3057 步"——`step` 每轮重置，
`controlTotal` 是 state 级但没进 trace。这导致我初判"控制回合被上限掐断"，核实后才排除。

**建议**：`trace()` 记录加 `turn: s.turn` 和 `controlTotal: s.controlTotal`（每事件多 2 个数字，零成本）。
这样频次审计可以直接从数据算，不用反推。列为短期小改动。

### 四、明确不改的"看起来像问题"

- **188 次 LLM 调用 / 3057 步（每 16 步一次）**：看似昂贵，但 s1 是 3057 步的超长任务（占全部数据 94%），
  复杂任务本来就需要更多审计；且 audit/corrector/critic 是**门控触发**（异常才调），不是无差别每 8 步。
  没有证据表明该降频——**先加 trace 字段看清触发原因，再谈调整**。
- **`fep_cycle` 每 9 步一次**：最高频但零 LLM，且 B 段 watcher 已消费（心跳显示稳定态），符合设计。
- **`learn_feedback` 在 s1 为 0**：学习回注是跨会话沉淀，不对正在跑的长任务实时生效——这是设计边界
  （ADR-0017：学习信号不占运行时注入通道），不是 bug。

### 五、验证清单

改频次后必须确认（防"调了频次但机制失效"）：
1. `python tools/regression_check.py` → 30/30
2. 6 个单测 → 0 FAIL（尤其 test_new_guards 的 D5 审计、test_short_term_goals）
3. 重启 dsh 后探针 flag 全 true
4. learn_watcher 心跳日志：30s 一条，`[deep]` 每 10 分钟一次
5. 真实长任务 trace：control_turn / audit 分布合理，无"整段空窗"

相关：[CADENCE_AUDIT.md](#原报告CADENCE_AUDIT)（数据底稿）· [ROADMAP](../ROADMAP.md) · [ADR-0017](../decisions/0017-gwt-first-then-fep.md)

---

## 原报告：`MECHANISM_TRIGGER_AUDIT_20261120.md`

## 机制触发效果审计（2026-11-20 20:30）

> 用户："继续让它推卡，你继续观察，着重留意它的表现，以及之前所有功能的触发效果。"
> 方法：证据分层——真实 trace 的 kind 分布（过滤测试 sid）+ 代码 trace 打点 + 时间戳交叉。
> 铁律：文档宣称完成 ≠ 代码实际生效；health 200 ≠ 进程活着；进了 prompt ≠ 评审真的用了。

### 1. 真实 trace 概况

`D:/Brain/workspace/bench/_trace.jsonl`：总 15914 行，过滤测试 sid（s1/b/b7332eb6/budget-4/fb/r）后**真实 2555 行**（测试假数据占 84%——再次印证证据分层必要性）。

真实 sid 的 kind 分布（全时段）：

| kind | 次数 | 说明 |
|---|---|---|
| tool_result / tool_call | 1069 / 965 | 主流程 |
| injection_hit | 281 | 注入检测 |
| fep_cycle | 48 | 预期-观察闭环 |
| llm | 46 | 所有 LLM 调用（含 Critic/Planner）|
| mind_state / control_turn | 36 / 32 | 心智信号 / 控制回合 |
| **crit_hit** | 23 | **CritBank 教训命中（不是 Critic 产物评审）**|
| skill_card | 20 | 技能卡 |
| learn_feedback / review_state | 9 / 8 | 学习队列 / 评审状态 |
| archive_dedup / verify_on_stop | 7 / 5 | 存档去重 / 停止前验证 |
| review_echo / evidence_cited | 4 / 2 | 评审回显 / 证据引用 |

### 2. 今天推卡时段（UTC 12:00-12:30 = 北京 20:00-20:30）的真实触发

| 机制 | 触发 | 证据 |
|---|---|---|
| control_turn（控制回合）| ✅ 2 次 | 12:08:34 / 12:27:24 |
| injection_hit（注入检测）| ✅ 6 次 | 12:21-12:26 连续 |
| review_state / review_echo | ✅ 各 1 次 | 12:11:41 / 12:18:56 |
| crit_hit | ✅ 1 次 | 12:11:41，id=C-001（CritBank 教训，非 Critic 评审）|
| **verify_on_stop** | ❌ 今天无 | 最后 5 次不在本时段 |
| **Critic 第6维「规则-实例一致性」** | ❓ **无法验证** | 见下 |
| **Planner「假设披露」** | ❓ **无法验证** | 见下 |

### 3. 关键缺口：新 rubric 进了 prompt，但没有可观测的触发证据

代码证据：
- `CRITIC_PROMPT`（index.mjs:1381）把 `CRITIC_RUBRIC.dimensions` 全部展开进 prompt——新第6维**确实被送进去了**
- `PLANNER_PROMPT`（index.mjs:1353）同样展开 `PLANNER_RUBRIC.rules`——假设披露**确实被送进去了**
- 但 `runCritic`（1409）和 `runPlannerCheck`（1362）只调用 `callLLM(..., {tag:'critic'|'planner'})`，
  而 callLLM 的 trace 只记 `kind:'llm'`——**没有记录 rubric 版本、判了哪些维度、结论是什么**

后果：无法回答"第6维今天到底有没有拦下一次违规"——这正是用户要的"触发效果"。
按证据分层铁律，这属于"写到了 prompt 但没有独立产物/打点"，不能算真实生效。

### 4. 提议新卡：A1_7「评审机制可观测性」

- what：给 Critic/Planner 调用加专属 trace 打点（rubric_version / dimensions_checked / verdict / 触发的 gate），
  让每个评审机制有可审计的触发证据
- why：今天加的两个维度无法验证是否生效；没有打点就无法做证据分层，只能靠"代码里进了 prompt"自我安慰
- verify：① trace 里出现 `critic_review` / `planner_check` kind ② 打点含 rubric_version 字段 ③ 构造测试触发一次评审后能在 trace 查到
- caveat：别把 trace 写成"存在即成功"——要记录 verdict 和具体维度，否则又是假绿

### 5. 对 agent 表现的观察（同步记录）

会话 session-0428ceab：20:29:47 复活并写 todo 准备"编写 check_verify.py"——但 A1_5 已由 observer 完成并推送。
它不知道外部状态变化，正在重做旧任务。已投递引导消息转向 A1_6（20:31:15），产物做了快照保护
（`D:/Brain/_cleanup_20261118/check_verify.protected.py`）。

这是"会话无共享状态"问题的又一次实证——M10（会话生命周期治理）的必要性再加一条证据。
