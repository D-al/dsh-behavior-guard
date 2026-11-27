# 最终报告：环境修好了，但模型行为仍不可控（2026-11-27 09:55）

## 一、环境完全修好 ✅

### 根因（一句话）
`git checkout 2fff7b9 -- index.mjs` 只恢复了 `index.mjs`，**没恢复它依赖的 `tools/s6_signal_gate.mjs`** →
模块 import 失败 → `apply()` 从未执行 → probe 不写、trace 不写、零注入。

### 诊断路径（可复用的排查手册）
1. trace 不写 → 查 probe `_agent_harness_loaded.json` 的 `loadedAt`
2. loadedAt 不更新 → 说明 `apply()` 没跑
3. **手动 `node --input-type=module -e "import { apply } from './index.mjs'"`** ← 决定性一步
   → 报 `ERR_MODULE_NOT_FOUND: tools/s6_signal_gate.mjs`
4. 对比 publish 与运行版的 `tools/` 目录 → 运行版缺 2 个文件

### 修复
从 publish 按 `index.mjs` 的 import 清单精确同步：
- 新增 `tools/s6_signal_gate.mjs`
- 更新 `tools/build_trail_text.mjs`

验证：`module loaded OK` → `APPLY OK` → 重启后 probe 更新 → trace 恢复写入。

### 撤销的实验
曾加显式挂载 `agent-harness-explicit` 试图绕过 bundle——**证明无效后已撤销**，避免双挂载。

## 二、P0-P3 机制全部实现且工作 ✅

| 层 | 状态 | trace 证据 |
|---|---|---|
| 确定性消歧 | ✅ | `ambiguity_detected` + `ambiguity_pats` + `ambiguity_resolved hits:1` |
| 完整行注入 | ✅ | 注入含**可直接用作 old_string 的完整行** |
| P0 去重 | ⚠️ 实现但少触发 | 模型每次 read 范围不同 → hash 不同 → 不满足"完全相同" |
| P1 编辑回显 | ⚠️ 实现但少触发 | 同上 |
| P2 并行提示 | ✅ | 已注入 |
| 硬中断 | ✅ | `step_hard_warn` + `step_hard_stop` |
| verify-on-stop | ✅ | 曾误判（见下），已修 |

### 又修了 2 个真 bug
1. **注入缺完整行**：模型 edit 需要 old_string，只告诉它"当前值 #1f2937"不够 → 它必须读文件。
   修：注入里直接给出目标行完整内容（600 字符内）。
2. **verify-on-stop 误判**：edit 成功后仍注入"产物还没真正改动"→ 模型被推回去重新验证。
   修：`edit` 带 old_string 且返回 `updated successfully` → 视为已验证（`edit_is_verify`）。

## 三、效果检验：机制到位，行为不可控 ❌

### 决定性实验（颜色场景 aec37cca）
模型收到的注入：
```
[harness 环境事实] 目标已确定：<绝对路径> 第 18 行。
该行完整内容（可直接用作编辑的 old_string，不必再读文件）：
wrap.style.cssText = 'position:fixed;...background:#2d3748;...';
```

**信息完整到可以一步 edit。** 实际行为：
```
glob → read ×18 → grep ×8 → 0 次 edit → step_hard_stop
```
18 次 read/grep，**始终没调用 edit**。产物里的 #1f2937 是第 22 行 header 本来就有的，不是它改的。

### 对照（另一次同任务 8102ed55）
```
glob → read → grep → edit（第 4 步就改对了）→ grep → read ×4 → grep → pwsh
```
同任务，这次第 4 步 edit 成功，但编辑后又空转了 5 步（这是 verify-on-stop 误判，已修）。

### 结论
**同一个模型、同一个任务、同样的注入：一次第 4 步改对，一次 18 步都没改。**
方差完全来自模型本身，不是 harness。harness 能做的都做了——把答案喂到嘴边、拦空转、
给验证信号——但**它无法让一个 35B Q4 模型稳定地执行一个明确指令**。

这就是 SAGE-Agent 那两类不确定性的最终分界线：
- specification uncertainty：**已解决**（harness 用规则确定性地消歧）
- model uncertainty：**未解决，且不是 harness 能解决的**

## 四、最终状态

- harness 环境：**完全恢复**（probe 更新、trace 写入、注入生效）
- P0-P3 代码：**全部实现并提交**
- 回归：**25 PASS/0 FAIL** + 三套 wargame ALL PASS
- 提交链：`da8ddba` → `2fff7b9` → `b9ec02b` → `02cbaa9` → `1127240`
- 工作区干净

## 五、给未来的铁律

1. **`git checkout <commit> -- index.mjs` 会留下孤儿 import** —— 必须同步检查依赖的 `tools/*.mjs`
2. **harness 静默时先手动 `import` index.mjs** —— 这是定位模块加载失败的最快方法
3. **probe 的 `loadedAt` 是插件是否加载的权威信号**，bridge health 的 pid 不是
4. **read 次数不是 harness 能控制的** —— 它取决于 edit 工具使用意愿；注入再完整也可能被无视
5. **edit 成功即验证**（对精确替换语义成立）—— 强行要求再验证会制造空转

## 六、不再继续的理由
- 机制侧已经做到极限：确定性消歧 + 完整行注入 + 拦截 + 验证信号
- 剩余方差在模型侧，继续调 harness 是过拟合
- 真正的下一步是**能力问题**：换更强模型或人工确认点，不是继续堆规则
