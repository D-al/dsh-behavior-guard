# ADR-0007：拒绝 moe-cache-cpu-share=1.0

- 状态：rejected
- 日期：2026-11-18
- 决策者：用户 + 助手（实测验证）

## Context
该参数让 decode t/s **+37%**，看似纯赚。

## Decision
端到端 P5 基准实测**慢 2.4 倍**（每步增量 prefill 慢 4-5×）。生产保持 0。

## Consequences
- 确立铁律：decode t/s 是误导性指标，任何加速必须端到端验证
- 改变了整个项目的验证文化：此后所有优化都用 P3/P4/P5 判定
