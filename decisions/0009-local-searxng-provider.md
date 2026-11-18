# ADR-0009：本地 SearXNG provider

- 状态：accepted
- 日期：2026-10-16
- 决策者：用户 + 助手（实测验证）

## Context
dsh 内置 deepseek/exa/perplexity 搜索 provider 均需外网/API key。

## Decision
自定义 provider 插件走本地 SearXNG，cordis.patch.yml 把 web 的 searchProvider 指向它。

## Consequences
- 曾尝试禁用 tool-web：连带 web 服务出问题且实际没移除工具 → 放弃该路
- rc.2/3 升级后默认改回 DeepSeek Search，但显式配置幸免——这是潜在脆弱点
