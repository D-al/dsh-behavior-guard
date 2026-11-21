# 机器判据设计标准（2026-11-21）

> 缘起：M10 卡 4/4 判据全绿，但承诺的 kill_switch 没接进主程序、硬件三层检查完全没实现——**判据假绿**。
> 本报告建立标准 + 全量审计 60 张卡 103 条判据，并据此修复。

---

## 一、10 条判据设计 checklist（调研结论）

来源：mutation testing、契约测试、SWE-bench/WebArena/τ-bench 终态验证、RRSI、OverclaimBench 等一手研究。

| # | 检查项 | 拦截的病 |
|---|---|---|
| 1 | **可失败性**：故意破坏机制，判据必须 FAIL；否则无效 | 假绿测试 |
| 2 | **存在 ≠ 生效**：file_exists/grep 只能当前置门槛，不能作为机制生效的唯一证据 | M10/S15 |
| 3 | **承诺—判据 1:1 映射**：卡里每写一条机制承诺，必须有对应行为判据 | M10（4机制3条只查存在）|
| 4 | **环境终态 > 自报**：查可观察副作用，不采信 agent 声明/文档说有 | 假完成 |
| 5 | **验证接线**：机制接入主流程必须集成/E2E 判据，不能靠静态判据 | S15（57/57 未接线）|
| 6 | **负向断言**：断言"不该发生什么"（范围、权限、无关对象不变）| 副作用 |
| 7 | **判据先于实现**：执行前固定，判定与执行分离，附证据收据 | 事后解释 |
| 8 | **可重复去抖**：多次运行一致，判据源与实现隔离防作弊 | flaky / 硬编码通过 |
| 9 | **量化审计**：定期统计可失败率与存在性判据占比，设门槛 | 长期防回归 |
| 10 | **高风险对抗判据**：关键机制构造 plausible wrong patch，判据必须拒绝 | only-common-case 补丁 |

---

## 二、判据分级（审计口径）

| 等级 | 类型 | 含义 |
|---|---|---|
| **强** | `test_pass` / `gate_result` / `trace_count` / `trace_absent` / `json_field` | 验行为、事件、状态；实现删掉 → 判据 FAIL |
| **弱** | `file_exists` / `file_grep` | 验文件在/文本有；**弱 ≠ 错**，但只能当前置门槛 |
| **无** | `manual` / 空 | 需人工，不算绿 |

**关键区分（避免过度修正）**：
- **实现型卡**（承诺机制接线：kill_switch / verify-on-edit / sid 过滤）→ 弱判据 = 假绿，必须升级
- **文档/决策型卡**（交付物就是文档：实验结论、重定基线分析）→ `file_exists` 是合理判据，但标注 `verify_type: document`
- **治理型卡**（STRATEGY.md 人类设定）→ `file_exists` + consistency 哈希锁 = 强证据（哈希锁验的是"未被篡改"，是行为）

---

## 三、全量审计结果（60 卡 / 103 判据）


| 等级 | 数量 | 说明 |
|---|---|---|
| OK（纯强）| 14 | 直接验行为 |
| MIXED（强弱混合）| 15 | 强判据兜底，可接受 |
| WEAK_ONLY（纯弱）| 16 | **需逐卡判断**：实现型必须修，文档型标注 |
| MANUAL | 15 | 未实现/需人工，不算完成 |

**已完成但纯弱判据（最高风险）10 张**：S4, S7, gpu_guard, watcher_freq3, rebaseline, S11, A0, A3_5, A1_7, S16

---

## 四、修复记录（2026-11-21）

### M10（会话生命周期治理 / 刹车）— 重写为 1:1 行为判据

**原判据（4/4 假绿）**：
- grep bridge.mjs `case 'cancel'` → 只证明 CLI 命令写了
- grep index.mjs `sessionController.cancel` → 只证明调用写了
- file_exists SESSION_BRAKE 文档 × 2 → 只证明文档写了

**问题**：卡的 `what` 承诺 4 个机制（kill_switch 三级刹车 / taskProfile / loop_breaker / 硬件三层检查），
判据一个都没验。文档自己"待办"段写着"硬件三层检查 + cancel inbox 语义还没写进判据"。

**新判据方向（按 1:1 + 验证接线）**：
1. `test_pass tools/test_kill_switch.mjs`（已有 4 断言）— 验 kill_switch 逻辑
2. `file_grep index.mjs 'killSwitch|kill_switch'` — 验**接进主程序**（原来完全没有）
3. `test_pass tools/test_future_claim_guard.py` — 验安全护栏（已有 8 PASS）
4. 硬件三层检查 / cancel inbox 语义 → 标 `manual`，明确"未实现不算完成"

### A1_7（评审可观测性）— 升级为真实 trace 证据

**原**：grep index.mjs 有 `review_verdict` 文本 + 文档存在
**新**：加 `trace_count(kind=review_verdict, min=10)` — 真实 trace 里已有 **286 次**触发，这是行为证据

### A0（sid 黑名单）— 升级为行为判据

**原**：file_exists test_sids.json + grep 3 个脚本含 test_sids
**新**：加 `test_pass tools/test_sid_blacklist.py` — 验"黑名单真能过滤掉测试 sid"

### 审计工具

`tools/audit_verify.py` — 静态分类所有卡判据强弱，--strict 模式发现 WEAK_ONLY 就非零退出。
这是第 9 条"量化审计"的落地，防未来回退。
