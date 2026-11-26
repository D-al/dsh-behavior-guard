# 复盘：dsh 崩溃弹窗 + 会话空白 + 退出后资源不掉（2026-11-26 12:3x）

## 症状（用户截图 + 补充）
1. 插件页报错：`启用失败: client api: pluginManager/setBundleEnabled failed: Failed to fetch`
2. 弹窗：`DeepSeek Harness 无法使用 / 应用无法启动或已意外停止`，提示"有其他正在运行的 DSH"
3. 会话窗口一片空白（显示"缓存... 53%"）
4. 用户补充：**"我尝试过重启 dsh，但退出 dsh 后内存和显存占用都不掉"**

## 根因（crash 日志 + 进程树实证）

### 直接致命错误：EADDRINUSE :::8999
crash 日志 `crash-2026-11-26T04-32-16-554Z-host.log`：
```
dsh: fatal uncaught exception: Error: listen EADDRINUSE: address already in use :::8999
    at Server.listen (node:net:2562)
    at dsh-hardware-monitor/server/index.js:215
    at HardwareMonitorServer.start (...index.js:154)
    at [cordis.init] (...impl.js:52)
```
- 8999 是 hardware-monitor 的 HTTP 端口
- 用户的 enable/disable 操作历史显示 04:30/04:31/04:32 连续反复切换 bundle
- 每次 enable → server.start() 想 listen 8999 → 旧实例还占着 → EADDRINUSE → **fatal uncaught exception → 整个 dsh 退出**

### 为什么"退出后内存显存不掉"——孤儿 llama-server
进程树（崩溃时）：
```
19636 (shell) → 11160 (host, --expose-internals) → 6588 (llama router) → 18408 (模型实例, 21GB + 7735MiB 显存)
```
- llama-server 用 `detached:true` + `unref()` 启动（autostart index.mjs:686-692）
- **dsh 崩溃时 disposer 根本跑不到**（fatal exception 直接退出）
- detached 的 llama 实例变孤儿 → 21GB 内存 + 7.7GB 显存不释放
- 用户"重启"只杀 dsh 进程 → 孤儿 llama 还在 → 显存/内存不掉
- 新 host 启动 → hardware-monitor 又想 listen 8999 → 旧 host/实例的端口残留 → EADDRINUSE 循环

### 次要错误（warning，非致命）
`llm-deepseek-account: models is no longer configurable` —— 账户插件配置格式过时，只 warning 不致命。

## 修复过程
1. 查证：确认只有一个 dsh 实例（11160 是 19636 的 host 子进程，不是两个独立 DSH）
2. 确认 llama 进程树与显存归属（nvidia-smi：18408 占 7735MiB）
3. 用加固版 `restart_dsh.ps1` 重启 → 新 bridge pid 12648、8999 正常返回 HTML、8081 健康

## 加固（已落地）
`D:/Brain/workspace/bench/restart_dsh.ps1`（纯 ASCII，PowerShell 5.1 兼容）：
- 原有：`Stop-NamedProc llama-server` + 等 8081 释放
- **新增**：
  1. 停 llama 后等 2s **二次检查**，残留的用 `taskkill /PID /T /F` 强杀
  2. 等待端口从"只 8081"扩展为 **8081 + 8999 都要释放**
  3. 注释说明 EADDRINUSE 8999 的因果

## 如何避免
1. **不要用 UI 的退出/重启按钮**（崩溃时 disposer 跑不到）→ 用计划任务 `RestartDsh`（走加固脚本）
2. **不要反复 enable/disable hardware-monitor**（操作历史显示连续切换，每次都触发 listen 8999）
3. **插件 server 的 listen 应加 SO_REUSEADDR / 容错**：EADDRINUSE 不应是 `fatal uncaught exception`——
   这是 hardware-monitor 插件 `server/index.js:215` 的设计缺陷（未 catch listen error），
   而 dsh 把未捕获异常升级为 fatal。理想修法：插件侧 catch EADDRINUSE 并降级为 warning（不致命）
4. **autostart disposer 对 detached 进程不可靠**：正常路径 `taskkill /T /F` 有效，但崩溃路径无解——
   真正的兜底是独立进程看门狗（已有 freeze_watch.py 但只监控"冻死"，不监控"孤儿显存"）

## 诚实边界
- 我没有直接观测到"退出 dsh 那一刻 llama 变孤儿"的完整时序——是从进程树（detached llama 是 host 的孙进程）
  + 崩溃日志（fatal 跳过 disposer）+ 用户观察（资源不掉）推断的强证据链
- 8999 的旧占用者在新 host 启动时是否已退出，无法从当前状态回溯（现在已被新实例正常占用）
- llm-deepseek-account 的 warning 未处理（非致命，且不在本次任务范围）
