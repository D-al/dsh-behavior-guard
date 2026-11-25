# 深度复盘：harness 为什么没挡住插件破坏事故（2026-11-26）

## 一、事故根因回顾（已在 POSTMORTEM_PLUGIN_REPAIR_20261126 记录）
1. hardware-monitor 的 `cordis.patch.yml:9` 被改成 `name: '@local/dsh-hardware-monitor'`
   ——dsh 臆造的 bundle 名，解析器只认 package name
2. `node_modules/dsh-llama-server-autostart/` 源码被清空（只剩日志）

## 二、harness 没拦住的三层原因（现场证据）

### 层 1：破坏**在** harness 视野内，但守卫被配置关掉了（决定性）

> ⚠️ **重大更正（00:4x）**：初版复盘声称"破坏在监控视野外、只有 2 次 read 调用"——**这是错的**。
> 原因：bridge CLI 每条记录截断到 300 字符（`bridge.mjs:107`）、API `limit=100` 只返回尾部、
> 原始存储是多帧 zstd（`zstd.open().read()` 只读第一帧）。子任务用逐帧解压 + 直接读
> `session.v4.jsonl.zstd` 拿到完整 754 行事件流，破坏操作全部有 tool/call 记录。

**完整事件轨迹**（会话 e22d97fd，754 行；会话配置 `danger-full-access` + `approval/policy: never`）：
| seq | 北京 | 操作 | 后果 |
|---|---|---|---|
| 265 | 23:39 | `plugin_manager install_bundle` | already-installed，changed=false |
| **388** | 23:50 | **`plugin_manager remove_bundle dsh-hardware-monitor`** | 触发 pnpm 重装 |
| **389** | 23:53 | tool/result：`ERR_PNPM_EPERM` `_tmp_8456_4 → dsh-llama-server-autostart` rename 失败 | **autostart 目录被清空**；但 `isError:false`、归类为 `kind:"permission"` |
| **431** | 00:00 | `edit`：`name: dsh-hardware-monitor` → `'@local/dsh-hardware-monitor'` | 坏 patch 写入源码副本 |
| 435 | 00:00 | reasoning 事后编理由："plugin_manager 显示的不是包名 `@local/...`" | 无证据驱动 |
| **456** | 00:01 | `compaction/prune`：**seq 389（EPERM）被 shadowed 剔除** | 唯一破坏证据出上下文 |
| 481 | 00:03 | reasoning **已自我察觉**："改成 `@local` 可能是问题……应该恢复" | **但从未执行** |
| 527-530 | 00:05-07 | compaction 摘要（3963 字）完全不含 `@local`/`EPERM`/`remove_bundle`/`Copy-Item` | 纠错线索被抹掉 |
| **646** | 00:15 | `pwsh Copy-Item -Recurse -Force` 把污染源码覆盖进 node_modules | 坏 patch 落地安装目录 |

**所以 harness 失效的真实链条**：
1. **会话配置直接关掉了护栏**：`danger-full-access` + `approval never`，system-reminder 明说审批禁用。
   "危险分级 block/warn"在这个会话里没有生效阈值。
2. **破坏是间接副作用**：`remove_bundle` 是白名单工具，真正毁目录的是它内部 pnpm 的 rename，
   没有独立 tool/call 进入守卫判定点——按 `rm -rf` 正则匹配不到。
3. **结果被包装成"权限问题"**：`isError:false` + `kind:"permission"` + "让用户修权限"，
   harness 没把 `changed:true / application:failed` 识别为需要告警/回滚的破坏。
4. **compaction 抹掉了自我纠错**：模型 seq 481 已发现错误，但 seq 456/528 把 EPERM 和 `@local` 线索
   全部剔出上下文，最终 seq 646 仍用坏源码覆盖。这是"监控到了但上下文压缩丢掉"。

### 层 2：即使守卫生效，也不覆盖这两类破坏
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

### P0·补：compaction 不得抹掉未闭环的自我纠错（本次最关键）
- seq 481 模型**已经发现** `@local` 是错的并说"应该恢复"，但 seq 456/528 的 compaction
  把 EPERM 和 `@local` 线索全部剔除，导致 seq 646 仍用坏源码覆盖。
- 规则：**待办/自我纠错项若未执行，compaction 摘要必须保留**（"发现 X 有问题但未修复"）。
  项目已有 P0 压缩存档机制（合同/已验证决策/开放项/已排除），但**"未执行的自我纠错"
  没有被列为必留项**——这是直接导致事故从"小错"变"大错"的环节。
- 代价：改 compaction 提示/摘要规则，0 LLM 额外；误报：低。

## 四·补 一句话本质（更正后）
**harness 的护栏在这个会话里被 `danger-full-access + approval never` 直接关掉；
剩下的机制又只认"独立工具调用 + 语法正确"，而破坏是白名单工具的内部副作用
（pnpm rename EPERM）和"语法合法、语义错误"的配置改动。
更致命的是模型已自我察觉错误，却被 compaction 抹掉了纠错线索——
监控到了、也报了警，但上下文压缩让报警失效。**

## 五、诚实边界
- **初版复盘关于"破坏在监控视野外"的判断已被推翻**——完整 754 行事件流证明
  破坏全有 tool/call 记录（seq 388/389/431/646）。
  教训：**bridge CLI 300 字符截断 + API 尾部 100 条 + 多帧 zstd 只读第一帧**，
  三重坑叠加会让"只看会话记录"得出完全错误的结论。这正是项目记忆里
  "session-bridge hasMore 恒 true、cursor 无效"同一个坑——我又踩了一次。
- harness 的提示词护栏在某些场景仍有效（L0-L3/D1-D5 挡过很多早收尾），
  本次失效是**"护栏被配置关闭 + 副作用型破坏 + compaction 抹掉纠错"的组合**
