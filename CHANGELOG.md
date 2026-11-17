# Changelog

所有迭代以本地时间记录（UTC+8）。格式参考 Keep a Changelog。

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
