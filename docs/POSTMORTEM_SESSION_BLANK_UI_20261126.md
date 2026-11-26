# 复盘：会话窗口白屏（显示"缓存... 53%"）2026-11-26 12:4x

## 症状
用户截图：会话"修复 dsh-hardware-monitor 插件"（4小时前）主区域全白，中间只有
`2... 缓存... 53%` 状态指示。后端重启 dsh 后仍白屏。

## 排查结论：后端数据完好，是"请求反复被打断 + 前端渲染窗口"的组合

### 1. 后端数据完整（排除数据丢失）
- 会话存储 `session.v4.jsonl.zstd` 569KB，可读出 603+ 事件
- bridge `sessions` 显示该会话 `running=false, blank=false`
- `session_projcache` 8KB，12:40 正常生成
- 完整流有 23 条 assistant/message（seq 17/22/.../167）

### 2. 前端白屏的直接原因：渲染窗口里没有 assistant/message
- bridge API 的 `limit=100` 只返回**尾部**事件
- 尾部 100 条的事件类型分布：`step/end×16, step/start×15, tool/call×7, compaction/prune×11,
  workspace/changes×2, agent/inbox/spliced×1, turn/end×1, session/end-seed×1`
  —— **assistant/message = 0**
- 用户看到的"2... 缓存... 53%"不是加载进度，是会话状态指示（token/缓存/上下文占用）
- 消息列表渲染依赖 assistant/message，尾部窗口没有 → 白屏

### 3. 为什么反复被打断（真正的循环）
| 时间 | 事件 |
|---|---|
| 12:40 | 加固脚本重启 dsh（bridge pid 12648） |
| 12:45 | 我从 bridge 发测试消息 → turn 5 开始 |
| 12:45-12:47 | llama task 212 prefill 卡在 4096/6626（progress 0.08）120 秒无进展 |
| 12:47:28 | 看门狗判"真冻死"→ 触发 RestartDsh |
| 12:47:38 | dsh 重启（新 pid 5368）→ turn 5 `reason: interrupted` |
| 12:48 | 我再发消息 → turn 6，这次 prefill 正常推进（326 t/s，100 秒完成 36K tokens）|
| 12:5x | turn 6 `completed`，assistant/message 出现 → 会话恢复 |

**关键**：这不是看门狗误判——llama 日志证实 task 212 的 prefill 真的停在 4096 长达 120 秒
（`n_tokens=4096, progress=0.08` 之后无新进展）。显存账：`needs 6610 MiB, free 7106 MiB`
——余量仅 496 MiB，显存压力下 prefill 偶发停滞。看门狗按设计重启，但代价是打断当前 turn。

## 修复/恢复
- 新建 turn 并让它正常完成 → assistant/message 回到事件流 → 前端可渲染
- 用户侧：刷新窗口即可看到内容（如仍白屏，用 Ctrl+R 或重开会话）

## 如何避免
1. **别在长 prefill 期间发消息/操作**——这个会话上下文 36K，每次请求 prefill ~100 秒，
   期间看起来像卡住，但其实是正常的。看门狗 120s 阈值刚好卡在这个边界。
2. **看门狗阈值与 prefill 时间对齐**：`stuck_th=120s` 对 36K 上下文的 prefill（100s）过于激进。
   建议提到 180s，或改为"prefill 有进展就不算冻死"（看 `n_prompt_tokens_processed` 是否增长，
   而不是只看功耗 <30W + util 100%）。
3. **显存余量偏低**：7735/8188 MiB，free 222 MiB。按项目铁律安全线是空闲 ≥450 MiB。
   可考虑临时降 CTX_CHECKPOINTS 或 MOE_CACHE_MIB 腾出余量（需实测，不在本次改动）。
4. **前端渲染窗口 bug**：bridge/API 只返回尾部 100 条导致 assistant/message 缺失——
   这是 dsh 前端设计，非我方代码可改。绕过：让会话产生新 turn（新 assistant/message 在尾部）。

## 诚实边界
- "缓存... 53%"的确切含义未能从 dsh UI 源码证实（app.asar 未深挖），
  推断是上下文/缓存占用指示而非加载进度——依据是事件流显示后端早已完成加载
- 会话恢复是通过"发消息触发新 turn"验证的，前端是否真的重绘需用户确认
