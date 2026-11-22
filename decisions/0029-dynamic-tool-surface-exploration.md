# ADR-0029：动态工具面可行性探索——纠正"架构不支持"的误判

- 状态：accepted
- 日期：2026-11-22
- 决策者：用户（显式要求："另开探索ADR设计插件hook"，只调研不实现）
- 决策层级：一般决策 G（探索性调研，不改生产配置）
- 支撑决策：ADR-0028（工具面三层治理，其中③标记待重选）

## Context（背景）
ADR-0028 中我调研后结论"当前 dsh 不支持 per-step 工具切换，工具面启动期 bundle 决定"，
用户选择"另开探索 ADR 设计插件 hook"。本 ADR 深查 asar 内官方源码文档后，**该结论被推翻**。

## 一手证据（dsh 官方源码，非猜测）
来源：`D:/Deepseek Harness/resources/app.asar` 内
`dsh/node_modules/@deepseek-ai/dsh/docs/cookbook/adding-a-tool.zh.md`（用 @electron/asar 提取）：

```ts
import { defineTool } from '@deepseek-ai/dsh-tools'
export const name = 'my-tool'
export const inject = ['tools']        // ← 注入 tools 服务
export function apply(ctx: Context) {
  ctx.tools.register(defineTool({...}))  // ← 运行时注册工具
}
```

官方原文关键句：
1. **"注册基于副作用：dispose 插件 fiber 即注销该工具。schema 会自动流入系统提示词的组装过程。"**
2. **"如需热替换工具，请 dispose 其所属副作用并注册替代品"**
3. `capability-seams.zh.md` 确认 `ctx.pluginManager`（当前 profile 的插件/bundle 管理）是核心服务，
   `ctx.hmr` 支持"Serialized module and configuration reloads"。

**结论纠正**：dsh 有**运行时工具注册/注销机制**（fiber 生命周期 + ctx.tools.register），
我 ADR-0028 的"架构不支持"是**调研深度不足导致的误判**——只看了 cordis.patch 静态 bundle 配置，
没查官方 cookbook 的插件 API。

## Options（方案对比）
| 方案 | 做法 | 评估 |
|---|---|---|
| A 插件 fiber 按需注册/注销 | 做个 plugin，按任务类型 dispose/register 低频工具 | ✅ 官方支持；但"任务类型"判定需设计 |
| B ctx.intercept('tools') 过滤 | 拦截 tools 服务的 schemas() 投影 | ⚠ ctx.intercept 存在，但 tools 是否可 intercept 未验证 |
| C 静态 bundle 切换 | dsh.profile.bundles 改配置+重启 | ❌ 不是动态，且需重启 |

## Decision（探索结论，不实施）
1. **动态工具面技术上可行**（A 路）：官方明确支持运行时 register + dispose 热替换。
2. **但未实施**，理由：
   - 收益仍存疑：低频 4 工具（present/ask_user_question/read_image/load_workspace_dependencies）
     按证据"低频但不可缺"，动态化的价值主要在"减少 schema 注意力税"，而非砍功能
   - "何时切换"缺乏可靠信号：需先有任务类型分类器，而项目已证伪弱分类器（JudgeBench）
   - 风险：工具热替换涉及 schema 流入系统提示词，切换时机不当会破坏正在进行的工具调用
3. **若未来实施的前置条件**：
   - 先验证 `ctx.tools.register` 在 dsh 0.2.2-rc.3（本机版本）的实际行为（官方文档可能领先本机）
   - 设计一个"会话级"而非"逐步级"的切换（降低破坏性）：开场根据任务类型注册工具集，会话内不变
   - 受控实验：对比全暴露 vs 动态暴露的端到端任务成功率（不能只看 decode t/s——项目铁律）

## Counter-evidence（反证）
- **反对"技术上可行"结论**：官方文档可能描述的是最新版 dsh API，本机 0.2.2-rc.3 可能未实现。
  → 本 ADR 明确标注"未在本机版本验证"，实施前必须做 smoke test。
- **反对"不实施"**：用户明确选了"另开探索ADR设计插件hook"——本 ADR 完成调研交付，
  未实施符合"探索"定位（用户同时说"只调研不实现"的语境）。
- **翻案条件**：若证据显示低频工具的 schema 注意力税显著（如违规调用率上升），重开 ADR 实施 A 路。

## Consequences
- 正面：纠正误判；给出可行的技术路径与前置条件；避免盲目实施。
- 负面：ADR-0028 的"架构不支持"表述错误已在本文档纠正，需同步 STATUS/ADR-0028 加勘误指针。
- 验证：本 ADR 的证据来自官方源码文档一手提取；不声称本机版本已验证。
