# ADR-0028：工具面三层治理落实 + 动态工具面可行性结论

- 状态：accepted
- 日期：2026-11-22
- 决策者：用户（显式拍板：①已禁用入口立即移除 ②核心7全部常驻 ③低频关键"真做动态工具面"）
- 决策层级：重要决策 I（改变工具面配置）
- 支撑决策：M5 卡（三层治理原则，用户 2026-11-22 07:30 已拍板）

## Context（背景）
M5 卡的三层治理原则已于 2026-11-22 07:30 拍板（记在 ROADMAP_GRAPH.md:664）：
核心常驻 / 低频关键按需加载 / 已禁用入口移除。但"哪些进内核"的具体清单未定，
闸门 P-USER-DECISION 一直未满足。本 ADR 落实具体清单。

证据（docs/PIPELINE_AND_INFRA_BRIDGE_20261120.md）：37 会话 / 1959 调用 / 17 工具，前 7 占 95.7%。
关键纠正：**低频≠可砍**——read_image/ask_user_question 等是"场景少见但不可缺"。

## 核实发现（与旧认知的差异）
1. **job_* 早已移除**：cordis.patch.yml:271 `tool-jobs disabled: true`（2026-11-17 裁剪），
   M5 证据里的 9+2 次违规是**禁用前历史数据**——不需要再移除。
2. **web_fetch 是唯一仍暴露的禁用入口**：tool-web 当前 `fetch: true`，但 cordis.patch.yml:123 注释
   明确记录"禁用 tool-web 会连带 web 服务出问题，且实测并未真正移除工具"——之前尝试失败过。
3. **tool_surface_audit.py 有接口漂移 bug**：`tool_audit.audit` 已返回 4 值（含 dup_count），
   调用方还解包 3 值 → ValueError。本轮已修。

## Options（方案对比）
| 层 | 选项 | 结论 |
|---|---|---|
| 第3层 已禁用入口 | A. disabled tool-web 整个包 / B. 只改 fetch:false 保留 search | ✅ B（A 历史证明连带 web 服务故障且未真移除）|
| 第1层 核心7 | A. 全常驻 / B. 缩到前5 | ✅ A（95.7% 覆盖，无争议）|
| 第2层 低频关键 | A. 全暴露 / B. prompt 提示触发条件 / C. 真做动态工具面 | 用户选 C，但架构不支持 → 待重选（见 Counter-evidence）|

## Decision
1. **第 3 层（已禁用入口）**：`tool-web` 的 `fetch: true` → `false`，**保留 search（SearXNG）**。
   不直接 disabled tool-web（历史证明会连带 web 服务故障）。回滚点：
   `D:/Brain/_cleanup_20261118/cordis.patch.before_tooltrim_*.yml`。
   ⚠ 配置已改但**未验证生效**——dsh 按需 STOPPED，需下次 start 后采真实事件确认 web_fetch 真消失。
2. **第 1 层（核心 7）**：pwsh/read/todo_write/glob/edit/write/grep 全部常驻，不改（覆盖 95.7%）。
3. **第 2 层（低频关键）**：用户要求"真做动态工具面"。**调研结论：当前 dsh 不支持 per-step 动态工具切换**——
   工具面在启动时由 cordis.patch.yml bundle 决定；唯一开关是 `dsh.profile.bundles`（会话级，非逐步）。
   历史教训：连静态 disabled tool-web 都失败过。
   → **本 ADR 不实施动态工具面**（无可靠机制 + 收益小：那 4 个工具低频但不可缺，本来就不该砍）。
   > ⚠ **勘误（2026-11-22 同日）**："架构不支持"的结论**已被 ADR-0029 推翻**——
   > 深查 asar 内官方 cookbook 确认 dsh 有 `ctx.tools.register` + fiber dispose 的运行时热替换机制。
   > 本条保留作为决策过程记录，正确结论见 ADR-0029。
   标记为用户决策与架构现实冲突，**待用户重新选择**：保持全暴露（推荐）或另开探索 ADR 设计插件级 hook。

## Counter-evidence（反证）
- **反对只改 fetch:false**：如果 fetch 能力实际由 web 服务提供而非 tool-web 的 config，改这里可能无效。
  → 必须下次 start 后验证真实工具 schema 里 fetch 是否消失；无效则回滚并重开 ADR。
- **反对放弃动态工具面**：用户明确要求了。
  → 本 ADR 诚实记录"架构不支持"，不是否决用户意图；给出替代路径（插件 hook 探索）待用户定。
- **翻案条件**：若 dsh 后续版本提供 per-session 工具过滤 API，重开 ADR 实施。

## Consequences
- 正面：web_fetch 入口收敛；审计 bug 修复；动态工具面的架构障碍显性化。
- 负面：动态工具面未实现（用户要求未满足，需重新决策）；web_fetch 修改待验证。
- 验证：下次 dsh start 后读 request/header 的 tools schema，确认无 fetch 能力、search 仍在。
