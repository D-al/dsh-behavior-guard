# Changelog

所有迭代以本地时间记录（UTC+8）。格式参考 Keep a Changelog。

## [1.1.2] - 2026-11-18 00:40

### Added（present 前确定性深检，~0.3s / 0 LLM）
- **Python 顶层 import 可解析性**：AST 收集 import → `importlib.util.find_spec` 检查
  （**不执行模块**，安全）——语法通过但依赖缺失的产物在这里被拦
- **占位符扫描**：TODO/FIXME/XXX、`pass` 空实现、文档"待补充/占位"
- **空文件/极短文件**（<10 字节）
- **shell 脚本语法**（bash -n）
- **Markdown 无标题结构**
- 走 Critic 之前的独立确定性路径：发现问题直接 steer（不经 LLM，零延迟成本）

### Tests
- 18/18（新增：缺失 import 拦截 / 占位符拦截）

## [1.1.1] - 2026-11-18 01:00

### Added（verify-on-edit：确定性语法检查，0 LLM 成本）
- 每次 write/edit 成功后对 .py/.json/.yml(yaml) 做**确定性语法检查**（py_compile / JSON.parse /
  yaml.safe_load），发现错误立即注入"修好再继续"。
- 依据：**Qwen3.5-35B scaffold 实验**（r/LocalLLaMA, 288 upvotes）——verify-on-edit 让
  SWE-bench Verified Hard **22.2% → 37.8%（+15.6pp）**；9B 换 scaffold 19.11%→45.56%。
  tech4talk："确定性的修复应该在 LLM 推理循环之外"。
- 成本：每文件 ~80-150ms 进程调用，0 token、0 LLM 调用——**这是当前性价比最高的质量杠杆**。
- 跳过 cordis*.yml（dsh 的 !!js 扩展会让标准 yaml 解析误报）。

### Tests
- 26/26 + 16/16 + 模块加载 OK

## [1.1.0] - 2026-11-18 00:45

### Added（P1 Critic + P2 Planner 检查，角色架构完整化）
- **Critic（产物质量评审）**：present 前触发，只读产物文件（≤3000 字），按**异质 rubric**
  四维度（达标性/完整性/可用性/一致性）输出 ACCEPT/REJECT/UNCERTAIN。
  REJECT → steer 带"最关键修正动作"；ACCEPT → 放行（等价独立验收，不再触发 D4 闸门）；
  UNCERTAIN → 回退 D4。每会话 ≤2 次、超时 90s。
  依据：四角色标准（Planner/Executor/Critic/Verifier）；Apple 2026——异质 rubric 才有独立信号。
- **Planner 检查（P2）**：首次出现 [VERIFY] 项时，验"验收标准是否可验证"
  （可执行判据 vs 感受性描述），不可验证则注入改写要求。每会话 1 次。
  依据：verify-gate 的 criteria-at-birth；spec-driven——一次成功 vs 四轮修正的差别来自 spec 精确度。

### 运行期成本（本机 800 t/s prefill / 27 t/s decode）
- Critic：10-20s × 1-2 次/会话 = +15~40s（+3~8%）
- Planner：~11s × 1 次/任务 = +2%
- 合计 P1+P2 全开：+5~10% 会话时长；净收益为正（省 2-3 轮返工 60~180s/任务）

### Tests
- 26/26 + 16/16；AGENTS.md 重整为四段结构（铁律/开工/做工/收工）3873 token（<4096）

## [1.0.9] - 2026-11-18 00:30

### Changed（P0 角色架构：零成本 schema 化）
- 审计员输出纪律：`issue` 必须以 `stepN:` 开头（引用具体步骤）；`fix` 只允许**一个可执行动作**
  （动词开头、不含"或者/二选一"多选建议）——执行者照做即可，消除模糊判定
- 配套：AGENTS.md 执行合同（开工前 3 行 spec）+ 决策理由写进 todo 条目

## [1.0.8] - 2026-11-18 00:15

### Changed（零成本 prompt 优化）
- **Few-shot 实例**（Stanford/Google：few-shot 使输出变异性 -52%；关键示例放最后对抗 recency bias）：
  审计 prompt 加入 3 个实例——ISSUE（重复失败）/ UNCERTAIN（证据不足）/ OK，
  UNCERTAIN 实例放在最后（最需要抑制的错误模式）
- **否定句改正例表述**：纠正器 prompt 的"禁止编造参数名/不要拼路径"改为
  "args 照抄证据里的调用格式"/"路径原样复制证据文本里的那一段"（正例约束 > 否定句）

## [1.0.7] - 2026-11-18 00:05

