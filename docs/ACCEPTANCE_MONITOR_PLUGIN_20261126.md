# 验收报告：dsh 硬件监控插件开发（2026-11-26 15:10）

> 角色：独立验收（只读）。**未修改任何插件代码**——遵守用户"不要直接帮它干活"的约束。
> 数据来源：逐帧解压会话 `session-a91afe6d` 完整事件流（1425 事件）+ 磁盘产物 + app.asar 实证。

## 一、进度结论：**没做完，卡在最后一步（左侧入口不显示）**

会话 14:57 `turn/end completed`，但结束方式是"让用户去 F12 控制台粘代码"——
把诊断甩给用户，**任务未闭环**。

## 二、用户目标演进（会话里四次漂移）

| 时间 | 用户诉求 | 状态 |
|---|---|---|
| 13:07 | 一打开插件就崩溃，分析 crash log | ✅ 已修（见下） |
| 13:20/14:22 | 左侧要有可点进去的入口 | ❌ **未达成** |
| 13:36 | 页面 ERR_CONNECTION_REFUSED | ✅ 已修（改用根路径） |
| 14:57 | （会话自行结束）让用户在 F12 粘代码 | ⚠ 未完成 |

## 三、验收项逐条

### ✅ 通过 1：8999 EADDRINUSE 崩溃已修
`server/index.js:204-214` 有 `server.on('error')` 且对 EADDRINUSE 做 port++ 重试。
实测：`curl localhost:8999/` = 200，`/api/stats` = 200。
`impl.js` 的 `inject:['logger']` 也已移除（改为 `ctx.logger ?? console`）。

### ✅ 通过 2：UI 破坏已修（相比上午）
client.js 从"100vh 全屏 iframe 塞 `conversation.composer.dock`"（导致白屏）
改成 **40×40 小图标按钮**，注入 `sidebar.right.header.actions`，order 50。
方向正确，不会再撑爆布局。

### ✅ 通过 3：双副本同步
工作区 `default-workspace/hardware-monitor-plugin/` 与安装目录 `node_modules/dsh-hardware-monitor/`
三个文件（client.js / server/index.js / server/impl.js）sha256 完全一致。

### ❌ 失败 1（致命）：入口 slot 是无效的——这就是"左边没入口"的原因
- client.js 注入的是 **`sidebar.right.header.actions`**
- 我在 `D:/Deepseek Harness/resources/app.asar` 里 grep 所有 `sidebar.right.*` slot，
  **没有 `header.actions`**。真实存在的有：`sidebar.right.pane.tab`(129)、
  `sidebar.right.tab.guide.actions`(29)、`sidebar.right.tab.guide.entry`(22)、
  `sidebar.right.tab.menu.item`(21)、`sidebar.right.pane.tab.title`(77)、`sidebar.right.toggle`(8) 等。
- **它自己在 seq1402 已经承认**："`sidebar.right.header.actions` 不是 DSH 内置的 slot，注册被静默忽略"
  ——但 client.js 至今仍是这个无效 slot（14:02 写入后未改）。
- 结论：**注册被静默忽略，按钮永远不显示**。这是任务失败的直接原因。

### ⚠ 问题 2：`/ui` 路由是 404，但 client.js 点击开的是根路径（200）
- `/ui` = 404（服务端没注册该路由）
- client.js 的 onClick 用 `window.open('http://localhost:8999/')`（根路径，200）
- 所以点击能打开仪表盘——这部分侥幸对了，但 impl.js:55 的日志还写着
  "Dashboard available at .../ui"（404），说明代码里路径认知不一致。

### ⚠ 问题 3：会话后期陷入重复探测循环（harness 自己报了 6 次）
13:20-14:57 期间 harness 反复提示：
- "read ×4 重复"、"grep ×3 超时"、"pwsh ×6"、"glob ×5 超时"
- "任务存档"压缩了至少 5 次，每次都把"查找可用 slots"列为开放问题
- 最后靠"让用户去 F12 粘代码"收尾——典型的**放弃式完成**

## 四、问题诊断（为什么没达到预期）

1. **不会找 slot**：它反复用 `glob **/*.js` 扫 app.asar（二进制打包文件，扫不出源码），
   正确方法是对 asar 做字符串扫描（我这次用的 `grep -ao` 直接命中 12 个真实 slot）。
2. **自我承认问题但不修**：seq1402 明确说 slot 无效，却没有回头改 client.js——
   这是 harness"说归说、做归做"的老问题（今天第 N 次）。
3. **目标漂移 + 压缩丢线索**：四次目标切换，每次压缩都把"左侧入口"这个真实目标
   挤到次要位置，转向"崩溃修复"和"ERR_CONNECTION_REFUSED"。
4. **验证缺失**：它写 client.js 后只做了语法检查（还因为相对路径报了 4 次 Cannot find module），
   **从未验证 slot 是否真的存在**——如果验证一步，当场就能发现 slot 名错。

## 五、给 dsh 的改进建议（只建议，不动手）

1. 把 client.js 里的 `sidebar.right.header.actions` 换成 app.asar 里真实存在的 slot，
   例如 `sidebar.right.pane.tab`（129 次引用，最通用）或 `sidebar.right.tab.menu.item`。
2. 注入后加验证：grep app.asar 确认 slot 名存在，而不是靠猜。
3. 把 impl.js 的 `/ui` 日志改成实际可用的根路径 `/`。
4. 避免"让用户去 F12 粘代码"这种未完成交付——要么自己验证，要么明确说"卡在哪里、需要什么"。

## 六、诚实边界
- 我没在 DSH Web GUI 里实际点击验证（只读约束 + 不操作 UI）——slot 无效是基于 app.asar 字符串证据的强推断
- app.asar 里的 slot 名出现次数不等于"该 slot 可用于第三方插件注入"——需要 DSH 文档或实际测试确认
- 8999 服务的 port++ 重试代码我看过但没做故障注入测试
