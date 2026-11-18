# 外围能力调研（2026-11-18 凌晨）

> 问题：还能给这个本地 35B 赋予哪些"外围能力"（连接器 / MCP / 其他）？
> 结论先说：**不接 MCP，把外围能力做成 Skills**。下面是证据与替代方案。

## 一、MCP 生态现状（2026-11）

- PulseMCP 索引 **20,115 个 MCP server**（2026-07）；90% 走本地 stdio（数据不出本机）
- 独立测评的共识是 **3~6 个服务器**，而不是"越多越好"
- **客户端约 40 个工具后开始退化**（Cursor 有记载的约 40 硬限；超出后工具在设置里可见但对 agent 静默消失）
- 每个工具定义**每次请求都在上下文里**：轻量 server ~400 token/轮，重量级 3,500+/轮
  - GitHub MCP 默认 **42 工具**；Playwright 默认 23（全开 68）；三件套默认合计 **67 工具 > 40 上限**
- **"我连了 12 个 MCP，agent 变笨了"**是社区真实投诉

## 二、本地小模型的额外约束（这是决定性的）

mcptrove 针对**本地 LLM** 的专门分析：

> "A quantized 7B running on your own GPU has a smaller effective context and weaker
> instruction-following, which means it picks the wrong tool, invents arguments, or loops.
> The fix isn't a smarter server — it's fewer, clearer tools."

本地短名单只推荐三个：**Anyquery**（用 SQL 查文件/DB/40+ 应用）、**Git reference server**、
**GitMCP**（把 GitHub 仓库变成实时文档，治"编造 API"）。

## 三、我们的实测数据（决定性）

| 指标 | 数值 |
|---|---|
| 当前工具面 | **28 个**（已接近 40 退化线）|
| 单个真实会话（71 步）实际调用 | **11 个**（ask_user_question/edit/glob/list_agents/present/pwsh/read/todo_write/web_search/write + 一次 web_fetch）|
| 零调用工具 | **17 个** |
| dsh 的 MCP 支持 | **无**（cordis.patch.yml 无 mcp 节点，基础包无 mcp 服务）|

⇒ 加 MCP = 在 28 个之上再加 12~42 个定义，**直接跨过 40 线**；而 BFCL 实测 20+ 工具时准确率
已降到 65~78%，38% 的错误是参数填错。**这是负收益。**

## 四、外围能力怎么做（替代方案）

### 1. Skills（已落地，正确载体）
过程性知识按需加载，**不占工具面**。已有 5 个：release-plugin / debug-llama-server /
verify-artifact / web-fetch / git-workflow。
- 社区依据：Keyhole 白皮书把 Skills 列为核心层——"只在相关时加载的过程性知识"
- 扩展方式：遇到"这类任务总是同一套步骤"，就沉淀一个 skill（成本：一篇 md）

### 2. 给已有工具补能力（比新增工具便宜）
| 缺口 | 现状 | 低成本方案 |
|---|---|---|
| **网页正文抓取** | `web_fetch` 不可用（无 provider），只有搜索摘要 | **web-fetch skill**：python urllib + 正则提正文（已写）|
| 结构化数据查询 | 只能 read 文件 | python 解析（csv/json/yaml），必要时 sqlite3 模块 |
| 图片理解 | 有 `read_image` | ✓ 已有 |
| 联网搜索 | SearXNG ✓ | ✓ 已有 |

### 3. 工具面裁剪（真正的"扩容"）
社区一致：**减少工具 > 增加工具**。我们 28 个里有 17 个零调用。
- 计划：用 `bench/trace_report.py` 积累一周的工具调用分布 → 把确认零调用的静态 disable
  （`cordis.patch.yml` 的 preset plugins 逐条 disabled）
- 目标：**工具面降到 18~20 个**，把省下的 context 让给上下文/思考
- 风险：低频但必需的（spawn_teammate / wait_agent / read_image / skill）不能盲目裁——
  用 trace 数据 + 一次真实任务回归来确认

### 4. 明确不做的
- **MCP 服务器**：dsh 不支持 + 工具面已满 + 本地模型更怕工具膨胀（三重否决）
- **向量数据库记忆**：35B 的检索判断力撑不起 embedding 检索的质量门槛
- **浏览器自动化**（Playwright 类）：23 个工具，本地跑不动（显存/延迟），且我们不需要
- **GitHub MCP**：42 工具——想用 GitHub 就让用户在网页/Git Bash 操作

## 五、如果将来要接 MCP 的前置条件

1. dsh 支持 MCP（上游）
2. 工具面先降到 ≤20
3. 只接 **≤2 工具**的薄服务器（如 Context7 式文档检索），且要有"按需加载 schema"的机制
   （Claude Code 的做法：工具 schema 延迟到真正需要时才注入）

三条都满足之前，**不动**。
