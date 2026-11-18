# “这个脑”全面盘点与架构优化报告（2026-11-18）

> 范围：`D:/Brain/**`（engine / dsh-data / workspace / publish / appdata）+ junction 映射 + 计划任务 + harness 插件。
> 目的：找出**进一步优化的空间（含架构层）**，并评估"给上游开 PR"是否值得。

---

## 一、资产地图（实测体积）

| 域 | 体积 | 内容 | 健康度 |
|---|---|---|---|
| `engine/llama-b12244-src` | **1005 MB** | 自编 b12244 源码 + build 产物 | ✓ 必要，但 build 中间物可清 |
| `dsh-data/dsh-runtimes` | 288 MB | dsh 内置 node runtime | ✓ 不动 |
| `appdata-local-updater/installer.exe` | 276 MB | **0.2.0-rc.2**（10-13，过期）| ⚠ 可清（升级时会重新下）|
| `appdata-local-pnpm-store` | 111 MB | pnpm 缓存 | ⚠ 含 33MB 旧日志 |
| `dsh-data`（其余） | ~7 MB | 7 会话 / 附件 / profile / plugins | ✓ 健康 |
| `workspace/bench` | 78 MB | 174 py + 41 mjs + 119 json + 167 临时文件 + 45MB 会话转储 + 16M 调优日志 | ⚠ **主要混乱源** |
| `publish/dsh-behavior-guard` | 2.5 MB | 63 文件 / Single Source of Truth | ✓ 已整理 |

**总量约 1.5 GB**，其中真正必要约 1.1 GB——**可优化空间约 400 MB**（主要是 build 中间物 + 过期 installer + 实验转储）。

---

## 二、五个架构级问题（按影响排序）

### A1. 存储层分裂：7 个 junction 指向 4 个物理根 🔴 最高

```
default-workspace/
  bench    → D:/Brain/workspace/bench
  memory   → D:/Brain/workspace/memory
  p        → D:/WorkBuddyWorkSpace/2026-10-13-20-41-43   ← 另一个工作区！
  dsh      → D:/Brain/dsh-data
  gguf     → D:/GGUF_Download
  llama    → D:/llama.cpp
  wb       → C:/Users/Ad/.workbuddy
```

**问题**：`p/` 指向 `WorkBuddyWorkSpace/<时间戳>/`——这是一个**带时间戳的会话工作区**，换机器/换会话就失效。
这是"一键开箱"最大的结构性障碍：脚本里的所有 `p/bench/xxx` 路径都绑死在这个时间戳上。

**优化方向**：
1. 把活跃脚本从 `WorkBuddyWorkSpace/<时间戳>/bench` **迁到** `D:/Brain/workspace/bench`（唯一真源）。
2. `p/` 改为指向 `D:/Brain/workspace`（稳定路径，无时间戳）。
3. 让 harness 库成为脚本的唯一副本（v2.4 已完成大部分），运行副本只从库 install。

**收益**：换机器/重装后只需建 4 个固定 junction，不用改任何脚本路径。**这是从"能跑"到"可移植"的关键一步**。

### A2. 配置四处维护，一致性只查两处 🔴

当前同一语义的配置散在：
| 位置 | 内容 | 一致性检查 |
|---|---|---|
| `config/env.llama` | 引擎参数 | ✓ `config_check.py` 比对 INI |
| `llama-router-preset.ini` | 路由/温度 | ✓ 同上 |
| `cordis.patch.yml` | 插件 config + contextWindow | ❌ 未纳入比对 |
| `AGENTS.md` | 行为协议 | ❌ 未纳入比对 |
| `skills/*.md` keywords | 技能触发词 | ❌ 未纳入比对 |

**优化方向**：扩展 `config_check.py` 为**全栈一致性检查**——至少加入：
- `cordis.patch.yml` 的 `contextWindow` vs `.env` 的 `CTX`
- AGENTS.md 里提到的 skill 名是否都存在（防止外置后死链）
- skill keywords 是否有空/重复（防止检索失效）

**收益**：这类"配置漂移"是隐性 bug 的温床（我们已抓到过 2 处 env/INI 真不一致）。

### A3. 注入链 1300 行单文件，无模块边界 🟡

`index.mjs` 现在承载 L0-L3 / D1-D5 / P0/P1/P1.5 / 控制回合 / Skills / CritBank / trace / JSON 重试 / 危险操作——**全部在一个文件里**。

**问题**：
- 加一个新机制要在 1300 行里找插入点（今晚加 G2 trace 时就踩过 state 漏初始化的坑）
- 无法单独测试某个机制（测试靠全局 emit 事件）
- 加载顺序/预算竞争隐式（sharedMaxPerTurn / 各机制自己的上限互相不知情）

**优化方向**：拆成模块（不需要改 dsh 接口，只是 Node 内部 import）：
```
index.mjs          ← 编排 + 配置
modules/
  guards.mjs       ← L0-L3 / D1-D5
  continuity.mjs   ← P0/P1/P1.5
  meta.mjs         ← 控制回合 / Skills / CritBank
  feedback.mjs     ← trace / 审计自校准 / 概率校准
  safety.mjs       ← 危险操作分级
```
**收益**：可维护性 + 可测试性 + 预算统一管理。**风险**：重构期可能引入回归——建议等 dsh 升级稳定后再做，且必须保持 26+40 测试全过。

