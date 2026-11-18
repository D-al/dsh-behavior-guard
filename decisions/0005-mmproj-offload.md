# ADR-0005：MMPROJ_OFFLOAD=1

- 状态：accepted
- 日期：2026-11-06
- 决策者：用户 + 助手（实测验证）

## Context
预填充"卡死"，初判显存换页 / `--cache-ram`。

## Decision
采样器抓现场：`slot encode_mtmd_:` 后 41 秒才解码，GPU 0-6% / 16W / CPU 1.4 核 → 真因视觉编码器在 CPU。设 `MMPROJ_OFFLOAD=1`。

## Consequences
- 视觉编码从 141s 降到可接受
- cache-ram 关掉后照旧复现 → 该归因证伪（保持 0 无害）
- 教训：采样器抓现场 > 猜归因
