# md 文件体系规划（2026-11-18）

> ✅ **执行状态（10:45）**：低风险动作 1-4 已完成；归档已建；迁移备份已提炼 brain 快照入库、
> 其余移到 `_archive_backups_20261118/`（回收站 API 被安全策略拦，故用可恢复移动）。
> 本库已升级为 Single Source of Truth，见 README「一键开箱」+ `setup/install.ps1`。

> 背景：AGENTS.md 外置后（3959→2461 token），知识分散在 10 个 skill、7 份报告、
> 30+ 天日志、18 份 dsh_extract 文档里，且有多个 junction 指向同一批文件。
> 本文档给出**分类原则 + 目标结构 + 整理动作清单**，供确认后执行。

---

## 一、现状盘点（活跃文件，排除 .bak 迁移备份）

| 位置 | 内容 | 数量 | 问题 |
|---|---|---|---|
| `dsh-data/AGENTS.md` | 常驻工作协议 | 1 | ✓ 已瘦身到 2461 tok |
| `bench/skills/*.md` | 按需技能卡 | 10 | ✓ 有 frontmatter，插件按关键词注入 |
| `bench/*REPORT* / USAGE_GUIDE / PERIPHERAL_CAPABILITIES` | 决策报告 | 4 | 混在 bench/ 根，与脚本同层 |
| `bench/dsh_extract/*.md` | 第三方插件 README 副本 | 18 | **只读归档，却占着活跃目录** |
| `bench/brain_map.md` / `ROLE_ARCHITECTURE_PLAN.md` / `_part8.md` | 一次性草稿/旧计划 | 3 | **已完成任务中间产物，未清理** |
| `default-workspace/*.md` | 用户产物（MoE 解析/检验手册/summary） | 3 | 混在工作区根 |
| `memory/YYYY-MM-DD.md` | 每日日志（append-only） | 30+ | ✓ 正常；但 >30 天应蒸馏 |
| `.workbuddy/memory.bak-migrate-*` | 迁移备份 | 30+ | 备份，保留但不应干扰搜索 |

**三个真问题**：
1. **活跃/归档混放**：`dsh_extract/`（18 份只读副本）和 `_part8.md`（一次性草稿）跟可执行脚本同目录。
2. **没有"项目级单一入口"**：想知道"这套系统怎么运作"要读 README + USAGE_GUIDE + 4 份报告 + memory。
3. **junction 陷阱**：`bench`/`memory`/`p` 都是 junction，`find` 默认不跟随——任何整理脚本必须显式处理实际路径。

---

## 二、分类原则：按生命周期，不按主题

| 类别 | 判定标准 | 存放位置 | 谁读 |
|---|---|---|---|
| **L0 常驻** | 无触发信号、违规代价极高、每会话必用 | `dsh-data/AGENTS.md`（唯一） | 每次自动注入 |
| **L1 按需** | 有明确触发信号（关键词/门控）| `bench/skills/*.md`（带 frontmatter）| 插件按信号注入摘要，模型再 read 全文 |
| **L2 参考** | 决策依据、调研报告，需要时查 | `bench/docs/`（新建）| 人或 AI 按索引读 |
| **L3 日志** | 时序记录，append-only | `memory/YYYY-MM-DD.md` + `memory/MEMORY.md` | 复盘时读 |
| **L4 归档** | 只读副本/历史快照/一次性草稿 | `bench/archive/`（新建）| 几乎不读；保留可追溯性 |

**关键纪律**：
- L0 **只有一个文件**——任何想加进 AGENTS.md 的内容，先问"有没有触发信号可以外置到 L1"。
- L1 **必须有 frontmatter**（name/summary/keywords），否则插件无法检索——写了等于没写。
- L2/L3 **不进插件检索**（避免噪声），靠文档索引导航。
- L4 **不删除**（保留可追溯），但移出活跃目录。

---

## 三、目标结构

