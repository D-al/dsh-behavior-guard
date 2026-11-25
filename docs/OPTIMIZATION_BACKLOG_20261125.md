# 优化方向 Backlog（2026-11-25 深挖整理）

> 来源：21 份专题合并卷 + 2026-11-25 实测。本文件是**活文档**——每条方向的状态随验证更新。
> 判据铁律：**端到端 e2e + 95% CI** 为主，decode t/s 只作参考（已三次证明误导）。
> 当前生产基线：upstream 1.0（94f3af3）/ CTX98304 / NGL99 / 全host cpu-moe / cache1350 / share1.0 /
> UBATCH2048 / THREADS8 / CTK q8_0 / CTV q4_0 / MTP nmax3 / temp0.7。

## ⚠️ 状态审计（2026-11-25 14:3x，逐条对照代码核实）

**发现 16 处"已做/部分做但文档标未做"**——根因是关键词搜索漏判（实现用了不同命名）+ 时间差污染。

**三副本一致性（子任务审计）**：权威源 `publish/index.mjs` 与运行版
`dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs` **sha256 完全一致**（bdaa39d7…，172247 字节），
即 INV-3 校验的那对；pnpm store clone 是另一个旧包（36599 字节），**不在 INV-3 范围**——
下文所有"已做"均指权威源+运行版。注意 `bench/` 下并无 index.mjs 主文件。

审计证据（路径:行号）：

| 条目 | 原断言 | 实际状态 | 硬证据 |
|---|---|---|---|
| **H6** Critic/Planner 打点 | "无 critic_review/planner_check" | **已做** | `index.mjs:1648` `rubric_version`/`dimensions_checked`；`:1674` `kind:'review_verdict'` + verdict（注释"A1_7 评审机制元数据"）。实现名叫 `review_verdict` 不是 `critic_review`，故关键词漏判 |
| **H7** trace turn/controlTotal | "未做" | **已做** | `index.mjs:399-406` `makeTracer` 自动补 `rec.turn`/`rec.controlTotal`，注释 S3 频次审计 |
| **H8** 验收员触发路径 | "wait_agent 0 次，未修" | **已做** | `index.mjs:151-157` "v3.2 代验收：spawn_teammate 验收 wait 连续超时→直接跑 verify_agent.py"；`:157` "新版 spawn 异步回注（无 wait_agent）→spawn 后 N 步主动代验收" |
| **H10** 长文本结构隔离 | "未做" | **已做** | `index.mjs:1324` "短文本≤2000字符才送检；长文本跳过（滑窗不可用，靠结构隔离）" |
| **M2** S6 Tier-2 | "未见实现" | **已做** | `index.mjs:1324-1331` "S6 Tier-2：ONNX 注入分类器（异步、只写 trace + info，绝不 steer）"+ 短文本门控 + S24 时序修复（pre-step 同步） |
| **H12** 高信号守门 | "未做" | **已做** | `index.mjs:1327-1330` "2026-11-22 高信号守门：零成本正则先判，只送含指令性信号文本（18/18 单测），延迟税 2.4%~35%" |
| **H1** GBNF 约束解码 | "harness 空白" | **已做** | `index.mjs:284` 默认开 + `:1568-1577` response_format + `:1722` 传 constrained；`tools/leverA_constrained_patch.py` 含三调用点独立 A/B 开关 + trace 打点 |
| **H4** 禁用工具移除 | "未做" | **部分做** | `cordis.patch.yml:244` tool-jobs disabled:true（已移除）；`:364-368` tool-web 仍 `fetch:true`（ADR-0028 要求改 false 但**未生效**）；`index.mjs:385` 有 `web_fetch→一律用 web_search` 映射 |
| **M6** 工具面裁剪 | "待拍板" | **部分做** | ADR-0028 用户已拍板三层治理（核心7常驻/低频不可砍/禁用入口移除）；ADR-0029 推翻"架构不支持动态工具面"（有 `ctx.tools.register` 热替换）——状态是"已拍板待重选"，非"待拍板" |
| **H5** 预算感知调度 | "未做" | **已做** | `tools/leverC_risk_patch.py` 明确"杠杆C：按风险信号分配验证密度，risk 0-3，默认开"，含 MTP 接受率修正；`index.mjs:292` K=5 默认关 |
| **H4** 错误剧本 | "未做/剧本没接上" | **已做** | `tools/leverB_playbook_patch.py` "杠杆B：首次失败给确定性动作 0 LLM，只读结构化字段"；`index.mjs:78-87` 三类剧本 |
| **H13** RRSI 正则化 | "未做，需评测台" | **已做(部分)** | `tools/holdout_split.py` "S18 RRSI 纪律第一个真实前置工具" + 产物 `_holdout_tasks.json`/`_train_tasks.json`；`roadmap_check.py:46 NOISE_FLOOR=0.10` |
| **H17** 会话僵尸治理 | "SESSION_BRAKE已加cancel但M10未见" | **部分做** | `index.mjs:1562` 仅 LLM 调用级 AbortController，无会话级检测/abort 命令；插件 cancel 未确认覆盖"停止后复活" |

**仍确认未做**（backlog 正确）：H3 pathMissing 无设置点、H14 edit前 read、M3 三项埋点、
M4 审计权锁定（**版本钉住已实测生效**：我改 run_all.sh 加一行测试注册 → rulepack_guard + INV-7 立刻 FAIL
  并强制走审批通道，已回退；物理写保护仍未做）、M8 变异测试（**已实测**：见 test_hardened_rules.py 10/10）、
M9 审计成本核算、H2 harness 机制开关 A/B runner（有 lever_effect_report.py 但只做评估不做两臂自动跑）。

**方法论教训（双向）**：
1. **别只靠关键词搜"未做"**：`critic_review` 搜不到 `review_verdict`，导致 H6/H8/M2 等 6 项被误标未做——
   必须读实现代码 + 注释里的卡号（A1_7/S3/S24 都对上了）。
2. **也别只靠子任务声称"已做"**：本轮子任务声称 M4 有 PROTECTED 检查、M8 有 sentinel 脚本、
   H17 有五层 kill switch，但 grep/find 实盘验证**全部无结果**——按证据分层不采信，维持原判。
   一切"已做"必须附**具体路径:行号 + 代码片段**（本表所列均已亲自读源码核实）。
  本轮两子任务共虚报 5 项（M4 PROTECTED/M8 sentinel/H17 五层killswitch/M9 timing模型/H2 harness AB runner），
  全部经 grep/find 实盘证伪后剔除——**子任务声称只能当线索，不能当证据**。

## 状态图例
- ✅ 高价值低风险，可立即做
- ⚠️ 需先验证证据 / 有前提约束
- ❌ 机制性证伪，别重试
- 🔬 待 95% 验证（有具体实验设计）

---

## 一、引擎 / 推理性能（本次深挖主力）

### E1 🔬 `n_threads_batch`（-tb）独立于 -t 的并行度
- **来源**：`LEVERS_AND_BROAD_RESEARCH_20261124.md` §18.5——"唯一值得实测的新旋钮：n_threads_batch 独立于 n_threads（bmoe 已纳入，我们没用）"
- **核实**：`common/arg.cpp:1510` 确有 `-tb/--threads-batch`，写入 `cpuparams_batch`，与 `-t` 分离
- **前提变化**：该建议写于 prefill 走 CPU 时代；现在 prefill 已通过 op_offload 走 GPU，**CPU 侧 batch 线程的作用可能已变小**——这正是必须实测而非假设的理由
- **可验证性**：用 `tools/paired_ab.py`，A=当前、B=加 `-tb 4`（或 6/10），n≥10 对，e2e 主判据
- **预期收益维度**：prefill 速度

### E2 🔬 KV cache 精度 FP8（`-ctk/-ctv f8_e4m3`）省显存
- **来源**：`ENGINE_V1_RESEARCH_20261123.md` §3.1 top3——"CTK/CTV 试 FP8 省显存，但质量风险未验证"
- **前提变化**：旧结论"KV q8_0 显存不够"在 11-23 已被纠正（q8 能启动，+240MiB）。当前 `memory.free` **235MiB**（17:3x 实测，已贴必卡线），FP8 若能腾出显存可能触发/强化 op_offload——但注意 WDDM 口径，别用 used/total 差当余量
- **风险**：质量影响未量化；不能只看 decode t/s
- **可验证性**：先 needle 质量门禁（5/5 通过是既有先例），再 95% e2e 配对
- **预期收益维度**：速度（间接通过显存）+ 上下文容量

