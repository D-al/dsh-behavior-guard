# A/B 实验最终报告（2026-11-27 15:50）

> 用户："根治；然后继续做实验"
> **诚实结论：根治完成了；实验跑完了，但拿不到"越学越聪明"的因果证据。**
> 原因不是机制失效，而是：① 第一层测的是纯观测开关，② 样本量与方差不足以支撑结论。

## 一、根治完成的三项

| 项 | 根因 | 根治 | 验证 |
|---|---|---|---|
| critbank 双副本漂移 | config 9 条 vs bench 10 条 + 双向复制脚本 | bench→config 同步为 10 条字节一致；新增 `tools/critbank_gate.py`（SHA256 一致 + 无裸文件名 + ID 连续），接入回归链 `test_critbank_gate.mjs`；`critbank_calibration.py` 改读 bench（与运行时同一副本） | 门禁 OK：10 条/sha256=64ceb782a100205c/裸文件名 0；负向测试能检出裸串、不误判绝对路径 |
| 裸文件名复发 | install-restore-config.ps1 / sync.ps1 复制 + 人工从旧模板复制（**无生成脚本**，watcher 明令禁改） | 门禁把"裸 verify_agent.py"列为 fail-closed；每次启动/回归都查 | 负向测试 True / 绝对误检 False |
| compaction 纠错保留验证缺口 | 短会话无 compaction，`unclosed_correction_preserved` 埋点从未真实触发 | 不能造真实长会话（59K token 阈值，6 分钟/轮），改为源码级 + 行为级集成测试 `test_compaction_correction.mjs`：真纠错句 2/2 穿透去重、纯计划 0/6 排除 | 9 PASS / 0 FAIL |

**仍然不是真实验证**：`unclosed_correction_preserved` 没在真实 compaction 中触发过。这是诚实边界，不伪装成"根治成功"。

## 二、实验设计与执行

### 2.1 三层证据

| 层 | 开关 | 因果链 |
|---|---|---|
| 第一层 | `reflectionMiningEnabled` | 捕获（**纯观测**） |
| 第二层 | `reflectionInjectEnabled` | 捕获 → 回注 → 行为（**真干预**） |
| 自然实验 | 按上线时间切 trace | 混杂变量多 |

### 2.2 数据

| 组 | n | tool_calls/会话 | failures/会话 | hard_stop/会话 | mined/会话 |
|---|---|---|---|---|---|
| off（捕获关） | 2 | 7.50 | 3.00 | 1.00 | 0 |
| on（捕获开，未回注） | 8 | 4.25 | 1.00 | 0.25 | 4.50 |
| inject-on（捕获+回注） | 4 | 6.25 | 1.75 | **0.00** | 5.75 |

回注埋点实证：`reflection_live_injected: 2`（控制回合 2 次都触发），确认因果链路真的打通了。

自然实验（同 trace 按上线时间切）：重犯率 6.2%(1/16) → 0%(0/10)，hard_stop/session 0.44 → 0.67（反向）。

### 2.3 关键自我纠错

跑到一半发现：**72 次 `reflection_mined`，但 `reflection_compact_injected: 0`、`reflection_live_injected: 0`**。

**第一层 A/B 测的是纯观测开关——捕获了但从未回注，不可能改变行为。**
观察到的组间差异（on 4.25 calls vs off 7.5）来自随机方差与会话混杂：
- off-1 遇到路径歧义（`ambiguity_detected`），6 次失败
- on 组扩大到 8 次后波动巨大（2~8 calls，2/8 硬停）
- inject-3 未完成（10 calls / 4 failures）

## 三、为什么拿不到因果结论（诚实）

1. **样本量不足**：n=2/8/4，35B 单次方差 ±10%，要判优至少每组 20 次
2. **非同批次**：三组在不同时间跑，中间重启过 3 次，模型状态/温度/上下文可能不同
3. **任务太简单**：固定 2 步任务，区分度低（A 组多数恰好 2 calls/1 failure）
4. **任务陷阱不同**：有的会话遇到歧义、有的没遇到，这是最大混杂
5. **自然实验 41 vs 6 会话不可比**，重犯率 1 次 vs 0 次完全不显著

## 四、这次实验真正证明了什么

✅ **证明**：
- 机制生效（HVR 分流、宽正则捕获、三闸门、critbank 门禁、回注链路）
- 误拦消失（P0 三项真实验证）
- 根治有效（critbank 门禁、校准对齐、compaction 集成测试）
- 回注链路打通（`reflection_live_injected > 0`）

❌ **没证明**：
- 模型因这些机制变得更聪明
- 同类错误率显著下降
- 回注优于不回注（inject-on 的 failures 1.75 反而高于 on 的 1.0）

## 五、下一步（要拿因果结论必须做）

1. **同批次随机化**：一次重启内交替跑 on/off/inject-on，消除重启与时序混杂
2. **每组 ≥20 次**，3 种任务类型（简单/歧义/长链）
3. **固定判据**：任务成功率 + 同类错误率 + hard_stop，不只看 tool_calls
4. **先验功效分析**：按当前方差（±3 calls）算需要的样本量，可能是每组 50+ 次
5. **若仍无差异**：接受"这些机制的价值在防错配，不在提升能力"——
   与"harness 杠杆 > 模型选择"不矛盾（那个杠杆来自 scaffold 结构，不是反思回注）

## 六、产物清单

- `tools/critbank_gate.py` + `tools/test_critbank_gate.mjs`：critbank 一致性门禁
- `tools/critbank_calibration.py`：对齐 bench 副本
- `tools/test_compaction_correction.mjs`：compaction 去重穿透集成测试（9 PASS）
- `tools/reflectionInjectEnabled` 开关 + `tools/test_reflection_inject.mjs`（5 PASS）
- `tools/ab_reflection_runner.py`：受控实验执行器
- `tools/ab_reflection_analysis.py` + `tools/ab_summary.py`：数据分析
- `bench/_ab_reflection_result.json`：14 组原始数据
- 全量回归：25 PASS + 三套 wargame ALL PASS + reflection 21/21 + compaction 9/9 + gate OK + inject 5/5 + 24/24
