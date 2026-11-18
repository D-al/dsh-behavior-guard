# 脑的地图 —— dsh 本地智能体的全部构成物（2026-11-17 状态）

> 分散在三个位置是 dsh 的加载机制决定的（插件必须在 node_modules、配置必须在
> profiles\desktop、系统提示必须在 .dsh）——**物理整合不可行**，本地图 + 快照脚本
> （snapshot_brain.py）就是整合的形式。

## 层 1：引擎与权重（不动层）

| 构成物 | 位置 | 说明 |
|---|---|---|
| llama-server.exe | `D:\llama.cpp\build\bin\` | 自编 b12244（含 autoparser 补丁） |
| 模型权重 Q4 21.3GB | `D:\GGUF_Download\Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf` | router 模式按需加载 |
| 计划任务 RestartDsh | Windows Task Scheduler | 重启 dsh host 的标准入口 |

## 层 2：配置（`C:\Users\Ad\.dsh\`）

| 构成物 | 职责 |
|---|---|
| `AGENTS.md`（12.3KB/3405 token） | 系统提示：14 项规则（锚点路由/es.exe/短路径/todo 协议/CritBank/路由表/候选协议/验收协议/角色章程/注入防护/工具指引） |
| `profiles\desktop\cordis.patch.yml` | 插件挂载 + 工具裁剪（tool-jobs disabled）+ 压缩参数 |
| `profiles\desktop\.env.llama` | 引擎参数（CTX 98304/NGL 99/NCMOE 40/预算 4096/模板路径…） |

## 层 3：插件（`C:\Users\Ad\.dsh\profiles\desktop\node_modules\`）

| 插件 | 职责 | 状态 |
|---|---|---|
| **dsh-behavior-guard**（36KB） | 行为治理全家桶：L0-L3 早收尾拦截 + D1/D2/D3 信号 + 周期审计（自适应窗口）+ 纠正器 + 代执行 + 代验收 + todo 观测 + 共享注入预算 | 26/26 单测迁移 ✓ |
| **dsh-task-continuity**（7.6KB） | P0 压缩存档 + P1 todo 闹钟 | 三场景验证 ✓ |
| **dsh-llama-server-autostart**（39KB） | llama-server 进程管理（收养/退出清理） | 生产运行 |
| ~~dsh-turn-continuation-guard~~ | 已合并入 behavior-guard（文件保留可回滚） | 剔除 |
| ~~dsh-reason-guard~~ / ~~dsh-search-budget~~ | 场景被 D1/task-plan 覆盖（文件保留可回滚） | 剔除 |

## 层 4：模板（`D:\WorkBuddyWorkSpace\2026-10-13-20-41-43\bench\`）

| 构成物 | 职责 |
|---|---|
| `chat_template_zh.jinja`（19KB） | 思考锚点「嗯，我需要」/ 失败标注[已排除] / is_stub 防退化 / tool_response 定界 / 同字标注 |

## 层 5：工具与门禁（同上 bench\）

| 构成物 | 职责 |
|---|---|
| `regression_check.py` | **27 项回归门禁**（改动后必跑，全绿才算上线） |
| `audit_session.py` | 会话审计员（浪费/跑偏/假完成/重复/根因） |
| `verify_agent.py` | 三态产物验收（环境级，PASS/FAIL/INCONCLUSIVE） |
| `auto_review.py` | 自动复盘（扫描新会话→CritBank 候选，HITL） |
| `snapshot_brain.py` | 本文件清单的一键快照/恢复 |
| `entropy_probe.py` / `speed_probe.py` / `tool_audit.py` | 熵/速度/工具面探针 |
| `test_turn_guard.mjs` | behavior-guard L0-L3 单测（26 项） |
| `configs/` | 历史快照与配置版本 |

## 层 6：记忆（`D:\WorkBuddyWorkSpace\2026-10-13-20-41-43\.workbuddy\memory\`）

每日日志（YYYY-MM-DD.md）+ CritBank 9 条（在 AGENTS.md 内）。

## 依赖关系

```
llama-server(引擎) ←─ .env.llama(参数) ── chat_template(模板)
      ↑ autostart 插件管理
dsh host ←─ cordis.patch.yml(挂载) ←─ node_modules(插件实现)
   ↑ AGENTS.md(系统提示)
会话产物 → sessions/*.jsonl → auto_review/audit_session → CritBank(AGENTS.md)
snapshot_brain.py ──快照──> bench/configs/brain-*/
```
