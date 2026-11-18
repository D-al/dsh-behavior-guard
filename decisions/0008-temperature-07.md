# ADR-0008：Q4 温度定 0.7

- 状态：accepted
- 日期：2026-11-10
- 决策者：用户 + 助手（实测验证）

## Context
温度扫描呈 U 形：0.1 想完不干（683 字计划后 EOS），0.9 草率收工。

## Decision
Q4 定 0.7，P3/P4/P5 三项 2/2 且最快。

## Consequences
- 温度是主导变量（> 量化档位）
- .env 的 LLAMA_35B_TEMP 必须留空（CLI 会覆盖 preset）