```
dsh-data/
├── AGENTS.md                    ← L0 唯一常驻（2461 tok）
│
bench/
├── skills/                      ← L1 按需（10 个，frontmatter 驱动）
│   ├── todo-discipline.md
│   ├── roles.md
│   ├── tool-boundaries.md
│   └── ...（7 个其他）
├── docs/                        ← L2 参考（新建，从 bench/ 根迁入）
│   ├── README-harness.md        ← 项目单一入口（指向所有其他文档）
│   ├── USAGE_GUIDE.md
│   ├── PERIPHERAL_CAPABILITIES.md
│   ├── MORNING_REPORT_20261118.md
│   ├── RESEARCH_NOTES.md        ← 论文索引的活文档（从 README Part 8 拆出）
│   └── config-history/
├── archive/                     ← L4 归档（新建）
│   ├── dsh_extract/             ← 18 份第三方 README 副本
│   ├── one-off/                 ← brain_map.md / ROLE_ARCHITECTURE_PLAN.md / _part8.md
│   └── snapshots/
├── memory/ → D:/Brain/workspace/memory   ← L3 日志（junction）
├── *.py / *.mjs                 ← 可执行脚本（保持原位，不挪）
└── rubrics/ critbank.json       ← 机器可读配置（保持原位）
```

---

## 四、整理动作清单（待确认后执行）

### 低风险（纯移动，不改内容）
| # | 动作 | 影响 |
|---|---|---|
| 1 | 新建 `bench/docs/`，迁入 4 份报告（`USAGE_GUIDE` / `PERIPHERAL_CAPABILITIES` / `MORNING_REPORT` / `tuning_review`）| 需更新 README 里的相对链接 |
| 2 | 新建 `bench/archive/dsh_extract/`，迁入 18 份第三方 README | 无代码引用，纯归档 |
| 3 | 新建 `bench/archive/one-off/`，迁入 `brain_map.md` / `ROLE_ARCHITECTURE_PLAN.md` / `_part8.md` | `_part8.md` 已并入 README 可删（保留归档）|
| 4 | 写 `bench/docs/README-harness.md` 作为单一入口 | 新增，不改现有 |

### 中风险（需要更新路径引用）
| # | 动作 | 注意 |
|---|---|---|
| 5 | 更新 GitHub README 的文档链接（指向 `docs/`）| 需同步重新推送 |
| 6 | 更新 `AGENTS.md` 里指向 skill 的引用（无需改，skill 文件名不变）| 验证即可 |
| 7 | 更新 `regression_check.py` 的"文档存在性"检查（如有）| 门禁必须 29/29 |

### 需要你决策
| # | 问题 | 选项 |
|---|---|---|
| 8 | `default-workspace/` 里的 3 份 md（MoE 解析/检验手册/summary）| 保留原地（用户产物）/ 迁入 `docs/notes/` |
| 9 | `.bak-migrate-20261117/`（30+ 份迁移备份）| 保留 / 压缩成单个 zip 归档（省空间+免搜索噪声）|
| 10 | >30 天的日志（`memory/2026-10-*`）| 按系统要求蒸馏进 MEMORY.md 后删除（append-only 日志的例外）|

---

## 五、配套机制（让体系可自维护）

1. **AGENTS.md 加一行文档索引**（~60 tok，余量 1635 足够）：
   > 项目文档入口：`bench/docs/README-harness.md`；技能见 `bench/skills/`；决策依据见 `docs/`。
2. **新 skill 的 lint**：写个 `bench/skill_lint.py` 检查 frontmatter 完整性（name/summary/keywords），
   跑在门禁里——防止"写了 skill 但检索不到"。
3. **日志蒸馏提醒**：每月初检查 `memory/` 里 >30 天的文件，提示蒸馏（不自动删）。
4. **文档地图自更新**：`README-harness.md` 里列出所有 L1/L2 文件及一句话用途，新增文档时同步加一行。

---

## 六、为什么这样分（第一性原理）

这次调整的本质是**把"模型的注意力"当成稀缺资源来分配**：
- L0（AGENTS.md）是**常驻税**——每会话都付，必须压到最低（只留无触发信号的铁律）。
- L1（skills）是**按需税**——命中才付，且只付摘要（全文要模型主动 read）。
- L2/L3/L4 **不进模型上下文**——只在人主动查阅或工具检索时读取。

对应论文依据：
- [Structure Beats Scale](https://weightythoughts.substack.com/p/structure-beats-scale)——四层知识结构 > 全量塞入
- [U-Fold](https://arxiv.org/abs/2603.25158) 的检索式上下文（摘要+todo+工具关键行）
- [The Complexity Trap (arXiv 2508.21433)](https://arxiv.org/abs/2508.21433)——observation masking 优于全量摘要
- 我们自己的实测：AGENTS.md 从 3959→2461 tok，余量从 137→1635，且 10 个 skill 命中测试全过
