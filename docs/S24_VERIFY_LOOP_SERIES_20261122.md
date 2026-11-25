# S24 验证与读取回路（2026-11-22）

> 验证/读取回路设计与复测修复

> 本卷合并 2 份原报告（2026-11-25 整理）。

## 本卷目录

- `S24_VERIFY_AND_READ_LOOP_20261122.md`
- `S24_RETEST_AND_VERIFY_FIX_20261122.md`

---

## 原报告：`S24_VERIFY_AND_READ_LOOP_20261122.md`

## S24 真实验证 + 连续读文件归因 + Diff-XYZ 纠错（2026-11-22）

> 触发：用户先问"做真实验证"，中途插问"它刚刚连续读了好多次文件，分析原因"，并要求查 Diff-XYZ 编辑能力最高的方法。

### 一、S24 真实验证：代码存在≠生效（又一次实证）

#### 做了什么
- 造必然失败的 edit 任务（对不存在的文件 edit 一个 sentinel），新会话 `session-795b3a1e…`
- 结果：edit 连续 **3 次失败**，trace 里有 `tool_result FAIL` ×3，但 **S24 的 `tool_failure` / `tool_failure_heal` 打点 = 0**

#### 根因（实测）
查真实 `tool/result` 结构：
```
data.error = {name:'FsError', code:'FS_STALE_VERSION'}
content: 'Error: cannot edit "...": file changed since it was read — re-read the file, then retry'
```
**真实错误码是 `FS_STALE_VERSION`**，而 S24 的 `healHint` switch 只写了 `FS_EDIT_NOT_FOUND` / `FS_NOT_FOUND` → 返回 null → 不满足 `if (f && healHint(f))` → 没设 pendingHeal → 没打点。

#### 修复与状态
- 已加 `FS_STALE_VERSION` case（语义：先 read 再 edit），单测 9/9
- ⚠ **修复后尚未重测**：dsh 已按"按需"关闭，第二轮真实验证待做
- S24 卡状态 `in_progress`（诚实：单测过、真实验证未完成）

**铁律再验证**：项目里"代码存在+单测过≠真实生效"的规定，这次又抓到一次——单测覆盖了想象中的错误码，真实环境用了另一个码。

### 二、连续读文件归因：不是模型贪读，是守卫判据自相矛盾

#### 事实澄清
验证会话的工具序列是 `edit×3 → write×1 → read×1`——**没有"连续多次 read"**（全局同期只有这一个会话，read 仅 1 次）。

#### 但发现了真正的重复拦截死循环
- seq 46：守卫注入 `[harness 停止条件｜必须执行]` —— "调用 read 读取刚写的文件，读回后才能收尾"
- seq 48：模型照做，read 成功
- seq 58：守卫又注入 `[停止条件｜第 2 次拦截]` —— "你上一条结束尝试已被否决——缺少验证动作，现在必须调用 read"

#### 根因：提示与判据矛盾
- `index.mjs:1034` **S13 收紧**：废弃"write+read 宽松规则"——普通 read **不算**验证证据，必须带 `[VERIFY]` 标记或是 `test_*`/`verify_*` 文件
- `index.mjs:1890` **verify-on-stop 提示词**：却叫模型"调用 read 读取文件确认内容"就能收尾

于是模型照提示做了 read，判据不认（verifyEvidence 仍 0），再次拦截——**指令让它做 A，判据只认 B**。这是"读来读去/反复拦截"的真凶，与 S24 无关。

#### 建议（未执行）
二选一：① 让提示词要求"带 [VERIFY] 的读取或真实验证命令"（与 S13 判据一致）；② 把 read 回读本身作为一类弱验证证据计入。① 更符合 S13 防假绿的初衷。

### 三、Diff-XYZ 论文纠错：35B 属于"格式获益"区间，不属于"收益小"

#### 论文原文（arXiv:2510.12487v2, Table 5）
比较 4 种表示：`udiff` / `udiff-h`（relaxed hunk header）/ `udiff-l`（ADD/DEL/CON  verbose）/ **`search-replace`**（Aider/PatchPilot 风格锚点替换）。

**各模型 Apply EM（越高越好）：**
| 模型 | udiff | udiff-h | udiff-l | search-replace |
|---|---:|---:|---:|---:|
| GPT-4o | 0.86 | 0.85 | 0.82 | **0.94** |
| GPT-4.1 | 0.90 | 0.92 | 0.91 | **0.96** |
| Claude 4 Sonnet | 0.95 | 0.95 | 0.95 | **0.97** |
| **Qwen2.5-Coder-7B** | 0.58 | 0.57 | 0.57 | **0.75** |
| **Qwen2.5-Coder-32B** | 0.84 | 0.83 | 0.83 | **0.92** |
| Qwen2.5-Coder-3B | 0.38 | 0.41 | 0.34 | 0.41 |
| Qwen2.5-Coder-1.5B | 0.16 | 0.16 | 0.11 | **0.22** |

