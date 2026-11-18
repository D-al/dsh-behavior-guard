# 说明书集合（Manuals）

> README 只讲"是什么、为什么、做了什么"；本文件讲"怎么用、怎么调、怎么排障"。
> 它是一份**操作手册索引**——每个小节都是独立的说明书，按需查阅。

## 目录

1. [一键开箱与同步](#1-一键开箱与同步)
2. [生产参数](#2-生产参数)
3. [工具与脚本速查](#3-工具与脚本速查)
4. [论文速查表](#4-论文速查表)
5. [版本基线与升级](#5-版本基线与升级)
6. [故障排查](#6-故障排查)

---

## 1. 一键开箱与同步

### 1.1 新机器完整流程

```powershell
# 0. 前置：装 dsh 本体 + llama.cpp（自编 b12244）+ 模型 GGUF
#    见 §5 版本基线

# 1. 克隆库
git clone https://github.com/D-al/dsh-behavior-guard.git
cd dsh-behavior-guard

# 2. 安装插件与配置（默认不覆盖已存在文件）
.\setup\install.ps1 -DryRun     # 预演
.\setup\install.ps1             # 执行
.\setup\install.ps1 -Force      # 需覆盖时（会先备份 .bak-<时间戳>）

# 3. 建 junction（p/ bench/ memory/ dsh/ gguf/ llama/ wb/）
.\setup\links.ps1 -DryRun
.\setup\links.ps1

# 4. 重启 dsh（需在桌面前台，已登录）
Stop-Process -Name "DeepSeek Harness" -Force
Start-ScheduledTask -TaskName RestartDsh

# 5. 验证
curl http://127.0.0.1:8081/health
python bench/config_check.py
python bench/regression_check.py     # 应 30/30
```

**install.ps1 恢复的内容**：
`config/`（AGENTS.md / env.llama / llama-router-preset.ini / chat_template_zh.jinja / critbank.json / rubrics/4 / patches/autoparser-fix.patch）、`skills/`(10)、`tools/`(19)、`docs/`、插件本体（pnpm add）。

**links.ps1 建的 7 个 junction**（在 `C:\Users\Ad\Documents\deepseek-harness\default-workspace\`）：

| 名称 | 目标 |
|---|---|
| `bench` | `D:\Brain\workspace\bench` |
| `memory` | `D:\Brain\workspace\memory` |
| `p` | `D:\Brain\workspace` ← **稳定根，无时间戳** |
| `dsh` | `D:\Brain\dsh-data` |
| `gguf` | `D:\GGUF_Download` |
| `llama` | `D:\llama.cpp` |
| `wb` | `C:\Users\Ad\.workbuddy` |

另建 `C:\Users\Ad\.dsh → D:\Brain\dsh-data`（profile 根）。

### 1.2 日常回写（本机 → 库）

```powershell
.\setup\sync.ps1 -DryRun     # 看哪些文件有差异
.\setup\sync.ps1             # 同步生产资产
.\setup\sync.ps1 -Commit     # 同步并 git commit（仍需手动 push）
```

**只同步**：config/ / skills/ / tools/ / docs/ 中库里已有的文件。
**不同步**：实验脚本（`_` 前缀）、日志、测试结果（`_*.json`）、备份（`*.bak-*`）。

---

## 2. 生产参数

### 2.1 `.env.llama`（`config/env.llama`）

```
CTX 98304 / NGL 99 / NCMOE 40 / MOE_CACHE_CPU_SHARE 0 / MOE_CACHE_MIB 1350
UBATCH 1536 / THREADS 6 / BATCH 4096 / CTK q8_0 / CTV q4_0 / MMPROJ_OFFLOAD 1
SPEC_TYPE draft-mtp / NMAX 5 / SPEC_DRAFT_P_MIN 0.8 / CTX_CHECKPOINTS 2
TEMP 留空 / TOP_P 0.95 / REASONING_BUDGET 4096 / REPEAT_PENALTY 1.1
DRY 0.8-1.75-32-512
```

**铁律**：
- `.env` **覆盖** INI——`config_check.py` 比对 23 个重叠键。
- `LLAMA_35B_TEMP` 必须**留空**（CLI 会覆盖 preset 的温度）。
- `CTX_CHECKPOINTS=2` 是承重墙（降到 1 每步全量重预填 **+23%**）。
- `MOE_CACHE_CPU_SHARE=0`——1.0 让 decode +37% 但端到端慢 **2.4×**。
- `DRY --dry-allowed-length 32`（设 2 会让模型改字形躲惩罚）。

### 2.2 压缩配置

`thresholdRatio 0.55`（54K 触发）/ `retain 16384` / `headroom 16384`（硬顶 73728）。
需改两处：`.env` + `cordis.patch.yml` 的 contextWindow。

### 2.3 性能基线（暖态：warmup 2-3 次 + 5 次取中位）

| 上下文 | decode | prefill |
|---|---|---|
| 20K | 27.2 t/s | 800 t/s |
| 60K | 23.9 t/s | 781 t/s |

单次 ±10%；判优至少 2 次。显存安全线：空闲 ≥450 MiB（186 必卡）。

---

## 3. 工具与脚本速查

### 3.1 测试与门禁

| 脚本 | 作用 | 期望 |
|---|---|---|
| `test_turn_guard.mjs` | L0-L3 早收尾单测 | 26 PASS |
| `test_new_guards.mjs` | D1-D5/Critic/Skills 等新守卫单测 | 40 PASS |
| `regression_check.py` | 生产级门禁（模板/规则/插件/引擎/渲染/配置）| **30/30** |
| `config_check.py` | 四层配置一致性 | `[一致]` |

### 3.2 运维与观测

| 脚本 | 作用 |
|---|---|
| `trace_report.py` | 按会话统计工具/LLM 调用、耗时、失败率（数据不足时会提示）|
| `trace_timeline.py` | 失败时间线（t_err / t_lock / t_obs + lag）|
| `auditor_metrics.py` | 审计干预有效率统计 |
| `audit_calibrate.py` | 用 `_audit_feedback.jsonl` 生成阈值调整建议 |
| `crit_revision.py` | CritBank 反向修订建议（生成 `_crit_revisions.json`）|
| `skill_draft.py` | 从 trace 生成 skill 草稿（生成 `_skill_drafts/`）|
| `freeze_watch.py` | 看门狗（双进度 + 功耗，两停 120s 且 <30W 才判死）|
| `speed_probe.py` | speed 基准（用法 `<2k\|20k> <次数> <warm>`）|

### 3.3 回归基准

`agentlab.py`（7 小任务）/ `projectlab.py`（P1-P5）/ `replay_good.py`（真实长会话重放）/
`verify_agent.py`（三态验收）/ `config_check.py` / `token_audit.py` / `tool_audit.py`。

⚠ 短任务测试台覆盖不到"20+ 轮后遇失败工具结果"；改守卫前先过回放现场。

---

## 4. 论文速查表

> 按主题分组，每条 **[标题 + arXiv 链接] + 我们用它做什么**。完整故事见 README 各分支末尾"依据"行。

### A · 失败预测 / 风险门控

| 论文 | 我们的用法 |
|---|---|
| [SU: How to Speculate about Uncertainty (2609.05274)](https://arxiv.org/abs/2609.05274) | MTP 信心信号来源（零改动版读 draft acceptance）|
| [Feedback That Backfires (2608.23651)](https://arxiv.org/abs/2608.23651) | D1 重复探测：失败记录使重复概率 0.06→0.54 |
| [Calibrated to Act (2608.27167)](https://arxiv.org/abs/2608.27167) | 审计员自校准闭环 |
| [Confident Fools (2610.41124)](https://arxiv.org/abs/2610.41124) / [MARTA (2610.05223)](https://arxiv.org/abs/2610.05223) | 规则代替元认知 |

### B · 验证 / 评审

| 论文 | 我们的用法 |
|---|---|
| [MAST (2503.13657)](https://arxiv.org/abs/2503.13657) | 21.3% 失败是验证缺口 → D4/D5 |
| [Agent-as-a-Judge (2410.10934)](https://arxiv.org/abs/2410.10934) | 审计员主动取证 |
| [JudgePanel (2608.29168)](https://arxiv.org/abs/2608.29168) | 否决多 judge 投票 |
| [Post-Reasoning (2605.06165)](https://arxiv.org/abs/2605.06165) | 先判定再论证 |
| [SEVA (2606.29713)](https://arxiv.org/abs/2606.29713) | 结构化可审计验收输出 |
| [AgentV-RL (2604.16004)](https://arxiv.org/abs/2604.16004) | 双向验证（正向+反向）|
| [AutoResearchEval (2608.14905)](https://arxiv.org/abs/2608.14905) | 45 类失败模式，根因=缺元认知闭环 |
| [AgentRx (2602.02475)](https://arxiv.org/abs/2602.02475) | 失败步定位 |

### C · 角色 / 元推理

| 论文 | 我们的用法 |
|---|---|
| [Three Roles One Model (2604.11465)](https://arxiv.org/abs/2604.11465) | 三角色协作骨架 |
| [Thinking Before Thinking (2609.38147)](https://arxiv.org/abs/2609.38147) | 控制回合（Controller 四动作）|
| [Tyler (2606.16360)](https://arxiv.org/abs/2606.16360) | 全局定向是独立算子 |
| [Plan Declaration-Execution Gap (2609.38108)](https://arxiv.org/abs/2609.38108) | P1 闹钟（计划只有 22~45% 被遵守）|

### D · 记忆 / 上下文 / 压缩

| 论文 | 我们的用法 |
|---|---|
| [MemGPT (2310.08560)](https://arxiv.org/abs/2310.08560) / [Hippo (2610.24453)](https://arxiv.org/abs/2610.24453) | P0 存档 + 防污染 |
| [StateForge (2609.32520)](https://arxiv.org/abs/2609.32520) | 显式维护活动需求列表 |
| [The Complexity Trap (2508.21433)](https://arxiv.org/abs/2508.21433) | observation masking 优于纯摘要 |
| [Why Pay for Long Reasoning (2611.03852)](https://arxiv.org/abs/2611.03852) / [Think or Remember (2611.10982)](https://arxiv.org/abs/2611.10982) | 不改写历史（后缀税 > 收益）|
| [Frontier LMs Struggle to Copy (2607.16072)](https://arxiv.org/abs/2607.16072) / [CopyGen (2610.28393)](https://arxiv.org/abs/2610.28393) | 短路径约定 |

### E · 工具 / 自进化 / 能力边界

| 论文 | 我们的用法 |
|---|---|
| [RAG-MCP (2505.03275)](https://arxiv.org/abs/2505.03275) | 工具面预算 |
| [Cartograph (2609.30293)](https://arxiv.org/abs/2609.30293) | 渐进披露（但不做动态工具面）|
| [Trace2Skill (2603.25158)](https://arxiv.org/abs/2603.25158) / [SkillCAT (2606.13317)](https://arxiv.org/abs/2606.13317) / [SkillComposer (2606.06079)](https://arxiv.org/abs/2606.06079) | G1 技能草稿 |
| [CDSE (2610.23599)](https://arxiv.org/abs/2610.23599) | 技能四功能分化 |
| [ReHarness (2610.12668)](https://arxiv.org/abs/2610.12668) | G2 反向修订 |
| [HaMo (2610.34724)](https://arxiv.org/abs/2610.34724) / [Recuris](https://github.com/Gen-Verse/Recuris) | 持续学习 / 递归记忆（前沿）|
| [ODAR (2602.23681)](https://arxiv.org/abs/2602.23681) / [Adaptive TTC (PMLR v306)](https://proceedings.mlr.press/v306/bilal26a.html) / [Learning When to Think (2608.20256)](https://arxiv.org/abs/2608.20256) | 自适应算力路由（前沿）|

---

## 5. 版本基线与升级

### 5.1 当前版本栈（2026-11-18 验证）

| 组件 | 版本 |
|---|---|
| dsh | **0.2.2-rc.3**（app.asar 11-13，已实测）|
| llama.cpp | 自编 **b12244** + [autoparser 2 行补丁](https://github.com/D-al/dsh-behavior-guard/blob/main/config/patches/autoparser-fix.patch) |
| node / pnpm（rc.3 后）| 24.21.0 / 11.28.5 |
| 模型 | Qwen3.6-35B-A3B UD-Q4_K_XL（21.28 GiB）|
| harness | v2.5.3 |

### 5.2 升级检查清单（每次升级必做）

1. **备份 profile**：`_backup-before-<version>-<date>/`（AGENTS.md / package.json / cordis.patch.yml / 插件清单）。
2. **grep 所有 `{{...}}` 变量**——rc.3 只注册 `provider` / `model`；`{{cwd}}` 会导致本轮运行失败。
3. **查 pnpm 路径**——rc.3 迁到 `resources/runtime/primary-runtime/dependencies/pnpm/bin/pnpm.cjs`。
4. **virtual store**——路径从 junction 变物理路径时 `pnpm update` 报 `ERR_PNPM_UNEXPECTED_VIRTUAL_STORE`；若 index.mjs md5 与库一致，只同步版本戳即可，别冒险 `pnpm install`。
5. **查 bundles 变化**——rc.2 起少 `dsh-experimental-agent-team-profile`（AgentTeam 改具名，不影响本 harness）。
6. **重启 → 探针 → 全测**（26+40+30/30 + config_check）。

### 5.3 autoparser 补丁（每次重编引擎必打）

```
common/chat-auto-parser-generator.cpp:
  444: format.per_call_start  →  p.optspace(format.per_call_start)
  473: p.until(trigger_marker) →  p.until(trim_whitespace(trigger_marker))
```
补丁文件：`config/patches/autoparser-fix.patch`。上游 [#29307](https://github.com/ggml-org/llama.cpp/pull/29307) 至今未合并，**不能撤**。

---

## 6. 故障排查

| 症状 | 原因 | 处理 |
|---|---|---|
| `unknown prompt variable "{{cwd}}"` | rc.3 变量白名单收紧 | 已修复；升级后 grep `{{` |
| 本轮运行失败，报告 UNKNOWN | 多为 prompt 变量/配置解析失败 | 看 dsh 错误信息里的 section 名 |
| harness 插件没加载 | pnpm virtual store 路径变化 | 见 §5.2 第 4 条 |
| 工具 unknown | 工具 id 写错（如 `pswsh`）| shell 唯一 id 是 `pwsh` |
| 写 junction 路径被拒 | canonical path 防逃逸（正确行为）| 写工作区非 junction 路径，或绝对路径提权 |
| 长任务卡死 1~2 t/s | 显存空闲 <186 MiB，WDDM 换页 | 跑长任务前重启清 MoE cache |
| `_audit_feedback.jsonl` 不存在 | 机制已装但真实审计未触发 | 不是故障，trace_report 会提示 |
| 全盘找文件慢 | 用了 Get-ChildItem 递归 | 用 `es.exe "关键词"`（秒级）|

**诊断流程**：`curl /health` → 探针时间戳 → `config_check.py` → `regression_check.py` → `trace_report.py` → 会话文件修改时间。