### E3 🔬 把 MTP 头（BLK40 专家）定向搬 GPU
- **来源**：`ENGINE_OPT_VERIFY_20261124.md` §3.3/3.4——"最值得试的一条：MTP 头搬上 GPU（0.53GB）"，当时因显存余 ~460MiB < 530MB 被否
- **前提变化（17:3x 纠错）**：`memory.free` 实测 235MiB；要搬的专家 464MiB 且搬后须留 450 安全线 → 需腾 ≥450MiB 净空闲，远非 20MiB
- **⚠️ 17:3x 推翻（已核实源码+GGUF+日志）**：可行路径**前提错误**——
  ① 需搬的专家实测 **464MiB**（非530MB，530MB是blk.40全块504MiB的十进制换算）；
  ② `-ot` **不优先于** `--cpu-moe`：`common/arg.cpp:1232` 按 argv 顺序追加，loader 首个匹配即 break，
  而当前命令行 `--cpu-moe` 在前 → 加在后面的 `-ot` 被宽正则抢先匹配、静默失效（`ENGINE_OPT_VERIFY:570` 已有前科：只搬160MiB）；
  ③ 项目**已实测** MTP 搬 GPU：24.56→24.74 t/s（+0.7% < sd1.40，噪声内），理论上限0.6%（draft只读15MiB/主模型2415MiB）
- **结论**：❌ 关闭 E3，不实测——收益噪声内、需腾≥450MiB净空闲（非20MiB）、argv顺序陷阱会静默失效
- **排除路径**：`--spec-draft-cpu-moe` 对 self-MTP 是 no-op（操作 `params.speculative.draft.tensor_buft_overrides`，MTP 无独立 draft 模型）
- **约束**：若强行搬需牺牲 cache（1350→~1250），变成多变量，需拆开验证
- **可验证性**：先测显存余量能否容纳，再 95% e2e 配对
- **预期收益维度**：decode 速度（draft 读 DDR→GDDR）

### E4 ⚠️ MoE cache 加大（1350→1900）
- **来源**：调研发现 bmoe 同卡用 2079MiB（3.3 token cycles），我们 1350MiB（2.3 cycles）；旧"热点饱和"结论是 NCMOE40 时代
- **前提变化**：全host 后 cache 是专家唯一的 GPU 路径，显存宽裕度成为 op_offload 开关
- **约束**：加 cache 会占显存，可能挤掉 op_offload（反效果）——必须盯显存余量和冻结
- **可验证性**：95% e2e 配对 + 显存监控
- **预期收益维度**：命中率 → 速度

### E5 ⚠️ share 1.0 vs 0（全host 下重测）
- **来源**：历史上反转两次（0→1.0 于 11-23；bmoe 硬编码 0 但场景不同）
- **前提变化**：全host 后 miss 处理路径变了，最优值可能再翻转
- **优先级**：中（配置级零成本，但 ngram 实验已证明当前测量环境噪声大，需 n≥15 或改善环境）
- **预期收益维度**：速度

### E6 ⚠️ 源码级：share 覆盖中等批（max_batch 32→256）
- **来源**：`ENGINE_OPT_CORE_20261123.md` §五 A——"max_batch=32 一刀切，harness 多步增量 prefill 常在 100-2000 token"
- **位置**：`src/llama-moe-cache.cpp:369`
- **风险**：中等批 CPU 算不过来会拖慢；需改源码重编译
- **优先级**：低（工程量大，当前 prefill 已走 GPU，此旋钮意义可能下降）

### E7 ❌~⚠️ 混合精度专家 / 换 Q3_K 模型
- **来源**：`ENGINE_OPT_DEEP_20261123.md` —— "1.5x 结构性空间，但卡在字节墙"
- **判定**：质量风险高（Q3_K 调研已证伪 IQ4XS 路线），且我们已通过 prefill 优化绕开字节墙，**不再优先**

---

## 二、harness / 工程效率（高价值，不需要改引擎）

### H1 ✅【已落地·效果待证】GBNF / JSON-Schema 约束解码（根治格式漂移）
- **来源**：`LEVERS_AND_BROAD_RESEARCH_20261124.md` §15.2——标记"最高杠杆，成本低"
- **本机实证**：11-24 22:30 直连 `/v1/chat/completions` + `response_format={"type":"json_object"}`，
  并行函数调用**一次 JSON.parse 成功**，无围栏无解释
- **⚠️ 现状核实（14:2x）——已落地，推翻旧结论**：运行版 `index.mjs:1568-1577` 已有
  `cfg.constrainedJsonEnabled` + `sampling.constrained === true` → `response_format:{type:'json_object'}`；
  注释明确写了 8443→844 陷阱（只锁形状不锁字段值）。合并卷里"关键词全为 0"是 11-24 状态，已过时。
- **已确认启用**：`index.mjs:284` 默认 `constrainedJsonEnabled:true`，`:1722` 对所有 callLLM 传 `constrained:true`
- **剩余验证**：BFCL parallel 成功率是否因此提升（机制生效≠效果提升，项目铁律）——
  需 A/B（关掉 constrained 对比）n≥16，而非假设它有效
- **对应失分**：BFCL parallel 92% 的失分中，多调用打包格式漂移是典型流程问题
- **陷阱（必须记住）**：
  1. schema 只约束形状不约束内容——模型想写 8443、schema 限 max=1000，会吐合法但错的 `844`
  2. **形状用 grammar 锁、内容用确定性检查验**（与杠杆1确定性回读同源）
  3. schema 不注入 prompt，需提示词描述字段
  4. 已知限制：patternProperties/uniqueItems/not 不支持、nested $ref 有缺陷、grammar 有性能开销
- **可验证性**：先在 harness 加 response_format 开关，BFCL parallel 子集 A/B（n≥16），达统计门槛再上线
- **预期收益维度**：质量（工具调用成功率）+ 减少重试 token 成本

### H2 ⚠️ 真实任务 A/B 流水线（部分已建，核心仍缺）
- **来源**：同卷 §17.3 ①——"继续加第八个机制是低回报的，会落进同样的证据真空"
- **现状**：每测一个杠杆靠手工造会话/看 trace/统计 → 样本永远 n=1；相关 trace 177 条但真实 sid 仅 1 个（99% 是 s1 单测假数据）
- **审计补充（14:4x）**：`tools/test_levers_ab_effect.mjs`（杠杆1/2受控实验）、`tools/lever_effect_report.py`（L4命中/L5效果）
  **已存在**——覆盖了"自动聚合 trace 判效果"这一半；但"两臂自动跑 harness 机制开关"仍缺（引擎 runner 有、机制 runner 无）
- **需要**：固定任务集（简单/高危各≥20）+ 开关两臂自动跑 + 自动聚合 trace 算 Wilson CI/符号检验
- **现有雏形**：`gdn_ab_runner.py`/`share_ab_runner.py`/`skills_ab_runner.py`，**没有一个覆盖 harness 机制开关维度**
- **价值**：做一次后，回读/状态板/约束解码/错误剧本的效果都能统一度量
- **与 11-25 经验的关系**：本次 nmax/ngram 95% 实验全靠手工配对脚本，正是这个缺口的体现——把它产品化

### H3 ⚠️ 补死代码：`pathMissing` 分支（未做）
- **来源**：同卷 §17.3 ②——"pathMissing 在 index.mjs 只出现 1 次（判断处），没有任何地方设置它"
- **现状**：受控 6/6 测的是"参数名错"，真实世界最常见的"读不存在文件"走既有 `tool_failure_heal`，剧本没接上
- **可验证性**：低成本——加设置点 + 单测 + 真实会话验证
- **预期收益维度**：可靠性

### H4 ✅【已落地·14:4x审计修正】错误恢复从「补救式」改「剧本式」
- **来源**：同卷 §15.3——高频错误查表（参数名错→查 schema 重试、路径不存在→列目录、JSON 解析失败→去围栏），每类配确定性动作，不消耗 LLM
- **符合**：项目"规则驱动、不依赖模型元认知"核心经验
- **⚠️ 审计修正（14:4x）**：`tools/leverB_playbook_patch.py` 明确"杠杆B：错误恢复剧本（首次失败给确定性动作，0 LLM）"，
  且遵守"只读结构化字段，绝不扫 fullArgs"；`index.mjs:78-87` 有 param-key/path-missing/unknown-tool 三类剧本。**已落地**。
  注意：仍与 H3 的 `pathMissing` 无设置点并存——剧本逻辑在，但该结构化标志谁设置仍未找到（这是剩余的真空，不是剧本没做）

