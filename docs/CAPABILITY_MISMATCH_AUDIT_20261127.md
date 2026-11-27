# 能力错配清单：模型有能力，但 harness 没承接导致被迫出错（2026-11-27 14:45）

> 用户问题："还有没有类似于这种问题的：模型本身很强，但 harness 没有承接，导致模型被迫选择出错的地方？"
> 结论：**有，至少 5 类，全部有真实会话级证据**（可定位到会话 ID 和 seq）。
> 这类问题的共同特征：**失败归因被搞反了——看起来是模型能力不足，实际是 harness 的判据/通道/注入有问题。**

## 零、为什么要系统排查这类问题

论文侧最硬的证据：**ToolBottleneckBench**（arXiv:2610.21098）20408 次评分中
**91.5% 的失败由 harness 上限终止**，模型结论错误仅 5.5%；输出上限放大 16× 后
惩罚从 −43.7pp 降到 −2.7pp。另有 4 harness × 4 模型 × 18 任务的 LRAB 矩阵
（arXiv:2610.02001，含 **35B**）：同模型不同 harness 成绩可差一倍以上。

**评估单位应该是"harness–model pair"，不是"模型"。** 这是本次排查的方法论前提。

---

## 一、有实证的 5 类错配

### 1.1 做对了却被拦（最高优先级，可修）

| 会话 | 证据 | 错配机制 |
|---|---|---|
| `38d7c6d2` seq29-39 | shell 替换标题成功 → seq34-36 `read` 确认第25行已改 → seq39 `present`；但 trace L2036 `zero_write_claim` → L2037 `safety_gate_block` flags=["声称改了文件但本轮零写入"] → 两次 audit NEED_EVIDENCE → **L2053 step_hard_stop streak=9** | 零写入守卫**只认 `edit`/`write` 工具，不认 shell 写入**；模型验证也做了仍被判"无证据" |
| `8102ed55` | trace L2310 `edit` OK → L2312 `fep_cycle` **`observed.verified:true`** → L2313 `grep` OK → **L2315 verify_on_stop + L2316 safety_gate_block flags=["收尾验证缺失"]** → 5+ 步无效循环 → L2334 step_hard_stop | 门禁**不认 FEP 的 verified:true 与 grep 为验证** |
| `bd357644` seq88-89 | 注入 `[harness 控制回合] ① 已确立：(暂无完成项)`，但 trace L2219 显示 step7 已 edit OK；模型原文："**为什么harness说我已经连续5步没有改动任何文件？我明明在第5轮就已经调用了edit工具…我应该直接告诉用户任务完成了**"；随后仍被迫 5 次 read/grep → L2253 step_hard_stop streak=11 | **控制回合快照 done:0 与实际 wrote:true 自相矛盾**，模型知道答案却被迫继续 |

**修法**：① 零写入判据纳入 shell 写命令（pwsh/bash 中含 Set-Content/Out-File/cp/mv 等）；
② verify_on_stop 认 FEP `verified:true` 和 grep；③ 控制回合快照生成后做一致性校验（wrote:true → done≥1）。

### 1.2 想验证但没通道（可修）

| 会话 | 证据 | 错配机制 |
|---|---|---|
| `269ec283` seq1197/1214 | 注入"【相关教训 C-003】…跑 verify_agent.py 三态判定；自己的测试全绿不算数"；模型原文："**但我也没有看到可用的 verify_agent.py 脚本**" → 自签"验证报告"结束。脚本实际存在于 `tools/verify_agent.py` | **注入只给文件名，未给路径、未注册工具**——模型知道规则却无法执行 |
| `70f4485a` seq1943 | 原文"需要验证一下这个 VBS 文件语法是否正确" → 无工具调用直接 completed → 下一轮用户截图报火绒删文件 | verify-on-edit 只覆盖 `node --check`/`py_compile`/yaml，**VBS 无检查器** |
| 统计 | 193 条"验证意图"思维链，**23 条**本条+后续 4 事件无工具调用；shell 绕路 170/341 次含文件写操作（12 会话） | 验证通道缺失 → 要么跳过、要么绕路 |