### A4. 实验资产与生产资产混放 🟡（清理即可，零风险）

`bench/` 根有 **167 个 `_` 前缀文件**（19 py / 2 mjs / 89 json / 24 log / 10 jsonl / 13 txt），其中：
- **生产必需**：`_trace.jsonl` / `_compaction_ledger.jsonl` / `_agent_harness_loaded.json`（3 个）
- **大体积可归档**：`_cur*.jsonl` 8 个共 **45 MB**（会话转储）、`_projectlab_result.*` 系列
- **一次性实验**：`_obs1.py` / `_danger.py` / `_ctl.py` 等我今晚的临时脚本

**优化方向**：
```
bench/archive/experiments/    ← 89 json + 24 log + 13 txt
bench/archive/session-dumps/  ← _cur*.jsonl (45MB)
bench/moe-cache-tune-run/     → archive/  (16M)
bench/__pycache__/            → 删（1.4M，可自动再生）
```
保留 `_trace.jsonl` / `_compaction_ledger.jsonl` / 探针在原位（插件硬编码路径）。

**收益**：bench 根目录从 334 个文件降到 ~170 个，找生产脚本不再被实验产物淹没。

### A5. 自校准闭环空转 🟡（机制已装，数据未积累）

`_audit_feedback.jsonl` **不存在**——代码有写入逻辑（index.mjs:1478），但从没触发过。
意味着 G5 概率校准脚本（audit_calibrate.py）目前无数据可算。

**原因**：D5 审计门控在真实会话中触发次数少（我们大部分工作是 WorkBuddy 会话，不走 dsh harness）。

**优化方向**：不急着"造数据"——等真实 dsh 使用后自然积累。但可以做一件事：
让 `trace_report.py` 在报告里显示"审计反馈 N 条，不足以校准"的提示，避免误以为机制坏了。

---

## 三、开 PR 上游：值不值得？

### 我们的补丁内容（`config/patches/autoparser-fix.patch`）
两行修复 `chat-auto-parser-generator.cpp`：
- **444 行**：`format.per_call_start` → `p.optspace(format.per_call_start)`（允许前导空白）
- **473 行**：`p.until(trigger_marker)` → `p.until(trim_whitespace(trigger_marker))`（marker 前后空白不误判）

**症状**：工具调用标记前后有空白时解析失败（Qwen3.6 中文模板下必现）。
**本地已打**（源码 444/473 行确认），每次升级要重打。

### 上游状态
- **#29307 token-aware parsing**：未合并（62 commits），是大重构，**不会吸收我们的小修**
- 没有现成的针对这两行的 issue/PR（搜过）

### 判断：**值得开，但优先级中等**

| 维度 | 评估 |
|---|---|
| 修复正确性 | 高——两行都是防御性空白处理，不破坏现有行为 |
| 复现成本 | 中——需要写最小 chat template + 工具调用样例，证明"有空白时失败/修复后成功" |
| 维护收益 | 中——每次升级省 2 分钟手打；更重要的是**社区背书后不用再维护 patch 文件** |
| 风险 | 低——即使被拒也不影响本地（补丁继续留着） |

**建议**：先做 A1/A2/A4（本地收益确定），等 dsh 升级稳定后，再花半天写个 PR（含 repro + 测试）。
PR 标题建议：`common: tolerate whitespace around tool-call markers in tagged parser`。

---

## 四、优化清单（按 ROI 排序）

| # | 动作 | 成本 | 收益 | 风险 |
|---|---|---|---|---|
| **1** | 迁脚本到 `D:/Brain/workspace/bench`，`p/` 改指稳定路径 | 30 min | **可移植性质变** | 中（要改 AGENTS.md 路径约定 + 全测）|
| **2** | 归档 167 个实验文件 + 45MB 会话转储 + 16M 调优日志 | 10 min | 目录清爽、找文件快 | 低（保留 3 个生产 jsonl）|
| **3** | 扩展 `config_check.py` 为全栈一致性 | 1 h | 防隐性配置漂移 | 低 |
| **4** | 清 `__pycache__` + 过期 installer.exe（276M）| 2 min | 省空间 | 低 |
| **5** | `trace_report.py` 加"数据不足"提示 | 10 min | 避免误判机制坏了 | 无 |
| **6** | 拆 `index.mjs` 为 6 个模块 | 半天 | 可维护性质变 | **高**（必须全测 + 回放）|
| **7** | 给上游开 autoparser PR | 半天 | 社区贡献 + 免维护 patch | 低 |
| **8** | dsh 升到 rc.3（需 GUI） | 用户操作 | 新功能 | 中（4 个行为变化）|

**推荐顺序**：2 → 4 → 5 → 3 → 1 → 8 → 7 → 6。
（先做零风险的清理，再做可移植性改造，最后才动引擎/架构/上游。）

---

## 五、一句话总结

**这个脑的架构方向是对的（harness 外置 + append-only + 分层记忆），但"物理布局"还没跟上"逻辑架构"**——
7 个 junction 绑死时间戳、167 个实验文件混在根目录、配置四处维护只查两处。
这三件事解决后，它才真正从"一台机器上的精调系统"变成"可复制的脑"。
