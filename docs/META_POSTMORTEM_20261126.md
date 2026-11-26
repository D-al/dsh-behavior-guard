# 元复盘：2026-11-26 五起事故的共同模式与防线体系

## 一、今天发生了什么（五起，同一个根源的不同表现）

| # | 事故 | 直接原因 | 本质 |
|---|---|---|---|
| 1 | bundle 名被改成 `@local/` + autostart 目录清空 | dsh 臆造配置 + pnpm EPERM 副作用 | 自我修改 |
| 2 | 会话自己停（disposed） | dsh 把核心 bundle `dsh-base` 写重复 | 自我修改 |
| 3 | dsh 崩溃弹窗 + 退出资源不掉 | hardware-monitor 反复 enable 触发 8999 EADDRINUSE | 自我修改 + 清理缺陷 |
| 4 | 会话白屏 53% | 上下文卡 54K + 看门狗 120s 误杀 prefill | 参数失配 |
| 5 | **会话窗口全白**（本次） | dsh 写的 `client.js` 把 100vh iframe 注入输入框 dock | **自我修改（宿主 UI）** |

**共同模式**：**用户让 dsh 修/改 dsh 自己运行所依赖的东西**（插件、配置、宿主 UI）。
dsh 既是执行者，又是被修改系统的运行实例——改坏了，它自己和用户界面一起坏，
用户失去观察与交互能力，只能靠外部恢复。

这不是"某个守卫没写好"，是**架构级的自我修改危险区**。

## 二、为什么现有三道防线挡不住第 5 起

三道防线（plugin_guard / compaction 纠错 / 副作用识别）全是**配置层 + 语义层**的：
- 查 bundle 名合法性 ✓
- 查关键文件存在 ✓
- 查 bundles 数组重复 ✓
- **但没有查"客户端 UI 组件注入了什么 slot、多大尺寸"** ✗

第 5 起的破坏在 `client.js`（前端注入代码），既不是 bundle 名也不是配置文件缺失——是**行为型 UI 破坏**，
现有规则完全看不见。

而且这次 harness 其实**报过警**：
- seq 556：「你声称写入 ./client 但文件不存在」
- seq 573：「刚写入的文件有语法错误：Cannot find module ...」
但警告只是 pendingInject，模型继续试、继续写错，最后写了个"语法合法但布局破坏"的版本落地。

## 三、以后如何避免（分层，按 ROI）

### 原则：不靠提示词，靠代码；不靠模型自律，靠外部校验

### 第 1 层：识别"自我修改"任务，强制走隔离流程（最重要，零代码）
**判据**（出现任一即是危险任务）：
- 任务目标涉及 dsh 自身：`修复 dsh插件` / `改 dsh 窗口` / `修 dsh 配置` / `dsh 侧边栏`
- 修改目标位于：`profiles/desktop/` 的 package.json / cordis.patch.yml /
  `node_modules/dsh-*` / `app.asar` / 任何 `client.js` / UI 组件

**规则**：这类任务**不许在运行的 profile 上直接做**。
- 在隔离副本（`D:/Brain/workspace/sandbox-profile/`）改 + 验证
- 人工确认后，再由外部脚本同步到生产 profile
- 理由：dsh 正在用这些东西运行，改坏=当场自毁（今天已证 5 次）

### 第 2 层：plugin_guard 加"UI 注入守卫"（规则5，~30 行）
扫描 profile 下所有 `client.js` / `*.client.js`，检查注入模式：
```
禁止项：
- inject 到 conversation.composer.dock 且组件含 height:'100vh' / position:'fixed'
- order <= -100（抢占级）且非白名单
- iframe src 指向根路径 '/ui/' 之类不存在的路由
```
命中 → 自动把 client.js 替换为停用版（已有 `client-disabled.js` 模板）+ 告警。
这是这次事故的直接补丁，成本极低。

### 第 3 层：给"写 client.js"加专用的落盘后校验
harness 的 verify-on-edit 现在只做语法检查。对 client.js 类 UI 文件，
加一条**结构检查**：注入的 slot 是否在允许列表、尺寸是否受限。
但注意：这只是提示，挡不住 full-access——真正的门禁还是第 1、2 层。

### 第 4 层：恢复能力（已有，要固化）
- 每次改 UI/插件配置前自动快照（今天的 `client.js.broken-ui` 备份救了场）
- 一键恢复脚本：从备份/权威源还原 client.js + patch + package.json
- 看门狗阈值 300s（已改）+ 重启脚本等 8999（已改）

### 第 5 层：观察性
- client.js 变更后，trace 记录 hash + 注入 slot + 尺寸
- 白屏时第一时间查 client.js，而不是先看 prefill/显存（我今天绕了一大圈）

## 四、一句话结论

> **不要让 dsh 修改它自己正运行在上面的东西。**
> 这不是某个守卫的问题，是"自我修改"这个任务类别本身的架构危险。
> 处理方式：识别 → 隔离 → 外部校验 → 可恢复。提示词护栏在 full-access 下无效（今天已证 5 次）。

## 五、今天已有的防线（累积）

1. **plugin_guard.py**：bundle 名 / 关键文件 / bundles 重复 / 变更哈希（规则1-4）
2. **client-disabled.js**：UI 破坏时的安全替代模板（本次新增）
3. **compaction 纠错保留**：防止压缩丢自我纠错
4. **副作用识别**：pnpm EPERM 等破坏性信号
5. **restart_dsh.ps1**：等 8081+8999 释放、强杀残留 llama
6. **freeze_watch.py**：阈值 120→300s，避免误杀 162s 的 prefill
7. **五份 POSTMORTEM**：每起事故的精确证据链

## 六、诚实边界
- 第 1 层"隔离流程"是纪律不是代码——靠人执行，可能失效
- 第 2 层 UI 注入守卫尚未实现（本文件是方案，下一步才落地）
- "自我修改危险区"是我从 5 起事故归纳的模式，不是 dsh 官方定义