**修法**：注入教训时带**绝对路径**（`D:/Brain/publish/dsh-behavior-guard/tools/verify_agent.py`）；
非标准文件类型降级到"用 read 回读 + 明确说明未验证"，而不是假装完成。

### 1.3 想回忆但看不到历史（部分已修）

- `e22d97fd` seq481 原文："**我注意到之前的编辑把name改成了`@local/...`，但这可能是个问题…我应该把这个恢复成原始的`dsh-hardware-monitor`格式**"；
  seq528 compaction 摘要 3963 字里 `@local`/`EPERM`/`remove_bundle` **全部为 -1**；seq646 仍 `Copy-Item` 用坏源码覆盖。
- 代码级：`_outcome.jsonl` 23790 行**只写不读**；`episodic_search.py` 从未注册给模型、prompt 也不告知可用。
- **已部分修复**：本轮 P0-3 让 outcome 保留原始 reasoning；P1 宽正则捕获反思。但 compaction 必留未闭环纠错**尚未实现**（文档 `POSTMORTEM_HARNESS_BLINDSPOT_20261126.md:88-94` 已给方案）。

### 1.4 工具面逼出绕路（可修）

`70f4485a` seq2342："让我直接用 write 工具写一个干净的 VBS 文件，不用 shell 命令" → 仍调 shell；
seq2329/2349 read 显示文件被写成 `System.Management.Automation.PSRemotingJob`（shell 写入损坏）；
seq2357 才真正 "我直接用 write 工具来创建文件！这样完全绕开 PowerShell 的编码问题" → seq2358 write 成功。

**模型知道正确选择，被门禁和编码问题逼着绕了 5 次。** 修法：写前锚点确认 + 工具结果去重 + 编码问题显式提示。

### 1.5 注入打断原计划（可修）

- `bd357644` L2242 注入（00:45:40）→ L2243-2247（00:46:07）5 个工具调用，模型原计划"直接结束"。
- `2dbd40d2` seq73 原文："**用户又给了个meta指令说要我列任务清单，这个其实是多余的——任务本身已经完成了…那个meta指令是harness发来的要求我先建todo的提醒…不过既然系统明确要求先列清单再执行，那我还是得遵守这个流程**"。
- `COMPACTION_CONTEXT_CADENCE_20261120.md:58-65`：存档内容完全相同时照样注入，模型不知道"这份提醒已经发了 82 次"，形成自我强化循环。
- d1_probe_guard 升级路径：`a91afe6d` L440 → L441 `ask_user_question`，模型**被迫从自主排查转为向用户求助**。

---

## 二、不是 harness 问题的（排除误判）

排查中刻意验证反面，避免过度归因：

- **handoff_gate 24 次全部 `blocked:false`**——只是提醒，从未真正阻断
- **d1_probe_guard 20 次全部 `escalated:true`**——只注入"重复动作"提醒
- safety_gate_block 其余 flag（"重复探测已达上限"/"产物语义问题未修正"/"产物评审未通过"）多数有真实依据：
  `a91afe6d` L555/574/580 连续 4-6 次写入完全相同内容，非误拦
- 文档 `ROOT_CAUSE_FIXES_20261127.md:59-64` 称 d1722ae1 "出现 handoff_gate 拦截"，但当前 trace 该 sid 仅 4 行且无 handoff_gate——**文档与 trace 不一致，不作为实证**

**纪律**：不是所有拦截都是误拦。要有会话原文证明"模型已做对"，才能归因 harness。

---

## 三、论文侧证据（为什么会这样）