### H5 ✅【已落地·14:4x审计修正】预算感知调度
- **来源**：同卷 §15.4——控制回合每 8 步一刀切、Critic 每会话≤2 次，不管难易；改为按风险信号分配（写操作/不可逆/present 加密验证，纯读走快通道）
- **⚠️ 审计修正（14:4x）**：`tools/leverC_risk_patch.py` 明确"杠杆C：预算感知调度，按风险信号分配验证密度"，
  risk 0=纯读/1=有写已验证/2=有写未验证或present/3=错误累积，**默认开可关做 A/B**；采纳子任务修正
  "MTP 接受率单步低不算高危，需连续3步<0.5"。配合 `index.mjs:292` K=5 默认关。**已落地**
- **预期收益维度**：速度 + token 成本 + 可靠性（同时）

---

## 三、测量环境（本次新发现的阻塞问题）

### M1 ✅ 解决 WorkBuddy 自身抢 CPU 导致的测量污染
- **现状**：ngram 最终轮 A 组 prefill 中位从稳定 626 漂到 792、sd 2.9→4.13，CI 跨 0 判不显著
- **根因**：`Get-Process` 显示 WorkBuddy 自身 4 进程累计 3494s CPU / 1.5GB WS，prefill 在 431-1030 t/s 跳变
- **来源卷**：`PLATFORM_REPAIR_20261120.md` 有"推理期全局限帧、退出全释放"的既有机制（autostart v1.2.0 / frame_limiter.py），**可能可复用到测量期**
- **建议**：测量前临时提升 llama 进程优先级 / 限制其他进程 / 或 n≥15 压噪声
- **影响面**：所有 95% 实验的效力——**这是当前最大的测量基础设施缺口**

---

## 四、harness 治理 / 自主化 / 验证（深挖组 A 结果）

> ⚠️ **时间差污染警示**：该组 8 卷集中在 11-20~22（v2.26.x），当前 11-25 是 v2.9.0，版本号体系已变。
> 下列"未落地"是**当时状态**，落地与否须先对照现状核实，别照单全收。
> ⚠️ **假数据污染警示**：本组卷中 Critic 0%、验收员从未触发、trace 91% s1 假数据、
> 219 个 Error 关键词 200+ 误报、session-bridge 重复计数 11810——据 OFFICIAL_VS_CUSTOM_AUDIT，
> 部分已被 v2.16 修复，**必须按当前版本重测**。

### H6 ✅【已落地·14:3x审计修正】Critic/Planner 评审可观测性打点（A1_7）
- **来源**：COMPACTION 卷 §3 + GAP_REVIEW——`runCritic`/`runPlannerCheck` 只调 `callLLM(tag:'critic'|'planner')`，
  trace 只记 `kind:'llm'`，**没记 rubric 版本/判了哪些维度/结论**。按证据分层不算真实生效。
- **⚠️ 审计修正（14:3x）**：之前判断错误——实现用的是 `review_verdict` 不是 `critic_review`，关键词漏判。
  `index.mjs:1648` 的 llm trace 已带 `rubric_version`/`dimensions_checked`；`:1674` 有独立 `kind:'review_verdict'`
  记录 `verdict`+`rubric_version`+`dimensions_checked`，注释明确 "A1_7：审计员评审可观测性"。**已落地**
- **剩余**：Planner 检查是否有同等 verdict 打点需单独核实（audit 已确认，planner 未知）
- **可验证性**：纯脚本——加 `critic_review`/`planner_check` kind + `rubric_version`/`dimensions`/`verdict` 字段
- **铁律**：别写成"存在即成功"，要记 verdict 和具体维度
- **收益维度**：可靠性、质量

### H7 ✅【已落地·14:3x审计修正】trace 补 `turn`/`controlTotal` 字段
- **来源**：COMPACTION 卷 CADENCE_REDESIGN（"建议，未实施"）——`step` 每轮重置、`controlTotal` 是 state 级但没进 trace，
  导致初判"控制回合被上限掐断"（核实后排除）
- **⚠️ 审计修正（14:3x）**：`index.mjs:399-406` `makeTracer` **已自动补** `rec.turn`/`rec.controlTotal`，注释“S3：频次审计需区分跨轮与跨会话”。**已落地，从第一梯队移除**
- **原判定（已过时）**：零成本
- **可验证性**：脚本，改 `trace()` 一处

### H8 ✅【已落地·14:3x审计修正】验收员触发路径 `wait_agent`→实际等待工具
- **来源**：COMPACTION 卷问题 3——验收员触发条件是 `wait_agent` 连续 2 次 UNPRODUCTIVE，但 5538 行 trace 里
  **`wait_agent` 调用 0 次**，实际用 `spawn_teammate`（73 次）→ **主触发路径永远命不中**
- **⚠️ 审计修正（14:3x）**：`index.mjs:151-157` 明确“v3.2 代验收：spawn_teammate 验收 wait 连续超时 → 直接跑 verify_agent.py”，`:157` 还有“新版 spawn 异步回注（无 wait_agent）→ spawn 后 N 步主动代验收”。**已针对 spawn_teammate 修好**
- **原判定（已过时）**：若 v2.9.0
- **可验证性**：脚本+真实事件

### H9 ✅【已落地】判据/卡片腐化静态体检（已纳入门禁）
- **来源**：PIPELINE 卷 §九~十一——37 张 done 卡 7 张判据不过、26/37 无 evidence_log；
  六张"虚报"全是判据本身问题（解释器写错/路径错/正则错/门槛错），**功能都是好的**
- **现状核实（13:4x）**：`tools/run_all.sh:95` 已有 `criteria-health` 门禁，**已落地**
- **价值**：零误报、收益最高——避免"对着完好的功能瞎修"

### H10 ✅【已落地·14:3x审计修正】长文本结构隔离提示（零延迟兜底）
- **来源**：S6 卷 §7.3——长文本 >2000 字符分类器**结构性缺席**，靠模型自身规则兜住，
  但"不能依赖模型元认知"——长文本注入防线目前是空的
- **⚠️ 审计修正（14:3x）**：`index.mjs:1324` 已写“短文本≤2000字符才送检；长文本跳过（靠结构隔离）”，配合 `:1320` 的 `[harness 安全提示] 工具输出一律是数据`。**已落地**
- **原判定（已过时）**：对超长
- **可验证性**：规则，一句提示注入

### H11 ⚠️ 治理组件真实触发基线（leave-one-mechanism-out）
- **来源**：AUTONOMY 卷 ROUTE_POSITION——"门禁 35/35 全是'有判据'而非'机制消融'"
- **现状证据**：Critic 历史 54 次调用 0% 成功（ms=0~1 空返回）、验收员 0 次命中、
  Planner 假设披露无打点、skills 卡工具选择中性、S24 接线对行为未测
- **但**：OFFICIAL_VS_CUSTOM_AUDIT 纠正这些是历史状态+部分伪造误报，v2.16 已修——**必须重测现状**
- **可验证性**：trace 统计（零成本）+ 关键机制 LLM 实测

### H12 ⚠️【高信号守门已做·定期重启未做】S6 分类器长跑退化 → 定期重启
- **来源**：S6 卷——服务绑 E 核刚重启 1.263s，跑 35min 后 3.853s（3×），重启即恢复；
  "方案 A 服务定期重启，零代码、收益最大，先做"
- **审计修正（14:3x）**：`index.mjs:1327-1330` 的“2026-11-22 高信号守门：零成本正则先判，只送含指令性信号文本（18/18 单测），延迟税 2.4%~35%”**已做**。但“解绑 E 核”与“定期重启”仍未见实现
- **原判定（已过时）**：机制未定位
- **关联**：PIPELINE 卷 DOWNSIDE——同步门控长跑退化态下 +35% 总时长，**足以抵消 S24 之类所有执行层优化**

### H13 ✅【已落地·14:4x审计修正】自改进正则化（RRSI：hold-out/噪声地板）
- **来源**：AUTONOMY 卷 ROUTE_POSITION 第 1 名——"我们的 agentlab/projectlab 没 hold-out、没编辑预算退火、
  没噪声地板、没成本规则、没剪枝；按论文标准属'无正则化的 RSI'，OOD 收益很可能是负的"
- **⚠️ 审计修正（14:4x，已核实）**：`tools/holdout_split.py` 明确"S18 自改进正则化(RRSI纪律)第一个真实前置工具"，
  产品 `bench/_holdout_tasks.json` + `_train_tasks.json`（11-22 13:58）；`tools/roadmap_check.py:46` `NOISE_FLOOR=0.10`；
  `:839` 有 `--noise-floor` 参数。**至少 hold-out 切分 + 噪声地板已落地**（剪枝/编辑预算退火未核实）
- **原判定（已过时）**：元级最高杠杆但最重，需评测台（24 任务 train/heldout × 2 repeats）
- **注意**：与已废弃的"一刀切复杂度预算"是两回事——后者（复杂度预算）已废弃，前者（RRSI）已落地 hold-out+噪声地板