### Added（Agent-as-Judge 定向取证 + 零成本 prompt 优化）
- **审计员可主动取证**：审计员输出 `{"verdict":"NEED_EVIDENCE","tool":"glob 或 read","args":{...}}`
  → 插件确定性代执行（只读白名单 + allowedRoots 安全边界）→ 证据回喂 → 共最多 2 轮
  （`auditEvidenceRounds`），轮次用尽自动转弃权（不介入）。
  依据：Agent-as-a-Judge（arXiv 2410.10934）；生产实践要求"证据预算/动作预算/早停/说不确定"。
  成本：每轮 +1 次 LLM（5-15s）+ 1 次工具（0.1-2s），仅在 D5 门控触发时发生。
- **Post-Reasoning 指令**（arXiv 2605.06165，NTU 2025：117 个模型-任务组合 88% 有效、零成本）：
  审计 prompt 加"先给判定结论，不要逐条罗列分析过程"——收紧判定首 token 的分布。

### Note
- 审计员的工具能力**严格只读**（read/glob + 安全边界），不给写权限——写是执行者职责
- 取证仅限 NEED_EVIDENCE 轮次内，单轮单次调用，轮次上限硬编码 2

## [1.0.6] - 2026-11-17 23:55

### Added（MTP 信心信号 —— 阶段 1，零改动落地）
- **读 llama-server 日志的 `draft acceptance` 作为 MTP 信心信号**：llama-server 每次请求
  都会打印 `draft acceptance = 0.89 (X accepted / Y generated)`——MTP draft 头与主模型的一致率。
  **低接受率 = 模型在犹豫/漂移（不确定）**，与 SU（arXiv 2609.05274）的 draft cross-likelihood
  同源，只是聚合到请求级。每次读取只扫日志尾部 16KB，**零额外推理、零显存**（<0.01ms/次）。
- D5 审计门控新增第 5 信号：`draft acceptance < 0.65` → `low-draft-acceptance` 触发审计。
  基线：正常会话 0.84~0.95（实测 78 条记录），<0.65 为显著异常。
- 这是"多审计员"的正确替代方向：**信号源多样性（MTP/重复/交付/压缩）>> judge 数量多样性**
  （Apple 2026-06《Nine Judges, Two Effective Votes》：9 个 LLM judge ≈ 2 个独立投票，
  同家族错误高度相关；JudgePanel 2608.29168 用 1 个 compact judge 蒸馏 panel 能力）。

### Note
- 阶段 2（per-token surprisal 需改 llama-server C++ 输出）经评估**不做**：门控是"每步决策"，
  请求级聚合信号（接受率）已足够；per-token 只在 postmortem 诊断"哪个 token 开始崩"时才有价值。

## [1.0.5] - 2026-11-17 23:45

### Added（审计员完善：校准闭环 + 盲点补齐 + 弃权通道）
- **审计员自校准闭环**：每次审计干预写入 `_audit_feedback.jsonl`（gate 类型/step/时间），
  3 步后自动结算"注入后是否有新失败"（有效/无效）→ `auditor_metrics.py` 按门控统计有效率，
  有效率 <50% 的门控提示收紧——回答"谁审计审计员"（Agnost AI 校准方法论：per-type precision/recall）
- **审计 prompt 加 D 类检查（遗漏/omission）**：SLEIGHT-Bench（Anthropic Fellows 2026-05）
  实测 omission 是 per-step 检查最弱处（40 条规避轨迹中 omission/N-hops/jailbreak 类 0% 检出）
- **弃权通道（UNCERTAIN）**：证据不足时审计员输出"不可确定"而不是被迫给 OK/ISSUE
  （AGNOST 原则：必须保留 insufficient-evidence 输出；也不放行——held-out gate 原则）

### Fixed
- **纠正器路径规则修正**（猜路径实证）：从"改写为短相对路径"改为"只能原样取自证据文本，
  不得推断/改写；没有就 ask_user/abandon"——此前该规则诱导纠正器拼出不存在的路径
  （memory/dsh-session-trash-bin/package.json），注入后成为干扰源

### Tests
- 26/26（turn-guard）+ 14/14（new_guards）

## [1.0.4] - 2026-11-17 23:35

### Added
- **CritBank 经验检索（检索式上下文注入）**：结构化失效教训库（critbank.json，9 条），
  审计门控触发时按轨迹特征（工具名/错误文本）关键词匹配，注入最相关 1~2 条教训——
  零 LLM 成本。解决"AGENTS.md 4K 只能静态放 9 条、放不下更多教训"的容量问题。
  依据：U-Fold（2026）的检索式工作上下文——不让全部历史常驻窗口，按需取相关行。
- present-gate 文案强化：验收标准要求引用 todo 清单里的 [VERIFY] 项逐条对照
  （verify-gate 的 "criteria at birth" 原则——验收标准在任务创建时就定义）

### Tests
- test_new_guards 14/14（新增 CritBank 解析与命中用例）

## [1.0.3] - 2026-11-17 23:20

