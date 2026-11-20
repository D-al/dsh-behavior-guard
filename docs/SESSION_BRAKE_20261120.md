# 会话刹车：dsh 中断能力的正确抽象层（2026-11-20 20:45）

> 用户："最大的问题是刹不住车，dsh 没有随时打断它思考并引入新对话；同时开两个会话很危险，开新会话前一定检查硬件，有并行立刻开子任务分盯+单独汇总子任务呈递。"

## 1. 我之前错在哪

我此前判断"dsh 无会话终止 API"，依据是 REST 端点 `DELETE/PATCH/POST /v1/sessions/<id>` 全返回 404。
**这是查错了抽象层**：真正的中断不走 REST 资源语义，而走 **cordis service 方法**。

权威源码（`node_modules/@deepseek-ai/dsh-api-remotes/lib/client.js`，编译自
`packages/api/session-controller/src/index.ts:500`）明确定义：

```
session/cancel({sessionId}) -> {accepted:true}
  service: sessionController
  description: Cancel one active Agent turn without dropping its pending inbox.
```

另有 `subagents/interruptByUser({childSessionId})` 用于中断子会话（对 absent/idle/completed 是安全 no-op）。

## 2. 已实现（立即止血）

- bridge 插件 `index.mjs`：正则加 `cancel`，新增 `POST /v1/sessions/<sid>/cancel` → `ctrl.cancel({sessionId})`
- bridge CLI `bridge.mjs`：新增 `node bridge.mjs cancel <sessionId>`
- 重启 dsh 加载新插件（旧 pid 1532 → 新 pid 35916）
- **实测**：`cancel session-NONEXISTENT-TEST` 返回 `session not found (not attached)`——
  业务错误而非 501/404，证明 `ctrl.cancel()` 确实调到了 sessionController

## 3. 开新会话前的硬性检查（用户规则，已固化）

**不能只看会话列表的 running 标志**——它可能是僵死残留（之前多次 running=true 但无事件）。
必须三层交叉：

1. **硬件**（最快、最可靠）：`nvidia-smi --query-gpu=utilization.gpu,utilization.memory,power.draw,memory.used`
   - 无推理：util <15%、带宽 <5%、功耗 <30W、显存 <1GiB
   - 有推理：Copy 引擎高 + 带宽高 + 功耗 100W+（**不要用聚合 util%，它骗人**）
2. **会话列表**：`node bridge.mjs sessions` 看 running 数
3. **llama slots**：`/slots` 的 `is_processing` + `n_prompt_tokens_processed`（0 且不动=冻死，非活跃）

只有三层都显示"无活跃推理"才开新会话。

## 4. 并行时的处置（用户规则）

一旦发现两个以上会话同时活跃：
1. **立刻开子任务分盯**——每个会话一个 observer 子任务，各自只读跟踪事件流+硬件
2. **单独开一个汇总子任务**——轮询所有子任务状态，专门呈递给用户
3. 不要用主代理反复切来切去（会漏看、会拖延）

## 5. 待办

- M10（会话生命周期治理）卡应吸收本文：把 `cancel` 命令 + 硬件三层检查 + 并行子任务协议写进判据
- cancel 的"保留 pending inbox"语义要注意：取消后若 inbox 有堆积消息，会话可能立刻重跑——
  使用前应确认 inbox 已清空，或 cancel 后检查是否真停

## 6. 证据

- 重启前：两个会话 running=true（0428ceab / 8a15c0b8），双推理
- 重启后：19 个会话全 running=false，GPU 7% / 带宽 2% / 16.64W / 893MiB
- 刹车端点：200 业务响应（not found），非 501