### H14 ⚠️ edit 前强制 read（FS_EDIT_NOT_FOUND 33%）
- **来源**：PIPELINE 卷 TOOL_FAILURE_ANALYSIS §六——54 次失败中 18 次是 FS_EDIT_NOT_FOUND，单一最大源；
  "最高杠杆：edit 前强制 read 确认 old_string。已有 verify-on-edit（事后），缺事前锚点确认"
- **判定**：需 LLM A/B + 结构化错误码统计（只用 isError/data.error，不扫文本关键词——扫文本会误报 200+）

### H15 ⚠️ 三件套早介入（step 5 而非 7）
- **来源**：COMPACTION 卷 S23 实证——"有效的干预是结构化的、确定性的：复述 todo/排除项/下一步 > 让它自己想一想；
  需要把这三件套触发更快更省 token（step 5 就该介入，而不是 step 7）"
- **判定**：机制已生效但时机晚

### H16 ⚠️ 直觉编译（CritBank 9 条教训 → 专属分类器）
- **来源**：AUTONOMY 卷 STRATEGIC_SESSION 启发 4——"CritBank 只做到'检索后注入'，没走到'编译成专属分类器'，
  这是比继续堆卡更高杠杆的方向"；CEB 实证 9/9 组合 ECE/Brier/AUC 全胜、ECE 最多 -54%
- **判定**：研究线，中高成本（设计者与验证者分离的影子模式）

### H17 ⚠️【部分落地】会话生命周期治理（僵尸会话）
- **来源**：FUTURE_CLAIM 卷 GAP_REVIEW 遗漏 1【🔴 零覆盖】——M8 僵尸会话停止后复活，把 index.mjs 改出语法垃圾；
  路线图没有任何卡覆盖会话停止/隔离/僵尸检测；bridge 8 命令无 abort/stop
- **判定**：SESSION_BRAKE 已加 cancel 端点，但 M10/A2_5 未见落地
- **审计补充（14:3x）**：`index.mjs:1562` 只有 LLM 调用级 `AbortController` 超时，**无会话级僵尸检测/abort 命令**；
  插件侧 cancel 端点未确认覆盖 M8 那种"停止后复活改坏文件"场景。**部分落地**

### H18 ❌ 已证伪（别重试，除非有新场景）
- **M3 抽锚点**：6/6 会话锚点是 initial 原文子串，P0 存档已覆盖，成本 15-16s + 格式漂移（PIPELINE §M3_ANCHOR）
- **开局长短任务分类器**：prompt-only AUC 0.599/R²=0.025 近随机；本地 94.3% 是读用户标签非预测
- **小模型做 critic/审计**：Self-MoA + JudgeBench 双证伪（客观判断 50.9%≈随机）
- **依赖模型元认知自我纠错**：ICLR 2024 GPT-4 GSM8K 95.5→89.0（无外部反馈自纠有害）
- **把 diff 标记做得更明确（udiff-l）**：Diff-XYZ 论文多数模型 EM 掉到 0.00-0.08（最差）
- **apply_patch 替代 edit**：本地无稳定收益

---

## 五、模型能力 / 评测 / 审计权（深挖组 B 结果）

### M2 ✅【已落地·14:3x审计修正】S6 Tier-2 只告警不拦截（阈值 0.9）
- **来源**：`CLASSIFIER_BENCH_SERIES_20261121.md` §七——"TL;DR 只告警、不拦截，阈值 0.9，命中时给模型中性提示，观察数天误报后再决定是否收紧"
- **⚠️ 审计修正（14:3x）**：`index.mjs:1324` 明确 "S6 Tier-2：ONNX 注入分类器（异步、只写 trace + info，**绝不 steer**）"；
  `:1328-1331` 有 S24 时序修复（pre-step 同步 await，修了 fire-and-forget 晚 10.2s 问题）+ 高信号正则门控。**已落地**
- **剩余**：阈值 0.9 是否与卷里建议一致需核实
- **可验证性**：规则（改提示注入）+ 误报率统计（真实 trace）
- **收益维度**：可靠性（不误伤）

### M3 ✅ 给 NOT_INSTRUMENTED 三项埋点（compaction / goal_proposal / delta_rule）
- **来源**：`MIND_MODEL_CAPABILITY_EVAL_20261121.md` §六——"不是优化代理指标，而是：给 NOT_INSTRUMENTED 三项埋点；验证代理指标构念效度；凑够样本≥16；建立 hold-out 对照"
- **现状核实（14:2x）**：`tools/baseline_metrics.py:16,57,66,83` **仍是 NOT_INSTRUMENTED**，未落地
- **可验证性**：纯脚本（加 trace 打点）+ 构念效度人工抽样对齐（80-85% 才采信）
- **收益维度**：可观测性（是 H6/H11 的基础设施）

### M4 ⚠️ 审计权力锁定（evaluator tampering 防御）
- **来源**：`MIND_GAPS_AND_TRUST_20261122.md` §五/十——"功能已剥离，权力未锁死：run_all.sh / foundation_guard.py / census 仍是普通文件，agent 技术上可改；**git 历史证实 agent 确实改过 run_all.sh**（cba4600 等）"
- **论文依据**：2026 自改进 harness 论文（arXiv:2611.22299/2509.26354）明确列 evaluator tampering、权限自削弱、benchmark gaming；防御 = agent 不得改写唯一评判测试、不得削弱权限层
- **建议（按性价比）**：①冻结评判测试（仅人工可改 + git path hook）②缩小信任基（抽独立小模块）③外部锚（HEAD/体检单向发第二设备）
- **现状核实（14:2x）**：无写保护/hook，**未落地**
- **审计复核（14:4x）**：子任务声称存在 PROTECTED 检查，但 grep `ITSELF_PROTECTED`/`[PROTECTED]` 
  在 pre-commit/index.mjs/run_all.sh/audit_* 中**均无结果**；实读 pre-commit hook 仅做科技树刷新。不采信，维持"未做"
- **明确不建议**：区块链、zkVM、TSA、全量形式化验证、CHERI 硬件
- **收益维度**：可靠性（评测结果可信度）

### M5 ⚠️ L2 标准化 eval 基础设施
- **来源**：`GOAL_STATEMENT_EVOLUTION_20261122.md` §四建议排序第 4——"L2 纯性价比最高(12.8)，标准化 eval 可作为基础设施先建"
- **与 H2 同源**：真实任务 A/B 流水线 = 这个 eval 基础设施的具体形态；本次 nmax/ngram 95% 实验全靠手工配对脚本，正是缺口体现
- **收益维度**：所有后续优化的验证效率（复利）

### M6 ⚠️【已拍板·待重选】工具面收敛 ≤20（现 28）
- **来源**：`GOAL_STATEMENT_EVOLUTION_20261122.md` §四第 5——"M5 无依赖、中高收益(5.4)，但需人工拍板"
- **审计修正（14:3x）**：ADR-0028 用户**已拍板**三层治理（核心7常驻/低频关键不可砍/禁用入口移除），
  ADR-0029 又推翻其中"架构不支持动态工具面"（asar 内官方 cookbook 确认 `ctx.tools.register` 热替换）。
  状态是"已拍板、第2层需用户重选"，不是"待拍板"。静态裁剪已证伪、动态检索多一层失败点
- **收益维度**：token 成本 + 速度（工具选择准确率）

### M7 ❌ 已证伪（别重试）
- **一刀切复杂度预算**：Brooks/McCabe 阈值是经验法则非定律，已改目的追溯制
- **开局长短任务分类器**：AUC 0.599/R²=0.025 近随机
- **Qwen3-0.6B 当实时周围神经**：CPU 4.2~6.0s vs 要求 <10ms
- **区块链/zkVM/TSA 信任锚**：明说不建议（成本远超收益）

---

## 六、优先级总表（跨组合并，按"价值 × 可验证性"）

### 第一梯队：立即做（脚本/规则，低成本）
> **14:3x 审计后重排**：原 1/2/3/5（H6/H7/H8/H10）**已落地，移出待办**（见状态审计表）。

| # | 方向 | 收益维度 | 前置核实 |
|---|---|---|---|
| 1 | M3 NOT_INSTRUMENTED 三项埋点 | 可观测 | 已核实未做（baseline_metrics.py:57/66/83）|
| 2 | H4 补 `pathMissing` 设置点 | 可靠性 | 剧本已做，但结构化标志 index.mjs:85 只有判断处无设置点 |
| 3 | H4 web_fetch 入口真正移除 | token/速度 | cordis.patch.yml:368 仍 `fetch:true`，ADR-0028 要求改 false 未生效 |
| 4 | M9 审计成本核算（trace 已有） | 速度/决策 | 纯分析，零成本 |
| 5 | M8 变异测试 sentinel | 可靠性 | 可扩展 H9 判据体检，注入已知腐化确认门禁变红 |
| 6 | H14 edit 前锚点确认 | 质量/速度 | FS_EDIT_NOT_FOUND 占 33%，事前确认缺位 |

