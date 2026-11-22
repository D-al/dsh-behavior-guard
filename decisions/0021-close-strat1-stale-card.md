# ADR-0021：关闭陈旧卡 STRAT1（战略陈述已由 ADR-0020 落地）

- 状态：accepted
- 日期：2026-11-22
- 决策者：用户（显式批准："陈旧卡关了；跑一次真实决策环"，2026-11-22 14:31）
- 决策层级：一般决策 G（状态同步，非新方向）
- 支撑决策：ADR-0020（战略目标 v3.1 落地）

## Context（背景）
STRAT1「战略陈述（模型只读顶层约束）」判据两条全过：
- `STRATEGY.md` 存在 ✅
- `tools/consistency_guard.py` 含 STRATEGY 校验（3 hits）✅

其交付物已由 ADR-0020（commit c3ef93f）落地——STRATEGY.md §0/§2.1 已换成 v3.1 目标与 6 个二值 KR。
但卡状态仍是 `ready`——典型陈旧卡。

卡标记 `autonomous=false` + 触及元治理，`cmd_claim` 会拒绝自动领取。
`cmd_apply` 无 autonomy 校验，故**禁止用自动环代关**（防绕过治理锁）。

## Options
| 方案 | 做法 | 结论 |
|---|---|---|
| A 自动环代关 | 手工切 doing 再 apply | ❌ 绕过 autonomous=false 治理锁 |
| B 人工按 ADR 写回 done（选中）| 人类批准 + ADR 留痕 + 直接改权威源 | ✅ |

## Counter-evidence（反证）
- **反对本决策的最强理由**：STRAT1 虽判据全过，但"交付物存在"是弱证据——STRATEGY.md 在但可能与 v3.1 目标不一致。若如此，关卡会掩盖目标漂移。
- **什么信号会翻案**：若 ADR-0020 被撤销、或 STRATEGY.md §0 回退到旧目标，则恢复 STRAT1 为 ready 重新验收。
- **汇聚独立性**：判据(STRATEGY存在+consistency_guard 3hits)与 ADR-0020 同源于本会话，独立性有限；用户显式批准是外部锚点。

## Decision
用户显式批准后，将 STRAT1 状态从 `ready` 写回 `done`，`done_at` 记当前时间，
`evidence_log` 记本 ADR 编号 + commit。不经过自动 claim/apply。

## Consequences
- 正面：消除陈旧卡，卡状态与交付物一致。
- 负面：这是人工状态写入，须 ADR 留痕（本文件即留痕）。
- 验证：`roadmap_check --verify STRAT1` 判据全过；三源判据一致。