#### 回答用户问题：什么方法编辑能力最高
**`search-replace` 格式**——在 Apply 任务上对几乎所有模型都是最高（强模型 0.94-0.97，7B 0.75，32B 0.92）。Diff-Generation 上它也大多最高。Anti-Apply 上偶有例外（32B 的 udiff 0.87 略高于 search-replace 0.85）。

#### 对 S14 卡的纠错（重要）
S14 卡记的结论"**smaller open models benefit little from any formatting choice**"——这是**摘要原句被误读到本地 35B 上**：
- 论文里的 "smaller open models" 指 **0.5B / 1.5B / 3B**（绝对分 0.00-0.41）
- **7B 和 32B 明确从 search-replace 大幅获益**（+29% / +10%）
- 本地是 **35B**——落在获益区间，不是"收益小"区间

**但结论方向不需要翻案**：dsh 原生 edit 工具就是 `old_string`/`new_string` 的 search-replace 形态——本地已经在用论文推荐的最优格式。真正的问题不是格式选错，是 **old_string 太长导致精确复制失败**（RoPE 1D 归纳偏置），也就是 S14 "降复现负担"和 S24 "执行层兜底"针对的点。

#### 附带发现：`udiff-l`（显式 ADD/DEL/CON 标记）是最差的——多数模型上 Diff-Gen EM 掉到 0.00-0.08。任何"把 diff 标记做得更明确"的想法都被论文证伪。

---

## 原报告：`S24_RETEST_AND_VERIFY_FIX_20261122.md`

## S24 换测法重测 + verify-on-stop 矛盾修复（2026-11-22 收尾）

> 触发：用户"重测修复后的，是不是要换种测法；修矛盾"

### 一、换测法：从"靠模型犯错看 trace"改成"真实事件结构驱动接线"

#### 旧测法的问题
- 造必然失败的 edit 任务，靠 35B 自然犯错 → 它用 write 绕开，测的是运气
- 首轮抓到 FS_STALE_VERSION 覆盖缺口（单测覆盖想象码，真实环境用另一码）——但即便修了，再次靠模型犯错仍不可靠

#### 新测法（确定性）
`tools/test_tool_failure_heal_integration.mjs`：mock ctx → 用**真实抓到的事件结构**（FS_STALE_VERSION / isError:true / source.callId）驱动 `session/event` → 触发 `agent/pre-step` → 断言 decision.messages 里有自愈提示。

**4/4 PASS**：
1. FS_STALE_VERSION 失败 → 注入 '[harness 工具自愈]…先 read 目标文件'
2. 只注入一次（pendingHeal 已清，不重复）
3. 开关关闭时不注入
4. 用户取消（ASK_CANCELLED）不注入（避免提示风暴）

加上纯函数单测 9/9 → **S24 卡从 in_progress 提到 done**，有确定性证据。

### 二、verify-on-stop 矛盾修复

#### 根因（上次查到）
- 判据（index.mjs:1034 S13）：普通 read **不算**验证证据（要 pwsh 验证命令 / 带 `[VERIFY]` 标记或 `test_` 文件）
- 提示词（index.mjs:1890）：却说"调用 read 读取刚写文件，读回后就能收尾"
- → 模型照提示 read，判据不认，二次拦截 → "读来读去"死循环

#### 修复
提示词改为与判据同源：
- 第 1 次：明确"用 pwsh 跑真实验证命令（py_compile / node --check / pytest）；数据文件则 read 带 [VERIFY] 的验收文件；**普通 read 不算验证**"
- 第 2 次：明确"仍缺少判据认可的验证证据；单纯 read 刚写的普通文件不计入"

#### 一致性单测（钉死防回归）
`tools/test_maintenance_fixes.mjs` 加 2 条：断言提示不再说"读回之后才能收尾"、且给出判据认可的动作。全文件 **7/7 PASS**。

### 三、状态
- 门禁 **69/69**（原 68 + 新增集成测试）
- 运行版 index.mjs 与权威源 sha 一致（38d8ee30…）
- dsh 按需关闭（本轮不需要拉起；真实验证首轮已完成，修复由集成测试确定性覆盖）
- 推送：`2f74236`，工作区干净

### 四、诚实标注
- S24 的"真实会话端到端失败率下降"**仍未测**——本轮验证的是"接线正确"（确定性集成测试），不是"对 35B 行为有效"。要测后者需拉 dsh 跑 A/B 多轮，是另一个实验。
- 但相比首轮"靠模型犯错看 trace"，新测法排除了运气因素，能确定"钩子在正确事件下会注入正确提示"。
