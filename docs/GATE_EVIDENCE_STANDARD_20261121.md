# 闸门证据标准：让"需拍板/需验证"不再空泛（2026-11-21）

> 缘起：用户问"按科技树是不是该先拍板哪些工具进内核"——查发现 M5 卡了很久，
> 不是因为决策难，而是**拍板需要的数据一直没结构化**：数据躺在 docs 和 dump 里，
> 闸门只写"用户拍板哪些工具进内核"，看不出"数据齐没齐、还差什么"。
> 用户要求"把所有类似问题解决了"——本文是通用解法。

---

## 一、问题：闸门有四种，只有一种该等人

| 闸门类型 | 例子 | 缺什么 | 怎么解 |
|---|---|---|---|
| **指标型** | P-86M-LATENCY 延迟<500ms | 无（有阈值）| 保持，跑测试验 |
| **数据支撑型** | P-USER-DECISION 拍板工具 | **数据没进闸门** | ← 本次修复重点 |
| **外部依赖型** | P-UPSTREAM-PR 等上游合并 | 无（等外部事件）| 标 HUMAN，不硬造 |
| **阈值待定型** | P-SWEBENCH 迁移子集 | 没定达标线 | 诚实标"阈值待定"，不硬造数字 |

**核心洞察**：`P-USER-DECISION` 不是"纯人工决策"——它是**数据可支撑的决策**。
把它归进"纯人工"是分类错误，导致数据缺口被隐藏。

---

## 二、M5 修复实例（模板）

**修前**：`preconditions: ['P-USER-DECISION: 用户拍板哪些工具进内核']`，manual-blocked，看不到数据状态。

**数据其实一直存在**：
- `docs/MEMORY_TO_MIND_MODEL_20261120.md` 记录"工具面28个、单会话只用11个、17零调用"
- `archive/session-dumps/_cur*.jsonl` 8个会话 dump，2849 次调用

**但 `tools/tool_audit.py` 是断的**：
- 默认路径 `bench/_cur8.jsonl` 不存在（历史遗留）
- 要求 request/header 含 tools schema，否则报"无法审计"——真实 dump 只有 tool/call 事件

**修法（四步）**：
1. 修 `tool_audit.py`：默认指向真实 dump、兼容无 schema 格式、加 `--json` 机器可读
2. 实测产出：`8 会话 / 2849 调用 / 11 工具 / 前5占90% / 前8占98%`
3. M5 加结构化 `data_gates`：
   ```yaml
   data_gates:
     - id: P-TOOL-FREQ-AUDIT
       desc: 工具频次审计：8会话2849调用/11工具/前5占90%/17零调用
       status: satisfied
       evidence: tools/tool_audit.py --json
       source: docs/... + archive/session-dumps/_cur*.jsonl
   decision_note: 数据已齐……拍板只需决定砍哪些低频工具，不再是拍脑袋
   ```
4. 科技树 M5 卡显示 `📊1/1` 角标，侧栏显示数据前置 + 决策状态

**结论**：闸门从"空泛拍板"变成"📊数据齐、只差你拍板"——决策成本大幅下降。

---

## 三、通用处理规则（以后照此办理）

遇到"卡在需拍板/需验证"的闸门：

1. **先分类**：指标型 / 数据支撑型 / 外部依赖型 / 阈值待定型
2. **数据支撑型**必须有 `data_gates`（含 id/desc/status/evidence/source）
   - `status: satisfied` 且 evidence 脚本可跑 → 卡上显示 📊N/N
   - 缺数据 → 审计报 VAGUE，禁止声称"只差拍板"
3. **空泛描述回填阈值**：从卡片自己的 `abort_if`/`caveats` 里提取（不硬造）
   - 例：M9 的"中文表现验证" → "中文准确率>=92%"（来自 abort_if）
4. **真无阈值的诚实标"阈值待定"**，不编数字
5. **纯外部/治理决策**标 HUMAN，不要求数据脚本

---

## 四、防回归

`tools/audit_gate_evidence.py --strict` 进门禁：
- 12 条前置逐条分类：6 指标 / 1 数据齐 / 5 人工或待定 / **0 空泛**
- **负对照验证**：删掉 M5 的 data_gates → P-USER-DECISION 立刻变 ✗空泛、审计 FAIL；恢复 → PASS
- 关键设计：`P-USER-DECISION` **不在** HUMAN_DECISION 白名单——它是数据支撑型，缺数据必须报错

`tools/tool_audit.py --json` 也进门禁——数据管道断了会立刻发现。

---

## 附：给用户的实际建议

工具面拍板的数据已经齐了：**实际只用 11/28 工具，前5种占90%，17个零调用**。
所以"砍哪些"的答案很明确——低频的 `web_fetch`(8次) / `load_workspace_dependencies`(8次) /
`job_kill`(16次) 是首选候选；但要不要砍仍需用户拍板（产品判断，agent 不得自主）。

门禁现 43/43；审计强判据（负对照验过）。