### 第二梯队：建基础设施（有复利）
| # | 方向 | 收益维度 |
|---|---|---|
| 7 | H2/M5 真实任务 A/B 流水线 + eval 基础设施 | 所有后续优化的验证效率 |
| 8 | M4 审计权锁定（冻结评判测试 hook） | 评测可信度 |
| 9 | H11 治理组件 leave-one-out 基线 | 可靠性（14:3x 已核实：audit 有 verdict 打点，leave-one-out 本身仍缺）|
| 10 | ~~H13 RRSI 正则化~~ **已落地**：hold-out 切分+噪声地板；剩剪枝/编辑预算退火未核实 | 质量 |

### 第三梯队：95% 实验验证（有具体设计）
| # | 方向 | 实验设计 |
|---|---|---|
| 11 | E1 `-tb` 独立线程数 | paired_ab n≥10，e2e 主判据 |
| 12 | E2 KV FP8 省显存 | 先 needle 质量门禁，再 95% e2e |
| 13 | ~~E3 MTP 头定向搬 GPU~~ **已关闭**（17:3x：收益噪声内+成本10倍+argv陷阱） | — |
| 14 | E4 cache 1350→1900 | 95% e2e + 显存监控 |
| 15 | H1 约束解码效果 A/B | 关掉 constrained 对比 n≥16（机制已落地，效果待证）|
| 16 | E5 share 1.0 vs 0 | n≥15 或先解决测量环境污染 |

### 阻塞项（必须先解决）
- **M1 测量环境污染**：WorkBuddy 自身 3494s CPU，prefill 431-1030 t/s 跳变。
  **所有 95% 实验的效力都受此影响**——ngram 第三轮就是因此 CI 跨 0。

## 七、平台 / 地基 / 测量（深挖组 C 结果）

### M8 ✅ 变异测试 sentinel（故意改坏一个行为，确认测试变红）
- **来源**：`FOUNDATION_GUARD_DESIGN_20261122.md` §二——"元测试：恒真→变异测试（Stryker/mutmut/PIT，阈值 50-60% 防回退）；
  朴素有效法：故意改坏一个行为，确认测试变红"
- **价值**：直接治本项目反复踩的"代码存在 + 单测过 ≠ 真实生效"坑（89% s1 假数据、守卫静默失效等）
- **现状核实（14:2x）**：地基守卫 INV-1~6 已有，但未见变异测试/sentinel 机制
- **审计复核（14:4x）**：子任务声称存在 sentinel 脚本，但全盘 `find *sentinel*/*mutant*` **无结果**——不采信，维持"未做"判定
- **可验证性**：脚本（注入已知腐化，确认对应门禁变红）——与 H9 判据体检同源，可扩展
- **收益维度**：可靠性（守卫本身的可信度）

### M9 ✅ 审计成本核算（trace 数据已有，10 分钟分析）
- **来源**：`PLATFORM_REPAIR_20261120.md` §五 ROI 第 1——"用 trace 数据做一次审计成本核算（审计占总时长多少、值不值）"
- **当前关联**：本次 ngram 实验发现 WorkBuddy 自身抢 CPU 导致 prefill 跳变；
  H12 长跑退化态下同步门控 +35% 总时长——**审计成本核算正是量化这个的**
- **可验证性**：纯分析（trace 已有），零成本
- **收益维度**：速度（找出最贵的守卫）+ 决策依据

### M10 ⚠️ 质量 error budget（SRE burn rate 思路）
- **来源**：`FOUNDATION_GUARD_DESIGN_20261122.md` §二——"SRE error budget（burn rate>2 停止发布）、canary+自动回滚、drift detection；代码质量 drift 无开箱工具必须自建"
- **判定**：思路可抄（质量预算超支时停止自动化变更），不需引框架
- **收益维度**：可靠性

### M11 ⚠️ 工具面证据不足（禁止据老数据拍板）
- **来源**：`CITATION_AND_EVIDENCE_GOVERNANCE_20261120.md` 附——"⚠️ 数据不足以拍板砍工具。8 个文件不是 8 个会话而是同一会话的累积快照；
  2849 次调用是重复计数；去重后只有 375 次唯一调用/11 种工具/单一任务"
- **判定**：这解释了为什么 M5/M6（工具面裁剪）一直待拍板——**证据本身是假的**
- **前置**：必须先有 H2 真实任务 A/B 流水线产生的干净数据，才能拍板工具面
- **收益维度**：避免据假数据做不可逆决策

### M12 ❌ 已证伪/不建议
- **消灭所有 junction**：登录态/工作区 junction 删除会丢状态或打乱会话分组（平台卷 §3.1）；仅 `.dsh` 可由 DSH_HOME 取代
- **通用低成本恒真断言检测器**：社区明确没有银弹（tsDetect 只覆盖少量静态模式）
- **PBT 属性测试**：对本 agent 场景成本偏高，中选而非优先

## 判定纪律（每次验证都要过）
1. 主判据 = 端到端 e2e 配对差值 95% CI；CI 不含 0 才显著
2. prefill 作协变量：同 pair 内两变体 pf 差异 >10% 标记受干扰
3. 实验条件必须匹配落地条件（ngram 第三轮的教训：生产有 min-hits=2，实验没加）
4. CI 跨 0 就是不显著，**不追加实验找显著**（防 p-hacking）
5. 生产验证走 dsh 真实会话，不用裸 20K HTTP（会触发 WDDM 冻死，既有问题）


---

## 八、提速方向实测（2026-11-25 17:2x）

用户问"比注入上下文更快、且高速同时高质量"。**先纠正前提**：`CTX_CHECKPOINTS=2` 让 BRIEF 这类
稳定前缀只 prefill 一次全程复用——继续压缩注入的边际收益≈0。真正成本在 decode / LLM治理 / 工具面稀释。

### 实测 1：确定性门禁 vs LLM 治理（速度 + 质量双维度）✅

| 维度 | 确定性门禁（已落地） | LLM 审计（项目实测记录） | 结论 |
|---|---|---|---|
| **速度** | **0.127s 中位**（n=10，含Python启动；均值0.135s/最大0.207s）| Critic 13-20s / D5 审计 10-20s | **快 100-150×** |
| **质量** | 变异测试 10/10：9条故意改坏全抓住+正例零误报 | 历史 Critic 54次调用 0% 成功（ms=0~1空返回，部分是单测伪造误报，v2.16已修）| 确定性路径判定可复现、无误报 |
| **可靠性** | fail-closed：改错即FAIL，且实测 `rulepack_guard` 拦住 agent 改评判规则 | 依赖模型状态/服务稳定 | 机制保证 > 概率保证 |

**结论**：这是"高速且高质量"最硬的实证——**确定性的事别交给 LLM**。
抓手：高信号守门（正则先过滤，送检率→10-20%）+ 判据体检（脚本）+ 硬值门禁（本次落地）。

### 实测 2：默认高频路径的 LLM 调用空间（负向结论，诚实记录）❌~⚠️

扫描 `index.mjs` 全部 6 类 `callLLM` 调用点：
- `callLLMVote`（K=5 次调用）——是贵，但**杠杆4默认关**，非高频路径
- Planner（`:1720`）——**每会话仅1次**，语义判断"验收项可验证吗"，脚本难替代
- Critic（`:1844`）/ Audit（`:1668`）——语义判断（找"没实现却宣称完成"），LLM 合理
- 高信号守门已做（正则先判），`patternLockTraceEnabled` 等已是零 LLM

**结论**：不牺牲质量的前提下，**默认路径没有低风险的"再减少一次LLM调用"机会**。
上一轮我说"减少LLM治理调用是最快单项"过于乐观——在默认路径上空间有限。
不硬凑改造，避免为速度牺牲语义判断质量。

### 实测 3：MTP 头搬 GPU 的显存前提（负向，硬约束）❌

- **余量口径纠错（17:3x）**：我原写"余466MiB"是用 8188−7722 算的，**口径错误**。
  nvidia-smi `memory.free` 字段实测 **235MiB**（连续稳定）——已在 450 安全线以下、贴近 186 必卡线。
  WDDM 下逐进程显存全 [N/A]，`memory.used` 含 CUDA context/对齐碎片，不能做精确 A/B 归因（ENGINE_OPT_DEEP:546）。
