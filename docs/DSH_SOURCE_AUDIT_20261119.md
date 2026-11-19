# dsh 开源源码权威核查（2026-11-19）

> 用户指出：dsh 是开源项目，路径/插件机制应扒对应版本源码而非猜。
> 本文记录从 `deepseek-ai/deepseek-harness` **dsh-v0.2.2-rc.3**（本机装的 commit `38a6a5c`）
> 扒到的权威机制，作为整治方案依据。

## 一、仓库与版本
- 仓库：`deepseek-ai/deepseek-harness`（284k★，TypeScript，MIT）
- 本机装的：`dsh-v0.2.2-rc.3`（FileVersion 0.2.2-rc.3）
- 已有更新 tag：rc.4 / rc.5（本机未升）
- 源码读取方式：GitHub raw（仓库 414MB，git clone 超时，改用 raw 单文件）

## 二、DSH_HOME 解析（`packages/util/home-paths`）
**权威原文**：
> `resolveDshHome()` // configured path, else `$DSH_HOME`, else `~/.dsh`
> An explicit configured path has the highest precedence, then `$DSH_HOME`, then the default
> `~/.dsh`. An empty or whitespace-only `$DSH_HOME` is treated as unset.

三层优先级：**显式配置路径 > `$DSH_HOME` 环境变量 > `~/.dsh`**。

## 三、profile 与启动（`packages/boot/app-boot`）
**权威原文**：
> A profile lives at `$DSH_HOME/profiles/` and combines installable bundles with its own `cordis.patch.yml`.
> A bundle's `dsh.bundle.patch` names one patch file or an ordered list of files.
> Profile loading removes retired installation-bundle selections from `dsh.profile.bundles` and rewrites the manifest only when needed.

- profile 目录 = `$DSH_HOME/profiles/`
- 插件挂载 = profile 的 `dsh.profile.bundles` 数组 + 包内 `dsh.bundle.patch` 指向的 patch
- 官方有"retire bundle 时自动从 bundles 移除并重写 manifest"的机制

**结论**：设置 `DSH_HOME=D:\Brain\dsh-data` → profile/插件/会话全从 D 盘读 → **C 盘 `.dsh` junction 可安全删除**。

## 四、shell 子进程继承（`packages/shell/shell-env`）
**权威原文**：
> Every call receives `DSH_HOME` (the absolute Harness home)... The shell executor discards inherited `DSH_*` values and merges the registry's current snapshot for each execution.
> `dshHome` config field: default `$DSH_HOME`, then `~/.dsh`.

模型 shell 调用自动获得正确的 `DSH_HOME`，不依赖 C 盘路径。

## 五、插件装上去卸不掉——根因与正解
本机现场：
- `profile/package.json` 的 `dependencies.dsh-agent-harness = "github:D-al/dsh-behavior-guard"`
- 同文件 `dsh.profile.bundles` 数组含 `"dsh-agent-harness"`
- `pnpm-lock.yaml` 锁在 commit `0bf42c6` / version **2.3.0**
- 权威仓库已 **v2.26.0**（GitHub tag v2.26.0，本地 HEAD 89f4d89）

**卸不掉**：声明式配置（dependencies + bundles + 包内 patch）每次启动强制挂载，手删文件没用，重启被 pnpm 按 lock 重装。
**版本不一致**：lock 锁旧 commit；我前几轮手工 cp 新 index.mjs 到 node_modules，但今晚 22:59 pnpm install 把它覆盖回 2.3.0（SHA 从 84b7cb 变 c612ac，新机制全丢）。
**正解（用户选：保留 github 依赖，修 lock 到最新）**：
1. 更新 lock 的 commit 到 v2.26.0 对应 commit
2. `pnpm install` 让 node_modules 物化新版
3. 卸载脚本 = 从 bundles 移除 + dependencies 移除 + pnpm install

## 六、pnpm 不行——根因（`.modules.yaml` 路径冲突）
- `.npmrc`：注释说 C 盘 `.dsh` 是 junction → D 盘，pnpm 解析出 D 路径，`.modules.yaml` 记 C 路径 → `ERR_PNPM_UNEXPECTED_VIRTUAL_STORE`
- `.modules.yaml`：`storeDir=C:\Users\Ad\AppData\Local\pnpm\store\v11`、`virtualStoreDir=C:\Users\Ad\.dsh\...\.pnpm`
- `pnpm-install.log`：只有一行截断的 "The modules directory at ... will [be removed]" → 卡在交互确认
- dsh 内置 pnpm：`dsh-runtimes/dsh-primary-runtime/dependencies/pnpm`（v11.28.5）

**根治**：junction 删除 + DSH_HOME 指向 D 盘后，所有路径统一为 D 盘真实路径，冲突自然消失。

## 七、会话依赖清单
- 会话桥 descriptor 由插件写 `$DSH_HOME/session-bridge.json`，bridge.mjs 每次调用重读（重启自动跟上）——**不依赖手动**，但 junction 删后要确保 DSH_HOME 正确
- 治理文档 ROADMAP/CHANGELOG/docs 在权威仓库 `publish/dsh-behavior-guard`，**没同步到 `p/bench`**（AGENTS.md 说以那里为准）→ dsh 读不到
- 计划任务：`D:\Brain\tasks\` 只有 RestartDsh.xml（正常）+ FreezeWatch.xml（**0 字节空文件**）；LearnWatchDaemon 无 XML（重装丢失）
- `setup/links.ps1` 在 AGENTS.md 被引用，但 `D:\Brain\workspace\bench\` 下是否存在待确认

> 依据：deepseek-ai/deepseek-harness@dsh-v0.2.2-rc.3 官方 README + 本机现场。遵循知识资产沉淀规则。
