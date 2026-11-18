# ADR-0016：p/ 指向稳定路径

- 状态：accepted
- 日期：2026-11-18
- 决策者：用户 + 助手

## Context
原 p/ junction 指向带时间戳的 WorkBuddyWorkSpace 目录，换机器/重装即断。

## Decision
p/ → D:/Brain/workspace（稳定根）；新增 setup/links.ps1 一键重建 7 个 junction。

## Consequences
- clone + 3 脚本即可复现全部路径
- 踩坑：AGENTS.md 曾写成 p/→D:/Brain 但与 p/bench=D:/Brain/workspace/bench 矛盾，已统一
