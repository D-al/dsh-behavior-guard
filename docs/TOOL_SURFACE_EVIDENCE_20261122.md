# 工具面证据更新：全量 37 会话真实频次（2026-11-22）

> 用户指出"推卡开了很多会话，工具调用应该很多"——旧证据（8快照去重375条/单一会话）
> 确实不足。本次从 dsh 会话存储 `session.v4.jsonl.zstd`（zstd 多帧，需 stream_reader().read()）
> 解压全部 37 个会话、1959 次工具调用、17 种工具。**这是目前最全的工具面证据**。

## 一、频次分布（29 个有调用的会话，1959 次）

| 工具 | 次数 | 占比 | 累计 |
|---|---|---|---|
| pwsh | 623 | 31.8% | 31.8% |
| read | 617 | 31.5% | 63.3% |
| todo_write | 150 | 7.7% | 71.0% |
| glob | 137 | 7.0% | 78.0% |
| edit | 129 | 6.6% | 84.6% |
| write | 127 | 6.5% | 91.1% |
| grep | 90 | 4.6% | 95.7% |
| present | 40 | 2.0% | 97.7% |
| job_output | 9 | 0.5% | — |
| web_search | 8 | 0.4% | — |
| ask_user_question | 8 | 0.4% | — |
| load_workspace_dependencies | 7 | 0.4% | — |
| working_directory | 5 | 0.3% | — |
| web_fetch | 4 | 0.2% | — |
| list_agents / job_kill / read_image | 2/2/1 | <0.1% | — |

**前 7 个工具占 95.7%**，和旧单一会话的结论（前 5 占 90%）方向一致但样本可信度高得多。

## 二、关键纠正：低频 ≠ 可砍

交叉核对 config/AGENTS.md 发现——多个低频工具**已经在提示层被禁用或限制**：
- `job_*`（job_output 9 + job_kill 2）：AGENTS.md:202 明确"已禁用"——调用是违规残留
- `web_fetch`（4）：AGENTS.md:56/107 明确"本机未配置 fetch 提供方，禁用"——调用是违规
- `read_image` / `list_agents` / `ask_user_question`：AGENTS.md:200-201 列为"容易忘记但需要时用"的关键能力

**所以真正的问题不是"低频工具占坑"这么简单**：
1. 已禁用工具仍暴露在工具面 → 模型偶尔违规调用（11 次）→ 浪费步骤
2. 但 `read_image`/`ask_user_question` 低频是因为"场景少见但不可缺"——砍了会在关键时刻断链

## 三、对 M5/S22 的证据判断

**证据充分度**：从"单一会话不足拍板"升级为"多会话、大样本、可拍板"。
- ✅ 频次证据现在充分（29 会话 / 1959 调用 / 17 工具）
- ⚠️ 但"砍哪些"仍需价值判断——尤其低频但关键的工具
- ✅ 有一个明确的低成本动作：**把已禁用的 job_*/web_fetch 从工具面移除**（不是"砍功能"，
  是"清理已经不用的入口"）——这个可以直接做，不需要价值拍板

## 四、数据来源与坑（供复现）

- 源：`D:/Brain/dsh-data/sessions/**/session.v4.jsonl.zstd`（37 文件，zstd 多帧）
- **坑1**：`zstd.ZstdDecompressor().decompress()` 只拿第一帧（239 字节元数据）——
  必须用 `with dctx.stream_reader(fh) as r: data = r.read()` 才拿到全部（6.5MB/2371行）
- **坑2**：`session-bridge` 的 `/events` API 的 cursor/hasMore 无效——传 cursor 返回同样窗口，
  limit 也无效（固定 444 条）。**不能用它做全量统计**（第一次统计得到 11810 的重复计数假数据）
- 统计脚本逻辑：解压 → 逐行 json → `type=='tool/call'` → data.name 计数
