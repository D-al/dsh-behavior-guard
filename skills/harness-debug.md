---
name: harness-debug
summary: 调试 dsh-agent-harness 插件本身——探针/单元测试/注入验证/常见坑
keywords: [harness, 插件调试, agent-harness, 探针, 注入不生效, 单元测试, test_new_guards]
---
# 调试 agent-harness

## 三个验证层次（从快到慢）

### 1. 探针（最快，验证"插件加载了没有"）
```powershell
Get-Item 'D:\Brain\workspace\bench\_agent_harness_loaded.json' | ForEach-Object { $_.LastWriteTime }
```
- 时间戳必须 = **本次重启时刻**；内容里有 `version` 和完整 `config`（能看出配置有没有生效）

### 2. 单元测试（验证"逻辑对不对"，不碰真实会话）
```bash
cd D:/WorkBuddyWorkSpace/2026-10-13-20-41-43/bench
node test_turn_guard.mjs     # L0-L3 共 26
node test_new_guards.mjs     # 40 项（合计 106 PASS，见 CHANGELOG v2.12.0）
```
测试用 `harness()` 造假的 ctx/agent，直接 `emit('session/event', {...})` 和 `emitPreStep()`
- **命名坑**：session/event 用 `id` 做键，pre-step 用 `agent.session.id`——两处必须同一个值（`s1`），
  否则 state 不匹配、测试"通过"但测的是空状态（这个坑踩过）

### 3. 真实会话（最终验证）
- 跑一个任务后看 `bench/_trace.jsonl` 是否有该会话的记录（`sid` 字段）
- `python bench/trace_report.py` 看统计

## 常见坑
| 症状 | 原因 | 修法 |
|---|---|---|
| 注入出现两次 | bundle + preset 双挂载 | 只留 bundle（`dsh.profile.bundles`），删 preset 里的显式挂载 |
| 注入完全不出现 | state 字段没初始化（如 ~undefined 比较） | 在 `stateOf()` 的初始化对象里补字段 |
| 深检/控制回合不触发 | 被包在别的 `if (cfg.xxx)` 块里 | 独立判定，别依赖其他开关 |
| 测试全过但真机不生效 | 改的是 publish 副本，不是 node_modules | 改 node_modules → 发布前 `cp` 到 publish |
| 更新后行为没变 | pnpm 缓存/未重启 | `pnpm update <包名>` + 重启 + 验探针时间 |

## 改代码前后的固定动作
1. 改 `node_modules/dsh-agent-harness/index.mjs`
2. `node --check <file>`
3. 跑两个测试 + 门禁
4. `cp` 到 `D:\Brain\publish\dsh-behavior-guard\index.mjs`（仓库名沿用）
5. 版本号 + CHANGELOG → commit → tag → push
6. `pnpm update` → 重启 → 验探针
