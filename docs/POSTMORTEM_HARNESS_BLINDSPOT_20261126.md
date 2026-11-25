# 深度复盘：harness 为什么没挡住插件破坏事故（2026-11-26）

## 一、事故根因回顾（已在 POSTMORTEM_PLUGIN_REPAIR_20261126 记录）
1. hardware-monitor 的 `cordis.patch.yml:9` 被改成 `name: '@local/dsh-hardware-monitor'`
   ——dsh 臆造的 bundle 名，解析器只认 package name
2. `node_modules/dsh-llama-server-autostart/` 源码被清空（只剩日志）

## 二、harness 没拦住的三层原因（现场证据）

### 层 1：破坏根本不在 harness 的监控视野内（决定性）
- dsh 会话 e22d97fd 完整事件流只有 **40 个事件、2 次工具调用，且都是 read**
  （统计工具分布：{'read': 2}），**没有任何 write/edit/bash 调用**
- 但同一时期产生了 3 次 `workspace/changes` 事件——内容只有 `{"turn":2}`，无变更详情
- 结论：破坏由**会话外的进程**执行——dsh 的插件管理器 / harness 的同步逻辑 /
  或另一个未被 bridge 记录的会话。**harness 的守卫只挂在 LLM 工具调用路径上，
  对 dsh 内部的插件管理操作完全看不见**

### 层 2：即使看见，守卫也不覆盖这两类破坏
- **危险操作分级**（index.mjs:248）：只匹配 shell 命令正则如 `/rm\s+-rf?\s+.../ `，
  dsh 用的是自己的插件安装/删除逻辑（非 shell 命令）→ 绕过
- **受保护目录概念不存在**：`node_modules` 在运行版 index.mjs 里只出现 **1 次**
  （:217 是个日志路径配置），没有任何"profile 配置/node_modules 写保护"逻辑
- **verify-on-edit 对 cordis 配置主动豁免**（`index.mjs:495-496`）：
  `(lower.endsWith('.yml')||'.yaml') && !lower.includes('cordis')`——为避免 `!!js` 标签误报，
  **cordis.patch.yml 直接跳过语法检查**。所以那个 bundle 名错误连语法检查都没走
- **危险操作分级是"软提示"不是门禁**（`index.mjs:205`、`1007`）：
  源码注释明说"不阻断，注入意识；真正拦截由 dsh approval policy 负责"。
  且 `classifyDanger(name, argsText)`（:267）的 name 参数在判断中未被使用——
  删除类工具若 argsText 为空或格式不符，会直接滑过（`index.mjs:1008-1034`）

### 层 3：三副本不同步让 harness 比想象中弱（隐藏放大器）
- 运行版 `node_modules/dsh-agent-harness/index.mjs` 与权威源 publish 同为 v2.26.6，
  但**实质差异 580 行**（忽略 CRLF 后）——运行版**缺少** S6 信号门、错误恢复剧本、
  tool_failure_healer 等 publish 已有的机制
- 项目铁律"文档宣称完成≠代码实际生效，三副本一致性反复不同步"再次应验
- 本次不是主因（危险守卫两边覆盖相当），但意味着"我们以为有的护栏，运行版可能没有"
- 子任务补充：运行版已装 `tool_failure_healer.mjs`（11-25 23:51 同步），
  它是**通用 JSON 解析重试器**——本事故的坏 bundle 名不引发 JSON parse 错误，
  所以这个"新机制"也完全用不上

## 三、更深层的架构问题：提示词铁律 vs 代码硬门禁
- 项目大量安全规则写在 AGENT_BRIEF / CAPABILITY_LADDER 提示词里
  （如"删 junction 用 fsutil reparsepoint delete"、"dsh 会话记录不等于全部真相"）
- 提示词只能约束**LLM 的显式决策**，约束不了：
  ① 会话外的自动化进程 ② 插件管理器的内部行为 ③ 语义级配置错误
- 这次事故是典型的"**提示词护栏挡不住系统性操作**"

## 四、补强方案（低成本、可验证）
### P0：profile 配置写保护（堵住"看不见"的问题）
- 对 `node_modules/*/cordis.patch.yml` 和 profile 的 `cordis.patch.yml`/`package.json`
  做**写入前后哈希快照 + bundle 名合法性校验**（`^[a-zA-Z0-9@/_-]+$` 且不以 `@local/` 开头）
- 触发点不应只在 LLM edit hook，而应在**文件监听层**（watch，捕获所有写入来源）
- 代价：一个后台 watcher + 规则；误报：低（bundle 名格式固定）

### P1：插件目录完整性门禁
- 维护权威源 manifest（publish 仓库），启动/插件变更后校验运行版关键文件存在
  （index.mjs/package.json/cordis.patch.yml/frame_limiter.py）
- 缺失即告警并从权威源恢复（POSTMORTEM_PLUGIN_REPAIR 的手工流程自动化）
- 代价：manifest 维护 + 启动校验；误报：低

### P2：三副本一致性 guard 常态化
- 已有 `tools/consistency_guard.py`，但这次运行版与 publish 差 580 行没拦住
- 把一致性校验纳入**启动门禁**而非"仅变更时提示"
- 代价：低（脚本已有）；误报：低

## 四·补 一句话本质
**harness 把"安全"建立在"LLM 会调用工具、且工具参数符合预期"这个假设上。
这次破坏既没有经过 LLM 工具调用，也是一个"语法合法、语义错误"的配置改动——
两个假设同时落空，所有提示词护栏集体失效。**

## 五、诚实边界
- 破坏操作的确切执行者**未能从会话记录确定**（events 里没有 write/edit/shell）
  ——这是证据缺口，不是"我猜是插件管理器"
- harness 的提示词护栏在某些场景仍有效（L0-L3/D1-D5 挡过很多早收尾），
  本次失效是**特定的"会话外操作 + 语义级配置错误"组合**
