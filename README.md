# dsh-agent-harness

> 仓库名沿用 `dsh-behavior-guard`（历史），npm 包名/插件 id 为 `dsh-agent-harness`（v2.0.0 起合并了 dsh-task-continuity）。

**DeepSeek Harness（dsh）agent harness 聚合插件** —— 行为治理 + 任务连续性，一个包承担"帮小模型分担负担、扩展能力边界"的全部工作。

> v2.0.0（2026-11-18）由 [dsh-behavior-guard](https://github.com/D-al/dsh-behavior-guard) v1.2.0 与 [dsh-task-continuity](https://github.com/D-al/dsh-task-continuity) v1.0.4 合并。
> 合并理由：两者事件面相同（session/event + agent/pre-step）、共享同一份会话状态（todo/失败轨迹/压缩事件）、
> 注入预算需要统一——分开维护会导致重复挂载与预算打架（实测过：preset 显式挂载 + bundle patch 双挂载 → 所有注入成对出现）。

## 为什么需要它（核心认知）

本地小模型（Qwen3.6-35B-A3B Q4 + 8GB 显存）不是不会做，而是**在长 agent 会话里会以可预测的方式退化**。
社区的共识是：**瓶颈不在模型，在 harness**（tech4talk：同一 35B 换 scaffold，SWE-bench Hard +15.6pp）。

本插件把"能由系统可靠完成的事"从模型肩上卸下来，让它只专注决策。

## 承担的职责（两张表）

### A. 行为治理（原 dsh-behavior-guard）

| 机制 | 触发 | 作用 |
|---|---|---|
| **L0 空手收尾** | 正文空 + 无工具调用 | 防"想完不干" |
| **L1 文件声明校验** | 声称写入 X → stat X 不存在 | 环境级 verified finish |
| **L2 产物贴正文** | 正文 ≥20 行代码 + 本轮无写调用 | 防"贴代码宣布完成" |
| **L3 短确认词** | 正文 ≤3 字确认词 + 无调用 | 防「只输出好」回路 |
| **D1 重复探测** | 同名调用 ≥3 且非生产 ≥2 | 注入"重复不是进展" |
| **D2 同参双败** | 完全同参连续 2 次失败 | 纠正器 → 只读代执行 |
| **D3 冗余 todo** | 清单 JSON 完全相同 ≥3 次 | 防空转 |
| **D4 交付闸门** | present + 本轮无验收痕迹 | "做的人不能自己签字" |
| **D5 风险门控审计** | 连续失败≥2 / 无进展≥6 / present 前 / 压缩后 / **MTP 置信 <0.65** | 只在风险点调 LLM 审计（SAG：算力 -66%、成功率 3 倍）|
| **Critic 产物评审** | present 前 | 异质 rubric 四维度（达标/完整/可用/一致）|
| **Planner 检查** | 首次 [VERIFY] 项 | 验"验收标准是否可验证" |
| **verify-on-edit** | 每次 write/edit | 确定性语法检查（0 LLM）|
| **present 深检** | present 前 | import 可解析/占位符/空文件/编码/重复段落/路径引用/交付物对照 |
| **控制回合**（v2.1）| 每 8 步 | 已确立/当前项/已排除 + "列 2-3 个候选再选"（Meta agentic meta-reasoning）|
| **Skills 技能卡**（v2.2）| 任务关键词命中 | 按需加载过程性知识（release-plugin/debug-llama-server/verify-artifact/web-fetch/git-workflow）|
| **危险操作分级**（v2.2）| 工具调用含破坏性模式 | block（rm -rf/reset --hard）要求说明 + 给更安全方案；warn 提示核对 |
| **per-step trace**（v2.2）| 每次工具/LLM 调用 | `_trace.jsonl` 记耗时/长度/状态/重试；`bench/trace_report.py` 按会话统计 |
| **JSON 解析重试**（v2.2）| LLM 输出不可解析 | 附"只输出纯 JSON"重试一次，重试计入 trace |

### B. 任务连续性（原 dsh-task-continuity）

| 机制 | 触发 | 作用 |
|---|---|---|
| **P0 压缩存档** | 上下文压缩后 | 重注入 初始任务+最新指令+**任务合同**+已验证决策+开放问题+**已排除**+三问自检 |
| **P1.5 todo 回灌** | 每次 todo_write 后 | 完整清单复述到最新位置（治"状态回卷/重问已答过的问题"）|
| **P1 todo 闹钟** | 4 步无单 / 5 步停滞 | 清单纪律执行 |

## 参考的论文（按机制）

| 机制 | 依据 |
|---|---|
| L0-L3 早收尾 | 2026-11-07 实测「只输出好」回路（7 次现场）|
| D1 重复探测 | Feedback-That-Backfires (2608.23651)：失败记录使重复概率 0.06→0.54 |
| D4 交付闸门 | IOV Labs 896 任务实测（小模型虚假完成 13%，自检仅降 0.9pp）+ verify-gate |
| D5 风险门控 | SAG（SKKU 2026-10）：gated critique 算力 -66%、成功率 3 倍；"precision intervention > constant supervision" |
| MTP 置信信号 | SU (2609.05274) 的 draft cross-likelihood；零改动版：读 llama-server 的 draft acceptance |
| Critic | 四角色标准（Planner/Executor/Critic/Verifier）；Apple 2026《Nine Judges, Two Effective Votes》：异质 rubric 才有独立信号 |
| verify-on-edit | Qwen3.5-35B scaffold 实验：Hard 22.2%→37.8%（+15.6pp）|
| P0 存档 | MemGPT (2310.08560) / Hippo (2610.24453) / ARC (ACL 2026) / StateForge (2609.32520) |
| P1.5 回灌 | Manus recitation；U-Fold（浙大/阿里 2026） |
| P1 闹钟 | Plan Declaration-Execution Gap (2609.38108)；Claude Code TodoWrite 实践 |

## 成本（运行期，本机 800 t/s prefill / 27 t/s decode）

| 机制 | 成本 |
|---|---|
| L0-L3 / D1-D3 / MTP / verify-on-edit / 深检 | **≈0**（确定性代码，无 LLM）|
| D5 审计 | 10-20s/次，仅风险点触发（每会话 2-5 次）|
| Critic | 13-20s/次，present 前 ≤2 次 |
| Planner | ~11s/任务 |
| 合计 | 会话时长 +5~10%，换掉反复修改的 20-40% 返工风险 |

## 配置

见 `cordis.patch.yml`（含全部默认值）。本机路径项（`verifyScript` / `pythonPath` / `allowedRoots` /
`specLogPath` / `critbankPath` / `ledgerPath`）**换机器必须改**。

外部依赖文件（可选，缺失则用内置默认）：
- `bench/critbank.json`（失效教训库）
- `bench/rubrics/*.json`（评审/审计/规划 rubric，可版本化）
- `bench/_audit_feedback.jsonl`、`_compaction_ledger.jsonl`（自校准与压缩审计日志）

## License
MIT
