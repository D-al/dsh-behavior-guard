# ADR-0013：append-only 注入，不改写历史

- 状态：accepted
- 日期：2026-11-17
- 决策者：用户 + 助手

## Context
改写思维链有 KV cache 后缀税（本机 20K 重预填充 25-44s）。

## Decision
压缩/注入只追加，不改写既有上下文。

## Consequences
- 避免后缀税
- 这是社区第一指标（Manus/Anthropic），完全不新——但本地 llama.cpp prefix cache 是否真命中仍待自证