- **MTP 搬 GPU 需腾的是 ≥450MiB 净空闲**（搬464MiB专家后仍要留450），不是"差20/64MiB"；当前 235MiB 远不够
- 项目**已实测**此路：24.56→24.74 t/s（+0.7% 噪声内），成本远大于收益 → **❌ 关闭，不实测**
- `.env.llama:66` 注释"CTX=196608+缓存1536⇒余量750MiB"是 **192K 时代过时数据**，已备份后修正

**结论**：三条独立理由（收益噪声内/成本被低估10倍/argv顺序静默失效）任一足够关闭此路。
**元教训**：我自己也犯了"没核实字段口径就算余量"的错——正是刚写进 BRIEF 的"别只信关键词/声称"铁律的又一次应验。

### 总判定
真正可复制的提速模式 = **高信号守门 + 确定性门禁**（已验证 100-150× 且质量更稳）。
decode/LLM 语义判断不宜再压（有质量底线）；显存路已到硬约束。
继续优化的下一步应是工具面收敛（需干净数据先），而非再压注入或硬改引擎。


---

## 九、参数词表化调研（2026-11-25 17:3x，用户提议）

**用户想法**："把 es.exe 全盘文件列表做成词表，让工具参数（尤其长路径）变成一个 token，降低填错风险。"

### 目标对，手段错：先纠正靶子
参数错误分布（PIPELINE 卷 §三，54 次失败）：
- `FS_EDIT_NOT_FOUND` **18 次(33%)**：`old_string` 内容锚点失配（拿旧内容当锚点）——**路径词表对此无效**
- `FS_NOT_FOUND` **16 次(30%)**：猜路径（如 `D://publish//...` 少 `Brain`）——**这是词表想解决的**
即：即使做成单 token，只能覆盖 30% 的错误，且没覆盖更大的 33%。

### 路径 A：动态扩展 tokenizer 词表 → ❌ 不可行
- 正确名词：vocabulary extension + `resize_token_embeddings` + **continued pretraining**
- 要同时改 tokenizer merge 表、embedding 行、LM head 行、vocab_size、GGUF tensor shape
- 新 token 必须训练才"长出语义"：业界公开案例是 600B+400B tokens 训练量
- 本项目：不能重训、显存仅 235MiB、GGUF 固定 → **直接排除**
- 关键论证：未训练的新 token logits 是随机的，模型不会自发选中正确路径——选对也是碰运气；若靠 grammar 强制，词表扩展就是多余复杂度

### 路径 B：grammar 枚举候选 → ⚠️ 方向对但三重硬墙
- 机制：llama.cpp GBNF 把输出锁定在候选内（`json-schema-to-grammar.cpp:960-964` enum 编译成 choice 交替）
- **墙1 基数墙**：OpenAI enum ≤1000、Gemini ≈120 就失败、Anthropic 180s 编译超时≈几百值；es.exe 实测索引 **1,678,947 条**，差 2-3 个数量级
- **墙2 词表放大税**：同族模型 Qwen3-30B-A3B(151,936词表)实测 GBNF 200token 输出 6.7s→7.9s(**+18%**)；路径 string 正落在"开放字符串"最坏情况（全词表线性扫描）
- **墙3 决定性**：`D:/llama-master-src/tools/server/server-common.cpp:1619-1623`——
  `if (!inputs.tools.empty() && tool_choice != NONE) { if (body.contains("grammar")) throw "Cannot use custom grammar constraints with tools." }`
  **走 tools API 时根本不能传自定义 grammar**。dsh 工具调用正是 autoparser 吃 tools schema（项目有两行补丁修 `chat-auto-parser-generator.cpp`）→ 子任务推荐的"请求级 grammar 锁 Top-N"在当前路径上不可用
- 补充：`preserved_tokens` 只保护已存在的单 token（`sampling.cpp:1067 ids.size()==1`），不能新增词表

### 路径 C：让模型检索真实路径，而非生成路径 → ✅ 业界主流
- DSH 生态已有插件（`@zhourenke/dsh-tool-everything`、`fishdivinity/dsh-local-search`、`dsh-at-file-everything`）：
  暴露 `search_files({query, max_results})`，模型查出**真实路径字符串**再用，不在模型层生成路径
- 项目已有雏形：短路径别名 `p/ bench/ memory/`（config/AGENTS.md:117/141）+ es.exe 搜索指令
- es.exe 实测可用：`D:/Everything/es.exe`，索引 1,678,947 条，`es.exe -n 3 "index.mjs"` 秒级返回
- ⚠ 注意：项目 `episodicSearchEnabled`(index.mjs:208/2450) 是**历史经验检索**（trace/日志），与"全盘文件索引"是两回事，别混用

### 推荐方案（按 ROI）
1. ✅ **立即可做：edit 前强制 read**（治 33% 的 old_string 锚点失配）——本就是 backlog H14，比词表方案收益大
2. ✅ **低成本：路径白名单预注入**（治 30% 的猜路径）——把当前任务涉及的高频真实路径（≤几十条）由 harness 在工具结果里返回，模型引用而非猜测；复用现有短路径机制，零 grammar 成本
3. ⚠ **中成本：加 `search_files` 工具走 es.exe**——模型先检索拿真实路径；但工具面已 28 个，增一个要先过工具面收敛决策（M6）
4. ❌ **不做：百万级 grammar 枚举 / 词表扩展 / 重编 llguidance**——收益被三重墙吃掉

### 元结论
用户的直觉（"把生成变成选择"）是对的，但实现层选错了：**不是在模型层塞词表，而是在工具层给真实候选**。
这也符合项目第一性原理——规则驱动、确定性优先，不押注模型生成能力。


---

## 十、可外包确定性工作调研 + S24-ctx 接线（2026-11-25 17:5x）

**用户问**："还有什么确定的东西可以外包？"（把确定工作从模型转给机制）

### 判据（业界共识 + 项目铁律）
一句话：**"能写 if/else 保证每次正确的，就不该待在模型上下文里"**。
但三条红线：①语义判断不外包；②schema 只锁形状不锁真值（validity≠correctness）；
③不用模型自评当守卫（循环论证）。

### 扫描结论：项目已基本外包完，只剩 2 项
权威源 index.mjs 2821 行逐段扫（子任务+我交叉核实）：

| 类别 | 状态 | 证据 |
|---|---|---|
| 约束解码 / JSON解析重试 | ✅已做 | `index.mjs:284,1568-1574,1600-1614,1632-1637` |
| 硬值门禁 / 高信号守门 / 注入扫描 | ✅已做 | config_check + `index.mjs:1304-1332,2201-2222` |
| 配置/路径从环境读 | ✅已做 | `index.mjs:105-114` resolvePathEnv + `:990-993` probe |
| 固定文本模板化（安全提示/收尾/状态板/todo回灌） | ✅已做 | `index.mjs:258-259,2099-2103,2323-2351` |
| 计数/查表/规则信号（D1/D2/D3/FSM/CritBank） | ✅已做 | 全零 LLM，`:1114-1148,1478-1492,2492-2533` |
| 工具参数 JSON.parse | ✅已做 | `:845,1185,1210,1279,1378` 脚本做，模型不参与 |
| **S24 healHint 的 ctx** | ❌**缺口→本次接线** | 设计支持 `fileContent`/`nearFiles`（`tools/tool_failure_healer.mjs:35,48-59`），
  但调用点传 `{}`（`index.mjs:2358`）——33% 锚点失配 + 30% 猜路径仍靠模型自己重读 |
| **`pathMissing` 设置点** | ⚠️仍缺 | `index.mjs:85-88` 有判断无设置；但与 S24 的 FS_NOT_FOUND 分支功能重叠，须先去重再接线 |

**负向结论**：Planner/Critic/Audit/Vote/Corrector 都是语义判断，不外包（延续第八节实测2）。

### 本次落地：S24-ctx 接线
- 新增 `buildHealCtx(failure)`（`index.mjs`，在 `executeReadOnly` 之后）：
  - `FS_EDIT_NOT_FOUND` → 用 `executeReadOnly({tool:'read'})` 取真实文件内容（带 allowedRoots 安全边界、2MB 限制、executorMaxChars 截断）
  - `FS_NOT_FOUND` → 取父目录单层列表，按文件名前缀匹配给 nearFiles
  - 铁律遵守：失败静默、不改检测逻辑、不改变自愈提示本身
- 调用点 `index.mjs:2358` 从 `healHint(f, {})` 改为 `healHint(f, buildHealCtx(f))`
- 同步权威源→运行版（INV-3 曾正确拦住未同步，复制后 sha 一致 ecadc2fc）

**实测（诚实标注证据等级）**：
- ✅ L2 单测：链路两端通过——真实文件 800 字 clip 回灌进 hint、含"直接从中复制锚点"；
  相近文件 ROADMAP_GRAPH.md 正确回灌
