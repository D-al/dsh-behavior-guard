# 部署报告：行为根源修复（2026-11-26 16:2x）

> 依据 `ROOT_CAUSE_AGENT_BEHAVIOR_20261126.md` 的三层根因，8 项修复全做。
> 全程补丁化、幂等、两版同步（publish 权威源 + runtime 运行版）。

## 修复清单与验证

| # | 修复 | 补丁脚本 | 验证 |
|---|---|---|---|
| P0-0 | checkSyntax 的 cwd bug | `patch_behavior_roots.py` | 相对路径 `hardware-monitor-plugin/client.js` 按 harness cwd 不存在 → 按 workspace 解析存在 ✓ |
| P0 | 语义检查器（slot/URL） | 同上 | 扫 asar 得 94 个 slot；`sidebar.right.header.actions` 判不存在 ✓；`conversation.composer.dock`/`pane.tab` 判存在 ✓ |
| P0 | 放弃式完成闸门 | 同上（+refine 收紧） | seq1420 命中；"请确认走哪个方案"和"代码里用了 window.open"均不误报 ✓ |
| P0 | Critic/深检真触发 | 同上 | 产物存在但没 present → 自动视为 present，Critic 上限 2 次/会话，幂等标记防死循环 ✓ |
| P1 | 目标锚定（叠加语义） | `patch_goal_anchor.py` + `patch_behavior_refine.py` | 原始目标 + 合法新增目标（崩溃/连接失败/左侧入口）都进 goalStack，state 重建不丢 ✓ |
| P1 | 防线2 正则扩展 | `patch_behavior_roots.py` | seq1402"slot 不存在/静默忽略"现在命中 ✓（原正则漏判）|
| P1 | verify_on_stop 溢出日志 | `patch_behavior_roots2.py` | 达上限 2 次后打 `verify_on_stop_overflow` trace 交 D5 兜底 ✓ |
| P1 | D1 重复探测升级 | 同上 | 第 3 次起"强制结束本轮"指令 + trace `d1_probe_guard` ✓ |
| P2 | skill 卡 | `bench/skills/dsh-ui-slots.md` | 记录 grep -ao 扫 asar 的正确方法 + 双副本同步 ✓ |

## 关键设计决策（诚实记录）

1. **目标锚定从"覆盖"改为"叠加"**：子任务复核指出崩溃/连接失败是用户**合法新增目标**，
   不是漂移。当前实现维护 `goalStack`（原始 + 新增），存档分两行显示，不抹掉合法目标。
2. **放弃式正则收紧为三条件**：指令性移交 + JS 代码证据 + 无工具调用。
   避免把"请确认走哪个方案"误判为放弃式交付。
3. **WS_ROOT 与 WORKSPACE_ROOT_FOR_CHECK 的"不一致"不是 bug**：
   前者是声明默认值（C 盘），后者用**实际存在的目录探测**（D 盘候选在前），
   实测相对路径解析正确。保留探测式实现。

## 验证文件
- `D:/tmp/dsh-investigate/test_behavior_roots.mjs` — cwd/slot/正则/放弃式四合一
- `D:/tmp/dsh-investigate/test_goal_anchor.mjs` — state 重建后目标保留
- `D:/tmp/dsh-investigate/test_refine.mjs` — 正则精度 + goalStack 叠加

## 落地状态
- 三个补丁脚本 + 一个精修脚本，全部幂等（`--check` 复验通过）
- 两版 `index.mjs` 语法检查通过（node --check）
- dsh 已重启（16:25），加载最终版本
- bridge/8081/8999 健康

## 诚实边界
- **未做真实会话回放**：没让 dsh 真的跑一遍"左侧入口"任务验证闸门拦截——
  这需要用户派任务触发，且会污染当前会话。验证靠单元级逻辑测试 + 事故原文回放。
- **语义检查的 URL 部分只覆盖 `/ui` 一个已知易错路径**，不是通用 URL 存在性检查。
- **Critic 真触发会增加 LLM 成本**（最多 2 次/会话，10-20s/次）——
  这是"软提醒无效"的必要代价。
- skill 卡改的是 `D:/Brain/workspace/bench/skills/`（harness 的 skillsDir 指向这里）。
