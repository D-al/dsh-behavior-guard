# 同族 harness 对标：社区在做什么，我们还能补什么（2026-11-19）

> 范围：GitHub 上真实存在的 Qwen3-35B-A3B 族 / dsh 生态 harness 项目。
> 判据：只写核实过仓库 README/源码的项目，不写搜索摘要里的二手结论。
> 我们的路线：权重零改动 + 纯 harness 文本注入 + 确定性门控（见 [README](../README.md)）。

## 一、核实过的项目

| 项目 | 定位 | 与我们相关的最有价值机制 |
|---|---|---|
| [qzzqzzb/Self-Harness](https://github.com/qzzqzzb/Self-Harness)（arXiv 2606.09498）| 让模型改进自己的 harness | 失败签名精确聚类 + 双 split 回归门禁 + 单 hook 最小改动；已纳入路线图（[方案](SELF_HARNESS_PLAN.md)）|
| [jb-san/mini-harness](https://github.com/jb-san/mini-harness) | 极小内核的本地 coding agent | **7 个原生工具**（read/write/list/shell/web_search/web_scrape/discover_skills），其余全靠 skill + skill 内脚本 + repo hooks；`beforeToolCall/afterToolCall/onToolError/onContextIncrease` hook；工具调用被 hook 拦截时以普通 tool error 呈现 |
| [nonentity303/dsh-browser-agent](https://github.com/nonentity303/dsh-browser-agent) | 浏览器里的 dsh mini harness（userscript）| **技能提示词永远排在固定安全规则之前**（无法覆盖安全底线）；跨域授权**仅本次任务有效**、不写持久白名单；工具默认关 + 逐次确认；插件在隔离沙箱跑（无 DOM/网络/存储）+ 死循环超时强杀；159 项自动化测试 |
| [microsoft/agent-lightning](https://github.com/microsoft/agent-lightning) | 用 RL 优化 agent harness（含 Qwen3.5-35B-A3B 案例）| harness 作为可训练对象（我们路线不适用，但证明"harness 是关键变量"）；其 CLI harness 实现可作结构参考 |
| [rllm-org/rllm](https://github.com/rllm-org/rllm) | LLM 训练/推理统一框架，含 `cli_harness.py` | CLI harness 的标准化接口（我们自建，可对照其任务封装格式）|

> 说明：直接在 GitHub 搜 `Qwen3-35B-A3B harness` 返回 0 结果——**这个精确模型名还没有专门的 harness 产品**。
> "35B-A3B 族"的适配主要散落在通用 agent 框架里（走 OpenAI 兼容端点），这正是我们的空位。

## 二、逐项对照

| 机制 / 优化 | 我们 | 社区 | 可借鉴 | 具体动作 |
|---|---|---|---|---|
| **工具面裁剪** | 28 个工具（待办：28→18-20，需用户拍板）| mini-harness 刻意只留 7 个，能力靠 skill + skill 内脚本；"加工具请求"默认当"加 skill"处理 | **高** | 把待办的工具面裁剪从"拍板数字"改成"结构改造"：保留最小内核（read/write/edit/search/shell/bridge），把低频能力挪进 10 个 skill 卡；hook 化拦截（`beforeToolCall` 对应我们的 DANGER 分级）|
| **hook 化运行时策略** | 策略写在 index.mjs 内部（L0-L3 / D1-D5 / danger）| mini-harness 的 hook 是**仓库/用户提供的外部文件**，加载一次、错误被捕获、超时、失败不崩内核 | **高** | 把危险操作分级和注入预算做成外部 hook 文件（现有 `danger` 规则外置），让策略可热替换而不改 index.mjs——正好服务 Self-Harness 的"可编辑面白名单"|
| **上下文利用率为注入触发** | 压缩 thresholdRatio 0.55（54K）固定 | mini-harness `onContextIncrease(util%)` hook：≥70% 自动触发外部动作（如重启）| 中 | 把我们的压缩阈值从"固定比例"升级为 hook 事件，允许外部脚本按利用率做轻量动作（如主动整理 todo），不改核心 |
| **安全规则优先级** | 安全规则在 prompt + 模板双层，未被明确"排序"| dsh-browser-agent 明确：**技能提示词永远排在固定安全规则之前，skill 无法覆盖安全底线** | **高** | 在 AGENTS.md 和 skills 加载顺序里显式声明"安全规则不可被 skill/prompt 覆盖"，加一条回归测试验证（当前靠约定，没有强制）|
| **授权作用域** | approval 已根治为 full-access + never（本机单人）| dsh-browser-agent：跨域授权仅本次任务有效、不写持久白名单、fail-closed | 中（本机不需要，但有参考价值）| 记录为 ADR 的安全对照：如果将来开放多用户，授权必须 task-scoped |
| **沙箱隔离执行** | 无（harness 不执行 LLM 生成代码）| dsh-browser-agent 插件在隔离沙箱跑，死循环超时强杀 | 低（我们本来就不执行生成代码）| 保持现状，不构成缺口 |
| **trace 可观测性** | `_trace.jsonl` + trace_report + D5 审计 | mini-harness 在 TUI 的 telemetry timeline 展示 hook 事件，hook 拦截/失败可见 | 中 | 把我们的 DANGER 拦截 / verify-on-stop 也进 trace（部分已有），确保"被拦"可见而不只是"通过"可见 |
| **自动化测试密度** | 106 PASS（7 文件）+ 30/30 门禁 | dsh-browser-agent 159 项自动化（含沙箱端到端）| 中 | 数量不是目标；补"安全规则不可覆盖""hook 失败不崩内核"两类语义测试更有价值 |
| **RL 优化 harness** | 不适用（权重零改 + 无训练）| agent-lightning 把 harness 当训练对象 | 不适用但值得知道 | 记入"明确不做"（训练），但保留其 CLI harness 接口作对照 |

## 三、最值得抄的 5 条（按 ROI）

1. **工具面结构改造**（高 ROI，中等成本）：把 28 个工具收敛到最小内核 + skill 化，用 hook 做危险拦截。
   这同时解掉待办里的"工具面裁剪"和 Self-Harness 的"可编辑面白名单"两件事。
2. **外部 hook 文件**：把 danger 分级 / 注入预算策略从 index.mjs 外置成 `hooks/*.mjs`，加载一次、错误隔离、失败不崩。
   让策略可替换、可测试，且不碰核心代码（对应 mini-harness 的 hook 模型）。
3. **安全规则不可覆盖的硬声明 + 回归测试**：在 AGENTS.md 显式排序，加一条测试确保 skill/prompt 无法覆盖安全底线。
4. **上下文利用率 hook**：把压缩阈值升级为事件，允许轻量外部动作（不新增 LLM）。
5. **hook 事件进 trace**：DANGER 拦截/失败也记 trace，让"被拦"可观测。

## 四、我们的相对位置

- **领先**：确定性门控的深度（L0-L3 + D1-D5 + 30/30 门禁）、引擎内部信号（MTP acceptance）、端到端证伪文化、跨层复用（GWT/FEP）。
- **齐平**：skill 化（我们有 10 个技能卡）、trace 可观测性。
- **落后**：策略的**外部化/hook 化**（我们写死在 index.mjs）、工具面**刻意做小**的工程哲学、安全优先级的**显式声明与测试**。
- **空位**：35B-A3B 族**没有专门 harness 产品**——我们在这条细分线上是最完整的实现之一（以本机单人场景为前提）。

相关：[COMPETITIVE_ANALYSIS.md](COMPETITIVE_ANALYSIS.md)（宏观社区对比）· [SELF_HARNESS_PLAN.md](SELF_HARNESS_PLAN.md)（harness 自进化）· [ROADMAP](../ROADMAP.md)
