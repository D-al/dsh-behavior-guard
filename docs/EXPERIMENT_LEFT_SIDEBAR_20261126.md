# 受控实验 #2：让它改到左边栏（2026-11-26 18:50-19:16）

> 指令："还是不对，我要的是左边栏那个入口，不是设置里的。你再弄一下。"
> 全程只读观察、不干预。目的：验证今天 11 项修复在真实任务的效果。

## 一、结果概览
- 时长：约 26 分钟，turn 12，共 29 步
- **状态：running（主动 ask_user_question 等用户澄清），未 completed**
- 产物：client.js 改为 `sidebar.footer.action`（真实存在、属 sidebar 左侧栏）
- 两副本 sha 一致：`5d45d0e5`

## 二、比上一轮明确改善的三点

### 1. skill 卡首次真实生效（重大突破）
- trace `skill_card names=dsh-ui-slots step=2` —— **上次 turn11 是 0 次**
- 会话 seq1712 模型主动 `read dsh-ui-slots.md`
- 这正是今天给 `dsh-ui-slots.md` 补口语化关键词（"那个入口/接着弄/点进去看"）的直接效果
- **证据**：seq1710 `[harness 技能可用] ... dsh-ui-slots`

### 2. 用对了 slot
- 本轮最终 `ctx.slots.inject('sidebar.footer.action')`
- **真实存在**（asar grep 命中 `sidebar.footer.action`）
- **属于 sidebar 左侧栏**，符合"左边栏"需求
- 对比上一轮：臆造 `sidebar.right.header.actions`（不存在）→ 错位 `settings.section`（设置页）
- 这是**第一次用对左侧栏的真实 slot**

### 3. 双副本真同步
- 两副本 sha 完全一致 `5d45d0e596e74a8c1a14`（1080B）
- 对比上一轮：声称"同步✅"实际 `7208d680` vs `fcac7193` 不同
- 说明 `checkDualCopy` 移入 verify-on-edit 每次写后检查起效（或模型自己同步了）

### 4. 不再 F12 甩锅
- 本轮无 "F12/控制台/粘贴代码" 类文案
- 结束时是 `ask_user_question`（主动澄清位置歧义），不是甩锅后 completed
- 这是**行为质的改善**：不确定就问，而非假装完成

## 三、发现一个真 bug（我引入的）

### 语义检查"连续 3 次写入相同"是误报
- trace `semantic_check_fail step=17 issues=["连续 3 次写入完全相同内容"]`
- 会话 seq1854 `[harness 语义检查] ... 连续 3 次写入完全相同内容`
- **但实测 turn12 只有 1 次 write client.js**（seq1820）
- **根因**：`patch_wargame_fixes.py` 的 `repeatedWriteCount`/`lastProductHash` 从不在 turn/start 重置，
  上一轮 turn11 残留的 hash 让本轮首次写入即被误判为"重复"
- **已修复**：turn/start 加 `s.repeatedWriteCount = 0; s.lastProductHash = ''`

### 误报的连锁伤害
- seq1854 误报后，模型被误导"先修正再继续"，多绕了几步
- 这是"机制自身制造问题"的又一例（如 cwd bug 假语法错误）

## 四、旧病复发清单

| 旧病 | 本轮状态 |
|---|---|
| 臆造 slot | 未复发 ✓ |
| 错位 slot（settings.section） | 未复发 ✓ |
| 双副本不同步却称一致 | 未复发 ✓ |
| F12 甩锅 + completed | 未复发 ✓ |
| 重复探测循环 | **部分复发**：grep×13、D1 强制停止在 step29 触发（但这是探索 slot 的必要 grep，不全是空转）|
| 目标漂移 | 未复发（全程锚定"左边栏"）|
| 连续写相同内容 | **误报**（真 bug，已修）|

## 五、新机制触发清单（turn12）
| 机制 | 触发 | 效果 |
|---|---|---|
| `skill_card` | 1（dsh-ui-slots）| ✅ 生效，模型读了卡 |
| `semantic_check_fail` | 1 | ❌ 误报（bug，已修）|
| `d1_probe_guard` | 1（grep×5）| ✅ 强制停止生效 |
| `open_correction_survived_compaction` | 4 | ✅ 纠错跨压缩保留 |
| `archive_dedup` | 1 | ✅ 存档去重生效（首次观察到此 kind）|
| `review_verdict` (audit) | 1 ISSUE | ✅ 审计识别到"只 grep 未改" |
| `control_turn` | 1 | 正常 |
| `safety_gate_block` | 0 | 本轮未触发（无甩锅/无 forceStop 场景）|

## 六、结论

**这次是明确改善的一轮**：
- **skill 卡机制从"零加载"变成"真实命中并读取"**——口语化关键词修复被实证有效
- **slot 从"臆造/错位"变成"用对真实 sidebar slot"**
- **双副本真同步、不甩锅、目标不漂移**

**但仍有两个问题**：
1. 我引入的"重复写入误报"bug（已修，需重启生效）
2. 它最终停在 `ask_user_question` 问 4 个选项——因为"左边栏"确实有 4 种可能位置（左侧窄栏/宽侧栏/顶部 tab/右侧面板）。**这算合理澄清**，但也说明：单靠"左边栏"这种模糊指令，模型仍无法确定具体 slot，需要更明确的指代。

## 七、诚实边界
- 会话仍在 running，未 turn/end，所以"最终是否成功"要等用户回答后才知道
- `sidebar.footer.action` 是否真的在 UI 上显示为"可点进去的入口"，未在 DSH 界面点击验证
- 重复写入 bug 修复后未重新验证（需重启 dsh）
- 本轮 grep×13 是否算"重复探测复发"有争议——探索 slot 时多次 grep asar 是合理的