### Changed（审计架构：周期 → 风险门控）
- **D5 审计门控（SAG gated critique）**：从"每 8 步固定审计"改为风险信号触发——
  (a) 轨迹连续失败≥2；(b) 连续 ≥6 步无生产性调用（无 write/edit/todo）；
  (c) present 已调用（交付前=风险最高点）；(d) 刚经历压缩（状态重建高危期）。
  确定性信号 D1/D2/D3 仍每步零成本检查，不变。
- 依据：SAG（SKKU/Soongsil, arXiv 2026-10）——gated critique 算力 **-66%**、任务成功率 **3 倍**；
  "precision intervention > constant supervision"。中文社区实践同结论（步骤级反思=每步多一次调用，
  10 步任务 20 次调用，只在刀刃上开）。

### Fixed（实证驱动的纠正器修复）
- **代执行失败时的注入不再包含纠正器猜测的路径**：真实会话里注入了"目标不存在：
  memory/dsh-session-trash-bin/package.json"（纠正器猜的路径不存在），该失败信息成为干扰源，
  模型随后反而进入重问循环。现在只给方向性指引（换方法核实目标），不把未验证的猜测写进上下文。

### Tests
- test_new_guards 12/12（新增 D5 门控两用例：正常推进 10 步零审计 / 连续失败触发）

## [1.0.2] - 2026-11-17 23:10

### Added
- **D4 present-gate（verify-gated completion）**：present 声明交付时，本轮若无独立验收痕迹
  （spawn 验收者 / 跑过 verify_agent.py）→ turn-stopping steer"做的人不能自己签字"。
  每轮 1 次、每会话 2 次预算；有验收痕迹则放行。
- 依据：IOV Labs 896 任务实测（小模型虚假完成 ~13%；自检仅 12.7%→11.8%，同一盲区）；
  verify-gate 开源实现（状态机 + 硬拒自签）；Claude Code /goal（独立 evaluator）；
  held-out gate 原则（Inconclusive 不放行）
- 离线测试 10/10（含"有 spawn 不 steer""跑过 verify_agent 不 steer""无 present 不 steer"）
- 补齐 sharedMaxPerTurn 到 DEFAULTS（此前仅使用未定义——预算实际未生效）

## [1.0.1] - 2026-11-17 21:45

### Added
- 详细 README：问题演进史（7 个实测失效现场）、途径、论文对照表、信号清单与实测结果、解决程度
- 版本戳与 tag（v1.0.1-20261117-2145）

### Fixed
- 首推 GitHub 时 `index.mjs` 缺失（构建产物复制被环境拦截未察觉）——从迁移备份补齐后重新推送（fcd3e6f）

### Security/Reliability
- 本仓库曾被 `pnpm update` 以旧版覆盖过一次（本地新版未先推送）——已确立纪律：**本地维护的插件必须先推 GitHub 再 pnpm update**

## [1.0.0] - 2026-11-17 19:58

### Added（首推 GitHub）
- 合并版首发布：dsh-turn-continuation-guard（L0-L3）+ dsh-audit-loop v3.3 合并为单插件
- 共享轨迹收集（call/todo/assistant 全入 trail）+ 统一注入预算（sharedMaxPerTurn=3）
- bundle 包形态（package.json `dsh.bundle.patch` + 包内 cordis.patch.yml）

### 内部迭代时间线（合并前的演进，均在 2026-11-17）
- 08:30-11:00 v1（turn-continuation-guard）：L1 文件声明校验（环境级 verified finish）+ L2 贴代码 + L3 确认词——26/26 单测
- 11:00-13:30 v2（audit-loop）：周期无历史审计（每 8 步）+ 修正器——漂移会话 step6 命中实测
- 13:30-14:30 v3.1：三档状态（FAIL/UNPRODUCTIVE/OK）+ 证据全文机制（审计看 2000 字证据而非 120 字摘要）——伪造验收 FAIL 精确判定
- 14:30-15:00 v3.2：只读代执行（纠正器确定正确参数后直接代跑）+ spawn 验收超时触发 verify_agent.py 代验收
- 15:00-16:00 v3.3：todo/write 观测 + D3 冗余 todo 检测（双向验证：真实推进不误伤/真冗余命中）
- 16:20-16:30 合并：turn-guard(339 行) + audit-loop(569 行) → behavior-guard(~750 行)，26/26 单测迁移全过

### 实验证伪记录（也是资产）
- v3.2 的"try 模式切换 + reasoning 预算硬切"实验：A/B 16 请求证明无效且有害，已回滚
- 审计员"todo 状态更新=浪费"误判：重放验证后加入判定纪律（防误伤）

[1.0.1]: https://github.com/D-al/dsh-behavior-guard/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/D-al/dsh-behavior-guard/releases/tag/v1.0.0
