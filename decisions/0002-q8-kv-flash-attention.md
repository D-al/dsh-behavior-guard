# ADR-0002：q8_0 KV + Flash Attention

- 状态：accepted
- 日期：2026-10-19
- 决策者：用户 + 助手（实测验证）

## Context
fp16 KV 在 32K 上下文时 8GB 卡加载即 OOM。

## Decision
启用 `LLAMA_KV_CACHE_TYPE=q8_0` + `LLAMA_FLASH_ATTENTION=1`。

## Consequences
- VRAM 峰值 7519/8188MB 通过，17.24 t/s，无 OOM
- "8GB 必须 q8_0 KV"后来被 35B 配置继承（CTK q8_0 / CTV q4_0）
- 验证：32K 上下文稳定不 OOM