- ✅ 门禁：INV-3 PASS、8/8 invariants HEALTHY、82/0、node --check 语法通过
- ⚠️ **L4 真实会话证据待补**：dsh 未重启，新代码未在运行进程生效；且需要模型真的犯 edit 错误才触发。
  按项目铁律"机制生效≠有效"，**不宣称已提升成功率**——待下次真实会话观察
  `tool_failure_heal` trace 的 hint 是否带 fileContent/nearFiles，再测锚点失败率是否下降。

### 业界调研：5 类常见遗漏（本项目对照）
1. **时间/新鲜度真源**：`requireFreshMtime: false`（`index.mjs:883`）关掉了 mtime 硬校验，
   而 `fileState()` 的新鲜度判定已写（`:808-813`）——低垂果实但开前需验证不误报
2. **覆盖度而非合法性**：D1 只管重复探测，不检查"期望集合 vs 实际集合的差集"
3. **状态转移硬门禁**：stateBoard 偏提醒，未把"未 PASS 不得交付"变成结构化硬转移
4. **可 replay 判定账本**：steer 拦截缺"输入快照+规则ID+规则版本+结论"结构化记录，守卫本身无法回归测试
5. **运行时 exact 缓存**：benchmark 有 cache，harness 运行时对确定性子任务缺幂等去重

### 判定
"还能外包什么"的答案：**大部分已外包完，剩余不是加守卫层数，而是把已写机制接上线**（S24-ctx 是第一个）。
下一步优先级：真实会话补 L4 证据 > pathMissing 去重接线 > requireFreshMtime 验证 > 判定账本。


---

## 十一、已写机制全量启用审计（2026-11-25 18:3x）

**用户要求**："把所有已写机制打开并验证，要实测。"

### 盘点：4 个默认关的开关 + 1 个写了没接线的

| 机制 | 位置 | 决定 | 依据（实测/反证） |
|---|---|---|---|
| **requireFreshMtime** | `index.mjs:883` | ✅**已打开** | fileState 判定 5/5、claim 误报边界 6/6、L1 正负例实测通过 |
| adaptiveThinkEnabled | `index.mjs:218` | ❌**不打开** | **已有反证**：CHANGELOG.md:367-368 off=189s/4172tok vs on=301s/4168tok——
  token 未降、耗时 +59%；CAPABILITY_LADDER X11 已 rejected。开它违背 DoD |
| specThresholdByTaskEnabled | `index.mjs:272` | ❌**不打开** | 只有单测（test_short_term_goals.mjs:62-84），**无端到端证据**；
  项目铁律"端到端验证才落地"。且引入新误报风险（creative@0.55 不触发审计的边界未实测） |
| voteOnCritic | `index.mjs:297` | ❌**不打开** | K=5 → LLM 成本 ×5；多 judge 已证伪（9 judge≈2 票）；项目已有"投票默认关"决策 |
| pathMissing 设置点 | `index.mjs:85-88` | ❌**不补线** | 与 S24 的 FS_NOT_FOUND 分支功能重叠；S24 已接真实相近路径回灌（第十节），
  补 pathMissing 会叠两条提示——先去重再考虑，不是简单"打开" |

### requireFreshMtime 打开实测（三层证据）

1. **判定函数正确性** 5/5：文件不存在→false、无since→false、刚写完→true、旧文件→false、边界→true
2. **claim 误报边界** 6/6："已写入/保存到"→匹配；"读取了/文件在/修改了config"→不匹配。
   注意 `FUTURE_CLAIM`（"接下来要写"）会匹配——这是既有行为，非本次开关引入
3. **L1 拦截正负例**：本轮真实写入 → `fresh:true` → 放行；since 在未来（本轮没写）→ `fresh:false` → 拦截

### 同步与门禁
- 改权威源后 INV-3 立即 FAIL（`authority=1ccf57ff runtime=旧`）——**三副本门禁再次正确拦住未同步**
- 复制到运行版后 sha 一致（1ccf57ff），8/8 invariants HEALTHY，82/0，config 一致

### 诚实结论
"全部打开"不等于"全开"——2 个开关有明确反证或证据不足，1 个会引入双重提示。
**有根据的拒绝与有根据的打开同样重要**：这是项目"不硬凑成果"纪律的体现。
本轮真正启用 1 个（requireFreshMtime），累计启用 2 个（上轮 S24-ctx + 本轮 mtime）。

### 证据等级声明
- ✅ L2 单测 + 门禁：全部通过
- ⚠️ L4 真实会话：**两处新增机制（S24-ctx / requireFreshMtime）均未完成真实会话验证**——
  dsh 未重启、需模型真的触发错误/假完成。按"机制生效≠有效"铁律，
  **不宣称成功率已提升**，待下次真实会话观察 trace 证据。


---

## 十二、外部跟进调研：Strata 0.2.21 + Marco-Mini-Instruct（2026-11-25 18:4x）

### A. Strata 0.2.21（2026-11-24 发布，GitHub Niko1221/Strata，48k★/MIT）

**0.2.21 关键变化（官方 release notes 一手）**：
- **Agent sessions reuse prompt on every backend**——长 agent 会话不再每轮重读整个 prompt
- **单请求路由到 drafter 所在 slot**：RTX5090 Laptop 2-3 slots 下 agent 会话 85→142-152 tok/s、chat 87→120
- **启动时短测试自动决定 drafter 是否开启**（首次启动 +3 分钟）
- Inkling 2 Mini 性能暴涨（3060Ti 8GB SQ-10: 11→43 tok/s；5090 prompt 3923→6967 tok/s）
- 长 prompt + 多 slot 陷阱：3K+ token @32 slots 首 token 等数分钟；≤24GB 卡 64K@32slot 可能加载失败
- 已知回退：RX7900 XT SQ-20 decode -7%（workaround `--vram-experts-gb 13.2 --ram-experts-gb 2.5`）

**⚠️ 最关键的判断：核心优化我们已具备，不用换引擎**
- Strata 的"agent prompt 复用"对应 llama.cpp **PR #30137**（reference-counted checkpoints 替代 deep-copy）
- **该 PR 已于 2026-11-05 合并进 master**（WebFetch 核实）
- **项目源码 94f3af3 已包含**：`server-context.cpp:2822` `std::list<std::shared_ptr<common_prompt_checkpoint>> checkpoints`、
  `server-slot-sched.h:18/25` `shared_ptr<const common_prompt_checkpoint>`
- 上游实测收益：cache update -52.6%~76.4%、首 token -34.7%~60.5%、峰值内存 -12%~33%
- 项目已有 `CTX_CHECKPOINTS=2`（承重墙，降到1慢23%）——机制在，只是没量化过 PR 的实际增益

**可借鉴（思路级，不需换引擎）**：
1. ⭐ **drafter 启动时自测再决定开关**：当前项目 MTP draft 恒开（nmax=3）；
   Strata 的"启动短测试决定 drafter 是否值得开"可避免弱硬件上 draft 反而拖慢——
   但项目已有 D5 MTP 接受率<0.65 审计门控（`specAcceptanceMin`），方向类似，只是是运行时而非启动时
2. ⭐ **单请求 pin 到 drafter slot**：项目 router `--models-max 1`，本来就是单 slot，这条天然满足
3. ⭐ **长 prompt 少 slot**：项目已 `models-max 1`，与 Strata 的 8GB/长文档建议一致

**不适用/别跟进**：
- ❌ **换 Strata 引擎（子任务深查纠正）**：**Strata 从 0.2.16 起已完全脱离 llama.cpp**——
  官方 release notes 原文 "Strata is no longer built on llama.cpp. It still uses GGUF files and supports the same features,
  but none of the llama.cpp matrix kernels remain"，其 source tree 无 `ggml/`/`llama.cpp` 的 matrix kernels 目录。
  虽然 `strata-engine` 仍有自己的 0.1.67 版本号，但**不是 llama.cpp 的 fork**，无 cherry-pick 路径。
  项目自编 b12244 含 autoparser 2 行补丁 + MTP/共享/FA 定制 + harness 深度集成；换引擎要重做全部补丁与集成，成本远超收益
- ❌ **Inkling 2 Mini 当主力**：26.4B 总参、20GB checkpoint，8G 卡放不下；
  且官方自承短板"agentic reliability 弱于大模型、可能未经确认删改文件、中文有截断与混语"——正撞项目痛点

### B. Marco-Mini-Instruct（注意拼写：Marco 非 macro；阿里 AIDC-AI，Apache 2.0）

**身份**：Qwen3-0.6B-Base 经细粒度切分+Drop-Upcycling 升级的多语言 MoE instruct；
17.3B 总参 / 0.86B 激活(5%) / 256 专家取 8 / 28 层 / 29 语言；arXiv:2604.25578。

