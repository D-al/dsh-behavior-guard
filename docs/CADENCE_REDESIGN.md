# 自动化频次重设：结论与依据（2026-11-19）

> 数据底稿见 [CADENCE_AUDIT.md](CADENCE_AUDIT.md)（代码当前值 + 5538 行 trace 的真实触发数）。
> 本文给出**哪些该改、哪些不该动**，每条注明是"实测数据"还是"社区依据"还是"设计权衡"。

## 一、总原则：按"成本 × 边际收益"分层，不是拍脑袋定数字

自动化机制分三类，**频次策略完全不同**：

| 类别 | 例子 | 成本 | 频次策略 |
|---|---|---|---|
| **零成本确定性** | fep_cycle 记录、crit_hit 命中、tool trace | 0 LLM，仅 IO | 可以高频（每步），但**只进 trace/队列，不占注入通道** |
| **零 LLM 注入** | control_turn、mind_state、todo 闹钟、skill_card | 消耗 token/注意力 | 中频 + 会话上限；**按 token 预算而非次数**更科学 |
| **有 LLM 调用** | audit、critic、corrector、planner | 10-20s + 钱 | 低频 + 门控触发；**只在边际收益高于成本时调用** |

社区共识（Generative Agents / Reflexion / ExpeL / Letta）：**事件驱动的巩固 + 低频周期性反思**，
而非固定每 N 步无差别触发。我们大部分机制已符合，问题集中在几处。

## 二、审计结论：不该动的（有依据，别手贱改）

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

## 三、该改的（3 项，按 ROI）

### 1. `learn_watcher.py`：每 30s 全量巩固 → 三层频率（**已改**）

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

### 2. 注入预算从"次数"升级为"token 感知"（**建议，未实施**）

**问题**：`maxInjectionsPerTurn/Session` 按**次数**计数，但一条 200 token 的 skill_card 和一条
1500 token 的控制回合摘要花同样的"1 次预算"——预算与真实成本脱节。社区（token-aware parsing,
llama.cpp #29307 未合并）方向是按 token 计量。

**建议**：在 `workspaceSnapshot` 里加 `injectionTokensUsed`，每次注入按 `estimateTokens(text)` 累加，
预算改为 `maxInjectionTokensPerTurn`（如 800）。**但**：这需要在 apply 层改注入路径，风险中等，
且需端到端验证不误挡 verify-on-stop 这类安全注入——列为中期目标，不急着做。

### 3. trace 补 `turn` 字段（**建议，未实施**）

**问题**：审计频次时无法从 trace 区分"同一会话跨 16 轮"与"单会话跑 3057 步"——`step` 每轮重置，
`controlTotal` 是 state 级但没进 trace。这导致我初判"控制回合被上限掐断"，核实后才排除。

**建议**：`trace()` 记录加 `turn: s.turn` 和 `controlTotal: s.controlTotal`（每事件多 2 个数字，零成本）。
这样频次审计可以直接从数据算，不用反推。列为短期小改动。

## 四、明确不改的"看起来像问题"

- **188 次 LLM 调用 / 3057 步（每 16 步一次）**：看似昂贵，但 s1 是 3057 步的超长任务（占全部数据 94%），
  复杂任务本来就需要更多审计；且 audit/corrector/critic 是**门控触发**（异常才调），不是无差别每 8 步。
  没有证据表明该降频——**先加 trace 字段看清触发原因，再谈调整**。
- **`fep_cycle` 每 9 步一次**：最高频但零 LLM，且 B 段 watcher 已消费（心跳显示稳定态），符合设计。
- **`learn_feedback` 在 s1 为 0**：学习回注是跨会话沉淀，不对正在跑的长任务实时生效——这是设计边界
  （ADR-0017：学习信号不占运行时注入通道），不是 bug。

## 五、验证清单

改频次后必须确认（防"调了频次但机制失效"）：
1. `python tools/regression_check.py` → 30/30
2. 6 个单测 → 0 FAIL（尤其 test_new_guards 的 D5 审计、test_short_term_goals）
3. 重启 dsh 后探针 flag 全 true
4. learn_watcher 心跳日志：30s 一条，`[deep]` 每 10 分钟一次
5. 真实长任务 trace：control_turn / audit 分布合理，无"整段空窗"

相关：[CADENCE_AUDIT.md](CADENCE_AUDIT.md)（数据底稿）· [ROADMAP](../ROADMAP.md) · [ADR-0017](../decisions/0017-gwt-first-then-fep.md)
