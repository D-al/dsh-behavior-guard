# harness 层拦截 read：成功实现 ACI（2026-11-27 01:05）

## 一、结论

**在 harness 层成功拦截了 read** —— 从"提示模型别读"变成"接口直接拒绝"。

| 方案 | 工具调用 | 结束方式 | 效果 |
|---|---|---|---|
| 基线（无干预） | **55 次** | 手动 cancel | 空转 |
| 仅 step 硬中断 | 12 次 | 自动 blocked | 止损 |
| **read 门控 + 硬中断** | **7 次** | 自动 blocked（read 被拒） | **下降 87%** |

实测证据：
```
read_denied  {sid: 30e7a50d, file: client.js, reads: 3}
read_denied  {sid: 30e7a50d, file: client.js, reads: 3}
tool/result  → "这个文件已经读过 3 次，内容不会因为再读一遍而变化。..."
TURN/END     {'kind': 'blocked'}
```
工具调用明细：read 5、glob 1、working_directory 1。

## 二、关键发现：dsh 有工具级门控，但需要 global 标志

### 源码依据
`dsh-tools/src/pipeline.ts:200`：
```ts
const carrier = scopeTarget(this.tools, exec.agent)
const gate = await this.ctx.waterfall(carrier, 'tools/pre-execute', exec,
  () => Promise.resolve<PreToolDecision>({ kind: 'allow' }))
```

`PreToolDecision`（contracts.ts:375）：
```ts
{ kind: 'allow' } | { kind: 'deny'; reason: string } | { kind: 'cancel' } | { kind: 'ask' }
```

### 三个坑（全部实测）

**坑 1：默认收不到（agent-scoped 派发）**
`tools/pre-execute` 通过 `scopeTarget(this.tools, exec.agent)` 派发，全局监听器被 scope 过滤。

**坑 2：`{ global: true }` 是解法**
`cordis/src/events.ts:170`：
```ts
.filter(hook => hook.global || !filter || filter.call(thisArg, hook.ctx))
```
`hook.global` 为真时**跳过 scope 过滤**。加上后实测 `diag_preexec` 触发 222 次 —— 事件完全通畅。

**坑 3：key 被路径写法切碎（最隐蔽）**
先用完整路径作 key → `n` 只涨到 2（222 次调用分散在多个 key 上）。
因为同一个文件在 `exec.arguments` 里可能是**相对路径或绝对路径**两种写法。

修复：**用 basename 作 key**。
```js
const _base0 = String(fp).split(/[\\/]/).pop() || fp
const k = sidey + '|' + _base0
```

## 三、实现细节

```js
const readCounts = new Map()   // 自包含计数，不依赖 states 的 key 匹配

ctx.on('tools/pre-execute', async (exec, next) => {
  if (!cfg.readGuardEnabled || exec?.name !== 'read') return next()
  const sid0 = String(exec?.agent?.session?.id || '')
  const a = exec.arguments || {}
  const fp = String(a.file_path || a.path || '')
  if (!sid0 || !fp) return next()
  if (a.offset > 0) return next()        // 带 offset = 想看特定片段，放行
  const sidey = sid0.replace(/^session-/, '')
  const base = String(fp).split(/[\\/]/).pop()
  const k = sidey + '|' + base
  const n = readCounts.get(k) || 0
  if (n >= cfg.readDenyThreshold) {      // 默认 3
    return { kind: 'deny', reason: '这个文件已经读过 N 次，内容不会因为再读一遍而变化。'
      + '如果只想看某一段，用 offset/limit 读指定范围；否则请直接改文件，或结束本轮说明卡在哪。' }
  }
  readCounts.set(k, n + 1)
  return next()
}, { global: true })
```

配置：`readGuardEnabled: true` / `readDenyThreshold: 3`

## 四、为什么这比提示词强

| | 提示词（旧的 mind_state） | 接口拒绝（read 门控） |
|---|---|---|
| 模型收到 | 一段文字"观察到重复动作" | **工具调用失败 + 错误原因** |
| 模型可忽略 | 能（10 次提示 0 次改变） | **不能，工具真的没执行** |
| 依据 | — | SWE-agent 论文：11% → 18%（+64%），零模型改动 |

这印证了 SWE-agent 的核心判断：**"模型不是普通人类用户，接口应围绕它最容易犯什么错来设计。"**

## 五、诚实边界

1. **单次对照**（55 → 12 → 7），有 ±10% 波动，但 8 倍差距量级可靠。
2. **basename 作 key 有误伤风险**：不同目录的同名文件会合并计数（如两个 `index.js`）。当前场景（单插件单文件）无影响，多文件项目需改用 `相对路径规范化`。
3. **`diag_preexec` 仍留在代码里**（222 次/轮，写 trace 有开销）。生产前应删除或降级为采样。
4. **未验证 deny 后模型是否改对**：本次任务仍是 `blocked`，产物未改。门控解决"别空转"，不解决"做对"。
5. **`{ global: true }` 会收到所有 agent 的调用**，已用 sid 过滤，但多个并发会话时 readCounts 会累积（key 含 sid，不会串）。
6. **未测 `tools/post-execute`**（可替换结果，做"有界视图"更彻底），是下一步候选。

## 六、下一步

| 优先级 | 做法 |
|---|---|
| P0 | 删掉 `diag_preexec` 诊断（性能） |
| P1 | 用 `tools/post-execute` 做**结果裁剪**：read 首次返回时只给前 100 行 + 提示"用 offset 看更多"（SWE-agent 原版做法） |
| P2 | basename → 规范化相对路径（避免同名文件误合并） |
| P2 | readCounts 每轮重置（当前跨轮累积，可能过早 deny） |
