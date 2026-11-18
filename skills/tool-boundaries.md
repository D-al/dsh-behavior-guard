---
name: tool-boundaries
summary: 工具语义边界表——相似工具怎么区分（glob/grep/es/read/pwsh），减少"挑错工具/填错参数"
keywords: [工具选择, glob, grep, es.exe, read, 找文件, 找内容, 参数填错, tool]
---
# 工具语义边界表

> 依据：BFCL 测试中工具 4→51 个时选择准确率 43%→2%；38% 的错误是**参数填错**而非选错。
> 工具描述相近时模型会在几个"看起来都行"的选项间摇摆——**用语义边界代替罗列**。

## 找东西：四类工具各管一类

| 需求 | 用 | 不用 |
|---|---|---|
| **找某个文件名**（知道名字或部分名字）| `es.exe "关键词"`（全盘秒级）| 不用 glob `**/`（不穿 junction）、不用 GCI 递归 |
| **按路径模式找**（`bench/*.py`）| `glob "bench/*.py"` | 不找 junction 内深层（`p/` `memory/`）——glob 不穿 junction |
| **找文件内容**（知道里面有什么词）| `grep "关键词" <路径>` | 不用 es（它按文件名索引）|
| **读已知路径** | `read <短相对路径>`（直接读，不要先 glob 确认）| 不用 70+ 字符绝对路径（复述 0/5）|

**判断口诀**：*名字 → es；路径模式 → glob；内容 → grep；已知就直接 read。*

## 执行 / 查询

| 需求 | 用 | 注意 |
|---|---|---|
| 跑命令 | `pwsh`（唯一正确 id）| 沙箱无 dsh/git/npm/node；UTF-8 前置 |
| 问用户 / 给选项 | `ask_user_question` | 别在正文里"请问…"然后结束 |
| 展示交付物 | `present` | 是**交付声明**不是验收——先验收 |
| 看图片 | `read_image` | 不要只读路径说"看不到"|
| 加载手册 | `skill` | 干活前先看有没有对应技能 |
| 子智能体 | `send_message` / `list_agents` | 验收员/审计员用 |

## 参数纪律（填错比选错更常见）

1. `pwsh` 的 `command` 参数是**字符串**，不是数组。
2. `read`/`edit` 的 `file_path` 用短相对路径（`memory/x.md` / `bench/x.py` / `p/bench/x.py`）。
3. `todo_write` 的 `todos` 是**数组**，每项含 content/status；一次写完整清单。
4. `glob` 的 pattern 不含前导 `./`；不在 junction 里递归。
5. 不确定参数格式 → 先看同类工具调用的历史成功样例，不凭记忆拼。

## 与 Skills 拓扑的关系

本表是"常驻的语义路标"（短、只讲边界）；具体流程在各自 skill 里（按需加载）：
- 发布 → `release-plugin` / 调试引擎 → `debug-llama-server` / 验收 → `verify-artifact`
- 抓网页 → `web-fetch` / git → `git-workflow` / 会话复盘 → `session-debug`
- 插件调试 → `harness-debug` / 工具边界 → 本文件
