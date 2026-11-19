# 周期性 cmd 窗口闪现：根因与修复（2026-11-19）

> 用户报告：机器每隔一段时间弹几个一闪而过的命令行窗口，不管在干什么。
> 结论：`learn_watcher.py` 的 `run_script()` 用 `python.exe` 起子进程时没设 `CREATE_NO_WINDOW`。

## 一、排查过程（三条线）

1. **计划任务**：列出所有启用的计划任务，按 LastRunTime 排序。根路径任务里 `WpsUpdateTask_Ad`（每小时）、
   `SogouExplorer Updater`（每2小时）有周期触发，但都是 GUI 程序，不是 cmd 窗口。
   `RestartDsh` 手动触发，不周期。
2. **启动项**：Startup 文件夹有 `FreezeWatch.vbs` 和 `LearnWatch.vbs`；注册表 Run 项均为 GUI 程序。
   两个 VBS 都用 `pythonw.exe` + `sh.Run(..., 0, False)`（隐藏窗口），本身不弹窗——**排除启动器**。
3. **脚本内部 subprocess 调用**（真正根因所在）：
   - `freeze_watch.py`：`nvidia-smi` / `powershell` 调用**都带** `creationflags=NOWIN`（L52/56/67/75）✅
   - `learn_watcher.py`：`PY = D:\Python\python.exe`（非 pythonw），`run_script()` 的
     `subprocess.run()`（L109）**没有** `creationflags` ❌

## 二、根因

`learn_watcher.py` 常驻运行（Startup 的 `LearnWatch.vbs` 用 pythonw 无窗口启动），
但**每 30 秒一轮**调用 `mind_state.py --json` 等脚本，每 20 轮（≈10 分钟）加跑 5 个索引/诊断脚本。

每次 `subprocess.run([python.exe, ...])` 都会：
- 创建一个**可见的控制台窗口**（因为父进程 pythonw 无控制台，子进程 python.exe 会新建一个）
- 脚本瞬间结束 → 窗口一闪而过

**完全吻合用户描述**："每隔一段时间弹几个一闪而过的命令行窗口"——
每 30 秒弹 1 个，每 10 分钟一口气弹 5~6 个（deep 巩固层）。

## 三、修复

### 3.1 代码（两处副本都改，避免"只改 bench 没同步权威仓库"的坑）
`tools/learn_watcher.py` + `D:/Brain/workspace/bench/learn_watcher.py` 的 `run_script()`：
```python
flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
r = subprocess.run(cmd, ..., creationflags=flags)
```
SHA256 已核对两版一致。功能验证：`run_script('mind_state', ['--json'])` 正常返回结果。

### 3.2 运行态
- 杀掉旧 watcher（加载旧代码），用**无窗口计划任务** `LearnWatchDaemon` 重启（pythonw.exe + 登录触发）。
- 保留 `LearnWatch.vbs` 会与计划任务双实例 → 改名为 `LearnWatch.vbs.disabled`（可逆，避免重复记账）。

## 四、验证

- **功能**：watcher 跨 40 秒稳定运行，日志每 30 秒一轮（19:26:27 / 19:26:57 / …）✅
- **弹窗消除**：连续采样 70 秒（覆盖 2 个完整周期），新增 conhost 窗口进程 = **0** ✅
  （修复前每次 `python.exe` 子进程都会创建 conhost）
- **单实例**：`pythonw.exe ... learn_watcher.py` 进程数 = 1 ✅

## 五、为什么会这样（教训）
`pythonw.exe`（无窗口）启动的守护进程，内部再 `subprocess.run(python.exe)` 时，
Windows 会给子进程新建控制台——**父进程无窗口不等于子进程无窗口**。
守护进程里起子进程必须显式 `CREATE_NO_WINDOW`（与 freeze_watch.py 的做法一致）。

> 遵循知识资产沉淀规则：排查三条线、根因、修复、验证证据都留档。