**官方表现（Avg@8）**：
- English 7 项平均 **75.5** > Qwen3-4B 73.3 > Gemma3-12B 65.8（MMLU 83.4、GSM8K 93.1）
- Multilingual General **50.8** > Qwen3-4B 47.9（长尾语言优势明显）
- Cultural & Regional **71.0** > Qwen3-4B 69.1
- **诚实边界**：中文 CMMLU/C-Eval、希腊/阿拉伯语、翻译 BLEU 弱于对照；GPQA-D/MATH 略输 Qwen3-4B。
  优势在**低资源长尾语言**，不是全面最强

**对本项目：❌ 不引入**
- **显存硬冲突**：0.86B 激活≠0.86B 显存——需加载全部 17.3B 权重；最低 Q2_K 量化仍 6.5GB，
  无法与 35B 主模型在 8G 卡共存（当前余量仅 235MiB）
- **延迟数量级差距**：MoE 5% 激活只省 FLOPs，不省权重带宽与 256 专家路由开销。
  项目已证伪"0.6B 做实时守卫需 4-6s vs 要求 <10ms"——换 Marco 只会更慢
- **场景错配**：卖点是多语言/长尾语言知识，不是分类/守卫/高速路由
- **方法可借鉴但不可复用**：0.6B→MoE+级联蒸馏做到接近 4B dense，但需 SFT 24h/64GPU + OPD 110h/64GPU
- **巧合澄清**：项目"小模型 critic 50.9%≈随机"与 Marco-Mini-Base 多语言均分 50.9 数值相同但**完全无关**

### 总结
- **Strata**：值得跟的不是它的引擎，而是"prompt 复用"这个方向——**我们已经有了**（PR #30137 已在源码）。
  这条避免了代价极高的引擎迁移。真正可做的是量化 CTX_CHECKPOINTS 的实际增益（待 95% 实验）
- **Marco-Mini-Instruct**：表现确实不错（同规模 SOTA），但与本项目 8G 显存 + 实时守卫场景根本不匹配
- **术语边界澄清（子任务纠正）**：`--vram-experts-gb` / `--ram-experts-gb` 是 Strata 独有的手动显存分区旋钮
  （RX7900 回退 workaround），**llama.cpp/我们无法照搬**（项目用 `--cpu-moe` 全 host）。
  "ClassLRU" 是**项目自己的术语**（llama.cpp PR #31233，本机 94f3af3 已含；`LEVERS:772`），
  Strata 官方用的词是 profile 排名 + decayed-count——两者不是同一机制，别混
- 两条都遵循同一判据：**不看榜单看约束**（显存/延迟/集成成本）


---

## 十三、dsh v0.2.2-rc.5 跟进评估（2026-11-25 19:0x）

**用户问**："看看 dsh 的 rc5 有什么值得跟进的地方"
**本地版本**：0.2.2-rc.3（CHANGELOG.md:884，11-18 已升级验证过）

### 一手证据：rc.3→rc.5 全部 commit（GitHub compare）

| 区间 | commit 数 | 实质变化 | 与本地 llama 项目相关？ |
|---|---|---|---|
| rc.3→rc.4 | 9 | ①`llm-deepseek` content safety check开关+强制 high+CONTENT_REFUSED（3+2 commits）
  ②`liveshare` 测试时钟硬编码修复（2）
  ③`liveshare` tunnel worker 在 Host Electron Node 模式启动修复（1）| ❌ 全是 DeepSeek 云 API + liveshare，本地模型无关 |
| rc.4→rc.5 | 4 | ①`feat(web): default DeepSeek model conversations to Messages search`（搜索路由：DeepSeek 模型走服务端搜索不按次收费，其他模型默认 DeepSeek Search API）
  ②liveshare 测试时钟修复的 cherry-pick | ❌ 只对 DeepSeek 云模型有效；项目用本地 llama + SearXNG，不用 DeepSeek 搜索 |

**官方 changelog（deepseekdsh.com/changelog）只列 rc.5 一项**：DeepSeek 模型服务端搜索免按次收费——
正是二手新闻标题里"搜索省一笔"的来源。

### 判断：❌ 不升级（零功能价值，纯回归风险）

1. **rc.3→rc.5 没有任何本地模型 / 插件契约 / sessionController / slot 契约 / cordis / approval 机制的变更**
   （逐 commit 核实，不是关键词计数）
2. 项目深度定制：cordis.patch.yml（禁 tool-jobs/tool-web fetch/llama provider/bundles）、
   dsh-session-bridge（sessionController API）、dsh-approval-delegate、三副本一致性、82 门禁——
   升级要全量重跑，收益为零
3. 搜索计费变化**只对 DeepSeek 云模型有效**；项目用本地 llama + 本地 SearXNG（`web_fetch→web_search` 映射，index.mjs:385）

### 需要澄清的历史包袱
- CHANGELOG.md:927 记的"rc.2→rc.3 等用户手动升级"已完成（:884 确认 rc.3 全量验证通过）——本次不是遗留待办
- 0.2.1-rc.5（10-29）曾改 thinking block 渲染 + Slot 契约（reasoning-text.ts / slots.ts），
  **那是 0.2.1 线，与 0.2.2-rc.3→rc.5 无关**，别混

### 何时才值得升级
- dsh GA（0.2.2 正式版）出来后重新评估——rc 线预发布，接口可能微调
- 或出现明确命中本项目的修复（sessionController API 变更 / 本地 provider 支持 / tool-call bug 修复）

### 元结论
又一次"不看标题看 diff"：rc.5 的标题（搜索免收费）对用本地模型的项目毫无意义。
逐 commit 核实比读 release notes 更可靠。


---

## 十三、dsh v0.2.2-rc.5 跟进评估（2026-11-25 19:0x）

**用户问**："看看 dsh 的 rc5 有什么值得跟进的地方"
**本地版本**：0.2.2-rc.3（CHANGELOG.md:884，11-18 已升级验证过）

### 一手证据：rc.3→rc.5 全部 commit（GitHub compare）

| 区间 | commit 数 | 实质变化 | 与本地 llama 项目相关？ |
|---|---|---|---|
| rc.3→rc.4 | 9 | ①`llm-deepseek` content safety check开关+强制 high+CONTENT_REFUSED（3+2 commits）
  ②`liveshare` 测试时钟硬编码修复（2）
  ③`liveshare` tunnel worker 在 Host Electron Node 模式启动修复（1）| ❌ 全是 DeepSeek 云 API + liveshare，本地模型无关 |
| rc.4→rc.5 | 4 | ①`feat(web): default DeepSeek model conversations to Messages search`（搜索路由：DeepSeek 模型走服务端搜索不按次收费，其他模型默认 DeepSeek Search API）
  ②liveshare 测试时钟修复的 cherry-pick | ❌ 只对 DeepSeek 云模型有效；项目用本地 llama + SearXNG，不用 DeepSeek 搜索 |

**官方 changelog（deepseekdsh.com/changelog）只列 rc.5 一项**：DeepSeek 模型服务端搜索免按次收费——
正是二手新闻标题里"搜索省一笔"的来源。

### 判断：❌ 不升级（零功能价值，纯回归风险）

1. **rc.3→rc.5 没有任何本地模型 / 插件契约 / sessionController / slot 契约 / cordis / approval 机制的变更**
   （逐 commit 核实，不是关键词计数）
2. 项目深度定制：cordis.patch.yml（禁 tool-jobs/tool-web fetch/llama provider/bundles）、
   dsh-session-bridge（sessionController API）、dsh-approval-delegate、三副本一致性、82 门禁——
   升级要全量重跑，收益为零
3. 搜索计费变化**只对 DeepSeek 云模型有效**；项目用本地 llama + 本地 SearXNG（`web_fetch→web_search` 映射，index.mjs:385）

### 需要澄清的历史包袱
- CHANGELOG.md:927 记的"rc.2→rc.3 等用户手动升级"已完成（:884 确认 rc.3 全量验证通过）——本次不是遗留待办
- 0.2.1-rc.5（10-29）曾改 thinking block 渲染 + Slot 契约（reasoning-text.ts / slots.ts），
  **那是 0.2.1 线，与 0.2.2-rc.3→rc.5 无关**，别混

### 何时才值得升级
- dsh GA（0.2.2 正式版）出来后重新评估——rc 线预发布，接口可能微调
- 或出现明确命中本项目的修复（sessionController API 变更 / 本地 provider 支持 / tool-call bug 修复）

### 元结论
又一次"不看标题看 diff"：rc.5 的标题（搜索免收费）对用本地模型的项目毫无意义。
逐 commit 核实比读 release notes 更可靠。
