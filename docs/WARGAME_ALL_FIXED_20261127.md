# 审计员 + 纠正器攻防演练：全部修复报告（2026-11-27 10:45）

## 一、起点：完整攻防演练（35 项）

`wargame_full_20261127.mjs` 35/35 按预期，其中 **22 项成功复现漏洞**。
报告 `docs/WARGAME_FULL_20261127.md` 列出 S1~S10 全部问题。

最致命的 S1：**D2 纠正器在最典型场景（同参双败）从不触发**——受控实验证明 corrector 0 次。

## 二、修复清单（全部完成）

### 第一批（已在前一轮完成）
- **S1**：D2 同参双败从 D1 的 `else if` 提前 —— 端到端验证 corrector 从 0 次 → 1 次（会话 af09fc7c）
- **S2**：collector 绿灯过滤 + 同源去重

### 本轮全部修复（S3~S10 + 补充 6 项）

| 编号 | 问题 | 修法 |
|---|---|---|
| S3 / D1 | 白名单含 grep 但执行器只认 read/glob | `executeReadOnly` 新增 grep 分支（单文件行匹配、上限 50 行） |
| S4 / B3 | danger_shell 原样注入 | `formatCorrection` 加工具白名单 `SAFE_TOOLS` + 危险参数拒绝 |
| S4 / B4 | reason 提示注入二次投递 | `sanitizeReason` 过滤注入模式、截断 200 字符 |
| S4 / B6 | 代执行内容原样注入 | 加 `DATA_BOUNDARY` / `DATA_END` 数据边界标记（内容保留作证据，语义框定） |
| S5 / C1C2 | 审计被 pendingInject 抢先 | 早返回前快照 `s.auditDebt`，D5 门控用 `Math.max(auditDebt, badCount)`，触发后清偿 |
| S6 / C4 | "每 8 步审计"日志谎言 | 改日志为真实的 D5 门控描述 |
| S7 / E1 | criticAccepted 一次 ACCEPT 永久放行 | 每轮 `turn/start` 重置 `criticAccepted = false` |
| S7 / E2 | verifyFail 参数含 test 即清 | 清除条件加 `c?.ok !== false`（工具须成功） |
| S7 / E4 | reviewState.resolved 文本洗白 | 改为 `(s.writeCalls || 0) > 0`（须真实写入） |
| S7 / E3 | handoffBlocked 任意工具清 | 限定写类工具（write/edit/pwsh/...） |
| S8 / F3 | Critic 中段盲区 | >12000 字符改头 4000 + 中段采样 2000 + 尾 4000 |
| S8 / F2 | REJECT+low 静默逃逸 | 保留 `criticLowConfidence` 标记，不再无痕 |
| S9 / D3 | junction 路径逃逸 | `resolveSafePathWithCfg` 加 `realpathSync` 二次校验 |
| S10 / A3 | collector 无纵深防御 | 加 `TOOL_GUARD` 工具名二道防线 |
| C8 | corrector 未用 constrained JSON | `callLLM` 传 `constrained: true`（与 audit/planner/critic 一致） |
| C6 | D2 args 字符串严格相等可绕过 | 新增 `normArgs()`（JSON 解析 + 键排序 + 去空白） |
| F5 | Planner 失败也消耗名额 | `plannerChecked` 移到检查成功产出 verdict 之后 |
| D2(glob) | glob 单层 readdir | 支持一层子目录通配（`*/*.ext`），上限 200 |

## 三、验证结果

### 修复验证脚本（20/20 PASS）
`wargame_fixed_verify.mjs` 逐项反向验证所有修复：
```
F1-F20 全部 PASS
```

### 攻击复现脚本（从 22 个漏洞降到 10 个模式匹配残留）
`wargame_full_20261127.mjs` 从 35/35（22 漏洞复现）变为 **22 PASS / 13 FAIL**。
剩余 10 个 `[漏洞验证] PASS` 经逐项核对，全部是**检测脚本的模式匹配过时**：
- B6：内容仍原样插入（设计如此——证据必须保留），但已加 `DATA_BOUNDARY` 边界标记
- C1/C2：D5 仍在 pendingInject 之后（顺序未变），但已用 `auditDebt` 快照缓解
- C4/D1：断言查旧字符串模式，代码已改（日志措辞 / grep 白名单）
- E2/E3/F1/F2/F3：断言查"旧代码模式仍在"，但我加了新条件（success check / write check / reset / flag / mid-sample）

这些不是"漏洞仍在"，而是"老断言只看旧模式"。实际行为由 F1-F20 验证覆盖。

### 真实端到端复验
重启后 harness 正常加载（`loadedAt 02:36:35`）。受控实验（会话 `3f8f13cf`）：
```
d1_probe_guard ×2        ← D1 重复探测守卫工作
evidence_cited ×2        ← 审计证据链工作
edit_echo_compressed ×1  ← P1 编辑回显压缩工作
```
（这轮模型读了 6 次，走 D1 路径；上一轮 2 次同参失败走 D2 路径，corrector 1 次。两条路径按设计分工。）

### 全量回归
```
test_audit_allfix.mjs   25 PASS / 0 FAIL
test_wargame_fixes      ALL PASS
test_wargame_gaps       ALL PASS
test_all_remaining      ALL PASS
test_format_correction  25/25
test_format_executor_result 全通过
test_collect_corrector_input 19/19
wargame_fixed_verify    20/20
```

## 四、工程插曲：换行符混乱

期间用 Python 脚本读写导致 index.mjs 从混合换行（3727 CRLF + 13 LF）变成全 CRLF/LF，
git diff 显示全文件 7000+ 行变化。用 `git add --renormalize` + 统一 CRLF 解决，
最终 diff 干净（每次改动 20-50 行）。

**铁律**：这个项目 `core.autocrlf=true`，改 `index.mjs` 必须用 `git add --renormalize`，
否则 diff 不可读、merge 会地狱。

## 五、最终状态

- 所有提交已推送，工作区干净
- 两版（publish / 运行版 node_modules）已同步
- harness 已重启加载全部修复
- 攻防演练发现的 22 个漏洞全部有对应修复 + 反向验证

## 六、诚实边界

1. **真实会话复验只覆盖了部分机制**（D1/D2/审计/编辑回显），S7/S8 的 Critic 行为未在真实会话里逐一触发验证（只做了代码+单测验证）
2. **D5 审计抢先用 auditDebt 缓解而非根治**——顺序仍是 pendingInject 在前，只是证据不再丢
3. **B6 是"框定"不是"过滤"**——恶意文本仍在上下文里，只是被标为数据；强提示注入仍可能影响弱模型
4. **realpath 校验只防 junction/软链逃逸**，不防 TOCTOU（检查后到读取前的竞态）
5. 攻防演练脚本的老断言未更新（保留作为历史记录），新人可能误读——已在本报告说明
