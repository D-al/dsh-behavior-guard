# 读源码结论：dsh 的 ask_user_question 如何从外部回答（2026-11-26 23:2x）

> 起因：为"通过 bridge 回答模型提问"重启了 9 次试错。用户指正"先读源码"。
> 本文是读 `app.asar` 内 TypeScript 源码（`@deepseek-ai/dsh-user-questions`）后的权威结论。
> **结论：我之前的方案在 API 语义上就是错的，不是参数调不对。**

## 一、源码事实（权威，非推测）

源码路径：`dsh/node_modules/@deepseek-ai/dsh-user-questions/src/index.ts`（364 行）

### 1. 服务名是 `userQuestions`
```ts
declare module '@deepseek-ai/cordis' {
  interface Context { userQuestions: UserQuestionService }
}
export class UserQuestionService extends TypertRemoteService {
  constructor(ctx: Context) { super(ctx, 'userQuestions') }
```
**`userQuestionPanels` 是另一个东西**——它是 UI 面板服务（`reflect.provide('userQuestionPanels', {...})`），只负责渲染/打开面板，不负责提交答案。

### 2. `answer()` 的第一个参数是 Agent，不是 sessionId
```ts
@Remote
answer(agent: Agent, callId: ToolCallId, answer: AskUserQuestionAnswer): boolean {
  this.assertLiveRoot(agent)                     // 必须是"活的" root agent
  const question = this.continued(agent).find(item => item.callId === callId)
  if (question === undefined) return false       // ← 关键：不是 continued 就直接 false
  ...
  agent.steer(message)                           // 内部就是发一条带 source 标记的 steer
```
`continued()` 的实现：
```ts
private continued(agent: Agent): readonly PendingUserQuestion[] {
  return this.questionProjectionHandle?.stateOf(agent.session)
    .questions.active.filter(q => q.state === 'continued') ?? []
}
```

### 3. 状态语义（决定一切）
```ts
/** `open` while the tool call may still return the answer;
 *  `continued` once the answer can only arrive as a new turn. */
export type UserQuestionState = 'open' | 'continued'
```
- `open`：工具调用**还阻塞着在等**答案 → `answer()` 返回 false，走不通
- `continued`：已经超时/转入下一轮，答案只能作为新 turn 到达 → `answer()` 可用

**这就是为什么 9 次试错全部无效**：模型卡在 `ask_user_question` 时状态是 `open`，
`answer()` 设计上就不处理——它只处理"超时后补答"。

### 4. 唯一能在 `open` 状态作答的挂钩点是 waterfall
```ts
// types.ts
'user-questions/request'(
  this: Scoped<Agent>,            // ← 定向派发：只发给该 Agent scope 的监听者
  request: AskUserQuestionRequestEvent,
  next: () => Promise<AskUserQuestionAnswer>,
): Promise<AskUserQuestionAnswer>
```
官方实现范例（`dsh-sdk-jsonrpc-server/src/user-questions.ts:20`）：
```ts
this.unregister = ctx.on('user-questions/request', async (request, next) => {
  const agent = request.agent
  if (!this.enabled || agent === undefined || !ownsAgent(agent)) return next()  // 不接管就放行
  return this.ask(request, String(agent.session.id))                            // 返回答案
})
```

## 二、bridge 为什么做不到（实测 + 源码双重证据）

**实测**：bridge 里注册 `ctx.on('user-questions/request', ...)` 后，
连续两轮让模型真实调用 `ask_user_question`（会话 `02ca26c2` turn1/turn2 各一次），
接管器**零留痕**（appendFileSync 同步写，不存在丢失）。

**源码解释**：该事件是 `this: Scoped<Agent>` 的定向派发——
> `Scope-filtered dispatch (@deepseek-ai/dsh-scope): agent-scoped listeners receive only that agent.`

bridge 是 profile 级全局插件，**不在任何 Agent scope 内**，所以收不到这个事件。
`sdk-jsonrpc-server` 能收到，是因为它按 Agent 注册（`ownsAgent(agent)` + agent 作用域）。

## 三、可行的三条路（按可靠性排序）

| 路径 | 可行性 | 说明 |
|---|---|---|
| **A. bridge 走 cancel + message 兜底** | ✅ 已实现并验证 | `POST /answer` → 取消卡住的 turn → 把答案作为新消息投递。功能等价，代价是丢当前 turn 的中间进度 |
| **B. 写一个 Agent-scoped 插件** | ⚠️ 未验证 | 参照 `sdk-jsonrpc-server` 的模式，在 Agent scope 里注册 waterfall。需要能拿到 agent 作用域（`scopeTarget(agent, agent)`）。这是"真正的解法"，但要写新插件，不是改 bridge |
| **C. 直接调 `userQuestions.answer()`** | ❌ 无效 | 只对 `continued` 状态生效；`open` 状态恒 false |

## 四、给 future 自己的三条教训

1. **先读源码再试**。这次为同一功能重启 9 次，如果一开始就读 `dsh-user-questions/src/index.ts`，
   5 分钟就能看出 `answer()` 只处理 `continued`——根本不用试。
2. **asar 里有完整 TS 源码**：`npx asar extract ... ./full` 后
   `full/dsh/node_modules/@deepseek-ai/*/src/*.ts` 全部可读，还有 JSDoc 说明设计意图。
3. **`ctx.on` 能不能收到事件，取决于插件在不在对应 scope**。全局插件 ≠ 万能订阅者。

## 五、当前 bridge 的实际能力（诚实说明）

- `POST /v1/sessions/:sid/question` `{armed:true}`：开启接管（状态可查，但事件收不到）
- `GET  /v1/sessions/:sid/question`：查看挂起/排队
- `POST /v1/sessions/:sid/answer`：**走 cancel+message 兜底，可用**
- 已注册 waterfall 接管器（若未来 bridge 被移入 Agent scope 即自动生效）

**结论：能用，但不是最优雅的路径。真正的无副作用方案需要写 Agent-scoped 插件（路径 B）。**
