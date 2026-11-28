# ADR-0020：启用反思回注（reflectionInjectEnabled=true），接受方向性结论

- 状态：accepted
- 日期：2026-11-29
- 决策者：项目所有者选 B（在 95% 把握未达的情况下接受方向性结论）

## Context（背景）

多轮 A/B 实验想回答"反思捕获 → 即时回注是否改善 agent 行为"。
实验遇到两个障碍：
1. **实验基础设施 bug（已修）**：runner 超时 240s 短于正常任务 243s，且超时后不 cancel 会话，
   导致残留会话累积到 14 个抢 llama 单槽位，雪球式超时被误判为"dsh 冻死"。
   根因见 [FREEZE_ROOTCAUSE](../docs/FREEZE_ROOTCAUSE_20261128.md)，修复后 45%→0%。
2. **效应量缩水**：早期小样本（n=74）显示 off 33% vs inject 4%（29pp，曾显著 p=0.028），
   随样本增加效应量持续缩小并稳定在 14pp。

最终 268 组有效样本（off 89 / on 88 / inject-on 91，同批次随机化，动态开关），结果：

| 指标 | off | on | inject-on |
|---|---|---|---|
| 硬停率（主） | 40% | 41% | **26%** |
| 答案正确率 | 9% | 10% | 9% |
| tool_calls | 6.04 | 6.45 | 6.21 |
| 新错误类型 | — | — | 无组间恶化 |

统计：off vs inject-on Fisher p=0.058，**Holm 校正后 p=0.125，未达 95% 显著**。
按当前效应量（14pp）power=0.95 需 n=289/组（约为已跑样本的 3 倍）。
全部细节见 [AB_FINAL](../docs/AB_FINAL_20261128.md)。

## Decision（决定）

1. **接受方向性结论，启用回注**：把 `index.mjs` 的 `reflectionInjectEnabled` 默认值改为 `true`，
   生产环境启用"反思捕获 → 即时回注"。
2. **删除 `_ab_mode.json`**（备份为 `.bak-20261129`），让生产回退到 cfg 默认值——
   否则该文件残留的 `off` 会强制关闭 mining 和 inject，覆盖 DEFAULTS。
3. **三副本同步**：权威源（publish）与运行版（node_modules）`index.mjs` SHA256 一致后重启 dsh。
4. **诚实标注**：这是**方向性证据，非统计显著**——任何对外描述都必须写明"硬停率降 14pp 但未达 95% 把握"。

## Consequences（后果）

- 正面：硬停率方向稳定下降（40%→26%），质量指标持平、新错误类型无恶化——
  以零质量代价换取更少的卡死。回注链路此前已验证真实触发（`reflection_live_injected` 埋点）。
- 负面：
  - **未达统计显著**（Holm p=0.125），存在小样本高估后效应仍不真实的风险（虽已排除早期假阳性）。
  - 对答案正确率**毫无帮助**（三组均 9%）——不要把回注描述成"提升答案质量"。
  - 回注带来额外 token 与延迟（本次未量化）。
- 验证：重启后 `_agent_harness_loaded.json` 显示 `reflectionInjectEnabled: true`、
  `reflectionMiningEnabled: true`；回归 25/21/9/7 全 PASS；`_ab_mode.json` 不存在。
- 回退：若出现质量下降或 token 暴涨，把 `reflectionInjectEnabled` 改回 `false` 并重启 dsh。

## 备注：为什么不继续跑到显著

按当前效应量还需约 600 会话（35 小时），边际收益低：
方向已跨多批次一致，且质量/新类型护栏均无恶化。用户选择接受方向性结论。
若未来有新证据（如换更敏感判据、或效应量回升），可用 ADR 更新本决策。
