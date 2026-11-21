# 压缩触发、重复工作、角色可见性、过程折叠：诊断报告（2026-11-19）

> 全部结论基于真实代码（`index.mjs`）+ 生产配置（profile `cordis.patch.yml`）+ 5538 行 trace + 110 条压缩账本。
> 区分【事实】（数据/代码直接可见）与【推断】（需进一步验证）。

---

## 问题 1：写入/读取文件时触发压缩——是设计还是 bug？

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

## 问题 2：压缩会不会导致重复干同一件事？

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

## 问题 3：验收员有发挥作用吗？为什么没看到注入？

**结论：验收员在稳定服务期工作，但整体成功率低；看不到注入有三层原因。**

### 3.1 触发条件与实际工具面脱节【事实】
验收员（代验收）的触发条件是：`wait_agent` 工具连续 `verifyMinWaits=2` 次 UNPRODUCTIVE
（index.mjs:992）。但 5538 行 trace 里 **`wait_agent` 调用 0 次**——
实际工作流用的是 `spawn_teammate`（73 次），不是 `wait_agent`。
→ **验收员的主触发路径在当前环境永远不会被命中**。这是角色设计与实际工具面的脱节。

### 3.2 角色 LLM 调用大量失败【事实】

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

### 3.3 注入是"只在发现问题才出现"【事实】
审计员走 `runAudit()` → 只有 `verdict === 'ISSUE'` 才产出注入文本（`[harness 独立审计]`），
`UNCERTAIN`（证据不足）直接弃权、`OK` 不注入（index.mjs:1896-1955）。
→ 用户看不到 = 大部分时候没有 ISSUE，或 ISSUE 因 LLM 失败没产出。**这是设计使然，不是角色没接。**

---

## 问题 4：其他角色呢？

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

## 问题 5：每次答完能不能把中间过程折叠起来？

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

## 建议的修复动作（按优先级）

| # | 动作 | 位置 | 风险 |
|---|---|---|---|
| 1 | 存档去重：相同 todo 签名的存档只注入一次，后续改为简短"存档未变化+N次"提示 | index.mjs P0 存档段 | 低（纯文本逻辑）|
| 2 | `foldedReplies: final` 加到 profile ui-chat config | profile cordis.patch.yml | 低（UI 配置，需重启 dsh）|
| 3 | 验收员触发从 `wait_agent` 扩展到 `spawn_teammate` 的完成检测 | index.mjs | 中（需理解 spawn 事件语义）|
| 4 | 角色 LLM 失败时记录明确 trace 字段（error/code），不再静默 | callLLMOnce | 低 |
| 5 | Critic 0% 成功率根因调查（手动触发复现） | 专项 | 中 |

本文为诊断；修复实施见后续 commit。

---

## 补记（2026-11-21）：受控单卡试跑实证 —— S23 自主推卡

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
