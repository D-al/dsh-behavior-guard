# dsh 平台层整治（2026-11-20 凌晨）

> 用户报告：①装上去卸不掉 ②插件版本与 GitHub 不一致 ③提示 pnpm 不行
> ④资产要通过 junction 虚拟映射到 D 盘、要改成真实目录 ⑤依赖人机会话的东西要整治。
> 用户补充：dsh 开源，应扒对应版本源码确认机制（已做，见 DSH_SOURCE_AUDIT_20261119.md）。

## 一、根因链（一个连环套）

1. **profile/package.json** 把 `dsh-agent-harness` 声明为 `github:D-al/dsh-behavior-guard` 依赖，
   并在 `dsh.profile.bundles` 数组里强制挂载 → 每次启动重新组合进 patch 树，**手删文件没用**。
2. **pnpm-lock.yaml** 把插件锁在 commit `0bf42c6` / **v2.3.0**，而权威仓库已 **v2.26.0** → 版本不一致。
   更隐蔽：前几轮手工 cp 新 index.mjs 到 node_modules，但 11-19 22:59 一次 pnpm install 把它覆盖回 2.3.0。
3. **pnpm 不行** = `ERR_PNPM_UNEXPECTED_VIRTUAL_STORE`：`.modules.yaml` 记 C 路径
   （`C:\Users\Ad\.dsh\...`）、pnpm 解析出 D 路径（`D:\Brain\dsh-data\...`），因 junction 同一物理目录两种拼写。
   `pnpm-install.log` 只有一行截断的 "modules directory ... will [be removed]" = 卡在交互确认。
4. **会话桥失效**：pnpm install 清理时删了 `dsh-session-bridge` / `dsh-approval-delegate` 两个 `link:` 依赖
   （junction 指向 bench），重启后插件没加载、descriptor 不更新。

## 二、已完成修复（本次）

### 2.1 插件升级到 v2.26.0（用户选"保留 github 依赖，修 lock 到最新"）
- 从 GitHub commit `89f4d89` 下载 tarball（sha512 已算），解出完整 v2.26.0 包（144 文件，
  含 docs/skills/tools/config），覆盖 `node_modules/dsh-agent-harness`。
- **pnpm-lock.yaml** 4 处 commit `0bf42c6` → `89f4d89`、integrity 换新、version 2.3.0 → 2.26.0。
  以后 pnpm install 会装新版，不再降级。
- 注意：`git status` 干净但文件内容 SHA 与 tarball 不同是 **CRLF 转换**所致（git blob hash vs 文件 sha256），
  逻辑一致，非问题。

### 2.2 node_modules link 依赖恢复
- 重建两个 junction：`dsh-session-bridge` / `dsh-approval-delegate` → `D:\Brain\workspace\bench\...`
  （这是 pnpm `link:` 依赖的标准机制，必须保留；用户"消灭 junction"指数据资产映射，不含此类）。
- 重启 dsh 后会话桥 descriptor 更新（pid 5832 / port 64002），`bridge.mjs health` = OK。

### 2.3 会话依赖整治
- **治理文档同步**：权威仓库 ROADMAP/CHANGELOG/README + docs/decisions/skills → `p/bench`（真实文件非 junction）。
  AGENTS.md 声明"以 p/bench/ROADMAP.md 为准"，此前那里是空的 → dsh 读不到，只能靠人机会话传递。
- 新增幂等同步脚本 `setup/sync-to-profile.ps1`，每次升级后运行即可。
- **计划任务定义**：导出 `LearnWatchDaemon.xml`（此前无 XML、重装丢失）；
  移走 0 字节的空 `FreezeWatch.xml`（否则 restore_all.ps1 会注册坏任务）。
- **环境变量**：用户级 `DSH_HOME=D:\Brain\dsh-data` 已设置（dsh 官方支持，见源码核查文档）。

### 2.4 权威源码核查（用户要求）
- 扒 `deepseek-ai/deepseek-harness@dsh-v0.2.2-rc.3` 官方 README：
  - `resolveDshHome()`：显式配置 > `$DSH_HOME` > `~/.dsh`
  - profile 在 `$DSH_HOME/profiles/`，插件由 bundles + 包内 patch 挂载
  - shell 调用自动获得 `DSH_HOME`
  - Electron userData（登录态）不受 DSH_HOME 控制

## 三、未完成（需用户知悉/下一步）

### 3.1 junction 消灭（进行中）
C 盘 6 个 junction 中：
- `.dsh` → 可由 DSH_HOME 取代，**可安全删**（待重启验证后执行）
- `AppData\Roaming\@deepseek-ai`（登录态）→ Electron 写死，删了会丢登录态，
  需 `--user-data-dir` 启动参数方案（子任务调研中）
- `AppData\Local\@deepseek-aidsh-desktop-updater` → 更新缓存，删了只是重新下载
- `WorkBuddyWorkSpace\...\bench` / `.workbuddy\memory` → WorkBuddy 工作区，删了影响当前工具链
- `default-workspace` 是真身目录（非 junction），历史证明换 junction 会打乱会话分组，不动

### 3.2 pnpm 收尾
- node_modules 里有一个被锁的 `dsh-llama-server-autostart` 目录（残留 `_tmp` 目录），
  导致 `pnpm install --force` 报 EPERM。当前功能正常（dsh 已加载 v2.26.0），
  但 pnpm 状态文件（.modules.yaml）不完整，下次 install 可能重装。已备份旧目录到 `_cleanup_20261118`。

### 3.3 卸载脚本
- 官方卸载方式：从 `package.json` 的 dependencies + `dsh.profile.bundles` 移除条目 → pnpm install。
  尚未写成一键脚本（待 junction 整治完成后一起做）。

## 四、验证状态
- dsh pid 3464 / 8081 health OK / 会话桥 health OK
- 插件 package.json version = 2.26.0
- 运行态快照 `_agent_harness_loaded.json` 已刷新

> 遵循知识资产沉淀规则。本文件记录已完成/未完成/风险，供接手者续作。
