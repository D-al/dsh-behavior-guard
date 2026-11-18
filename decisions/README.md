# 决策档案（ADR）

> Architecture Decision Records——每个"为什么这么决定"一条，**accepted 后不改原文**。
> 要改变主意：写新 ADR 并在旧条目标 `superseded by`。
> 格式遵循 [MADR](https://adr.github.io/madr/)（Context / Decision / Consequences）。

## 索引

### 配置与引擎（tuning）

| ADR | 决定 | 状态 | 日期 |
|---|---|---|---|
| [0001](0001-adopt-llama-server.md) | 选 llama-server 主线，不走 vLLM/LM Studio | accepted | 10-19 |
| [0002](0002-q8-kv-flash-attention.md) | q8_0 KV + Flash Attention 破 32K OOM | accepted | 10-19 |
| [0003](0003-ncpu-moe-40-cache-2736.md) | n-cpu-moe 40 / cache 2736（经复测翻案）| accepted | 10-27 |
| [0004](0004-reject-whole-layer-gpu.md) | 拒绝整层挪 GPU（A/B 证伪 -9.5%）| rejected | 10-27 |
| [0005](0005-mmproj-offload.md) | MMPROJ_OFFLOAD=1（归因翻案）| accepted | 11-06 |
| [0006](0006-chinese-anchor-self-narration.md) | 中文锚点必须是自述句 | accepted | 11-07 |
| [0007](0007-reject-moe-cpu-share.md) | 拒绝 moe-cache-cpu-share=1.0（端到端慢 2.4×）| rejected | 11-18 |
| [0008](0008-temperature-07.md) | Q4 温度定 0.7（U 形曲线）| accepted | 11-10 |
| [0009](0009-local-searxng-provider.md) | 本地 SearXNG 替换内置搜索 provider | accepted | 10-16 |
| [0010](0010-4b-not-lightweight.md) | 4B 不是"超轻量秒回" | accepted | 10-14 |

### 架构与治理

| ADR | 决定 | 状态 | 日期 |
|---|---|---|---|
| [0011](0011-single-model-multi-role.md) | 单权重多角色 conditioning，不搞多 agent | accepted | 11-17 |
| [0012](0012-deterministic-gates-first.md) | 确定性门控优先，LLM 只在必要时介入 | accepted | 11-18 |
| [0013](0013-append-only-injection.md) | append-only 注入，不改写历史 | accepted | 11-17 |
| [0014](0014-reject-forced-choice-injection.md) | 撤销"强制二选一"，改中性事实陈述 | supersedes 旧注入策略 | 11-18 |
| [0015](0015-skill-promotion-approval.md) | 技能写回必须审批，草稿不直接生效 | accepted | 11-18 |
| [0016](0016-portable-paths.md) | p/ 指向稳定路径，junction 建在稳定根 | accepted | 11-18 |

## 怎么记一条新决策

复制 [_ADR-TEMPLATE.md](_ADR-TEMPLATE.md)，编号 +1，写清 Context / Decision / Consequences。
**关键**：把"被推翻的决策"也记下来（状态 rejected/superseded）——负面资产和成功决策同等重要。
