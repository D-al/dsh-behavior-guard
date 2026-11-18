# ADR-0001：选 llama-server 主线

- 状态：accepted
- 日期：2026-10-19
- 决策者：用户 + 助手（实测验证）

## Context
用户想充分发挥 Qwen3.5-9B 本地推理；对比 Ollama / llama-server / vLLM / SGLang / LM Studio。

## Decision
单用户 Windows 首选 **llama-server**（llama.cpp 主线 b11654+ 支持 qwen35），原生 CUDA、OpenAI 兼容 /v1 对 dsh 是 drop-in。

## Consequences
- vLLM/SGLang 需 WSL2 且单用户反而慢；LM Studio 仅 GUI 备选
- 确立后续引擎调优路线：autoparser 补丁 → b12244 → 自编
- 验证：实际接入成功，后续所有调优基于此引擎
