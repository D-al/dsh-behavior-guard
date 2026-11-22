# S24 换测法重测 + verify-on-stop 矛盾修复（2026-11-22 收尾）

> 触发：用户"重测修复后的，是不是要换种测法；修矛盾"

## 一、换测法：从"靠模型犯错看 trace"改成"真实事件结构驱动接线"

### 旧测法的问题
- 造必然失败的 edit 任务，靠 35B 自然犯错 → 它用 write 绕开，测的是运气
- 首轮抓到 FS_STALE_VERSION 覆盖缺口（单测覆盖想象码，真实环境用另一码）——但即便修了，再次靠模型犯错仍不可靠

### 新测法（确定性）
`tools/test_tool_failure_heal_integration.mjs`：mock ctx → 用**真实抓到的事件结构**（FS_STALE_VERSION / isError:true / source.callId）驱动 `session/event` → 触发 `agent/pre-step` → 断言 decision.messages 里有自愈提示。

**4/4 PASS**：
1. FS_STALE_VERSION 失败 → 注入 '[harness 工具自愈]…先 read 目标文件'
2. 只注入一次（pendingHeal 已清，不重复）
3. 开关关闭时不注入
4. 用户取消（ASK_CANCELLED）不注入（避免提示风暴）

加上纯函数单测 9/9 → **S24 卡从 in_progress 提到 done**，有确定性证据。

## 二、verify-on-stop 矛盾修复

### 根因（上次查到）
- 判据（index.mjs:1034 S13）：普通 read **不算**验证证据（要 pwsh 验证命令 / 带 `[VERIFY]` 标记或 `test_` 文件）
- 提示词（index.mjs:1890）：却说"调用 read 读取刚写文件，读回后就能收尾"
- → 模型照提示 read，判据不认，二次拦截 → "读来读去"死循环

### 修复
提示词改为与判据同源：
- 第 1 次：明确"用 pwsh 跑真实验证命令（py_compile / node --check / pytest）；数据文件则 read 带 [VERIFY] 的验收文件；**普通 read 不算验证**"
- 第 2 次：明确"仍缺少判据认可的验证证据；单纯 read 刚写的普通文件不计入"

### 一致性单测（钉死防回归）
`tools/test_maintenance_fixes.mjs` 加 2 条：断言提示不再说"读回之后才能收尾"、且给出判据认可的动作。全文件 **7/7 PASS**。

## 三、状态
- 门禁 **69/69**（原 68 + 新增集成测试）
- 运行版 index.mjs 与权威源 sha 一致（38d8ee30…）
- dsh 按需关闭（本轮不需要拉起；真实验证首轮已完成，修复由集成测试确定性覆盖）
- 推送：`2f74236`，工作区干净

## 四、诚实标注
- S24 的"真实会话端到端失败率下降"**仍未测**——本轮验证的是"接线正确"（确定性集成测试），不是"对 35B 行为有效"。要测后者需拉 dsh 跑 A/B 多轮，是另一个实验。
- 但相比首轮"靠模型犯错看 trace"，新测法排除了运气因素，能确定"钩子在正确事件下会注入正确提示"。
