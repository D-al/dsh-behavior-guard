# 事故复盘：session 备份脚本放错位置导致 workspaceController 不可用（2026-11-25）

## 症状
用户让 dsh "移除工作区内会话（备份）"后，添加工作区报错：
```
workspace create failed: gateway/service-unavailable: TypeError:
gateway: workspace/create: active Service "workspaceController" is unavailable
```
重启 dsh 多次无效。

## 排查走过的弯路（记录以便避坑）
1. 怀疑非法字符/配置损坏 → 逐项核实 `cordis.patch.yml`（11-24 未改）、`package.json`、
   `workspace.json`（2 个 workspace + 5 个 session 引用全部完整，路径都存在）——全合法
2. 怀疑新 bundle `dsh-classifier-autostart` 拖垮插件树 → 临时移除 + 重启 → 无效（已恢复）
3. 怀疑 `.dsh` junction 丢失 → 查到它是空普通目录，但 `DSH_HOME` 显式指向 D 盘，不是根因
4. 正解来自用户提示："看看当时我让 dsh 写的脚本" → 找到 `clear_sessions.ps1`

## 根因
dsh 当时写的 `D:/Brain/_cleanup_20261118/clear_sessions.ps1`（18:59 执行）：
```powershell
$groupPath  = "D:\Brain\dsh-data\sessions\--D-Brain-dsh-data-profiles-desktop--"
$backupPath = "D:\Brain\dsh-data\sessions\_backup_sessions_20261118"
Move-Item ...  # 388 个 session-* 目录
```
两个致命点：
1. **备份目录放在 `sessions/` 内部**——dsh 的会话扫描器会遍历到它
2. **扁平化丢失 group 层级**——原本 `sessions/<group>/session-X`，备份成 `sessions/_backup.../session-X`，
   388 个孤儿 session 无 group 上下文 → workspaceController 初始化抛 TypeError → 服务 unavailable

且脚本把**当前 profile 自己的会话组**（`--D-Brain-dsh-data-profiles-desktop--`）清空了，
该组 cwd = `D:\Brain\dsh-data\profiles\desktop`，正是 dsh 启动计算的 session group 路径。

## 源码级机制（子任务从 asar 权威源码核实，非推断）

错误链：
```
sessionPersistence.list() 抛错
  → workspaceRegistry pending（inject sessionPersistence）
  → workspaceController pending（inject workspaceRegistry）
  → gateway 严格 ctx.get() 返回 undefined → gateway/service-unavailable
```

关键源码（asar 内路径）：
- **服务注册**：`dsh-api-workspace-controller/src/index.ts:57-95`（`WorkspaceController extends TypertRemoteService`，
  `inject=['remoteAccess','typert','workspaceRegistry']`，注册名 `workspaceController`）
- **网关严格查找**：`dsh-api-gateway/src/index.ts:829-837`——`receiverContext.get(descriptor.service)`，
  非 object 即抛 `gateway/service-unavailable`
- **"active ... unavailable" 的确切含义**：`cordis/src/reflect.ts:249-258`——服务在 store 里，
  但**提供它的 fiber 不是 ACTIVE**（pending/failed/disposed），严格 get 返回 undefined。
  ⚠ 所以报错里的 `TypeError:` 前缀**不是**"调用了 undefined 方法"（那会是另一条
  `gateway/method-unavailable` 路径，`:863-869`）
- **抛错点**：`dsh-session-persistence-jsonl/src/index.ts:1605-1632`——
  `corrupt session log "...": header id "..." and cwd identify "..."`：
  路径由 `header.cwd` 反推（`format.ts:227-271` 的 `projectKey(cwd)`），与实际所在目录不符即抛错
- **扫描器遍历 sessions/ 全部子目录**：`dsh-session-persistence-jsonl/src/index.ts:1673-1684`
  `listProjectDirs()` → `readdir(root)` 取所有子目录——扁平备份目录因此被当成一个 project 扫描
- **实证**：备份中的 `session-00dd946a` 在 projcache 里 cwd=`D:\Brain\dsh-data\profiles\desktop`，
  预期 group 是 `--D-Brain-dsh-data-profiles-desktop--`，实际却躺在 `_backup_sessions_20261118/` 下 → 必然不匹配
- **recycle-bin 插件非根因**：只 inject 三个服务并挂 `SessionTrashHost`，不注册/注销 workspaceController

## 修复（已验证有效）
```powershell
Move-Item "D:\Brain\dsh-data\sessions\_backup_sessions_20261118" `
          "D:\Brain\_cleanup_20261118\backup_sessions_outside"
# 重启 dsh
```
**用户实测：添加工作区恢复正常**（2026-11-25 22:14）。
388 个 session 完整保留在外面，随时可移回。

## 铁律（写进规范）
1. **备份 dsh 会话时，备份目录必须放在 `sessions/` 外面**——不要放在 sessions 树内部
2. **保持 group 目录层级**——`sessions/<group>/session-X`，不要扁平化
3. **不要清空当前 profile 自己的 session group**——那正是 dsh 启动要扫描的
4. 遇到 `gateway/service-unavailable: active Service "workspaceController" is unavailable`：
   **先查 `sessions/` 目录结构有没有被外部脚本动过**，别先怀疑配置/非法字符/bundle

## 证据等级
L4 真实会话：用户重启后实测"现在可以了"。备份未删除、可逆。
