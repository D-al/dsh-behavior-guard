# 部署：受控实验暴露的 4 个漏洞修复（2026-11-26 17:1x）

> 依据 `ACCEPTANCE_CONTROLLED_EXPERIMENT_20261126.md`：
> 模糊指令实验（39 分钟 / 44 步）暴露 4 个漏洞，全部修复。

## 修复清单

| # | 漏洞 | 修复 | 验证（用实验真实数据） |
|---|---|---|---|
| 1 | `handoff_gate` 用 `state.toolCalls===0`（本轮累计），step44 甩锅时累计=44 → 4 次触发全 blocked:false | 改用 `state.last?.toolCalls===0`（最后一条消息本身的 toolCalls）。seq1693 实测本条=0 → 新条件拦住 ✓ | test_experiment_fixes.mjs：seq1693 新条件 true、旧条件 false ✓ |
| 2 | D1 "强制停止"只是文本，模型继续跑到 step44 | 置 `s.forceStop=true` 硬标记；turn-stopping 开头硬拦 completed | 硬闸门标记逻辑测试 ✓ |
| 3 | 双副本不同步（它声称"同步✅"实际 sha 不同） | deep check 加 workspace 源 vs node_modules 安装副本 sha 比对，不一致 → 不允许交付 | 实测当前两副本 sha 不同 → 检出 true ✓ |
| 4 | Critic C-REJECT 只是 steer，模型继续跑完 completed | 置 `state.criticRejected=true`，与 forceStop/handoffBlocked 一起进硬闸门 | 3 标记逻辑测试 ✓ |

## 关键设计点

1. **硬闸门只拦一次**（`hardGateInjected` 标记）：防止死循环。代价是模型第二次甩锅不再拦——
   可接受，因为第一次拦截已强制它输出阶段性报告。
2. **标记每 turn 重置**：`forceStop/criticRejected/handoffBlocked/hardGateInjected`
   在 turn/start 时清零，避免一个 turn 的标记污染后续所有 turn。
3. **createHash import**：加了 `node:crypto` 的 `createHash`（原来只有 `randomUUID`，
   若漏加会导致双副本检查 ReferenceError 被 try 吞掉、静默失效）。

## 文件
- 补丁脚本：`tools/patch_experiment_fixes.py`（幂等标记 `EXPERIMENT_FIXES-PATCHED`）
- 验证脚本：`D:/tmp/dsh-investigate/test_experiment_fixes.mjs`
- 两版 `index.mjs`：publish + runtime 均已打补丁，语法检查通过

## 诚实边界
- 这是"用实验数据做的单元级验证"，**没有再次跑一次完整受控实验**——
  真实效果要等下次 dsh 任务触发闸门才能确认。
- 双副本 sha 检查只对 `hardware-monitor-plugin/` 这一条路径生效（路径匹配硬编码），
  其他插件不同步仍无法检出。
- 硬闸门拦住后模型会怎样（真的输出报告还是绕过去）未验证。
