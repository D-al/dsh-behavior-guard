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
