# 地基自动维护机制：调研 + 设计（2026-11-22）

> 缘起：用户问"靠人挨个查是沧海一粟，有没有办法自动维护地基？"
> 结论：**没有银弹，但有 4 个近乎零成本的机制可以组装成自治守护循环**。
> 社区调研（agent，1min）+ 本地盘点交叉验证。

## 一、为什么人工排查必然不够（本地证据）

地基腐化的三个特征：
1. **隐性**：腐化不报错不崩——纯弱判据、恒真断言、退出码 0 都是"看起来全绿"
2. **累积**：每个小改动都合理，叠加才致命——三副本漂移、测试陆续烂掉
3. **滞后**：发现时已在沙上盖了几层——A1 reflection 当年"换测试绕开"而非修，`test_controllable_forgetting` 潜伏至今

本地盘点：
- **有 19 个现成校验脚本**（config_check/audit_verify/audit_implicit_deps/check_verify/
  test_census/roadmap_check/audit_gate_evidence/tool_audit/self_harness_gate…）——素材齐全
- **有常驻 daemon**（LearnWatchDaemon / learn_watcher.py）——但只做学习 watcher，不巡检地基
- **缺编排层**：所有检查只在推卡/人工触发时跑，没有持续自治循环
- **设计≠代码**：CONSISTENCY_GUARD_DESIGN 写了 verify_integrity/mirror_drift，代码零实现
- 现在的模式永远是：**事故→人工发现→补一个检查**（响应式）

## 二、社区调研结论（5 方向 → 可落地）

| 方向 | 社区成熟做法 | 本地适用? |
|---|---|---|
| **适应度函数** | Ford《Building Evolutionary Architectures》：把架构约束写成**会失败的测试**；口诀"数据在哪、怎么取到"；轻量化是几十行扫描+CI，不引框架 | ✅ 高度适用——19 个检查器就是数据源 |
| **元测试** | ①没进门禁→collect census（已做）；②恒真→变异测试（Stryker/mutmut/PIT，阈值 50-60% 防回退）；③腐化→tsDetect/PyNose smell 检测；朴素有效法："故意改坏一个行为，确认测试变红" | ✅ census 已做；sentinel 可抄；变异测试按周跑 |
| **自改进护栏** | RRSI（arXiv:2609.24972，google-research/rrsi，Apache-2.0）：evolve/held-out 严格分离、leakage critic、noise floor δ、退火编辑预算、成本规则、失效剪枝、每轮 git worktree 隔离候选 | ⚠️ 抄 checklist，别照搬全流程（超参未验证）|
| **持续验证** | PBT（Hypothesis/fast-check）用不变量替代例子；变形测试无 oracle 时尤其适合 agent 多变输出；golden master 防快照膨胀 | ⚠️ 中选——PBT 对本场景成本偏高 |
| **风险早暴露** | SRE error budget（burn rate>2 停止发布）、canary+自动回滚、drift detection（PSI/KS）；"代码质量 drift"无开箱工具必须自建 | ✅ 质量 error budget 思路可抄 |

**社区明确没有银弹**：通用低成本恒真断言检测器不存在（tsDetect 只覆盖少量静态模式，变异测试诚实但慢）；
"自修改 agent 哪些核心必须不可变"无工程标准，RRSI 最接近。

## 三、最小可行机制：Foundation Guard（地基守护循环）

**核心洞察**：不写新检查器，给已有 19 个检查器加**自治编排 + 持续运行 + 异常升级**。

### 3.1 地基不变量清单（invariants，少而硬，6 条）
| # | 不变量 | 检查源（已存在）|
|---|---|---|
| INV-1 | 测试全在门禁 | `test_census.py` missing_in_gate=0 |
| INV-2 | 无纯弱判据卡 | `audit_verify.py --strict` 纯弱=0 |
| INV-3 | 权威源/运行版一致 | sha256 对比（我每次手工做→自动化）|
| INV-4 | 三副本一致（GRAPH/LADDER/TECH_TREE）| `audit_implicit_deps.py` + tech_tree --check（部分覆盖）|
| INV-5 | 无恒真断言/退出码丢失 | 静态扫描（A6 已清 4 处，需固化）|
| INV-6 | 门禁本身有效（sentinel）| 故意注入坏改动→确认门禁变红 |

### 3.2 自治循环（借 LearnWatchDaemon 巩固层，每 20 轮≈10min）
```
每轮巩固层触发 →
  跑 6 条 INV（都是纯脚本、零 LLM、几秒）→
  写 trace: foundation_check（PASS/FAIL + 具体哪条）→
  FAIL → 追加 _foundation_drift.jsonl + 阻止推卡状态（硬前置）→
  连续 N 次 FAIL → 升级告警（不静默）
```

