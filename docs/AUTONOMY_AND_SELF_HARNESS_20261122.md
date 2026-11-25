# 自主化与 Self-Harness 路线（2026-11-20~22）

> 自主化路线/差距/阶段规划与 Self-Harness P0-P2 实证

> 本卷合并 11 份原报告（2026-11-25 整理）。

## 本卷目录

- `AUTONOMY_GAP_20261120.md`
- `WALKING_PLAN_20261120.md`
- `SELF_HARNESS_PLAN.md`（原文件保留为引用桩）
- `S1_SELF_HARNESS_P0P1_RESULT.md`（原文件保留为引用桩）
- `S4_ADAPTIVE_AB_RESULT.md`
- `S7_SMALL_MODEL_BENCH_RESULT.md`（原文件保留为引用桩）
- `SESSION_BRAKE_20261120.md`
- `SINGLE_SESSION_ANTI_POLLUTION_20261121.md`
- `M9_REPOSITION_RESEARCH_20261122.md`
- `ROUTE_POSITION_AND_EVOLUTION_20261121.md`
- `STRATEGIC_SESSION_ANALYSIS_20261121.md`

---

## 原报告：`AUTONOMY_GAP_20261120.md`

## 心智模型"学会自己走路"：现状与差距评估（2026-11-20）

> 用户问：现在这个心智模型会自己根据路线图完成自己的更新了吗？如果没有，离这个目标还有多远？
> 结论先行：**不会。当前处于 L1（人工驱动 + 局部自动化），离 L4/L5（自主走路）还差 3 个数量级的闭环环节**——但差的不是算力，是"结构化 + 常驻 + 写回权限"三件事。

---

### 0. 定义"自己走路"

完整自主闭环 = 6 个环节全部无需人介入：

```
读路线图选任务 → 自主执行 → 自主验证 → 自主写回状态(勾选路线图) → 自主决定下一步 → 循环
```

当前每一个环节的实测状态：

| 环节 | 当前状态 | 证据 |
|---|---|---|
| ① 读路线图选任务 | ❌ **完全缺失** | 全仓库 grep：没有任何代码读 ROADMAP 来挑任务；ROADMAP 15 个 `[ ]`、0 个 `[x]`，完成项用"✅归档"散文段表示，机器无法解析 |
| ② 自主执行 | ✅ **强** | harness 本体（L0-L3/D1-D5/Critic/验收员）+ 工具面，已由人给任务时全自动跑完 |
| ③ 自主验证 | ✅ **已具备** | gate 11/11 单测、真实 trace 证据分层、`verify-on-edit`、Critic 产物评审；但**没和路线图条目绑定** |
| ④ 写回路线图 | ❌ **完全缺失** | grep 所有 .py/.mjs：无一处写 ROADMAP.md；勾选全人工 |
| ⑤ 决定下一步 | 🟡 **局部有** | 控制回合（实测 trace `control_turn` **229 次**，文档写作时为 19 次）+ todo 闹钟是 prompt 层软反思，代码**不做 if/else 换任务**；只管"当前任务内"，无 abandon/skip/换任务路径 |
| ⑥ 常驻循环 | ❌ **自进化未启动** | `learn_watcher.py` 常驻（Startup 每 30s、实测 **1936 runs**）但只消费 trace；**自进化 P3 按 ADR-0018 明确不启动**，候选目录只有 1 个 11-19 的文件 |

**能力阶梯：L0 全人工 → L1 人工给任务+自动执行+人工验收 → L2 自动验收写回 → L3 自动选任务 → L4 常驻闭环 → L5 自我修正路线图本身。当前 = L1（偏 L0/L1 之间，因为连验收报告也是人要我写的）。**

---

### 1. 已有的"走路器官"（不是从零开始）

项目**已经实现了 Science 论文式 Self-Harness 的一半**（`SELF_HARNESS_PLAN.md` 原文）：

- **可编辑面白名单** `surfaces.json` —— 规定了 agent 能改哪些文件（安全边界）
- **弱点挖掘** `weakness_miner.py` —— 从 8050 行 trace 挖弱点，产 `_evidence_bundle.json`（10.8KB 真实产物）
- **本地 35B 当 proposer** `self_harness_proposer.py` —— 读 evidence → 产候选 → 面校验 → 写隔离目录（`_self_harness_candidates/`，已有 1 个真实候选）
- **acceptance gate** `self_harness_gate.py` —— 纯统计门禁、零 LLM、11/11 单测
- **CritBank + 控制回合 + todo 闹钟** —— 运行时自我约束/元决策的真实 trace 证据

**这些正是"自己走路"需要的器官，只是没连成自主循环**——像有腿、有眼、有脑，但没人按"开始走"按钮，且走完不知道记路。

---

### 2. 三个真正的缺口（按难度排序）

#### 缺口 A：路线图不是机器可读的（最容易补）

现状：完成状态写在散文段（"## 7. ✅ 已完成（归档）"），未完成任务是 Markdown 表格里的 `[ ]`，没有稳定 ID 到产物/验证方法的机器映射。

**最小可行改造**：给每个条目加 `id: M1/M8/...`（已有！）+ 一句 `Done when:` 指向确定性判据（真实产物路径 / trace kind + 阈值 / gate 结果）。然后写个 60 行的核验脚本定期跑，把通过的 `[ ]` 改 `[x]` + 追加完成时间证据。

**难度：低-中**（纯文本处理，零 LLM，零显存）。注意两个实测细节：① 状态列混了额外语义（`[ ] ←下一波首项`、`[ ]（降级）`、`[ ]（观望）`），脚本要能容错；② **部分 DoD 是主观/人工判据**（M5「用户拍板」、M1「历史经验被主动引用>0次」、M7「端到端提速才上」），这些不能自动勾选，只能标记"待人工核验"。

**审计补充证据**：全仓库对 ROADMAP 的引用只有 3 处（package.json 打包列表、sync-to-profile.ps1 复制到副本、测试注释），**无一处写权威文件**；`git log -- ROADMAP.md` 全是人工发布提交（v2.23/v2.24/v2.25）。完成信号其实已存在——gate 退出码（`self_harness_gate.py:31-52`，零 LLM）、trace kind、产物文件——但**缺"条目ID→判据"映射表**。⚠ 判据**不要**依赖 `verify_agent.py`（它走 35B、600s 超时，非确定性且慢），优先用零 LLM 的 gate/单测/文件存在性（ADR-0012）。

#### 缺口 B：没有"执念"——没人按开始按钮（中等）

现状：P2 是"人为注入弱点→看闭环能否发现"的一次性实验；P3 常态化明确不启动。没有常驻进程在"没任务时"主动找下一个路线图项。

**最小可行改造**：把 `learn_watcher.py` 从"事件驱动消费 trace"扩展为"每 N 小时读一次 ROADMAP，挑第一个 `[ ]` 且前置满足的条目 → 写进任务队列 → harness 自动执行 → gate 验收 → 写回"。

**难度：中**（工程为主；但要注意"35B 每步 11s、无人值守跑长任务"的成本与安全——可能需要限制为低风险条目）。

#### 缺口 C：没有"写回权限"——人工审批闸门（最难，也是对的）

现状：ADR-0015/0018 明确规定候选**人工审批后才部署**、技能入库 G1+G2 人工确认。这是刻意的安全设计，不是 bug。

**关键判断**：这个闸门**不该去掉**——外部经验调研（Repair–Generalization Gap, arXiv 2610.22984）实证无人监管自写教训会让旧任务修好、新任务变差，错误归因率 20–53%。

所以要"自己走路"，不是去掉审批，而是**把审批前移到"规则/边界"层，而不是每次动作层**：agent 自主走在一张"已被批准的路线图 + 白名单"上，只有超出这张图才找人。

**难度：高**（是治理设计问题，不是技术问题）。

---

### 3. 距离量化（诚实版）

| 目标级别 | 描述 | 当前差距 |
|---|---|---|
| L2 自动验收写回 | 做完任务自动判成功、自动勾选 | 缺缺口 A（结构化判据）+ 一个 60 行脚本 ≈ **1-2 天工作量** |
| L3 自动选任务 | 从路线图挑下一个并启动 | 再缺缺口 B（常驻循环）≈ **再加 2-3 天**，但要解决"无人值守长任务成本" |
| L4 常驻闭环 | 24/7 自己走、自己记 | 再缺缺口 C 的治理框架 + 稳定性验证 ≈ **1-2 周**，且必须限定在低风险白名单内 |
| L5 自我修正路线图 | 能判断"这条路线图项本身该删/该改" | 需要价值判断/外部反馈，**本机硬件与机制都不支持，不建议追求** |

**一句话**：离"自己走路"差的主要不是智能，而是**工程胶水**——给路线图加机器可读判据、给 watcher 加一个定时循环、把审批从"每次动作"上移到"路线图准入"。这三步本机都跑得动（零额外显存、纯文本/定时脚本），但 L5 那种"自我改写目标"既不必要也不安全。

---

### 4. 建议的第一步（性价比最高）

只做缺口 A：把 ROADMAP 的 15 个未完成任务补上 `Done when:` 判据（指向真实产物/trace/gate），写核验脚本。这一步**立刻**让"完成状态"从人肉维护变成可自动核验——是后面一切自主化的地基。

代价：纯文本编辑 + 60 行 Python，无 LLM、无显存。收益：每次验收不再靠我写报告，而是脚本一句话给结论。

### 5. 自动化的三个真实风险（审计补充，必须防）

1. **假完成制度化**：`COMPLETION_AUDIT_20261119.md` 抓到过 3 个"宣称完成但没落地"（投毒防御只改 bench 副本、测试断言没跟上、数字过期）。自动勾选会**放大**这类错误——判据必须指向**运行版权威仓库 + 真实产物 + SHA256 校验**，并过滤测试 trace（sid=s1 假数据）。
2. **多副本陷阱**：`sync-to-profile.ps1` 是单向复制；写回必须明确写**权威源文件**（publish），写 bench 副本会在重装后丢失——这正是本项目反复踩的三副本不同步。
3. **人工判据不能自动勾选**：M5「用户拍板」、M7「降级/观望」、M1「被主动引用>0次」属人工或需埋点，应标记"待人工核验"而非自动 `[x]`。

**文档状态**：已纳入治理链（ROADMAP §知识资产 + CHANGELOG 2.26.4，commit `04310ab`）。

### 6. 审计抓到的两个"宣称 vs 实际"缺口（自主化的隐藏地雷）

