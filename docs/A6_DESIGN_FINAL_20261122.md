# A6「验收可信度加固」最终方案（社区调研 + 本地证据综合，2026-11-22）

> 缘起：两轮自动推卡复盘（docs/MEMORY_AND_REFACTOR_20261120.md）发现 9 阻碍 5 盲区，
> 科技树覆盖审计 8 类教训 0 全 / 5 部分 / 3 空白。
> 本文综合社区调研（2024-2026 一手实践）+ 本地已有方法论，重新设计 A6 并落地。

## 一、最重要的认知校正

**方法论不缺，缺的是接线。** 项目早已有：
- `docs/VERIFY_DESIGN_STANDARD_20261121.md` 10 条判据 checklist（来源就是 mutation testing / 契约测试 / SWE-bench / OverclaimBench）
- `lineage/MUTATION_AUDIT.md` 反向测试实证（抓出过恒真断言）
- `tools/check_verify.py` 判据四类病检测
- `tools/test_mutation_guards.mjs` mutation harness

但它们**没有接进自动推卡流程**——两轮推卡我凭经验核验，没走这套标准。A6 的核心不是"发明新方法"，是**把已有标准接线 + 补两个社区更优做法**。

## 二、社区调研结论（5 问题 → 可落地做法）

| 盲区 | 社区成熟做法 | 本地现状 | 结论 |
|---|---|---|---|
| 测试未纳入门禁 | **collection census**：基线快照所有测试 ID，diff 检出新增/删除；退出码不得被 `\|grep` 吞 | glob 自动发现 mjs（34/34），但 py 显式列表（1/12） | 抄 census 思路：快照 + diff，不止 glob |
| 伪行为测试 | **变异测试** kill rate 70-80% 设门槛；test smells（tautology/vacuous）静态识别 | 有 MUTATION_AUDIT 但没接 CI；4 处恒真断言仍在 | 抄：变异 kill rate + 清 4 处恒真 |
| agent 自报不可信 | **verifier-actor 分离**：每步从环境取 ground truth，自报必须附机器证据（退出码/hash）由外部复算 | 我一直在手工做独立核验，但没有制度化 | 抄：把"独立核验"写成 SOP + 判据 |
| 连续失败卡住 | **有界重试 + 代码级 circuit breaker**：同工具同参数重放/成本涨状态不变→升级；验证失败只修一次 | harness 有 D1/D2 探测环检测，但"改文件失败"无显式规则 | 抄：失败 2 次换方法（已是我实际做法），写进纪律 |
| 数据源不可信 | **幂等去重 + 数据契约 + 血缘**：稳定 id  upsert、重放两次 diff、reconciliation 告警 | A0 只过滤 sid；本次踩 zstd 多帧/cursor 无效/快照重复 4 个坑 | 抄：统计脚本必带 source/provenance 标签 + 去重自检 |

**出处**：Anthropic building-effective-agents、SWE-bench/SEAL、StrykerJS/mutmut/PIT、Great Expectations Core 1.0、DEV collection census、ICLR2024《LLMs Cannot Self-Correct》、Berkeley MAST。

**不采纳**：LLM-as-judge 自评（有 self-preference 偏差，与生成模型共基座时错误相关）——我们本来就用确定性判据，方向对。

## 三、A6 最终设计（判据 5 条，autonomous=true）

### 判据 1：测试收集普查（collection census）— 新增脚本
`tools/test_census.py`：
- 扫描 tools/ 下所有 `test_*.mjs`、`test_*.py`、`*gate*.py`（self_test 类）
- 与 `run_all.sh` 实际执行集合 diff → 输出 `missing_in_gate` 清单
- 与基线 `tools/_test_census_baseline.json` diff → 新增/删除测试报警（删除需豁免说明）
- exit 0 = 全覆盖且无未声明变更；exit 1 = 有缺失
- **本质**：把"第五类病（测试未纳入门禁）"从 check_verify.py 独立成 CI 门禁

### 判据 2：py 测试全纳入门禁（覆盖缺口修复）
- run_all.sh：11 个 test_*.py 逐一纳入（已预检 10/11 通过 + 1 个刚修好 = 11/11）
- 预期门禁数 44 → 55
- self_harness_gate 已在门禁（上轮纳入）

### 判据 3：清 4 处恒真断言
- test_new_guards.mjs:167（`|| true`）、:170（`check(...,true,true)`）→ 用 mock fetch 真测 MTP 信号
- test_build_trail_text_integration.mjs:99、test_task_profile_integration.mjs:75 → 改为真行为断言
- 判据：全库 grep 恒真模式 = 0 处

### 判据 4：独立核验 SOP（verifier-actor 分离制度化）
- 写 `docs/VERIFICATION_SOP_FOR_AUTOCARD.md`：模型自报不算数，必须 ①门禁真跑取 rc ②判据用 roadmap_check 真验 ③权威源/运行版 sha 真比 ④git 状态真查
- 把 SOP 关键点写进 A5（自己走）backlog 卡的前置条件

### 判据 5：行为断言规范 + 变异抽样
- 写 `docs/BEHAVIOR_ASSERTION_STANDARD.md`：真范例 test_disabled_tools.mjs（真调 apply()+emit）；反范例：源码 grep / MockState 重写 JS 逻辑
- 对 3 个关键守卫做变异抽样（关掉机制 → 对应测试必须 FAIL），记录到 MUTATION_AUDIT

## 四、与已有卡的关系（不重复造轮子）
- A1_5（判据元验证）：判据 1 的 census 脚本补它查不到的"第五类病"，但不改它的四类病逻辑
- A0（数据可信）：判据 5 的 SOP 补数据源陷阱 caveat，不改它的 sid 黑名单
- S17（函数外置）：判据 5 的行为断言规范是它的测试层补充
- A5（自己走）：判据 4 的 SOP 作为它的前置纪律

## 五、落地顺序
1. 先建 A6 卡（ready, autonomous=true, 5 判据）
2. 本次直接落地判据 1/2/3（有即时收益，且不依赖新卡流程）
3. 判据 4/5 文档随 A6 卡一起交付
4. 全门禁 55/55 后推 A6 done

## 六、数据来源
- 社区调研：agent general-purpose-1（2026-11-22），出处见第二节
- 本地证据：docs/MEMORY_AND_REFACTOR_20261120.md、VERIFY_DESIGN_STANDARD、MUTATION_AUDIT、门禁覆盖量化（py 1/12）、恒真断言扫描（4 处）
