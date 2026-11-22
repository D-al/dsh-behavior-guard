# dsh 自定义工具能力调研（2026-11-22）

> 用户问："dsh有没有给我们定制新工具留口子？（如果新轮子比官方好用，模型会不会倾向用我们的轮子？）"

## 一、第一问：能，正式 API（代码确证，非推断）

来源：本机运行版 `D:/Deepseek Harness/resources/app.asar` 内 `@deepseek-ai/dsh-tools` 源码与文档
（本机 dsh 2.26.6）。GitHub `deepseek-ai/deepseek-harness` 分支是 `master`。

### 1.1 路线 A：Host 插件直接注册新工具（推荐）
官方文档原文：
> "Mount `dsh-tools` wherever agents call tools: it provides `ctx.tools`, **the registry every tool
> plugin registers into** … **Registering a tool is enough to make it visible — the registry feeds
> its schemas into the system-prompt assembly automatically.**"

API 骨架（官方内置 todo_write 工具源码 `dsh-tool-todo/src/index.ts` 可整段抄）：
```js
export const name = 'my-tools'
export const inject = ['tools']          // 必须注入 tools 服务
export function apply(ctx, config) {
  const dispose = ctx.tools.register(defineTool({
    name: 'my_tool',                      // 模型可见名
    description: 'What the tool does.',   // 模型可见描述
    parameters: { path: { type: 'string', required: true, description: 'Absolute path' } },
    output: { schema: { type: 'string' }, render: (_a, v) => [{ type: 'text', text: v }] },
    async execute(args, exec) { return doWork(args.path, exec.signal) },  // 必须遵守取消
  }))
  ctx.effect(() => () => dispose())
}
```
挂载仍需标准 bundle 三件套（package.json exports + dsh.bundle.patch / cordis.patch.yml insert /
profile bundles 列出包名）——本机 8 个插件都是这个模式。

### 1.2 路线 B：MCP Server（零 Host 代码）
官方模板 `dsh-agent-preset/skills/dsh-doc/templates/mcp/`，配置-only bundle：
```yaml
- insert:
    - id: demo-mcp
      name: '@deepseek-ai/dsh-mcp-client'
      config: { serverName: demo, transport: streamable-http, url: http://127.0.0.1:3000/mcp }
```
工具自动以 `mcp__<serverName>__<tool>` 命名可见。**这是让模型用自研工具最省事的路。**

### 1.3 路线 C：只换已有工具的后端（不算造新工具）
本机 `dsh-searxng-autostart/index.mjs:142` 的 `ctx.web.registerSearchProvider()`——
替换内置 web_search 的 provider，不是新工具。

### 1.4 纠正我之前的错误判断
我曾把 `toolUpdate: addition-only` 理解成"harness 只能加不能改工具"——**错了**。
代码确证：它是 **LLM 请求序列化模式**（Anthropic Messages 传输层），
决定会话中途工具定义变化时如何投影（`tool_addition`/`tool_removal` 块 + beta header），
**不是工具注册权限开关**。真正的注册 API 是 `ctx.tools.register()`。

### 1.5 配套能力（官方 API）
- `ctx.tools.restrict()`：只能**删**工具（隐藏官方工具）
- `tools/pre-execute` waterfall：管 allow/deny/ask
- `ctx.tools.guard()`：单调拒绝
- 同名冲突：register 拒绝同名重复与保留名 `run_code`；支持 scoped shadow
- ⚠ 本机踩坑：直接 disabled `tool-web` 实测"工具没真移除且连带 web 服务出问题"
  （cordis.patch.yml:411）——隐藏官方工具要谨慎

## 二、第二问：模型会不会因为新轮子更好就倾向用——**提示词层面无效，有本地受控实验**

### 2.1 本地受控实验（记忆 2026-11-18，Skills 受控重复实验，11 会话）
- 注入工具指引 ON：common 任务全选 glob、rare 全选 pwsh
- 关闭指引 OFF：**完全一样**（common 仍 glob、rare 仍 pwsh）
- 结论原文："**注入对工具选择中性**……不能证明有用"

### 2.2 工具面注意力实测（记忆 2026-11-18）
工具数 36→15（-58%），但 pwsh description 1950→2007（占现总量 36%）——
**省的是"数量"维不是"描述"维**；模型偏好主要由**任务类型**驱动，不是描述写得好不好。

### 2.3 本地实际调用分布（55 会话）
17 个工具全是官方内置，**没有任何自定义工具被调用过**——本地虽装了 8 个插件，
但它们走事件/service 注入（sessionController/web provider），没走 tools.register。

### 2.4 机构研究佐证（docs/CLOUD_TODO_TRIGGER_MECHANISM_20261122.md）
- CARD：1.7B 裸自评 77-80%，专用微调估计器 89.2%
- StyleBench：策略选择元能力 72B+ 才稳定，7B 微调只学到固定偏好
- Why LLMs Choose Bad Plans：强制结构化规划反而放大过度自信
→ 35B 的模型自判不可靠，但这跟"工具注册 API"无关——API 是确定性的，模型选择是概率性的。

## 三、综合判断（回答用户的隐含问题）
| 场景 | 模型会不会用新轮子 | 依据 |
|---|---|---|
| 新工具填补**能力空白**（官方没有）| **会**——没有替代品 | session-bridge 那种 service 注入已验证 |
| 新工具**替代**官方工具（更好的 grep）| **大概率仍按任务习惯选旧的**——描述写得好不会翻转选择 | 本地受控实验：指引 ON/OFF 工具选择完全一致 |
| 想强制用新工具 | 需**隐藏官方工具**（`ctx.tools.restrict()`）或 pre-execute 拦截——不是靠描述 | 官方 API 支持，但有 tool-web 踩坑前车之鉴 |

**真正有效的路子（绕开"模型会不会选"）**：
1. 造**填补空白**的工具（MCP 最省事），不跟官方抢
2. 让工具**自己吐确定性信号**（如 scope: 15 files），harness 读信号决策——不依赖模型选择
3. 若必须替代：`ctx.tools.restrict()` 删官方工具 + register 新工具，但需 A/B 验证质量没降

## 四、诚实标注
- API 来自本机运行版 asar 内置源码（代码确证）；GitHub master README 只确认 "everything-is-a-plugin" 架构
- 第三方插件 `import { defineTool } from '@deepseek-ai/dsh-tools'` 可能解析失败（用户级 node_modules 解析不到 @deepseek-ai/*）
  ——稳妥做法：只 inject `ctx.tools`，用普通对象字面量 register，不 import 框架包（未实测，标未验证）
- 本地受控实验是轻量任务（1步 glob/pwsh），不能推广到复杂任务；样本 11 会话
- 未做任何工具注册 PoC——本报告只是能力调研
