# 四杠杆上线操作手册（测评完成后执行）

> 目标：四个优化杠杆细化到"测评一跑完就能上线"的程度。
> 原则：**准备 ≠ 应用**。以下脚本已写好并在临时副本验证通过，但**未应用到运行版**——
> 必须等 BFCL irrelevance 评测跑完（100/100），否则重启 dsh 会打断评测。

## 一、当前状态（2026-11-24 20:55）

- 评测：irrelevance 89/100，看护脚本 BFCLSupervisor 常驻（抗看门狗重启）
- 补丁：三个可用杠杆的 patch 脚本已写好，**在临时副本实跑验证通过**
  - 杠杆1 `lever1_state_readback_patch.py`：5 处替换，+96 行
  - 杠杆2 `lever2_state_board_patch.py`：5 处替换，+58 行
  - 杠杆4 `lever4_vote_patch.py`：4 处替换，+55 行（默认关）
  - 三补丁叠加：2541 → 2750 行，`node --check` 通过
- 杠杆3（工具阶段化）：**降级 P3/暂不做**——代码调研显示基建缺失（无 ctx.tools 接线）、
  阶段信号依赖已证伪的分类器、热替换风险高。退路：只在提示词层加"阶段建议工具"文本。

## 二、上线前检查（自动）

```bash
python tools/levers_deploy.py preflight
```

检查：①评测完成（100/100）②两副本 sha 一致 ③语法通过。**任一失败则拒绝上线**。

## 三、上线步骤（严格顺序）

```bash
# 1. 备份两处 index.mjs（必做，可回滚）
python tools/levers_deploy.py backup

# 2. 确认前置检查通过
python tools/levers_deploy.py preflight

# 3. 逐个应用杠杆（每次改权威源后自动同步运行版）
python tools/levers_deploy.py apply 1    # P0 确定性状态回读
python tools/levers_deploy.py apply 2    # P1 状态板
python tools/levers_deploy.py apply 4    # P2 K=5 投票（默认关，先不改行为）

# 4. 语法检查（两处）
node --check D:/Brain/publish/dsh-behavior-guard/index.mjs
node --check D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs

# 5. 门禁（必须 0 fail）
bash tools/run_all.sh    # 期望 77 pass, 0 fail

# 6. 重启 dsh（按 skills/release-plugin.md 的流程）
#    ⚠️ 此时评测必须已完成，否则不要重启
Stop-Process dsh/llama → Start-ScheduledTask RestartDsh → 等 65s → health check

# 7. 触发真实会话（让机制命中）
#    用 bridge 发一个明确"写文件+声称完成"的任务，触发确定性回读

# 8. 验证生效（L4 真实 sid trace + 门禁）
python tools/levers_verify.py --fresh-min <重启后的ISO时间>
# 全部 PASS 才算上线成功；有 FAIL 不得宣布完成
```

## 四、验证判据（三条缺一不可）

| 层 | 判据 | 脚本 |
|---|---|---|
| L2 单测 | 门禁 77 pass / 0 fail | `run_all.sh` |
| L4 trace | 真实 sid（非 s1）出现 `verify_state_readback` / `state_board_inject` / `self_consistency_vote` | `levers_verify.py` |
| L5 产物 | 故意制造"声称完成但文件没改"场景，确定性回读能拦住 present | 手工负向测试 |

⚠️ **L4 必须过滤 s1**：POSTMORTEM 实测 `_trace.jsonl` 9666 行中 89% 是单测假数据。

## 五、回滚（一键）

```bash
python tools/levers_deploy.py rollback
# 恢复两处 index.mjs 到备份 sha，然后重启 dsh
```

## 六、负向测试（防止机制静默失效）

1. **杠杆1**：故意让模型"声称完成但不写文件" → 必须被回读门拦截、不能 present
2. **杠杆1**：文件名含 "verify/test" 但内容没验证 → **不能**被误判为已验证（项目踩过的坑）
3. **杠杆2**：状态板超 4096 字节 → 必须自动截断，不能让 bridge 报 "text too long"
4. **杠杆4**：5 次采样全错但一致 → 必须因 minAgreement/置信度检查回退 UNCERTAIN，不能"把困惑封为共识"

## 七、A/B 验证（上线后持续观察，n≥16）

按 `LEVERS_LANDING_PLAN_20261124.md`：
-  Wilson 95% CI，不报单点
-  隐藏集防 Goodhart，分层报告防 Simpson 悖论
-  观测低值复测会自然回升（回归均值），多次取中位

## 八、一句话

