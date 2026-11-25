# 复盘：会话"自己停了"的真实根因（2026-11-26 01:2x）

## 症状
用户报："它突然不动了，显卡和 CPU 占用都很少"，随后澄清：
"既没有切走会话，也没有取消，是它自己停的；发测试消息后它立刻自动压缩上下文，然后就继续了。"

## 初判错误（诚实记录）
我最初判断为"上下文接近 54K 退化区 → 模型空流 → dsh dispose"，并建议降 `thresholdRatio`。
**这是错的**——完整事件流证明 `turn/end aborted/disposed` 之前发生了明确的**错误配置写入**，
上下文根本没到阈值（47004 < 54067）。

## 真实根因链（完整事件流，逐帧 zstd 解压 174 事件）

| seq | 事件 | 内容 |
|---|---|---|
| 131 | assistant/message (step 22) | reasoning：误判"bundle 注册缺失"，决定把 `@deepseek-ai/dsh-base` 加进 bundle 列表 |
| **132** | **tool/call edit** | `package.json`：`"dsh-hardware-monitor"` → `"dsh-hardware-monitor", "@deepseek-ai/dsh-base"` |
| 133 | tool/result | 写入成功（`isError:false`） |
| 134 | step/end | step 22 结束 |
| 135 | step/start | step 23 |
| **136** | **assistant/attempt** | **`stream: []`（空流）** |
| 137 | step/end | step 23 结束 |
| **138** | **turn/end** | `reason: {kind:"aborted", reason:{kind:"disposed"}}` |
| 139 | session/end-seed | 会话结束 |
| 140 | agent/inbox/spliced | 我发的测试消息（**插在 disposed 之后**——是新 turn，不是"唤醒"） |

**关键事实**：
1. `package.json` 里 `@deepseek-ai/dsh-base` **本来就在 bundles 数组第一行**（`:17`），
   dsh 又在 seq 132 把它追加到末尾 → **同一个核心 bundle 出现两次**
2. 修复后现场确认 `grep -c dsh-base = 2`，重复项一直在
3. 重复核心 bundle → dsh bundle loader 冲突 → agent 生命周期 dispose → 空流

## 为什么"发消息后立刻 compaction"
**因果倒置**：不是消息触发了压缩，而是压缩早已 pending。
- 压缩由 dsh 引擎按 token 阈值（54K）触发，且**只在新请求时检查**
- 会话 token 停在 47004，空闲时不检查；新消息进来 → 触发检查 → 发现已达阈值附近 → compaction
- 压缩后 token 降到 ~10K（task 3324 `n_tokens=10342`），会话恢复正常
- 所以"发消息→压缩→继续"是 dsh 的 lazy 压缩机制，**不是自停的原因，是自停后的恢复动作**

## 与今天部署的三道防线无关
- `side_effect_damage` 命中 **0** 次
- `open_correction_captured` 命中 **0** 次
- 两版 harness 补丁在此会话无触发

## 已执行修复
- `package.json` 删除末尾重复的 `"@deepseek-ai/dsh-base"`（保留第一行）
- 备份：`_cleanup_20261118/plugin-repair-20261126/package.json.dup-base.before`
- 验证：`grep -c dsh-base = 1`、JSON 合法、bundles=11

## 如何避免（按 ROI）

### P0：给 watcher 加"bundle 列表完整性"规则（本次漏洞）
`plugin_guard.py` 现在只查 `cordis.patch.yml` 的 bundle 名和关键文件存在性，
**没有查 profile 的 `package.json` bundles 数组重复**。这正是本次事故盲目点。
新增规则：`bundles` 数组内不得有重复项、核心 bundle（dsh-base/web-app）不得缺失或追加第二次。
命中 → 自动去重 + 告警（与现有 @local 修复同机制）。

### P0：禁止把核心 bundle 加进 profile patch
`@deepseek-ai/dsh-base` 等是 base bundle，profile 里只应引用一次。
写进 AGENT_BRIEF 铁律不够（提示词护栏在 full-access 下无效），必须做成 watcher 规则。

### P1：compaction 频率优化（次要）
`thresholdRatio 0.55` 在长任务里仍会因"存档回注推高 token"形成正反馈（历史最小间隔 0.6 秒）。
可考虑 0.45，但会牺牲上下文容量——**这不是本次根因，不要为此改动**。

## 诚实边界
- `disposed` 的直接发起者是 dsh core 的 agent 生命周期，我没有 dsh 源码证实
  "重复 bundle → dispose"的因果，只能从"写入重复项 → 下一步空流 → dispose"的时序 + 现场重复仍在
  推断。**这是强时序证据，不是源码级因果证明**
- 空流也可能是 llama-server 重启后不稳定期的独立因素（01:01 重启，会话跨越）
- 但无论哪条，"bundle 列表被写重复"都是确凿的配置污染，必须先修
