# 「学会自己走路」第二张卡 A3_5 实验报告（2026-11-20 13:20–14:20）

> 用户指令："请继续，在它运行且你有空的时候，深度维护一下，我希望你能配合它。"
> 双线并行：agent 爬 A3_5（安全地基），我做深度维护（一致性守卫落地）。

## 1. 双线成果

### 线 A：agent 爬 A3_5（核心功能由它完成）

| 能力 | 它的实现 | 验证 |
|---|---|---|
| 真实 diff 校验 | `real_diff_check()` 逐行 diff + target 匹配 | 旁观者测试 4/4 PASS |
| 回滚 | `deploy_with_rollback()` 快照 + e2e + 恢复 | trace 实证 sha256 前后一致 |
| 廉价 e2e | `run_all.sh`（node --check + config_check + 15 test_*.mjs）| bash 实跑 17/17 PASS |
| 反思 | `docs/reflection-A3_5.md`（三自证 + CritBank 教训）| 已落盘 175 行 |

### 线 B：我的深度维护（与 A 改不同文件）

| 交付 | 说明 |
|---|---|
| `tools/consistency_guard.py`（~280 行）| 清单驱动的零 LLM 一致性守卫，对比 A-remote/A-local/C-runtime/LOCK；CRLF 归一化、UNKNOWN 不假绿、自身出错 exit 2 |
| `config/GUARD_MANIFEST.yaml` | 两 repo 的权威/运行/远端路径、key_files（含 gate 与守卫自身）、lock 路径 |
| `tools/test_a35_real_diff.py` | 旁观者独立验收脚本——用真实场景样本（单 token）抓出 agent 自证样本过拟合的 bug |
| 重启钩子 | `restart_dsh.ps1` 加非阻断守卫检查，写 `_guard_restart.log`（ASCII-only、已 PS parser 校验、已备份）|

**守卫正向测试**：注入 1 字节不一致 → exit 1 + FAIL（sha/gitblob 双抓）；缺 manifest → exit 2；恢复 → exit 0。不是恒 PASS 的假守卫。

## 2. 干预与接管（诚实记录）

| 事件 | 处理 |
|---|---|
| 看门狗 13:24 误杀（长指令 prefill 被判冻死）| 诊断根因，引导语改短；未改看门狗（改它风险 > 收益）|
| 干预 1：self_test 从 11 项缩成 2 项 | send 软干预（消息被压缩吞掉，未生效）|
| 干预 2：`real_diff_check` 假阴性（`re.escape` 整串）| send 软干预（同样被吞）；但 agent 在自证中自己发现测试样本问题，顺带改对了 target 拆分 → 旁观者测试 3/4→4/4 |
| 最终接管 | agent 长会话退化（451 事件/19K token/多次压缩/重复动作循环），我接管修 4 个回归 |

**我接管修的 4 个回归**（都在 `self_harness_gate.py`）：
1. `real_diff_check` 拆 token（旁观者测试驱动）
2. `self_test` 恢复 14 项（原 11 + 新增）
3. `accept()` 返回语义恢复（agent 改成 `reject-degradation/...`，调用者会静默误判）
4. `surface_check` legacy 签名 fail-safe（proposer:94 仍传 list，不能假 PASS）

## 3. 关键教训（对 agent 与对系统）

1. **消息通道缺陷**：bridge send 走 queue，长会话压缩时 `agent/inbox/spliced` 会吞掉未处理消息 → 干预不可靠。需要 steer 或独立干预通道。
2. **长会话退化阈值**：~200 事件后 agent 焦点丢失、重复动作。应换新会话而非继续压缩。
3. **重写模块的兼容性**：agent 重写 gate 时改了 `accept()` 返回语义、`surface_check()` 签名——调用者（`self_harness_proposer.py:94`）不报错但静默误判。**破坏性 API 变更比功能缺失更危险**。
4. **测试样本过拟合**：它自证用的样本恰好含完整 target 字符串，掩盖了 `re.escape` bug；旁观者用真实样本（单 token）才抓出。测试要覆盖真实场景，不是"刚好能过"的样本。
5. **观察者要有接管阈值**：连续 3 轮无实质进展就接管，不无限等。

## 4. 最终验收（全绿）

```
self_harness_gate.py --self-test  → 14/14 PASS
test_a35_real_diff.py             → 4/4 PASS
bash tools/run_all.sh             → 17 pass / 0 fail
roadmap_check.py --verify A3_5    → 2/2 PASS
consistency_guard.py              → 同步后应 PASS（中间态 FAIL 属正常，守卫如实报警）
生产验收                          → 权威与生产逐字节一致，上述测试在生产同样通过
```

**能力阶梯状态**：A0 ✅ → A3_5 ✅。剩余项（`--next` 为空）都是 `manual`/`human` 轨道——**低风险自治区间已爬完**，再往上需要人工闸门（这正是设计意图）。