补丁已备好且验证过语法，但**上线 ≠ 应用补丁**——必须过 preflight、备份、门禁、重启、真实 trace、负向测试这一整条链，才算真正生效。


---

# 上线执行与效果评估（2026-11-24 21:25 实际完成）

## 执行结果
- **备份**：两副本 sha=362e3715 → `.backups/levers-20261124/`
- **补丁**：lever1/2/4 全部应用，累积 sha `362e3715→54a90719→75f3ac44→52cb3a0e`
- **门禁**：中途出现 2 个 FAIL，经查是真实健壮性问题（非测试妥协），修复后 **77 pass / 0 fail**
  - 修复1：回读门 steer 文案加 verify-on-stop 判据关键词（真实验证命令/[VERIFY]）
  - 修复2：无结构化写目标时 skipped=true 跳过（fail-open），不误拦普通 write 调用
  - 修复3：状态板走控制回合 parts.push，不占 sharedInjections 预算（原先被回读门+verify-on-stop 挤占，L4 从未命中）
- **重启**：dsh 21:13:02 重启，探针 21:13:04（本次加载，非旧值），health ok
- 最终两副本 sha=`0e1df753`（三次修复后）

## 效果评估（tools/lever_effect_report.py，UTC 时间戳，since=13:13:00Z）

| 杠杆 | L4 真实会话 | 证据 | 判定 |
|---|:---:|---|---|
| 1 确定性回读 | 1 条 | `ok=true, evidence=文件 exists=1 fresh=1 bytes=11`，且 verify_on_stop 独立触发1次 | **生效** |
| 2 状态板 | 1 条 | step=8 触发 control_turn，`bytes=90` | **生效** |
| 4 K=5 投票 | 0 条 | `voteOnCritic=false`（默认关，设计如此） | **未验证**（按设计） |

**关键观察**：
- 杠杆1 的正向路径已证实（真写了文件→回读成功→trace 有完整证据）
- 杠杆1 与 verify_on_stop **并存不互斥**（同 sid 两者都触发），符合"先修落盘再验证"的分层设计
- 杠杆2 从"代码存在但 L4 从未命中"到真实触发——修复注入预算挤占后生效，这是"上线审计三层交叉"方法的又一次实证

## 诚实的效果边界
- **机制生效 ≠ 成功率提升**：L4/L5 只证明"机制真的跑了并改变了可观测状态"
- 要声称"成功率提升 X%"需 n≥16 的 A/B + Wilson CI（σ≈10% 噪声地板），当前样本不足
- 杠杆4 默认关是刻意选择：先验证低风险的 1/2，投票 ×5 成本高，需用户决策是否开启
- 负向测试（故意"声称完成但不落盘"看是否被拦）尚未做真实会话级验证——现有 77 门禁含 L2 级负向断言

## 回滚
```bash
python tools/levers_deploy.py rollback   # 恢复到 362e3715（含三次修复前的原始版本）
```


---

# 杠杆4 K=5 投票效果验证（2026-11-24 21:40）

## 执行过程
1. 开启 `voteOnCritic=true`（toggle_vote.py），重启 dsh（探针 21:31:30）
2. 发真实交付任务（写 vote_test_report.md + present）触发 Critic
3. **真实会话首次结果：5 次采样全 PARSE_FAIL，耗时 100s（5×20s 超时）**
   - 根因：投票用 `callLLMOnce` 单次超时硬编码 20000ms，thinking 模型 20s 内出不完 JSON；
     原 Critic 的 `callLLM` 用 90000ms 且有 reasoning_content 兜底
   - 修复：单次超时 20s→60s（`Math.min(60000, timeoutMs)`），总预算 180s→360s
4. 补单测 `tools/test_self_consistency_vote.mjs`：**9/9 通过**
   - 多数票 ACCEPT 胜出 / 5 次采样记录 / agreed 阈值
   - tie 2/2/1 → UNCERTAIN（防"把困惑封为共识"）
   - 低于 minAgreement → UNCERTAIN
   - **thinking 格式（content 空 + reasoning_content 含 JSON）能解析，无 PARSE_FAIL** ← 真实会话 bug 的回归测试

## 关键决策：生产开关改回 false
- 全局开启 `voteOnCritic=true` 导致门禁从 77/0 掉到 75/3（a17_runtime / falsegreen_fixes / role_fixes）
- 根因：这些测试 mock fetch 假设 Critic 单次调用，投票改变了调用契约
- **改回 false 后 78 pass / 0 fail**（含新增投票测试）
- 结论：投票逻辑正确但**不能全局默认开**——它与现有测试契约和其他机制的预算模型冲突。
  若要用，需：(a) 只在对质量极敏感的任务类型按 taskProfile 条件开，或 (b) 重构测试契约。