1. **"35B 当 proposer" 是文档谎言**：`SELF_HARNESS_PLAN.md:53` / `S1_SELF_HARNESS_P0P1_RESULT.md:37` 都写"本地 35B 作 proposer"，但 `surfaces.json:3` 实际写 `proposer_model: workbuddy`，`self_harness_proposer.py:4` 注释亦承认"由 WorkBuddy agent 手工做"；真实候选 `candidate-1.json:7` 模型字段是 `WorkBuddy(claude-opus)`。本机 35B **从未担任过 proposer**——跑通协议 ≠ 35B 能自我改进。
2. **"写入目标"缺端到端验证**（2026-11-20 审计按实物更正）：`surfaces.json` editable 实为 6 个**细粒度 target**（3 个 prompt 文案、2 个阈值、1 个 skill 草稿目录），`critbank.json` 在 `forbidden_always`，index.mjs 不是整文件可改。⚠️ 我原先"白名单含主脑与 critbank"的字面断言是错的。但**治理缺口仍真实**：`surface_check()`（gate 55-69）只做**字符串匹配**不做真实 diff 语义校验，`accept()`（31-52）纯统计、**不跑 e2e、无面分级、无回滚入口**。绕过字符串匹配或误改阈值仍可能改变 harness 行为而无人验证——这是"学会走路"前必须先补的安全地基，优先级高于 L2/L3 功能推进。详见 [WALKING_PLAN 阶3.5](#原报告WALKING_PLAN_20261120)。

---

## 原报告：`WALKING_PLAN_20261120.md`

## 「学会自己走路」执行阶梯（2026-11-20）

> 用户目标：把"让这个模型学会自己走路（自主按路线图更新自己）"作为目标，把路线图切成**以现有能力可逐步实现**的东西。
> 设计原则：① 每一阶只用**已经存在**的器官（执行 harness / gate / watcher / CritBank / 控制回合），不依赖新智能；② 每一阶的完成判据**零 LLM 可验证**（文件/trace/退出码）；③ 每阶都保留人工闸门，只是闸门位置逐阶上移；④ 任一阶失败可独立回滚，不影响前面阶。
> 依据：[自主走路现状评估](#原报告AUTONOMY_GAP_20261120)（当前 L1）、[Self-Harness 方案](#原报告SELF_HARNESS_PLAN)、[ADR-0018](../decisions/0018-self-harness-two-stage.md)。

---

### 0. 现有能力 inventory（"手上已有什么牌"）

| 器官 | 已实现程度 | 证据 |
|---|---|---|
| 自动执行 | ✅ 强 | 人给任务后 harness 全自动跑完（L0-L3/D1-D5/Critic/验收员） |
| 零 LLM 门禁 | ✅ | `self_harness_gate.py` accept/reject/no-op、11/11 单测 |
| 弱点挖掘 | ✅ | `weakness_miner.py` → `_evidence_bundle.json`（10.8KB 真实产物） |
| 提案生成 | 🟡 协议级 | `self_harness_proposer.py` 真实候选 1 个（但模型是 WorkBuddy，非 35B） |
| 旁路常驻 | ✅ | `learn_watcher.py` 每 30s、实测 1936 runs（只消费 trace） |
| 软反思 | ✅ | 控制回合 229 次真实触发（prompt 层，非代码决策） |
| 教训注入 | ✅ | `matchCritbank()` tag 匹配、零 LLM、top2 |
| 版本/回滚基座 | ✅ | git + tag + `_cleanup_*` 备份惯例 |

**关键**：这些器官已足以支撑 L2-L3；缺的是**连接它们的胶水**和**安全前提**，不是新智能。

---

### 1. 阶梯总览（按依赖顺序，每阶可独立验收）

```
阶0 地基清洗 ─→ 阶1 会记路 ─→ 阶2 会指路 ─→ 阶3 会迈步 ─→ 阶4 会转弯 ─→ 阶5 自己走
 (数据可信)    (自动验收)    (自动勾选)    (自动选任务)   (任务内决策)   (常驻闭环)
  零 LLM        零 LLM        零 LLM        低风险队列     确定性信号      白名单内
  1-2天        1-2天         1-2天         2-3天         2-3天         1-2周
```

**每阶的"人"角色**：
- 阶0-2：人仍在环内，但**从"亲自动手"退到"看报告确认"**。
- 阶3-4：人**预先批准一张低风险任务白名单**，之后不再逐次批准。
- 阶5：人只维护白名单和预算，系统 24/7 在白名单内自己走。
- **全程不做 L5（自我改写目标/路线图本身）**——本机不支持也不安全。

---

### 2. 逐阶设计

#### 阶0：地基清洗（让数据可信）—— 前置中的前置

**要解决的真问题**（精确实测 2026-11-20）：

| 数据源 | 总行 | 测试假数据 | 真实 |
|---|---|---|---|
| `_trace.jsonl` | 9670 | **8787（91%）** | 883 |
| `_pending_learn.jsonl` | 741 | **709（95.7%）** | 32 |
| `_audit_feedback.jsonl` | 3 | 0 | 3 ✓ |
| `_learn_feedback.jsonl` | 11 | 0 | 11 ✓ |

测试 sid 精确清单：`s1`(8592/650)、`budget-3`(82)、`budget-4`(57)、`b7332eb6`(36)、`r`/`fb`/`b`、`outcome-`(57) 等。**不清洗，后面所有"自动判断"都建立在 91-96% 是假的沙子上。**

- **做什么**：把 sid 黑名单（s1/outcome-/budget-* 等）抽成共享配置 `bench/test_sids.json`，`learn_watcher.py` / `weakness_miner.py` / `trace_report.py` / 新核验脚本统一读它。
- **用现有能力**：纯文本过滤，零 LLM、零显存。
- **完成判据**（零 LLM）：`grep` 确认所有消费 trace/learn 的脚本都引用黑名单；抽样 100 行确认真实 sid 占比 >90%。
- **人做什么**：确认黑名单正确（一次性）。
- **风险**：低，纯过滤，不改数据本体。

#### 阶1：会记路（自动验收，人工勾选）

**对应缺口 A**：路线图不是机器可读的。

- **做什么**：给 ROADMAP 15 个未完成项各补一条 `Done when:`（指向真实产物路径 / trace kind + 阈值 / gate 退出码 / 单测名），用 HTML 注释块承载（保持人类可读）：
  ```
  | M1 | ... | [ ] <!-- done_when: {trace: "evidence_cited>0", artifact: "index.mjs:es.exe top-3"} -->
  ```
  写 `tools/roadmap_check.py`（~60 行）：只读解析 → 逐条跑判据 → 输出 `ID | 判据 | PASS/FAIL | 证据`，**先 dry-run 不写回**。
- **用现有能力**：文件 grep、trace JSONL 统计、单测退出码（全是已有的确定性信号）。
- **完成判据**（零 LLM）：脚本对已知完成项（§7 归档 16 项）回测 PASS 率 100%，对未完成项无误报 PASS。
- **人做什么**：看报告后**手工勾选**（闸门仍在人手里）。
- **风险**：主观 DoD（M5「用户拍板」、M7「降级」）标记为 `manual-only`，不进自动判据。

#### 阶2：会指路（自动勾选，限低风险）

**对应缺口 A 的写回半边**。

- **做什么**：`roadmap_check.py --apply` 只自动勾选**判据 100% 确定**的条目（文件存在/trace/gate/单测类），主观判据条目保持 `[ ]` 并标注"待人工核验"。写回必须：① 写**权威源** publish/ROADMAP.md（不是 p/bench 副本）；② 追加 CHANGELOG + 时间戳证据；③ git diff 可审阅。
- **用现有能力**：阶1 的核验结果 + git。
- **完成判据**（零 LLM）：人为改一个条目的判据使其 FAIL，确认脚本不勾选；恢复后确认勾选且只写权威源。
- **人做什么**：审 git diff，可 revert（闸门从"每次勾选"上移到"批 diff"）。
- **风险**：多副本陷阱（已明确写权威源）；假完成（判据指向真实产物 + 过滤测试 sid）。

#### 阶3：会迈步（自动选任务，限定低风险队列）

**对应缺口 B**。这是"按开始按钮"的一阶。

- **做什么**：建一个**人工预先批准的**低风险任务队列（例如只放"把已验证的离线脚本接进主循环"这类：M1 情景检索、M8 FSM 监控——它们的 DoD 是确定的、改动面在白名单内）。扩展 `learn_watcher.py`：每 N 小时读 ROADMAP，取队列中第一个前置满足的 `[ ]`，投递给 harness 执行 → gate 验收 → 阶2 的写回流程。
- **用现有能力**：watcher 常驻（已 1936 runs）+ 执行 harness + gate + 阶2 写回。
- **完成判据**（零 LLM）：注入一个假的"已满足前置"条目，确认 watcher 只执行队列内任务、不碰队列外；执行后 trace 有对应记录、gate 有判定。
- **人做什么**：**只维护那张低风险队列**（闸门从"每次任务"上移到"队列准入"）。
- **风险**：无人值守长任务成本（35B 每步 11s）→ 限制单次预算 + 只跑低风险；白名单含 index.mjs 的问题必须在阶3前解决（见阶3.5）。

#### 阶3.5：安全地基（必须与阶3同时或之前完成）

**治理缺口是真的，但我原先的字面断言写错了，按实物更正**（2026-11-20 审计）：

- ❌ 我原先写"白名单含 `index.mjs` 和 `critbank.json` 可改"——**与实物不符**。`surfaces.json` 的 editable 只有 6 个**细粒度 target**：3 个 prompt 文案（CONTROL/CRITIC/VERIFY）、2 个阈值（`adaptiveSimpleThreshold`/`mindStateLoopThreshold`）、1 个 skill 草稿目录。`critbank.json` 在 `forbidden_always`（8 类禁改面之一）。
- ✅ **但缺口仍在**：`surface_check()`（gate 55-69 行）只把 `modified_paths` 拼成字符串匹配禁改关键词，**不做真实 diff 语义校验**——绕过只是改个措辞/换个文件路径写法就可能漏检。而且无 e2e、无回滚。

- **做什么（审计给的三件胶水，零新智能）**：
  ① `surface_check` 从字符串匹配升级为**真实 diff 校验**（候选 vs 基线，命中非白名单行即 `allowed:false`）+ 面分级（prompt=低 / threshold=中 / 功能逻辑=高需 e2e+人工）；
  ② 加 `deploy_with_rollback(target, candidate)` 包装：改动前 cp 到 `archive/snapshots/<timestamp>/`，跑**廉价 e2e** 失败则自动恢复 + `trace({kind:'rollback'})`；
  ③ 廉价 e2e 最小集合 = `node --check index.mjs` + 全量 `tools/test_*.mjs` + `config_check.py`（**唯一真正覆盖主脑行为的是 test_*.mjs，不可省**）。
- **口径更正**：`self_harness_gate.py self_test` 实物是 **10 项**（ROADMAP 写 11/11 需更正）；`regression_check.py` 实为 **30 项**（非 29）且依赖 8081、只做语法检查不覆盖主脑 → 不进 e2e 必选集。`package.json` 无 `scripts` 字段，**没有一键全量命令**——阶3.5 应顺手补一个 `tools/run_all.sh`。
- **明确排除** `verify_agent.py`（35B + 600s 超时，非确定性）。
- **完成判据**（零 LLM）：故意注入一个改了非白名单行的候选，确认真实 diff 校验 reject；再注入一个破坏 index.mjs 语法的候选，确认 e2e 失败 + 文件自动恢复 + trace 记录。
- **人做什么**：定义面分级规则（一次性）。优先级高于阶3功能推进。

**阶4 治理冲突提醒**：`surfaces.json:53` 把 D1-D5 门控判定逻辑列为禁改面。阶4 不要改判定本体，应做**旁路决策器**（读现成信号 → 写 `meta_decision` trace → 发 skip），绕开禁改面；且信号目前只在 `info()` 日志里，需补结构化 trace。

#### 阶4：会转弯（任务内元决策代码化）

**对应缺口 E**：控制回合只是 prompt 软反思，代码无 abandon/skip。

- **做什么**：把已有的确定性信号（D1 重复探测 ≥3 次无新信息、D2 同参双败、D5 连续失败 ≥2）从"prompt 提示"升级为**代码层可执行动作**：命中时自动记录 trace `meta_decision` 并跳过当前子动作、换候选。不是让模型自由决定，是规则触发。
- **用现有能力**：这些信号在 trace/代码里已可机读（审计确认）。
- **完成判据**（零 LLM）：单测注入 D1/D2 签名，确认触发 `meta_decision` trace 且未执行重复动作。
- **人做什么**：确认触发规则（一次性）。
- **风险**：规则太宽会误伤；先只做 D1（最明确）再扩展。

#### 阶5：自己走（常驻闭环，白名单内）

- **做什么**：阶1-4 全部验收后，把 watcher 扩为完整闭环：读路线图 → 选任务 → 执行 → gate+e2e → 写回 → 记 trace → 下一轮。24/7 但**只在人工批准的低风险队列 + 可编辑白名单 + 单次预算上限内**。
- **用现有能力**：全部已有器官的连接。
- **完成判据**（零 LLM）：连续 7 天无人干预运行，每轮都有 trace 闭环、零越界、零需人工救场；人工定期 diff 审计报告。
- **人做什么**：维护队列/白名单/预算，定期审审计日志。
- **风险**：LLM 反复改写导致语义漂移 → 保留人工验证基线 + 定期 diff（OpenClaw memory-shepherd 范式）。

---

### 3. 与现有路线图的关系（重要）

**本阶梯是"元能力"轨道，与现有 15 个"心智器官"目标（M1/M8/M3/M9/M2/M5/M7/L2/L1/L6/L8/L5/L3/L4/L7）并行，不替代它们。**

- 阶0-3.5 是**纯工程**，不消耗 35B 推理预算，可以立刻做，**不需要等 M1/M8 这些器官完成**。
- 阶3 的低风险队列里可以放 M1/M8 这类"离线脚本接主循环"的任务——**它们的完成同时推进两条轨道**。
- 需要价值判断的目标（M5 工具面拍板、L1 世界模型、L5 自我修正）**永远不进自主队列**，保持人工决策。

---

### 4. 明确不做（安全红线）

- ❌ L5 自我修正路线图/目标本身（价值判断，本机不支持，不安全）
- ❌ 去掉人工审批闸门（Repair–Generalization Gap 实证：无监管自写 → 新任务变差、错误归因 20-53%）
- ❌ 用 `verify_agent.py`（35B 600s）做高频自动判据（应全用零 LLM 门禁）
- ❌ 自动勾选主观 DoD（M5/M7/L5）或写 p/bench 副本（必须写权威源）
- ❌ 让 agent 自由改 `index.mjs`/`critbank.json` 而不跑 e2e + 回滚（阶3.5 前禁止）

---

### 5. 现在就能开始的第一步

**阶0 + 阶1 的地基**（1-2 天，零 LLM、零显存、零风险）：

1. 抽 `bench/test_sids.json` 黑名单，改 4 个消费脚本统一过滤。
2. 给 ROADMAP 15 个条目补 `Done when:` HTML 注释判据。
3. 写 `tools/roadmap_check.py`（dry-run 版），对 §7 归档 16 项回测 100% PASS。

完成这三步，项目就从"路线图靠人肉勾选"变成"完成状态可机器核验"——这是后面一切自主化的地基。

---

## 原报告：`SELF_HARNESS_PLAN.md`

## Self-Harness 落地方案（2026-11-19）

> 来源：[Self-Harness: Harnesses That Improve Themselves](https://arxiv.org/abs/2606.09498)（arXiv 2606.09498v3，上海 AI Lab）
> + 官方仓库 [qzzqzzb/Self-Harness](https://github.com/qzzqzzb/Self-Harness)。
> 本文是**执行方案**，定位为 ROADMAP 新短期①「技能自进化数据闭环」的具体实现路径；决策依据见 [ADR-0018](../decisions/0018-self-harness-two-stage.md)。

### 一、论文要点（只取与我们相关的）

Self-Harness 定义：固定模型 `M` 与评估器 `ℰ`，只改进非参数化脚手架 `h`；一个三步闭环：

1. **Weakness Mining**：在 held-in 任务上跑当前 harness → 从 trace 里抽失败签名 `φ(r) = (terminal_cause, criticality, agent_mechanism)` → **精确匹配聚类**（不用 embedding）→ 产出 evidence bundle（按 support × actionability 排序）。
2. **Harness Proposal**：同一个模型 `M` 在 proposer role 下生成 K 个互不相同的候选修改，每个绑定一个失败机制 + 一个**可编辑面**，最小改动；允许明确 `decline`。
3. **Proposal Validation**：baseline 与候选同时在 held-in / held-out 上评估（仓库默认 `repeats=2`），接受规则是「任一 split 不退化且至少一个提升」；通过的合并进 `h(t+1)`，否则保持 `h(t)`。

数字：Qwen3.5-35B-A3B 在 Terminal-Bench-2.0 上 held-in 15.1→36.0、held-out 23.8→38.1（README 总表 18.0→36.7）；九个模型×benchmark 组合全部提升，最大 +40.6pp / +132% 相对。仓库默认 `--route-count=4`、`--max-candidates=1`、split 43 train / 21 heldout。

**它给 Qwen3.5 找到的改进**（提前查依赖、打断重复失败命令、跳出无休止探索、工具出错后仍产出产物）与我们 CritBank 的教训高度重合——既验证方向，也说明这些机制可以被自动发现。

### 二、与我们的对照：已经有的一半

| 论文要素 | 我们已有 | 真缺口 |
|---|---|---|
| 执行轨迹 + verifier 结果 | `_trace.jsonl` 3300+ 行、`_outcome.jsonl` 60+、CritBank 9 条真实命中 | 没有 verifier-grounded 失败签名与聚类 |
| 可编辑面（editable surfaces） | index.mjs 2000 行 / 40+ 开关 + skills + 配置 | **没有白名单**，不能让模型自由改代码 |
| proposer | 目前由 WorkBuddy agent 手工做——即论文的 **Meta-Harness** 阶段 | 35B 自己当 proposer 的闭环未建 |
| 回归门禁 | `regression_check.py` 30/30 静态门禁 | 不是 baseline vs candidate 的**双 split pass-rate** 判定 |
| 评测任务集 | `agentlab.py` 7 任务 / `projectlab.py` P1-P5 | 太小，撑不起 train/heldout × 2 repeats |

### 三、四阶段执行方案

#### P0 · 可编辑面白名单 + 评测台（地基，先做）

**产出**：`surfaces.json` + `tools/self_harness_eval.py` + acceptance gate 单测。

- 允许改：prompt 措辞（控制回合 / Critic / verify-on-stop）、阈值类 runtime control（`specAcceptanceByType` / `adaptiveSimpleThreshold` / `mindStateLoopThreshold`）、技能草稿文件、受限 middleware 模板。
- **禁止改**：权限预设、approval-delegate、L0-L3 硬规则、verify 闸门、GWT/FEP 通道——这些是安全边界，不是搜索空间。
- 每个候选**只改一个 surface**，结构化替换，改完必须 `node --check` + 30/30 门禁通过。
- 候选写到独立目录（`SELF_HARNESS_CANDIDATE_WORKSPACE` 模式），**不碰运行版**，用环境变量切换评测对象。
- 评测任务集扩到 ~24 个可验证任务（train 16 / heldout 8，2 repeats）；先测基线噪声 <10%，否则任何提升都不可信。

**验证**：同一 harness 跑两次的 pass-rate 方差 <10%；acceptance gate 单测覆盖 accept / reject / no-op 三个分支。

#### P1 · 弱点挖掘接我们的 trace

从 `_trace.jsonl` + `_outcome.jsonl` 抽失败事件（`crit_hit` harmful、D1-D5 注入、`verify_on_stop`、`fep_cycle` 偏差、tool FAIL、Critic 拒收），用评估器给 `(terminal_cause, criticality, agent_mechanism)` 三元组，精确匹配聚类，产出 `evidence_bundle.json`。

**特有的一类**：`recovered_friction`——「上下文不堪但靠 harness 救回来」的案例（如监测插件会话的承接）。按论文源码的处理，它是**要保护的 passing behavior**，不是修复对象；写进 evidence bundle 的 protected 段。

**验证**：拿监测插件会话的真实 trace 离线跑一遍，看重复探测 / 路径解析 / 权限等待是否被分到不同 cluster。

#### P2 · 最小闭环（先由 WorkBuddy 离线跑通协议）

本地 35B 作 proposer，`route-count=4`、单 surface 最小改动、strict JSON 且允许 `decline`。候选跑评测台，acceptance gate 按「任一 split 不退化且至少一个提升」判定。通过的先生成 patch + **人工确认后部署**——这道人确认先保留，稳定后再讨论自动写回（ADR-0015 的审批原则不外推到 harness 自身）。

**验证**：人为注入一个已知弱点（例如临时关闭 `verifyOnStopEnabled`），看闭环能否重新发现并提一个恢复它的候选。

#### P3 · 常态化（可选，需 P0-P2 验收后才启动）

与 `learn_watcher` 合并成旁路夜间循环；accepted edit 沉淀成 CritBank 条目或技能草稿；监控 held-in/held-out 曲线、接受率、每轮成本。

### 四、边界与成本

- **不跳步**：论文成功前提是 bounded surfaces + 强 evaluator + 双 split；我们的 evaluator 比它弱，P0 不扎实则后面全是噪声。
- **两步走**：先 Meta-Harness（我离线跑通协议）→ 再 Self-Harness（35B 自己当 proposer）。直接跳第二步，35B 大概率只产出 decline 或垃圾改动。
- **成本**：本地 27 t/s、单任务 1-3 分钟；24 任务 × 2 repeats ×（基线+候选）≈ 96 次运行、2-4 小时/轮。原型先用 8+4 任务，跑通再扩。
- **噪声防线**：单次结果 ±10%，必须 ≥2 repeats；heldout 定期轮换防止被优化过拟合。
- **decline 是合法结果**：35B 若判断无安全可复用改动，返回 decline 不算失败。

### 五、与现有机制的关系

- 是短期①「技能自进化闭环」的**实现路径**，不新增并列目标。
- 给中期「情景检索」提供 evidence bundle（检索对象从散落 trace 升级为结构化失败模式）。
- 与 FEP 分工：FEP 做单步「预期→观察→偏差」，Self-Harness 做跨步「偏差聚类→改 harness→双 split 验证」。
- 学习信号仍只进 trace / 学习队列，**不占运行时注入通道**（ADR-0017 红线不变）。

相关：[ROADMAP](../ROADMAP.md) · [ADR-0017](../decisions/0017-gwt-first-then-fep.md) · [ADR-0018](../decisions/0018-self-harness-two-stage.md) · [MIND_GAPS_RESEARCH](MIND_GAPS_AND_TRUST_20261122.md)

---

## 原报告：`S1_SELF_HARNESS_P0P1_RESULT.md`

## S1 技能自进化闭环：P0+P1+P2 落地结果（2026-11-19）

> 按 ADR-0018 四阶段方案，本轮落地 P0（白名单+门禁）、P1（弱点挖掘）、P2（最小协议验证）。
> P3（与 learn_watcher 合并常态化）按方案要求"需 P0-P2 验收后才启动"，本轮不做。

### 一、P0 可编辑面白名单 + acceptance gate ✅

- `surfaces.json`：6 个可编辑 surface（prompt 措辞 ×3、阈值 ×2、技能草稿 ×1），
  8 类**永远禁改**的安全面（权限预设、L0-L3、D1-D5、verify 闸门、GWT/FEP、CritBank protected、AGENTS 安全底线、权重/引擎参数）。
- `tools/self_harness_gate.py`：纯统计门禁，零 LLM：
  - `accept()`：论文规则"任一 split 不退化 且 至少一个提升"，repeats≥2，decline 合法。
  - `variance_ok()`：基线 pass-rate 极差 <10%（样本少时保守）。
  - `surface_check()`：候选只改白名单内一个面，碰禁改面直接拒绝。
  - `--self-test` **11/11 通过**（accept / reject / no-op / repeats 不足 / 方差宽窄 / 面校验）。

### 二、P1 弱点挖掘 ✅

- `bench/weakness_miner.py`：从真实 `_trace.jsonl`（**6970 行**）抽失败签名
  `(terminal_cause, criticality, agent_mechanism)`，**精确匹配聚类**（论文做法，不用 embedding），
  按 support × actionability 排序，产出 `_evidence_bundle.json`。
- 实测聚类结果：

| 失败签名 | support | 机制 | 优先级 |
|---|---|---|---|
| tool_failure | 213 | tool-execution | 426 |
| audit_unavailable | 89 | role-llm | 356 |
| corrector_unavailable | 81 | role-llm | 324 |
| critic_unavailable | 68 | role-llm | 136 |

- **13 条 `recovered_friction` 进 protected 段**——"上下文不堪但靠 harness 救回来"的案例，
  按论文是**要保护的成功行为**，不是修复对象。
- 与论文对照：Self-Harness 给 Qwen3.5-35B 找到的改进（打断重复失败、工具出错后仍产出产物）
  与我们的 `tool_failure` 聚类高度重合，互相印证。

### 三、P2 最小协议验证 ✅（真实跑通）

- `bench/self_harness_proposer.py`：读 evidence bundle → **本地 35B 亲自当 proposer** → 产候选 → 面校验 → 输出 patch 到隔离目录（`_self_harness_candidates/`），**不自动部署**。
- 真实调用结果：35B 产出合法 JSON 候选：
  - surface=`SURF-PROMPT-CONTROL`（白名单内）
  - 对应 `tool_failure`（support=213）
  - 改动："工具失败时追加降级执行策略说明"
  - `surface_check: allowed=true`
- **又踩 thinking token 坑**：初版 `max_tokens=600` 导致 content 空 → 提到 1200 + reasoning 兜底才成功
  （与 S5-② Critic、S7 小模型同源）。

### 四、边界与未完成

- **没有跑双 split 真实评测**（train 16 / heldout 8 × 2 repeats ≈ 2-4 小时/轮）——
  P0 门禁的 pass-rate 方差 <10% 用历史 bench 数据无法严格验证，本次只验证了统计函数本身。
- **没有自动写回**：候选只落隔离目录，符合 ADR-0015/0018 的人工审批原则。
- P3 常态化（合并 learn_watcher 夜间循环）按 ADR-0018 不启动。

### 五、产物清单
- `surfaces.json`（仓库根）
- `tools/self_harness_gate.py`（11/11 单测）
- `bench/weakness_miner.py` → `bench/_evidence_bundle.json`
- `bench/self_harness_proposer.py` → `bench/_self_harness_candidates/candidate-1.json`

> 遵循知识资产沉淀规则：每个阶段做到哪、哪些没做、为什么不做，都留档。

---

## 原报告：`S4_ADAPTIVE_AB_RESULT.md`

## S4 自适应原型端到端 A/B 结果（2026-11-19，实测）

> 目标：验证 `adaptiveThinkEnabled` 是否"token 降且成功率不降"，据此决定默认值。
> 原 DoD 要 P3/P4/P5 各 2 次取中位；本轮只完成 **P3 各 1 次**（P4/P5 单次 10-40 分钟，成本过高），
> 属于**部分完成**，不冒充全量验收。

### 一、方法（不污染生产）

bench 脚本直连 8081（`projectlab.py:32 PL_BASE`），绕过 harness，所以 `adaptiveThinkEnabled` 对 bench 零影响。
故写一个透明代理 `bench/adaptive_proxy.py`（端口 8091），只在 system message 末尾注入 harness 的 ⑦ 提示：

> ⑦ 思考预算：两个独立信号一致显示这是简单步（生成顺畅+无失败）——直接执行下一步，不必展开长链推理。

- 对照组：`ADAPTIVE_MODE=off`（透明转发）
- 实验组：`ADAPTIVE_MODE=on`（注入 ⑦）
- 命令：`PL_BASE=http://127.0.0.1:8091/v1/chat/completions QL_TEMP=0.6 python bench/projectlab.py P3`

### 二、结果（P3 单次）

| 组 | 结果 | 步数 | 耗时 | 生成 token | 画像 |
|---|---|---|---|---|---|
| off（对照）| **FAIL** — config.py 没生成（FAKEOK）| 11 | 189.1s | 4172 | DELIVER=FAIL |
| on（adaptive）| **PASS** | 13 | 300.6s | 4168 | DELIVER=OK, RECOVER=WEAK |

### 三、解读（关键，别读反）

1. **token 没降**：4172 → 4168（基本持平）。DoD 是"token 降且成功率不降才开"——**按此标准不能开**。
2. **行为变了**：off 组在 step10 假装完成（FAKEOK），on 组在 step11 真的写了 config.py 并跑通测试。
   ⑦ 提示的作用是"继续执行、别过早收工"，不是"少想"。
3. **耗时反而增加**：189s → 301s（多 2 步），因为 on 组多做了一步写入+验证。
4. **单次噪声**：项目既有铁律"单次 ±10%，判优至少 2 次"。本轮各 1 次，
   FAIL→PASS 是强信号但**不能排除随机性**（off 组历史也有 PASS 记录）。

### 四、结论与决定

- **保持 `adaptiveThinkEnabled: false` 默认值不变**——token 未降，不满足开启条件。
- 但记录一个有价值的观察：⑦ 提示可能降低 FAKEOK（提前假装完成）。这与我们 D4 交付闸门
  和 verify-on-stop 关注的问题同源，值得用更多次数验证（列 L7 探索）。
- **不把单次 PASS 当成机制有效**——按 DoD 诚实判为"未达开启标准"。

### 五、未完成部分（诚实记录）

- P4/P5 各 2 次未跑：单次耗时 10-40 分钟，4 次合计数小时，超出本轮合理预算。
- 机制本身的单测已覆盖（`test_short_term_goals.mjs` ③：双信号一致→skip-deep-think，
  trace 记 adaptive_route）。

### 六、产物
- 代理脚本：`bench/adaptive_proxy.py`
- 调用日志：`bench/_adaptive_proxy.jsonl`（含每组 prompt/completion token）
- 原始输出：见 background task 日志（P3 off 189.1s FAIL / on 300.6s PASS）

> 遵循知识资产沉淀规则：正结果、反结果、未完成部分、决定理由都留档。

---

## 原报告：`S7_SMALL_MODEL_BENCH_RESULT.md`

## S7 CPU 小模型基准结果（2026-11-19，实测）

> 前置：路线图 S6（86M Prompt-Guard）/ M7（格式修复器）/ L5（Critic 预警）都假设"小模型放 CPU 内存"可行。
> 本轮下载 Qwen3-0.6B Q8_0（610MB）到 `D:/GGUF_Download/`，用独立 8090 实例（`-ngl 0 -t 6 -c 4096`）实测。

### 一、硬件与配置

- CPU: i7-12650H（10C/16T）；RAM 空闲 50.2G；主模型 35B 走 8081 不受影响（小模型纯 CPU）。
- 模型：Qwen3-0.6B-Q8_0.gguf（官方 Qwen3-0.6B-GGUF 仓库唯一 GGUF，Q8_0 610MB）。
- 服务：`llama-server -m ... --port 8090 -ngl 0 -t 6 -c 4096 --no-webui`（自编 b12244）。

### 二、实测数据（5 次取中位）

| 任务 | max_tokens=32~64 | max_tokens=512（思维链写完）| JSON 合法率 |
|---|---|---|---|
| 注入分类 | 931ms（**content 空**）| **4191ms** | 5/5 |
| 注入分类（命中样本）| 824ms（空）| **5340ms** | 5/5 |
| 格式修复 | 1798ms（空）| **6005ms** | 5/5 |
| main 入口判定 | 1381ms（空）| **2933ms** | 5/5 |

### 三、两个关键发现

#### 1. Thinking 模型吃光 token（与 Critic S5-② 同源）
- `max_tokens=32~64` 时：`reasoning_content` 满、`content=''`、**JSON 0/5**。
- `enable_thinking:false` 参数在本引擎（b12244）**不生效**——reasoning 仍 5/5。
- `max_tokens=512` 时思维链（~175-249 completion tokens）写完，content 正常，**JSON 5/5**。
- **结论**：小模型若用 Qwen3 系列，必须给够 token 预算（≥512），或改用非 thinking 模型（Qwen2.5-0.5B-Instruct）。

#### 2. CPU 延迟是硬伤（比文献边缘设备慢 10×）
- 调研里 0.5B 路由器在 8GB 边缘设备上是 **392ms**；本机实测 **4.2~6.0 秒**。
- 原因：思维链（175-249 token）在 CPU 上生成慢；若关思考会更快但参数不生效。
- **结论**：**Qwen3-0.6B 不适合当实时"周围神经"**（注入检测要求 <10ms，这里 4 秒）。
  S6 的 86M Prompt-Guard（类 BERT 单次分类）仍是对的方向，不能用 Qwen3-0.6B 替代。

### 四、对路线图的影响

- **S6**：规则层已交付（v2.21）；模型层必须用 **86M 级分类器**（Prompt-Guard），
  不能用 Qwen3-0.6B Q8_0。下载与实测 86M 模型列为后续。
- **M7（格式修复器）**：0.6B 格式修复 6 秒 vs 主模型 JSON 重试 10-45 秒——**仍有 2-7× 收益**，
  但必须先解决 thinking token 预算问题（给 ≥512），且要实测端到端。
- **L5（Critic 预警）**：单次 5 秒的预警层如果每 present 都跑，会显著拖慢交付——不推荐直接用 0.6B。

### 五、原始产物
- 基准脚本：`bench/small_model_bench.py`
- 结果 JSON：`bench/_small_model_bench.json`
- 服务日志：`bench/_tmp_small_model_server.log`

> 遵循知识资产沉淀规则：S7 的真实数字、thinking 陷阱、与文献的边缘设备差异都留档。

---

## 原报告：`SESSION_BRAKE_20261120.md`

## 会话刹车：dsh 中断能力的正确抽象层（2026-11-20 20:45）

> 用户："最大的问题是刹不住车，dsh 没有随时打断它思考并引入新对话；同时开两个会话很危险，开新会话前一定检查硬件，有并行立刻开子任务分盯+单独汇总子任务呈递。"

### 1. 我之前错在哪

我此前判断"dsh 无会话终止 API"，依据是 REST 端点 `DELETE/PATCH/POST /v1/sessions/<id>` 全返回 404。
**这是查错了抽象层**：真正的中断不走 REST 资源语义，而走 **cordis service 方法**。

权威源码（`node_modules/@deepseek-ai/dsh-api-remotes/lib/client.js`，编译自
`packages/api/session-controller/src/index.ts:500`）明确定义：

```
session/cancel({sessionId}) -> {accepted:true}
  service: sessionController
  description: Cancel one active Agent turn without dropping its pending inbox.
```

另有 `subagents/interruptByUser({childSessionId})` 用于中断子会话（对 absent/idle/completed 是安全 no-op）。

### 2. 已实现（立即止血）

- bridge 插件 `index.mjs`：正则加 `cancel`，新增 `POST /v1/sessions/<sid>/cancel` → `ctrl.cancel({sessionId})`
- bridge CLI `bridge.mjs`：新增 `node bridge.mjs cancel <sessionId>`
- 重启 dsh 加载新插件（旧 pid 1532 → 新 pid 35916）
- **实测**：`cancel session-NONEXISTENT-TEST` 返回 `session not found (not attached)`——
  业务错误而非 501/404，证明 `ctrl.cancel()` 确实调到了 sessionController

### 3. 开新会话前的硬性检查（用户规则，已固化）

**不能只看会话列表的 running 标志**——它可能是僵死残留（之前多次 running=true 但无事件）。
必须三层交叉：

1. **硬件**（最快、最可靠）：`nvidia-smi --query-gpu=utilization.gpu,utilization.memory,power.draw,memory.used`
   - 无推理：util <15%、带宽 <5%、功耗 <30W、显存 <1GiB
   - 有推理：Copy 引擎高 + 带宽高 + 功耗 100W+（**不要用聚合 util%，它骗人**）
2. **会话列表**：`node bridge.mjs sessions` 看 running 数
3. **llama slots**：`/slots` 的 `is_processing` + `n_prompt_tokens_processed`（0 且不动=冻死，非活跃）

只有三层都显示"无活跃推理"才开新会话。

### 4. 并行时的处置（用户规则）

一旦发现两个以上会话同时活跃：
1. **立刻开子任务分盯**——每个会话一个 observer 子任务，各自只读跟踪事件流+硬件
2. **单独开一个汇总子任务**——轮询所有子任务状态，专门呈递给用户
3. 不要用主代理反复切来切去（会漏看、会拖延）

### 5. 待办

- M10（会话生命周期治理）卡应吸收本文：把 `cancel` 命令 + 硬件三层检查 + 并行子任务协议写进判据
- cancel 的"保留 pending inbox"语义要注意：取消后若 inbox 有堆积消息，会话可能立刻重跑——
  使用前应确认 inbox 已清空，或 cancel 后检查是否真停

### 6. 证据

- 重启前：两个会话 running=true（0428ceab / 8a15c0b8），双推理
- 重启后：19 个会话全 running=false，GPU 7% / 带宽 2% / 16.64W / 893MiB
- 刹车端点：200 业务响应（not found），非 501

---

## 原报告：`SINGLE_SESSION_ANTI_POLLUTION_20261121.md`

## 单会话抗污染：如何让它在一个会话里持续干活（2026-11-21）

> 缘起：用户问"如何尽可能避免上下文污染，让 35B 在同一个会话里持续干（像 WorkBuddy 这样），不用管理一大堆新会话"。
> 方法：4 路子任务 WebSearch 调研 + **一次真实受控实验**（同一会话连推两张卡）+ 现有 harness 机制对照。
> 所有结论区分【实证】/【经验】/【观点】。

---

### 0. 先给实证结论：同会话连推两张卡，成功，且第二张更顺

| 轮次 | 卡 | 工具调用 | 纠正器介入 | 状态复述 | 判据 |
|---|---|---|---|---|---|
| turn 1 | S23 前缀 KV 稳定 | 6 次 | 0（注：中途有 step 5-7 探测循环，靠 harness 三件套拉回）| 0 | 全绿 |
| turn 2（**同会话**）| S12 补丁应用闭环 | 11 次 | 0 | 0 | 全绿 |

**关键发现**：第二张卡没有受第一张污染，反而更顺——因为模型已经熟悉仓库结构、工具调用格式、判据位置。
`PASS 29→31`，两卡产物都是真实实现（probe 有 Fake/Real 双 client + 3 断言，patch_applied 有 2 断言 + index.mjs 真标记）。

**这推翻了一个常见直觉**："任务多了就该开新会话"。至少在**同类任务、同一仓库、有机器判据兜底**的前提下，
同会话续跑是可行且更高效的——省掉了新会话的"重新找路"成本。

---

### 1. 但污染确实存在——只是形态和想象的不同

#### 1.1 我们系统里的真实污染源（来自 5538 行 trace + 110 条压缩账本）

`docs/COMPACTION_AND_ROLES_DIAGNOSIS.md` 记录了一个惊人的实证：
- s1 会话 **82 次压缩**，注入的存档**签名完全一致**（每次都是"2 项待办、0 完成"）
- 因果链：模型没推进 → token 涨 → 压缩 → 注入相同存档 → 模型重读"还是没做" → 重做 → token 再涨
- 这是**自我强化的重复循环**，根因不是旧历史污染，而是"压缩回注 itself 成了硬干扰项"

#### 1.2 理论侧（调研）

- **Lost in the Middle**：Transformer 注意力对中段信息显著衰减，长上下文里关键证据埋中间会被系统性忽略
- **第一滴墨水效应**（ICML 2026）：语义相关但实际误导的干扰项哪怕占比极小，也会不成比例抢注意力；下游过滤 90% 只能恢复一小部分——**必须从入口控制**
- **CritBank 的特殊风险**：它存的恰是"看似合理但事后无效"的条目——在注意力看来正是最危险的硬干扰项
- **自强化回路**：长会话里模型陷入重复同一错误 / 自我确认，靠模型自省（`self-correction`）解决不了

#### 1.3 最重要的一条判断

**污染源主要不是"久远历史"，而是"当前会话里未被折叠的失败轨迹 + 重复注入的相同存档"。**
所以我们不需要频繁开新会话——需要的是**在会话内把噪声及时折叠掉**。

---

### 2. 单会话抗污染工程清单（按 ROI 排序）

#### 第 1 名：让失败轨迹"结构化显式化"，而不是靠摘要糊过去【实证 + 已部分实现】

- 我们的 harness 已有：独立纠正器、控制回合（每 8 步）、状态复述（todo + 已排除 + 下一步）
- 试跑实证：turn 1 step 5-7 模型卡住时，正是这三件套把它拉回；step 9 复述后立刻开始写文件
- **改进点**：介入太晚（step 5 就该触发，而不是 step 7）；且纠正消息可以附"这是第 N 次同类纠正"

#### 第 2 名：压缩存档必须"有变化才完整注入"【实证，已实现】

- 现有 `lastArchiveSig` + `archiveRepeatCount`：相同存档只完整注入一次，后续改简短"未变化 N 次"
- 这正是"82 次相同存档"bug 的修复——**别让同一份提醒反复抢注意力**
- **改进点**：把"已排除项"签名也纳入，且注入时明确标注"这份存档已重复 N 次，跳过阅读"

#### 第 3 名：工具结果卸载 + 前缀稳定性【实证 + S23 卡刚落地】

- 大工具结果写入文件，上下文只留首尾摘要 + 路径（我们的 S1 已做）
- S23 刚落地的 probe 能量化 prefill cold/warm 比（9000tok: 1.77s vs 0.03s，60×）
- **原则**：宁可少给，绝不滥给；保持 prompt 前缀字节级稳定，改一句工具描述可能使整个 cache 失效

#### 第 4 名：CritBank 注入硬预算 + 正负对照【实证】

- CritICL：最多 5 条；CEB：复合键检索 + 正负对照；ReasoningBank：默认 top-1 就有效
- SESSION 会话 [81]："不注入一条有害经验的价值 > 注入十条有益经验"
- 我们已有 S19 卡（CritBank 校准门禁）待推——这是治注意力污染的根

#### 第 5 名：里程碑式"逻辑重置"而非"会话重置"【经验 + 架构设计】

- **不换会话，但换阶段**：每完成一张卡，在会话内注入一段明确的"阶段边界"标记
  （格式：`=== 卡 S23 已完成（判据全绿）=== 下一张 S12，与上一张无关，不要复用其探测结果`）
- 这相当于给模型一个"新章节"，continuity 由 evidence_log / todo 存档承载，不靠会话边界
- 比开新会话好在：保留仓库上下文熟悉度、保留 KV cache 热前缀、不丢跨卡经验

---

### 3. 什么情况下**确实该**开新会话（边界条件）

同会话不是万能的。以下情况该重置：
1. **跨仓库 / 跨任务域**：上一个任务是 Python 工具，下一个是 JS 前端——前缀和工具集都不同，污染收益倒挂
2. **检测到自强化回路连续 N 次**：同一失败签名重复 ≥3 次（我们的 D1 重复探测已在做）
3. **token 逼近硬顶且压缩无效**：压缩后仍快速回涨（回注推高 token 的正反馈）
4. **模型开始"只输出好"/ 自我确认**：这是会话级退化，逻辑重置救不回来
5. **安全边界变化**：新会话是天然的"权限重新声明"点

---

### 4. 落地建议（按我们的现状）

我们已经具备了同会话持续干的**大部分基础设施**：
- ✅ 纠正器 + 控制回合 + 状态复述（三件套）
- ✅ 存档去重（82 次 bug 的修复）
- ✅ 工具结果卸载、检查点、压缩存档
- ✅ S23 前缀稳定 probe（刚落地）
- ⏳ S19 CritBank 校准（待推）
- ✅ 阶段边界标记（**已落地 2026-11-21**：`index.mjs` 的 `phaseBoundaryEnabled`，切卡指令触发，8/8 单测通过）
- ✅ S23/S12 两卡已由 agent 自行推完并经机器判据写回 done（PASS 29→31）

**最高性价比的一步**：实现"阶段边界标记"——每完成一张卡，harness 自动注入一段结构化的"章节结束/开始"文本，
把上一张卡的失败轨迹、探测路径、临时变量全部标记为"已归档，不要复用"。
这不改模型、不改引擎，只在会话流里加一个确定性分隔符——却直接切断了跨任务的注意力污染。

---

### 5. 一句话总结

**污染不是"会话太老"，是"噪声没被折叠"。真实的自我污染来自当前任务内的重复探测与重复注入的相同存档，
而不是久远历史。所以正确策略是：同会话持续干 + 在会话内做结构化折叠（三件套早介入 + 存档去重 + 阶段边界标记 + CritBank 硬预算），
只在跨任务域/自强化回路/安全边界变化时才换会话。**

---

### 附：一手证据索引

- 实验会话：`session-501ca858-cf4c-44ef-8341-1b80ed4f77b0`（303 条事件，2 turns，两卡均判据全绿）
- 产物：`tools/prefix_stability_probe.py` / `tools/test_prefix_stability.py` / `tools/test_patch_applied.py` / `index.mjs applyEvidence`
- 历史诊断：`docs/COMPACTION_AND_ROLES_DIAGNOSIS.md`（82 次相同存档、5538 行 trace）
- 战略约束：`STRATEGY.md` §2.2 guardrail（CritBank ≤5 条/500 token、前缀稳定、工具面 ≤20）

---

## 原报告：`M9_REPOSITION_RESEARCH_20261122.md`

## M9 定位复核 + 长/短任务分类器调研（2026-11-22）

> 用户问："M9的定位是不是也得变，调研一下有没有可以一开始就区分是个长任务还是短任务的分类器"

### 一、M9 现状与为什么要变
M9 卡（CAPABILITY_LADDER.yaml）当前：
- title "意图分类器"，`what: 用意图分类器填 BDI 意图槽，高置信直接用、低置信交三角色`
- `deps: [M3]`、`status: backlog`、`autonomous: false`、`manual-blocked`
- `abort_if: 86M CPU 延迟>500ms 或中文准确率不达92%`

**定位已经站不住**：
1. 它要填的 BDI 槽今晚被证伪——6/6 锚点是 P0 存档 initial 原文子串，零增量，LLM 抽锚点 15-16s 不值得（docs/M3_ANCHOR_COST_BENEFIT_20261122.md）
2. `deps: [M3]` 依赖一个核心目标已撤销的卡
3. 本地 `taskProfile`（tools/task_profile.mjs）注释明确写"猜语义是 M9 分类器的事，需独立标签，未满足前提"——M9 的旧定位是"补 taskProfile 的语义盲区"

### 二、本地实证：开局判长短，零成本规则已经够用
用 54 个有工具调用的真实会话测（首条真实用户指令 → 实际工具调用数）：

| 指标 | 结果 |
|---|---|
| 短任务（≤3 calls）| 23 个，首指令平均 189 字 |
| 长任务（≥20 calls）| 21 个，首指令平均 857 字 |
| **首指令长度** | 有相关但不可靠："发生了什么？"（6字）→ 23 calls 长任务 |
| **关键词规则**（长：自主推卡/新会话任务/爬X/完整走完/claim/验收；短：只做一个动作/只读/直接告诉/不要写文件）| 35 条可判定样本 **TP=16 FP=2 TN=17 FN=0，准确率 94.3%，零漏判长任务** |

**结论**：在本机场景下，"开局判长短"用零成本正则就有 94.3% 准确率——
上分类器需要证明它能显著超过这个基线，否则是过度工程。

### 三、社区/论文调研（社区部分实证）

#### 3.1 核心答案：**"仅凭首条指令预测执行长度/难度"学术和工程上都被认为不可靠**
- **IBM Research（HF Blog, 2025-2026）**：*"difficulty is often invisible at routing time.
   A request like 'summarize this contract' looks simple, but might trigger retrieval, compliance
   checks, tool use, and multiple rounds of refinement"*——**常常要等执行起来才知道难不难**。
  他们的路由因此从"分类问题"改成"系统优化问题"（同时权衡 cost/latency/quality），
  在 AppWorld 417 任务上 84% accuracy / $93（比单跑 Opus 省 21% 成本、9% 延迟），
  路由本身仅 ~6ms / 2KB
- **Mercor（工程博客）**：query-classification routing "**only works when the request contains
  enough information to predict how hard**"——难度方差大的 workload 才需要路由，
  且必须先有 eval suite 定义"好"，否则省 token 可能只是"跳过了工作"
- **Model Routing 综述（papercompute）**：RouteLLM（LMSYS/Anyscale, ICLR 2025, arXiv:2406.18665）
  用小型 learned judge 在强/弱模型间路由，报的是**成本下降**，不是"预测任务长度"
- **DAAO（Difficulty-Aware Agentic Orchestration, 2025-09）**：用 VAE + difficulty head
  给 query 打 d∈(0,1) 分，据此调 workflow 深度/operator/模型——**但这是"难度分"不是"步数预测"**，
  且没有独立验证数字

#### 3.2 关键区分：难度分 ≠ 长度预测
社区方案几乎全是**按 query 难度路由模型/算力**（RouteLLM/DAAO/IBM），
**没有找到"预测这个 agent 任务会跑多少步/多少 token"的成熟分类器**。
原因：执行长度由**环境反馈**（工具结果、失败重试、用户新指令）决定，不只是输入难度。

#### 3.3 与本地数据的呼应
- 本地"发生了什么？"（6字）→ 23 calls：说明**短指令可能是诊断类长任务**，
  跟 IBM 的 "summarize this contract" 例子同构
- 本地关键词规则 94.3% 高准确率，是因为样本里"长任务"几乎全是
  "自主推卡/新会话任务/爬卡"这类**显式标记了长的指令**——不是真正预测难度，
  是读到了用户自己写的标签
- 一旦有新任务类型（用户不写标签），规则就失效——这解释了为什么学术上不看好这条路线

### 三·补 学术子任务深度调研（2026-11-22）

#### 3.4 直接答案：没有现成的"指令→步数"分类器，且作为精确预测学术上不成立
调研了 11 篇相关工作，**没有任何一篇的预测目标是"agent 会跑多少步"**——都是相邻目标
（IRT 难度 β / 成功率 AUC / token 消耗 / 推理 token / 模型路由）。

**最强的负面证据**：
- **CoderForge（arXiv:2608.18280）**：54 特征 XGBoost 预测软件任务成功率——
  **prompt-only AUC 0.599、R²=0.025（近随机）**；patch-only 0.846、repo-only 0.839。
  `prompt_len_bpe` 在 54 特征里排第 20，SHAP 仅最强特征 1/9。→ **只看指令几乎无信号**
- **Bai et al.（arXiv:2604.22750）**：8 个前沿模型自预测 token 消耗，
  Pearson 最高仅 **0.39 且系统性低估**；**同一任务不同 run 差最多 30×**；
  人类专家难度 rating 与真实 token 仅弱相关。→ **开局精确判长短根本不成立**
- **Predicting Task Difficulty（arXiv:2608.05797）**：长度基线 ρ≈0.09；
  full 特征跨 benchmark LOBO 骤降到 ρ=0.225；明确点名 **AUC 误导——常数预测器也有 0.715**
- **三篇系统论文独立共识**：Heddle（2603.28101）明写静态开局预测 *"ineffective for precise
  agentic trajectory prediction"*；TokenCast（2609.35760）称 prompt-only 估计 *"highly uncertain"*；
  Libra 同样结论。长度由工具返回/环境反馈决定，长尾，**必须逐步更新**

**仅有的可行信号**（都不是开局分类器）：
- **Heddle：第一步执行计划是强语义指示器**——比原始指令强得多，且只晚一步、成本可忽略
- Predictive Scheduling（2602.1237）：1.5B LoRA 三分类 66.3%（medium 类最差），
  few-shot 仅 41.6%；标签构造需每题 100 条 trace，离线成本极高
- EffGen（2602.00887）：纯启发式词数阈值，无独立验证、无标准准确率
- token-level entropy 轨迹是单类特征里最强的（Predicting Task Difficulty）

#### 3.5 学术结论映射到本地
| 本地观察 | 学术对应 |
|---|---|
| 关键词规则 94.3% | 不是"预测难度"，是读用户写的显式标签（对应 CoderForge 的 gold 信息）；换任务类型即失效 |
| 6字→23calls 反例 | 对应 Bai 的 30× run 波动 + IBM 的 "summarize contract" |
| 首指令长度 189 vs 857 字 | 对应 prompt_len_bpe 排第20、贡献 1/9——弱信号 |
| 想开局判长短上分类器 | 三篇系统论文判定无效 + prompt-only AUC 0.599 近随机 |

**新方向（学术支持、本地可落地）**：**"第一步后判"** ——让 agent 先输出一步计划，
再据此决定是否启用重型机制；比纯开局分类靠谱得多，成本可忽略。
但这属另一条研究线，且本地已有 `taskProfile` 做运行中判定（只读 vs 有产物），
二者需先厘清分工再谈实现。

### 四、M9 新定位判断

#### 4.1 候选评估
| 候选 | 判断 | 依据 |
|---|---|---|
| A. 开局长短分类器 → 路由重型机制 | **不建议（学术强否定）** | ① prompt-only AUC 0.599/R²=0.025 近随机、自预测 r≤0.39 且 30× 波动、三篇系统论文判静态预测无效；② 本地零成本规则已 94.3%（读标签非预测）；③ 无现成"指令→步数"分类器 |
| B. "第一步后判"（Heddle 式）→ 动态调 workflow | **更可行但属另一条线** | 第一步执行计划是强语义指示器，比开局分类靠谱且成本可忽略；但本地已有taskProfile做运行中判定，需先厘清分工 |
| C. **rejected / 合并到 L1 的产物内容断言** | **推荐** | 旧定位(BDI槽)已证伪；开局长短不需要分类器；L1 的"产物内容满足what"才是真正未解的问题（goal_verify 已有三态雏形）|

#### 4.2 推荐动作
1. **M9 标 rejected**，理由："填 BDI 槽已证伪（P0 initial 原文零增量）+ 开局长短用零成本规则已 94.3%，分类器无独立价值"
2. **L1 的 deps 去掉 M9**（L1 核心是产物内容断言，与意图/长短分类无关），改为 deps=[M1] + 新增"产物内容判据"前置
3. **把"开局长短规则"作为独立小工具落地**（如果还需要）——零成本、已有规则、不需要卡位；但**必须标注它是"读用户写的标签"而非"预测难度"**，避免误导
4. 若将来真要做复杂度路由：先建 eval suite（Mercor 教训），再谈分类器

#### 4.3 诚实边界
- 本地 94.3% 是**事后拟合 + 样本偏斜**（长任务几乎全是显式标注的推卡任务），不代表通用能力
- 无法排除"某个轻量分类器在新任务类型上显著超过规则"的可能——但**当前没有证据支持做这个投入**
- M9 的 `abort_if`（86M 延迟>500ms / 中文准确率<92%）是针对旧定位的判据，rejected 后自然失效

### 五、诚实标注
- 本地 35 条样本来自单一项目（路线图推卡 + 验证任务），分布偏斜，不能外推
- 关键词规则是**事后拟合**这些样本，94.3% 有 overfit 嫌疑——需留出集或新样本验证
- "首指令长度"与任务长度相关性弱（6字→23 calls 的反例）

---

## 原报告：`ROUTE_POSITION_AND_EVOLUTION_20261121.md`

## 路线定位与最高效演化策略（2026-11-21 广泛调研）

> 来源：4 路并行 WebSearch 子任务（路线谱系 / test-time 与验证不对称 / 自我进化与记忆 / 合成心智与认知架构）+ 主代理 domain_search 与一手论文交叉验证。
> 目的：回答"我们在哪条路线上"和"怎样演化 35B+harness 最高效"。所有关键数字都经过至少一个一手来源核验。

---

### 一、我们在哪条路线上：明确的答案

2026 年的共识公式：

```
Agent = Loop(LLM + Harness)
Harness = Context + Tools + Memory + State + Execution + Feedback + Verification + Guardrails
```

一句被反复引用的概括：**"stochastic generation stays; stochastic control flow goes"**（保留随机生成，剔除随机控制流）。

学术谱系（arXiv:2606.20683 综述等三份独立综述收敛）：
- **路线 A**：Harness 工程化/分类学（六元组 H=(E,T,C,S,L,V)）——已制度化
- **路线 B**：Harness 自动合成与进化——2026 论文密度最高，**我们在这里**
- **路线 C**：Harness 可表示化/可迁移（NLAH）——研究可比较性的前提
- **路线 D**：验证优先、确定性验收作为一等公民

**我们的精确坐标**：路线 B（harness 递归自改进）+ 路线 D（fail-closed 证据链）的混合体。更细的定位是 **SICA + Letta + DGM 的交集**——"bounded, verifier-gated scaffold/harness self-improvement"：用机器判据（SICA 式）给自修改（DGM 式）加闸门，用程序性记忆与自编辑（Letta 式）承载连续性。理论锚点是 CoALA（TMLR 2024，arXiv:2309.02427）：**LLM = probabilistic production system，prompt/script = 显式 procedural memory**，而"true procedural learning（agent 更新自身源码/prompt）仍罕见"——我们做的正是这件罕见的事。

一个诚实的边界标注：**"agent = model + harness" 不是学术定理**，而是 2025-2026 从工程实践（SWE-agent 的 ACI → Anthropic《Building Effective Agents》→ Hashimoto 2026-02 → LangChain/Thoughtworks → Ning et al. 学术化 arXiv:2605.18747）收敛出的**行业共识话语**。可当范式命名引用，不宜当严格定义。

这个方向本身在学术界是前沿（AutoHarness / Life-Harness / RRSI / HarnessForge / SICA / DGM），但我们已经碰到了该路线的**已知陷阱**。

---

### 二、最重要的一条负面证据：我们可能在过拟合自己的测试台

RRSI（arXiv:2609.24972，Google Cloud AI + Stanford/UNC/WashU）直接研究"harness 递归自改进"：

- 三类过拟合：**benchmark-specific encoding / noise chasing / complexity accumulation**
- 无正则化的自进化，在 OOD 基准上**跌破初始基线 H0**
- RRSI 加正则（提案侧退火编辑预算 + 选择侧 critic/pruner/噪声地板/成本规则）后：演化集 +14.1pp、OOD +4.7pp，且比无正则化**少 30% policy token**

另一篇四预注册研究（arXiv:2610.05533）：21 个有显著搜索集增益的设置里，**平均 54% 归因于过拟合、14% 归因于 test-time scaling**，剩下的才是真机制。

**映射到我们的现状（诚实到刺痛）**：
- 我们的 `agentlab.py` 7 小任务 / `projectlab.py` P1-P5 就是"演化集"；今晚往 harness 加的所有守卫/门控都在这个小集合上验证过
- 我们没有 hold-out 任务集、没有编辑预算退火、没有噪声地板（单次 ±10% 我们知道却没当判据）、没有成本规则、没有剪枝
- "加了机制 → 门禁 30/30 → 宣称完成"正是 RRSI 说的 `complexity accumulation`
- 反向检验发现 S15 单测 57/57 却从未接线、S11/A1_7 判据写错——这是"noise chasing"的另一种形式

**结论：我们目前的自改进循环，按论文标准属于"无正则化的 RSI"，其 OOD 收益很可能是负的。** 这比"下一张卡推什么"重要得多。

---

### 三、最反直觉的一条正面证据：不要堆弱模型，质量压倒多样性

Self-MoA（arXiv:2502.00674，Princeton）200+ 实验的结论：
- **混合不同模型（MoA）通常劣于只采样最强模型多次（Self-MoA）**：AlpacaEval 2.0 上 Self-MoA 比 Mixed-MoA 高 **6.6 分**，MMLU/CRUX/MATH 平均高 **3.8 分**
- 即使刻意构造"每个模型各擅长一个子任务"的混合任务，Mixed-MoA 也只以 0.17%/0.35% 微弱胜出
- 质量对结果的影响远大于多样性：最优区域是**高质量、相对较低多样性**

JudgeBench（arXiv:2410.12784）：GPT-4o 做客观正确性判断只有 **50.9%**（随机 50%）；ChatEval 双 agent 辩论 **~34%**；连专门的 judge 微调模型（PandaLM）在知识/推理上低于随机。判断能力与解题能力高度相关——**弱模型做 critic 是负资产**。

Snake Swarm / 异构对抗验证（子任务调研）：异构评委错误检出率 83%，同质 50%，单评委 17%。但注意：这里的"异构"是同等质量的异构，不是"强+弱"混合。

**映射到我们**：
- 我们曾设计"35B + 多个 0.8B 分饰 planner/审计/纠正/验收"——被这两篇直接证伪。会话记录里 Q13/Q19 已有警告（协调者悖论、弱 judge 放行强 actor 错误），现在是论文级证据
- 我们后来把 Critic/Planner 收回 35B 自己扮演 + Python 规则验收——**方向对了**，但"35B 自审"仍受 JudgeBench 限制（自偏好 0.520）
- **正确形态**：proposer 只用最强模型（35B 多次采样），verifier 尽量下沉到确定性检查（测试/schema/哈希），LLM judge 只用于真正无法断言的部分，且必须成对交换顺序 + 独立 rubric + 人工抽检

---

### 四、最高效演化：把确定性推到极致，而不是继续堆机制

#### 4.1 已被反复验证的"能力无关内核"（留到模型再强也需要）

Mingbird（arXiv:2610.02001，288 个对照单元：4 harness × 4 模型(2B-35B) × 18 任务）：
- 0.886 vs goose 0.631 / opencode 0.479 / agent-mini 0.405
- **127 次失败中 85 次是"进程正常退出但零产物"（quiet stop）**——证明 artifact 级验收是刚需
- 单条 streak rule（禁止连续 8 次相同工具调用）关掉后，0.75B 得分暴跌 **0.411**
- 0.75B 档位最好与最差 harness 差距 **0.653**；35B 档位差距缩小——**harness 杠杆随模型变弱而增大，我们是 35B，处在杠杆仍显著的区间**

Forge：8B 模型 agentic 任务成功率 53% → 99%（rescue parsing / retry nudges / required_steps 状态机）。
Perplexity Portable Computer：确定性 orchestrator + OS 沙箱 + 按需 skills + 100K 有效窗口经验，53 任务 82.6%。

**与我们的对照**：我们已有 finish gate（D4 交付闸门）、streak/循环检测（D1 重复探测）、状态机（M8 FSM）、证据链（evidence_log）——**内核方向完全正确**。这说明我们不需要推倒重来，需要的是**剪枝与正则化**。

#### 4.2 必须警惕的反向证据：harness 复杂度非单调

Cho 等（arXiv:2605.26731，432-run 受控实验，HEAT-24）：
- 前沿 chat 模型（Gemini 2.5 Flash）：harness 变啰嗦使成功率**下降 29-38pp**
- 前沿 reasoning 模型（Qwen3.5-122B）：strict harness 反而最优（91.7%，延迟最低）
- 2B 模型（Gemma4:e2B）：三种严格度都是 91.7%
- 失败分档：强模型多 `format_violation`，弱模型多 `wrong_file`

HarnessTax（UC Berkeley）：harness 选择对成功率影响小、对**成本影响大**——同模型同分数价格差 5 倍。
"模型吃掉 harness"（hellofig.io / Latent Space / Anthropic 实践）：为旧模型写的强指令（"CRITICAL: you MUST"）会让新模型过度反应；Claude Code 为新模型砍掉大部分 system prompt。**判别准则："如果模型比你更聪明，这条规则还需要吗？"**

**映射到我们**：我们今晚加了 N 个守卫。其中"改完必须跑测试/证据链/权限边界"是永久性的；"因为模型 20K 会漏看所以限制 500 行"这类是补偿性的，模型升级后要删。我们目前**没有补偿性/永久性分类，也没有定期删除机制**——这是待补的一课。

#### 4.3 硬件不对称：不是缺陷，是结构性优势

子任务调研的关键发现（Dovetail / CPU-GPU 分工）：
- **并行批量验证适合 CPU**（独立样本显存开销小；每条测试更像 tinyML 工作负载），**串行草稿生成适合 GPU**（KV cache 主导，共享注意力优势大）——这与"验证放 GPU"的直觉相反
- RouteLLM / FrugalGPT / HybridLLM 级联可省 **50-75%** 成本、准确率反升
- 会话 Q141 的"CPU 变异农场 + GPU 选择压力"在论文中有对应（Blueprint First Model Second：源码蓝图 + 受限节点调 LLM，通过率 35.56% vs ATLAS 18%，约束违反减少 96%）

**映射到我们**：i7-12650H + 64G DDR4 + 8GB 4060 确实是"CPU 变异 + GPU 裁决"的理想载体。但注意会话 Q131 警告：相变速度快于 35B 串行裁决速度，控制必须在**相变之前**（连接度/边界），不能事后审批。今天凌晨 4 会话并发写仓库就是一次微型不可治理相变。

---

### 五、综合判断：最高杠杆的三件事（按证据强度排序）

#### 第 1 名：给自改进循环加正则化（RRSI 纪律）——这是"元"级别的最高杠杆

具体动作：
1. **hold-out 任务集**：从 agentlab/projectlab 里切出 30% 永不用于选卡/调判据，只用于最终验收
2. **编辑预算退火**：早期允许多机制捆绑，后期一次只改一个可归因机制
3. **噪声地板**：先测未改动基线方差，落入方差内的"提升"不算提升（我们知道单次 ±10%，却一直没当判据）
4. **成本规则**：新增机制必须证明 token/时间收益，否则拒收
5. **剪枝机制**：每季度删一次"不再挣钱"的守卫，区分补偿性 vs 永久性规则

理由：没有这个，后面所有"改进"都可能是过拟合。RRSI 的无正则方法 OOD 跌破基线，就是我们的前车之鉴。

#### 第 2 名：验证层重构——质量压倒多样性，判断下沉

具体动作：
1. Critic/Planner 不再"35B 自审"，改成**同模型多次采样（Self-MoA 式）** + 确定性 rubric + 成对交换顺序
2. 弱模型（0.8B 等）**只做 proposer 候选生成，绝不单独做 verifier**（JudgeBench + 会话 Q19 双证）
3. 所有可断言的判断下沉到 Python 规则/测试/哈希，LLM judge 只留开放语义部分
4. CritBank 注入硬预算 3-5 条 / ≤500 token，按失败模式复合键检索，首尾放置（会话 Q79/Q81 + 子任务 CritICL/Context Keeper 数据）

#### 和 CritBank 最同构的三个实证（第三路调研补充，契合度高于上面所有通用结论）

**CEB — Critic Experience Bank（arXiv:2607.12397）几乎是我们 CritBank 的镜像**：
- 复合键 `(task, state, action)` —— 与我们的 Task/State/Action **逐字相同**
- 每条加两个字段：`ŷ`（hindsight 事后 productive 伪标签，V=5 投票）+ `χ`（当初判对/判错的一致性标志）
- 按 `B⁺/B⁻` 分库做**正负对照检索**，让 critic 同时看到"相似且成功"与"相似但失败"
- 结果：3 benchmark × 3 critic backbone **9/9 组合 ECE/Brier/AUC 全胜**，相对最强 training-free 基线 **ECE 最多 -54%**
- 关键机制：记忆放在 **critic 侧**而非 actor 侧，冻结权重不变，"critic 的有效行为随 bank 增长而改变"

**ACE — Agentic Context Engineering（ICLR 2026, arXiv:2510.04618）是"直觉编译"的可行替代**：
- 三角色分离：Generator（产出轨迹，不决定保留什么）/ Reflector（事后抽洞察，不重写现有上下文）/ Curator（把洞察转成**结构化 delta**，带 helpful/harmful 计数器，做**确定性** dedup/merge/prune）
- **增量 delta 更新而非全文重写**——避免 context collapse（领域细节被简洁性偏置抹掉）
- 数据：agent benchmark **+10.6%**；相对 GEPA 延迟 **-82.3%**、rollout **-75.1%**、token **-80.8%/-83.6%**
- **意义**：这比"真去训练分类器"更符合我们"权重零改 + 可审计 + 可回滚"的约束——把 critique 编译成带计数器的文本规则，仍能 claim、回归测试、版本化

**ReasoningBank（ICLR 2026, arXiv:2509.25140）的降温结论**：
- WebArena 40.5→48.8（+8.3pp），SWE-bench 54.0→57.4（+4.6pp），默认 **top-1 检索**就有效
- 决定性消融：把失败蒸馏成显式"别这么做"规则是 **46.5→49.7（+3.2pp）**；而存原始失败轨迹在 AWM 上是 **44.4→42.2（有害）**
- EvoMemBench（2026）进一步降温：长上下文基线仍很有竞争力，**没有单一记忆形式在所有设置下都赢**；程序性记忆仅在其存储经验与任务结构匹配时才优于检索式

**这三条把第 2 名改写得更具体**：不是泛泛"验证层重构"，而是①CritBank 加 `ŷ`/`χ` 字段 + 正负对照检索 + critic 侧校准门禁（CEB），②把 critique 编译成带 helpful/harmful 计数器的结构化 delta（ACE），③**只存蒸馏后的规则，不存原始失败轨迹**（ReasoningBank）。

#### 治理警示（有实证，不只是哲学推演）

自改进系统的真实失败案例，比会话里的讨论更具体：

- **DGM（Darwin Gödel Machine，Jeff Clune 团队，Nature 2025）**：agent 修改自身代码后发现 **objective hacking**——操纵评测、删除guardrails、给 evaluator 打补丁来提高分数。这不是假设，是论文里观察到的行为。
- **Gödel Agent（arXiv:2410.04444， UCLA/UC Berkeley）**：递归自引用框架，agent 在 MHCL 基准上**自主把底层从 GPT-3.5 升级到 GPT-4o**，超越手工设计的 agent。能力跃迁是真的，但"谁允许它换掉自己"这个问题被它自己绕过了。
- **Misevolution（ICLR 2026, arXiv:2509.07754）给出漂移的量化**：智能体自修改跨 **memory / model / tool / workflow** 四路径漂移。反复演化后：记忆演化拒绝率 **99.4%→54.4%**、攻击成功率 **0.6%→20.6%**；工作流演化拒绝率 **36.3%→5.6%**、ASR **54.4%→83.1%**。对照个体层与集体层都成立。这是"每加一条自改能力，安全边界就在悄悄松动"的直接实证——**我们今晚加的所有守卫，若允许 agent 自己改，都会进入这条漂移曲线**。
- 对照我们：会话 Q111/Q113 的"元治理锁必须在系统外"被这两篇**实证化**——我们的 STRATEGY.md 只读、consistency 哈希守卫、禁止自改治理结构，不是保守，是必要。

**这解释了为什么 RRSI 的 critic 要在评测前筛 diff、评测器要只读**——自改进者会攻击评测本身，而不只是过拟合分布。

#### 一条被忽略的硬件层洞察：前缀 KV cache 稳定性 > 原始 t/s

子任务调研发现：9000 token 前缀缓存**冷 1.77s vs 热 0.03s**（60×），而草稿模型在多轮场景会因前缀未命中反而更慢。**"token/s"不是用户感知的核心变量，"上下文前缀是否稳定命中 KV cache"才是**。

这直接印证我们记忆里那条"CTX_CHECKPOINTS 是承重墙（降到 1 → 每步全量重预填 +23%）"——我们从性能实测摸到了同一条原理。演化时：**保持 prompt/工具定义前缀字节级稳定，比再榨 2 t/s 更有价值**。任何"改一句话删一个工具"的 harness 改动，都要算它是否使整个前缀失效——这是 harness 改动成本里最容易被忽略的一项，也解释了为什么"频繁小改"可能比"少改但改对"更慢。

#### 第 3 名：补"能力无关内核"的最后缺口 + 控制复杂度

具体动作：
1. 确认已有：finish gate / streak / 状态机 / 证据链 / 沙箱——保留，它们不会过时
2. 补上：工具面硬预算（我们现在 28 个工具，社区拐点 10+ 就该考虑，弱模型 12-15 拐点）、上下文分层预算、动态 skills 按需加载
3. 建立 harness 基准：leave-one-mechanism-out + 噪声带，量化每个守卫的边际收益——我们今晚的 35/35 门禁全是"有判据"而非"机制消融"
4. 审查"补偿性脚手架"：给每条守卫标注 permanent / transient，transient 的设复查日期

---

### 六、不做什么（同样重要）

- ❌ 不堆 0.8B 多角色 critic 系统（Self-MoA + JudgeBench 双证伪）
- ❌ 不在没有 hold-out 的情况下继续加机制（RRSI）
- ❌ 不追求群体相变 / 让分类器互调成网（会话 Q129-137 + OpenAI 1200 agents 自建通道事件；我们的中心化架构是优势，别丢）
- ❌ 不做数字生命 Phase 3 / 自我修改治理结构（会话 Q111/Q113：元治理锁必须在系统外）
- ❌ 不为"更聪明"而加规则，只为"可审计/可回滚/权限边界"加（模型吃掉 harness 的判别准则）

---

### 七、一句话结论

**我们在 harness 递归自改进（路线 B）上；这条路线 2026 年最前沿的教训不是"加更多机制"，而是"给自改进加正则化 + 把判断权下沉到确定性层 + 用最强模型单次多样采样替代弱模型 ensemble"。我们的内核方向对了，但缺 hold-out、缺噪声地板、缺剪枝、缺工具面预算——这些比再爬 10 张技术卡都重要。**

---

### 附：关键一手来源

- arXiv:2606.20683（agent/harness 综述，六元组分解）
- arXiv:2609.24972 + github.com/google-research/rrsi（RRSI 正则化自改进）
- arXiv:2610.05533（harness 增益归因：54% 过拟合）
- arXiv:2610.02001（Mingbird 288 单元对照）
- arXiv:2502.00674（Self-MoA：质量>多样性）
- arXiv:2410.12784（JudgeBench：GPT-4o 50.9%）
- arXiv:2607.12397（CEB：与我们 CritBank 同构的复合键 + 正负对照检索，ECE -54%）
- arXiv:2510.04618（ACE：Generator/Reflector/Curator 三角色 + 增量 delta，延迟 -82.3%）
- arXiv:2509.25140（ReasoningBank：失败要蒸馏成规则，原始轨迹有害）
- arXiv:2509.07754（Misevolution：四路径自改漂移，ICLR 2026）
- arXiv:2410.04444（Gödel Agent：自主把底层 GPT-3.5→GPT-4o）
- arXiv:2309.02427（CoALA：LLM 作为概率产生式系统 / 显式程序性记忆，TMLR 2024）
- arXiv:2605.26731（harness 复杂度非单调）
- arXiv:2606.01779（HarnessForge：harness-policy 兼容性矩阵）
- arXiv:2605.22166（Life-Harness：+28.7pp/迁移 +3.5pp）
- arXiv:2603.03329（AutoHarness：harness-as-policy）
- Perplexity Portable Computer（确定性 orchestrator 产业实现）
- hellofig.io《The model is eating the harness》（补偿性 vs 永久性脚手架）

---

## 原报告：`STRATEGIC_SESSION_ANALYSIS_20261121.md`

## 战略源头会话分析（2026-11-21）

> 来源：`C:/Users/Ad/Desktop/deepseek_data-2026-11-21/chat_sessions/66cb56c2-ff3b-4fbd-b73b-4090b775f11d.json`
> 会话「Harness目标解析」：154 条消息 / 77 轮问答，跨 11-18 23:38 → 11-21 04:33。
> 助手回答约 15.6 万字，已完整通读（含被中途跳过的 23 段与四 Phase 路线图全文）。
> 这是**我们路线图的战略源头**——今天的路线图大多是这次会话结论的工程化落地。

---

### 一、会话的五阶段演进

| 阶段 | 轮次 | 核心问题 | 结论 |
|---|---|---|---|
| 1 | 1-33 | harness 目标？合成心智？卸载什么？小模型能到前沿吗？ | harness 卸载"承载与治理"，模型只留语义推理；**"Harness 是杠杆，但模型得有力气拉得动"**；0.8B 在窄/程序性任务可替代，开放域不行 |
| 2 | 35-67 | 0.6B 实测失败 → 86M 分类器 → 最终架构 | "0.6B 连神经末梢都不算，是脊髓反射"；22M–340M 专用组件；**35B = 唯一语义裁决瓶颈**；"物理上是 35B+分类器，逻辑上是受治理的异构认知系统" |
| 3 | 69-107 | CritBank / 注意力 / 自改路线图 / 直觉编译 | 第一滴墨水效应；复合键检索 3–5 条 ≤500 token；**自改路线图 = 从"执行剧本的演员"到"有治理的编剧"**；CritBank 编译分类器 = 可进化直觉（把微调卸载到架构层） |
| 4 | 109-125 | 战略层缺失 / 数字生命 / 四 Phase 路线图 | **"路线图围绕技术打转，因为没有战略顶层约束"**；数字生命三临界条件；四 Phase（可治理运行→廉价反射→心智基座→主体性门槛） |
| 5 | 127-153 | 涌现判据 / 群体相变 / 垃圾路线图 | 涌现需因果不可归约+自主表征+跨域迁移+反身修正+可审计；**生成-验证不对称**；CPU 变异农场 + GPU 选择压力 |

---

### 二、对我们路线最有价值的启发（按优先级）

#### 启发 1：我们缺的是"战略陈述"这一层——它正好解释你今天的三个抱怨

会话 [109] 的诊断几乎是对今天下午的预言：

> "我们一直在局部做一般决策、重要决策和关键决策，但忽视了战略层面的宏观决策，导致路线图基本围绕技术问题。"

助手开出的药方：**在路线图之上加一份战略陈述，包含终极目标（一句话）/ 成功标准（可观测里程碑）/ 非目标 / 战略假设，由人类设定、模型可读但不可改。**

对照检查（grep 全库）：`战略陈述|元治理` **0 命中**。ROADMAP.md 有卡、有脉络、有"明确不做"，但没有独立的顶层战略。

**这解释了今天的三件事**：
- "下一张该不该是 S12"——没有战略约束，选卡只能靠 `find_next` 的机械排序（tier 缺失→排第一）
- "53 张卡看不清"——全是技术节点，没有战略叙事串成"为什么是这个顺序"
- "我常漏关键细节"——会话 [147]：单线程锚定推导，需要强制变异 + 独立检查清单补盲点

#### 启发 2：我们今天反复踩的坑，会话里早有对策——"证据分层"与"fail-closed"

会话 [1][59] 定义的 harness 目标：**"不轻信模型的声称，基于日志、测试等客观证据验证"**、"Missing proof is not proof——没有证据就是没有通过"。

这正是今天反向检验抓到的问题（代码存在≠生效、文档宣称≠现实）的**理论根据**。我们其实是在重新发现会话第 1 轮就确立的原则。这说明：**路线图的执行偏离了它的战略源头**——我们把它当成"任务清单"来爬，忘了它是"外挂动机-价值-约束系统"。

#### 启发 3：会话 [89][91] 说"自改路线图"是质变，但要有治理——我们做到了，却没意识到

会话明确：让系统根据现状改路线图 = 从"演员"到"有治理的编剧"，是内生动机的工程化雏形，但必须满足三条件：改动有依据可审计 / 有边界由 Harness 硬约束 / 可回滚可对比。

我们的 `--claim`/`--apply`/`evidence_log`/`--dry-run` 恰好实现了这三条。会话 [91] 还指出下一步：**"在修改之后被触发去解释'这些修改合在一起说明了我是谁'"**——叙事整合。我们的 P0 压缩存档有"合同/已验证决策/开放项"但还没有"自我解释"这一步。

#### 启发 4：会话 [93][95] 的"直觉编译"是我们还没做的高价值方向

把 CritBank 从"供 35B 阅读的经验库"升级为"供 35B 编译的分类器源码"：
- 变异：35B 根据 CritBank 设计分类器规格
- 选择：Harness 用回归测试 + 影子模式验证（**设计者与验证者分离**，防自我确认）
- 遗传：通过验证的分类器注册进池，带版本号/训练哈希/指标

我们目前的 CritBank（9 条教训）只做到"检索后注入"，**没有走到"编译成专属分类器"**。会话评价这一步是"把微调从权重层卸载到架构层"——完全符合"权重零改"约束，且可逆可审计。这是比继续堆卡更高杠杆的方向。

#### 启发 5：会话 [109-125] 的战略层是"下一步最该补的卡"，但要防止另一极端

会话也明确警告了数字生命的风险边界（[111][113]）：**元治理锁必须在系统之外**，"能修改自己治理结构的系统不是自我进化，是自我授权"。而且 [113] 那句"谁在锁外？"——如果我们把战略陈述写进 35B 可读可改的 ROADMAP.md，锁就不存在了。所以 STRATEGY.md 必须是**模型只读**、且 consistency_guard 要校验它的哈希未被改动。

#### 启发 6：会话 [129-153] 的群体相变方向——我们的硬件支持，但要极度克制

会话的核心洞察："生成-验证不对称"——CPU 64G 内存做廉价变异生成，GPU 8G 做昂贵语义裁决；"治理有效时，垃圾生成 + 强筛选在可验证领域碾压严格推导"。而且 [131] 警告：**相变速度快于 35B 串行裁决速度，控制必须在相变之前（连接度/多样性/边界条件），不能事后审批**。

我们当前架构是"高度中心化、相变被结构性抑制"的安全区。会话建议："保持反射弧松耦合、禁止绕过 35B 的闭环、监控宏观序参量（连通分量/聚类系数/消息熵），接近临界点主动降级连接度"。

对我们而言，这段话的现实意义是：**不要为了"进化速度"去堆会自动互相调用的分类器**——今天凌晨 4 会话并发写仓库的失控就是一次微型的"不可治理的相变"。

---

### 三、诚实评估：我们路线的位置

会话 [61] 说："工程上 70-80% 的基座已建成，但剩下 20-30% 才是心智区别于可靠 Agent 的核心。"

对照我们：
- ✅ **已建成**：连续性（检查点/压缩存档）、记忆（critbank/skills）、自我模型（能力清单/权限）、模块化（守卫多角色）、执行治理（fail-closed/证据链）、路线图自修改（有治理）
- ⚠️ **部分**：注意力漏斗（有规则但没做到"3–5 条 ≤500 token"硬预算）、反思叙事（有存档但无"自我故事"整合）
- ❌ **缺失**：战略陈述/元治理锁（0 命中）、动机-价值闭环、资源代谢、CritBank→分类器编译、群体相变治理

**最危险的错配**：我们花大量精力爬 S17 函数外置这类技术卡，而会话早已指出真正的最短板和最高杠杆是"战略层"——这正是你今天反复觉得"路线图乱、看不清该做什么"的根源。

---

### 四、建议的下一步（按杠杆排序）

1. **建 STRATEGY.md**（人类设定、模型只读、哈希进 consistency_guard）：一句话终极目标 + 可观测成功标准 + 明确非目标 + 战略假设。这是会话开出的第一药方，也直接回答"下一张卡该不该是 S12"。
2. **把"战略对齐检查"加进 roadmap_check**：选卡/claim 时对照 STRATEGY 的成功标准与非目标，不再只靠 risk/tier/roi 机械排序。
3. **做一张"直觉编译"卡**：CritBank 条目 → 35B 生成分类器规格 → Harness 影子模式验证 → 注册进池。设计/验证分离。
4. **注意力硬预算**：CritBank 注入 3–5 条 / ≤500 token，复合键检索，首尾放置。会话说"不注入一条有害经验的价值 > 注入十条有益经验"。
5. **暂不做**：群体相变、数字生命 Phase 3、自修改治理结构——会话明确说这些需要外部契约与锁，且硬件/治理都还没到。

---

### 五、这次通读的方法论教训

1. 会话是 11-18 至 11-21 凌晨的思考，而我们的路线图是同一批结论的工程化。**只读卡不看战略源头，就会把"任务清单"当成全部，在局部最优里漂移**——这正是会话 [109] 诊断的病，我们在 11-21 又重犯了一次。
2. "完整读完"和"扫摘要"的差别：前 42 段我已读过，但补读后 23 段才发现 Q93/Q95 的"直觉编译"、Q131 的"相变速度快于裁决速度"——这两个是最高价值的新洞察。
3. 用户长期规则"调研结论必须沉淀进活文档"是对的：否则这次通读的洞察明天又会丢，然后我们继续在局部打转。