### 3.3 关键设计原则（从本项目血泪 + 社区提炼）
1. **不变量少而硬**（6 条），不是把所有检查塞进去——噪音淹没信号
2. **失败可见但不阻断开发**：地基 FAIL 时允许改代码，但**禁止宣布完成/推卡状态**
3. **检查器自身也要被检查**：INV-6 sentinel 就是防"检查器自己恒真"（A6 教训）
4. **零 LLM、几秒、挂现有 daemon**——巡检本身不能成为新维护负担（S18 RRSI 成本规则）
5. **冻结 holdout**：agentlab/projectlab 的 30% 任务永不用于选卡（S18 已有，接进 guard）
6. **趋势可视化**：每次结果追加 jsonl，能看出"什么时候开始烂的"

### 3.4 与现有卡的关系
- A6（验收可信度 done）：INV-1/2/5 是 A6 成果的持续化——A6 是一次性修，Guard 是持续守
- S18（RRSI ready）：holdout + 噪声地板 + 一次一改 → Guard 的"编辑纪律"来源
- A5（自己走 backlog）：Guard 是 A5 常驻闭环的"地基心跳"前置——A5 启动时直接接
- LearnWatchDaemon：现成的常驻载体，挂巩固层即可，不新建 daemon

## 四、落地计划（分两步，先最小可行）

**第一步（本次做）**：`tools/foundation_guard.py` + INV 清单 + trace + drift jsonl，
并挂进 run_all.sh 作为第 58 项（让每次推卡都过地基检查），先不做常驻 daemon。

**第二步（验证有效后）**：挂 LearnWatchDaemon 巩固层做持续巡检 + 质量 error budget 趋势告警。

## 五、出处
- infoq.com/articles/fitness-functions-architecture（Ford 适应度函数）
- anthropic.com/research/property-based-testing + arXiv:2510.09907（agentic PBT）
- arXiv:2609.24972 / github.com/google-research/rrsi（自改进正则化）
- tsdetect.org（test smell）、macmyths.com "zero failures and zero tests look the same"
- 本地：docs/VERIFY_DESIGN_STANDARD、AUTOCARD_POSTMORTEM、lineage/MUTATION_AUDIT、CONSISTENCY_GUARD_DESIGN

---

## 六、方案修正：从"每10分钟轮询"到"变更驱动 + 按需体检 + 每日兜底"（2026-11-22 10:05）

**用户质疑**："长时间不推卡就一直扫硬盘，有没有像杀毒软件那样按需深度体检？"——质疑正确。

**实测**：foundation_guard 单次 2.4 秒，每10分钟=每天5.8分钟纯空转。
**社区调研修正**：2.4秒/天的兜底成本可忽略，不值得为省它牺牲兜底（Windows Defender 也是
realtime+nightly+weekly full）。所以不是"零定时"，是**高频轮询 → 分层**。

### 最终三层（对标杀毒软件）
| 层 | 触发 | 实现 | 空转 |
|---|---|---|---|
| **实时防护** | 每次推卡（run_all 第58项）| foundation_guard 全量跑 | 无（本来就要跑门禁）|
| **变更驱动巡检** | 指纹变化（代码/测试/权威源/运行版内容 hash）| LearnWatchDaemon 巩固层里比对指纹，变了才巡检 | **零**（无变化直接 skip）|
| **每日兜底** | 指纹没变但距上次≥24h | 同上，年龄判断；成功静默，失败告警 | 每天最多1次×2.4秒 |
| **按需深检** | 用户主动 | `tools/foundation_check.py`（doctor 风格：6条结果+失败定位+修复命令+--json）| 零（不跑就不耗）|

### 关键实现
- `tools/foundation_fingerprint.py`：内容 hash（**不用 mtime**——touch/改回原内容不该触发），
  覆盖 git HEAD + git status + 6个关键文件 + 所有 test_*.mjs/py
- 指纹基线 `D:/Brain/workspace/bench/_foundation_fingerprint.json` 含 `updated` 时间戳供每日兜底判断
- FAIL 时**不提交新基线**（下轮继续告警），HEALTHY 才提交
- foundation_guard 加 `--json`（供 agent 解析）+ 失败项附 `↳ 修复:` 具体命令
- foundation_check.py 是用户入口（区别于 daemon 内部用的 fingerprint/guard）

### 验证
- 稳态：连续两次体检，第二次显示"无变化"，daemon changed_rc=1（skip）→ **零空转确认**
- 变更检出：临时改 test_census.py → 指纹变 → 恢复 → 指纹回基线（内容 hash 正确）
- 每日兜底：年龄计算验证（81秒 < 86400 → 不触发）
- 门禁 58/58

### 社区出处（本轮补充）
fingerprint/cache（Bazel/GitHub Actions cache）、path filters（changed-files detection）、
pre-commit hooks（husky/lefthook）、杀毒软件 realtime/on-access vs on-demand full scan 分层、
Windows Defender daily quick + weekly full 兜底模型、error budget 用于质量 drift 告警。