## 效果评估（诚实）
- **L4 命中**：真实会话 `ae2d97e8` 出现 `self_consistency_vote` trace（5 次全 PARSE_FAIL，旧代码）
- **L2 验证**：修复后 9/9 单测通过，含 thinking 格式回归
- **未获得**：修复后真实会话的"正确投票"证据（未再跑一次 5 分钟的真实任务）
- **成功率提升**：无 A/B 数据（n≥16 门槛未达），不声称任何提升
- 生产默认关，成本（5×推理）与收益（防个别误判）的权衡需用户拍板

## 最终状态
- 生产：voteOnCritic=false（稳定态），门禁 78/0，两副本 sha=6e051953
- 能力：投票代码在包内且验证过，开关可逆（tools/toggle_vote.py on|off）


---

# 前3个杠杆效果测试（2026-11-24 22:20）

> 用户问"前3个杠杆效果怎么样"。杠杆3（工具阶段化）按调研结论**不做**（基建缺失+依赖已证伪分类器），
> 所以实际测已上线的杠杆1（确定性回读）+ 杠杆2（状态板）。

## 证据 A：受控 A/B 实验（tools/test_levers_ab_effect.mjs，12/12 通过）

同一场景开关机制对比，证明的是"机制改变了什么行为"，不是"trace 出现了"：

| 项 | 场景 | 结果 |
|---|---|---|
| L1-A/B | 关闭/开启回读门 | 关闭无 trace，开启有 trace（开关生效）|
| L1-C/D | 假完成（声称写入但文件不存在）| 开启后 `ok=false` **且 steer 拦截** ← 核心价值 |
| L1-E | 对照组（关闭）| 不拦截 |
| L1-F/G | 真落盘 | `ok=true` 且不误拦（无假阳性）|
| L2-A~E | 状态板 | trace 命中 + **内容进入 prompt** + 含 cwd/已改文件 + 字节≤4096 |

**这是"机制有效性"的硬证据**：假完成被拦、真落盘不误拦、状态板内容正确。

## 证据 B：历史 trace 分析（子任务，诚实结论）

- 两个杠杆在真实 sid 上各命中 **2 次**（样本严重不足）
- trace 中**无可归因证据**表明改变了真实会话行为或提升了成功率
- 唯一看似正向的 steer 上升是合成测试污染（s1 假数据，89% 基线）
- **判定：不能声称端到端效果**

## 证据 C：真实会话复验（修复后）

- 会话 `b860bd34`：写 cf_verify.txt，step=9 触发回读门
  - `ok=true, evidence=['...cf_verify.txt: exists=1 fresh=1 bytes=18']`
  - 产物真实存在且内容与字节数吻合 → 回读门在真实会话中正确工作
- 状态板未触发：该会话无控制回合（control_turn=0，既有每8步+预算行为），
  非杠杆2 bug——A/B 实验已证明触发时内容正确

## 过程中抓到并修复的真 bug

**杠杆2 的 `changedFiles` 累积里用了未定义的 `callFull`**（实际变量是 `fullArgs`）：
- `JSON.parse(callFull||'{}')` 抛 ReferenceError → 被 catch 吞掉 → changedFiles 永远为空
- 后果：状态板的 `changed=` 字段在生产中一直是 `(none)`，即使 trace 命中、机制"看起来生效"
- 这正是"文档宣称完成≠代码实际生效"的又一例：**trace 命中 ≠ 字段正确**
- 修复：callFull → fullArgs，sha a58d59a5，两副本同步，重启 22:16:19 生效
- 修复后 A/B 从 11/12 → 12/12，门禁 79/0

## 综合判定（三层分开说）

1. **机制触发（L4）**：✅ 真实会话命中（回读门 2+ 次、状态板 step=8 一次）
2. **行为改变（L5，受控）**：✅ A/B 12/12 硬证据——假完成被拦、真落盘放行、状态板进 prompt
3. **成功率提升（端到端）**：❌ **无证据**——真实会话样本 n=2，远不足 n≥16 A/B + Wilson CI 门槛

## 最终状态
- 生产：杠杆1/2 开启（sha a58d59a5，重启 22:16:19），杠杆4 默认关，杠杆3 不做
- 门禁：79 pass / 0 fail
- 回滚：`python tools/levers_deploy.py rollback`（回到 362e3715）