| 现象 | 论文数字 |
|---|---|
| 工具菜单过大 | 8→128 schema，成功率 **−17.5pp**（36 任务族中 34 个下降）；全量 vs RAG 检索 13.62% vs **43.13%** |
| 截断才是真凶 | 411 个截断回合中 **391 个在模型发出任何工具调用前**就结束；91.5% 失败由 harness 上限终止 |
| 指令过载 | 规则 10→160，**N=80 时所有模型 perfect-response rate 归零**；GPT-4o mini 容量 ~37-38 条；CLAUDE.md >200 行遵守度下降 |
| 位置效应 | Lost in the Middle：答案在第 10 位 53.8%，比无文档闭卷 56.1% 还差 |
| 过度拒绝 | XSTest：Llama-2-70b-chat 完全拒绝 38%，GPT-4 6.4%；**过度拒绝与拒绝不足不相关** |
| 无外部反馈自纠 | GSM8K 95.5%→89.0%，CommonSenseQA 75.8%→38.1%（已确认） |
| 多 agent 从众 | N=10 盲目从众 85.5%；**agent 孤立时最可能放弃正确答案**；噪声对照 63.2% ≥ 自我修正 61.0% |
| 复杂 scaffold 无效 | hypernetwork 227.8M 参数增益 **0%**；few-shot +21.5%、文档 +5.0% |
| harness 漂移 | 固定 LLM、35 个连续 harness 版本：解决率 23-39%，**无"越新越好"趋势**（ρ=0.208, p=0.231），token +70% |

**方法论文**：五指标归因框架（VCR / Model-Harness Fit / Cross-Model Fit / Interaction Residuals / Token Load，52168 轨迹）；
六个可立即从 session log 算的指标：Read:Edit 比 6.6→2.0、未读就改 6.2%→33.7%、
每千次工具调用打断 0.9→11.4、推理回圈 8.2→21.0、每 session prompt 数 35.9→27.9。

---

## 四、修法优先级（按证据强度 × 可修性）

| 优先级 | 动作 | 证据 | 风险 |
|---|---|---|---|
| **P0** | 零写入判据纳入 shell 写命令 | 会话 38d7c6d2 硬停 streak=9 | 低——可能放过真"只说不写"，但已有 L1 文件声明校验兜底 |
| **P0** | verify_on_stop 认 FEP verified:true + grep | 会话 8102ed55 5+ 步无效循环 | 低——FEP 是 harness 自己的判定，自洽 |
| **P0** | 控制回合快照一致性校验（wrote:true → done≥1） | 会话 bd357644 模型原文明确指出 | 低——纯确定性检查 |
| **P1** | 教训注入带绝对路径 | 会话 269ec283 "没看到脚本" | 低 |
| **P1** | compaction 必留未闭环纠错 | 会话 e22d97fd seq481→646 | 中——需在压缩流程加字段，已有方案 |
| **P1** | 注入去重（同一存档不发第 82 次） | 文档记录 | 低 |
| **P2** | 工具面裁剪 28→18~20（用户决策仍 pending） | 论文 8→128 −17.5pp；项目记忆拐点 12-15 | 中——需重测回归 |
| **P2** | 诊断指标常态化（Read:Edit 比、打断率、回圈率） | 论文五指标框架 | 低——纯观测 |

---

## 五、诚实边界

1. 会话证据是**个案**，不是 A/B——能证明"这次是 harness 错配"，不能证明"这类错配占全部失败的 X%"
2. 论文数字来自各自基准（多为前沿模型），35B 的具体拐点需本地实测
3. 部分 2026 论文（2610.x / 2607.x）需读者自行核实原文
4. "工具面裁剪"涉及用户决策，仍未拍板
5. 反思捕获刚接线，跨会话 A/B 未做——不能把"机制生效"当"能力错配已消除"

## 六、一句话总结

**这类问题的诊断口诀：先看失败停在哪、由谁终止，再看模型当时想做什么。**
如果 trace 显示"模型已验证/已写入/已知答案"但被拦、被要求重做——那是 harness 的判据错了，不是模型笨。
本次排查找到 5 类、11 个会话级实证，其中 3 个 P0 修复都是低风险确定性改动。

来源：会话 `38d7c6d2` / `8102ed55` / `bd357644` / `269ec283` / `70f4485a` / `e22d97fd` / `2dbd40d2` / `a91afe6d`；
论文 arXiv:2610.21098 / 2610.02001 / 2607.22585 / 2607.03691 / 2505.03275 / 2307.03172 / 2308.01263 / 2310.01798；
项目文档 `POSTMORTEM_HARNESS_BLINDSPOT_20261126.md` / `READ_EFFICIENCY_RESEARCH_20261127.md` / `COMPACTION_CONTEXT_CADENCE_20261120.md`。
