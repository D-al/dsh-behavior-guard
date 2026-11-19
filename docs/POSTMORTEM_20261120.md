# 2026-11-20 平台整治事故复盘：可复用的工程教训

> 起因：用户报告 5 个问题（插件装上去卸不掉 / 版本与 GitHub 不一致 / 提示 pnpm 不行 / 资产靠 junction 虚拟映射 / 依赖人机会话）。
> 结果：一路挖到"**我们 push 到 GitHub 的权威仓库本身就带着 P0**"，最终 2 个仓库各推一版、删除 C 盘 junction、帧率限制整合进 autostart。
> 这篇只记**教训与铁律**，过程细节见 `DSH_SOURCE_AUDIT_20261119.md`、`DSH_PLATFORM_REPAIR_20261120.md`、`REAL_TRACE_ACCEPTANCE_20261120.md`。

---

## 1. 元教训（最重要）：验收证据是分层的，不能拿低层冒充高层

事故最后一问是"harness 到底有没有实现路线图承诺的东西？毕竟之前可能是看着 A 去改 B"。这个问题逼出了一个决定性的发现：

`_trace.jsonl` 共 **9666 行**，按 sid 分组后 **8592 行（89%）来自 `s1`——单测伪造数据**（内含 100 次假 audit 失败、81 次假 critic 失败）。排除测试 sid 后，真实 dsh 会话只有 **883 行**。

如果直接用 9666 行论证"机制生效"，结论看着漂亮、实则被测试灌水污染。此前我甚至差点把"角色 LLM 成功率 9.7%"当成生产故障上报——那全是 s1 的假数据。

**证据阶梯（从弱到强，论证时必须说明用的是哪一级）：**

| 级别 | 证据 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| L1 | 代码存在 / grep 到关键词 | 写了 | 加载了、跑了 |
| L2 | 单测 PASS | 隔离环境下逻辑对 | 真实路径触发、真实配置生效 |
| L3 | 运行态快照刷新 | 插件被加载 | 具体机制被触发 |
| L4 | 真实 sid 的 trace 命中 | 机制在真实会话跑过 | 结果有效 |
| L5 | 独立产物落地且可核验 | 端到端生效 | — |

**"看着 A 改 B"的精确定义 = 拿 L1/L2 证据下 L4/L5 的结论。**

配套陷阱：**零证据 ≠ 没实现**。本次 `injection_hit` 在真实会话里 0 次，不能直接判"没实现"——造了一个含注入文本的文件让 dsh 用 read 读，受控实验真实命中 1 次。`audit_feedback` 在主 trace 搜不到，是因为它写独立文件 `_audit_feedback.jsonl`（3 条真实结算）。`adaptive_route=0` 则是设计本就默认关闭。

**铁律：判"没实现"之前，先区分「没触发」/「写到了别处」/「设计就关闭」/「真的没有」。**

---

## 2. 最大的结构性风险：三副本不一致（我反复踩）

这个项目同时存在：

| 角色 | 路径示例 | 特点 |
|---|---|---|
| 权威源 | `D:\Brain\publish\dsh-behavior-guard`、`D:\Brain\publish\dsh-llama-server-autostart` | push GitHub 的地方 |
| 运行版 | `D:\Brain\dsh-data\profiles\desktop\node_modules\*` | dsh 实际加载 |
| 副本 / 旧 clone | `D:\WorkBuddyWorkSpace\...\dsh-llama-server-autostart`（v1.1.0）、pnpm store 缓存 | 容易误认成权威源 |

本次具体翻车：

- 文档写 v2.26.1，运行版 node_modules 还是 **v2.3.0**；pnpm 一 install 就把手工修的代码覆盖回去。
- 我把**运行版（v1.1.0 旧参数逻辑）覆盖到了 Workspace 的旧 clone**，破坏了它（已 `git checkout -- .` 回滚）。真正的权威源是 publish 的 v1.1.1。
- `frame_limiter.py` 我在权威源修好了 `pid_alive`（WaitForSingleObject），运行版仍是旧的有 bug 版本；子任务也各自复制了一份早期版。
- CHANGELOG 宣称修了 `weakness_miner.py` / `self_harness_proposer.py`，权威 `tools/` 里**根本没有这两个文件**（只在 bench 有）。

**铁律：**

1. 改动前先问"**哪个是正在运行的**"，用运行态证据确认，不靠路径猜。
2. 单一权威源（SSOT = publish），所有副本由它派生。
3. 同步后用 **hash 校验**（`sha256sum`），不用"我记得复制过了"。
4. 子任务报告"改好了"必须主代理独立复核路径与 hash。

---

## 3. 开源项目扒源码，不靠试错

用户第一句就点破："dsh 是开源项目，它怎么设置会话路径你完全可以去 GitHub 上扒对应版本源码看。"

后来每一次关键结论都来自源码，而不是猜：

- `resolveDshHome()` 优先级（显式配置 > `$DSH_HOME` > `~/.dsh`）→ 才敢删 `.dsh` junction。
- profile 在 `$DSH_HOME/profiles/`、shell 自动注入 `DSH_HOME` → 才敢把登录态/userData 分开处理。
- Electron 无 `setPath('userData')`，但通用支持 `--user-data-dir` → 才知道登录态 junction 的正确补偿方式（且必须指向 `...\@deepseek-ai\dsh-desktop` 这一层，指向上一层会建错层丢登录态）。
- `!!js` 的真实实现：`JsExpr` 注册为 **`kind: "scalar"`**，只把标量文本整体 eval。

最后一条是这次最贵的试错：我按直觉写 `allowedRoots: !!js [...]`，YAML 把它当 flow sequence、逗号把 JS 表达式切碎 → **dsh 启动失败**。子任务扒 asar 源码（JsExpr 定义约 offset 18337710）才找到真相，官方 patch 里的数组一律用双引号包住整个表达式。回滚后改用"从包内 patch 删除路径键、由已参数化的 DEFAULTS 接管"。

**铁律：涉及第三方 loader / 框架语义，先扒对应版本的权威源码（或实现），再写代码。试错成本 >> 读源码成本。**

---

## 4. "文档宣称完成" ≠ "代码实际生效"

- v2.26.1 名为"平台层整治"，`git diff --stat v2.26.0 v2.26.1` 显示 **0 行代码改动**（只有版本号和文档）。
- `setup/links.ps1` 会把刚消灭的 `.dsh` junction 重新建回来，README/MANUALS 还把它列为"必跑步骤"——按官方文档重装就复现原坑。
- `install.ps1` 前置检查写死 `C:\Users\Ad\.dsh`，junction 删掉后直接 throw，后面所有恢复步骤都不执行。

**铁律：验收必须做三层交叉——①运行版真实打点 ②真实产物 ③脚本调用者；不要用关键词计数，也不要信 CHANGELOG。**

---

## 5. 破坏性操作：先建可逆点，再动手

本次大量使用可逆操作，这是没有造成数据丢失的关键：

- `node_modules` 用改名备份（`node_modules._old_...`）而非删除；被锁目录逐个探测出只有 `dsh-llama-server-autostart` 被占用。
- patch 部署前 `cp` 到 `_cleanup_20261118`，出问题一条命令回滚（三次回滚都靠它）。
- 删 junction 用 `fsutil reparsepoint delete C:\Users\Ad\.dsh`——**只删重解析点，不碰 D 盘真实数据**；删除后确认 C 盘变空目录、0 文件。
- 误覆盖的 clone 用 `git checkout -- .` 回滚。
- 空的 `FreezeWatch.xml`（0 字节，会被 `restore_all.ps1` 注册成坏任务）移到 `_cleanup_20261118`，不直接删。

**铁律：Windows 上绝不对 junction 用 `Remove-Item -Recurse -Force` / `rmdir /S`——会连带删除目标目录里的真实数据。**

---

## 6. Windows 特有的三个坑

1. **PowerShell 5.1 把 UTF-8 无 BOM 当 GBK**：`restart_dsh.ps1` 的中文注释导致语法错误，脚本根本跑不起来。这个 bug 潜伏已久，直到我把计划任务改走这个 wrapper 才暴露。修法：脚本**纯 ASCII**（或带 BOM）；本次所有安装/卸载脚本统一 ASCII-only + `Parser::ParseFile` 校验 `parse_errors=0`。
2. **`Stop-Process -Force` / Node `child.kill()` 在 Windows 走 `TerminateProcess`，Python `finally` 不执行**：实测限帧器被 Force kill 后 EcoQoS 残留、state 文件残留 `[26260]`（WorkBuddy 窗口还被降着帧）。修法 = 三重保险：①优雅信号 ②同步 `--release-all` 兜底 ③父进程看门狗（检测父死自己 release）。三者独立验证过。
3. **`link:` 依赖的 junction 是 pnpm 标准机制，属"必须保留"的例外**：用户要"消灭所有 junction"，但 node_modules 里的 link junction 改成真实复制会导致源码改动不生效。文档明确标注例外。

---

## 7. 判据用引擎级指标；先实测确认真凶，再设计方案

记忆里已有的教训再次生效：nvidia-smi 聚合 util% 空闲时也报 100%（WorkBuddy/dwm 的 3D 引擎），Copy 仅 0.8%、带宽 1%、功耗 25W——**不能用聚合 util% 判断推理是否在跑**。

本次新发现：实测分引擎 3D 占用 top 是 **WorkBuddy 的 GPU 进程 45.8% + dwm 36.8%**，dsh 自己此刻并不高。也就是说"给 dsh 窗口降帧"解决不了用户观察到的问题——真凶是承载对话的 WorkBuddy 窗口。用户随后把需求升级为"推理期间对所有窗口自动限帧，关掉时全释放"，这才是正确方案。

**铁律：先实测锁定真凶，再定方案；用户的需求调整往往比我的初始假设更准。**

---

## 8. 并行子任务：收益很大，但产出必须复核

用户三次强调"能并行就并行"（"有可以并行的可以交给子任务处理" / "大胆开并行子任务，能开就开" / "一旦发现有可以并行的，就直接让子任务们去完成"）。本轮开了多轮、每轮 2-3 路：配置层审计、代码层审计、一键装卸脚本、`!!js` 源码验证、19 个 Python 脚本路径修复、autostart 整合、junction 消灭方案。收益明显——**5 个 P0 和 19 文件 33 处路径修复不是一个人能在这个时长里做完的**。

但也踩了坑：

- 有子任务指定的权威源路径是错的（说 `bench/dsh-llama-server-autostart` 是权威源，实际不存在；真源在 publish）。
- 部分子任务结果投递丢失，未落盘也没进当前上下文。
- 子任务改了 publish 版但没同步运行版；子任务复制的 frame_limiter 是加固前版本。

**铁律：派子任务时给死路径 + 读写边界 + 要求输出文件清单和验证结果；回收时必须独立验证（hash / 语法 / 路径），不能只信报告。**

---

## 9. 用户的领域直觉是最贵的输入

这次真正的突破几乎都来自用户的质疑，而不是我的计划：

| 用户的话 | 带来的真修复 |
|---|---|
| "去 GitHub 扒对应版本源码" | 找到 `DSH_HOME` 优先级，才敢删 junction |
| "插件全删了从 GitHub 重装会不会更省事" | 全删重装，解决 EPERM / 半装状态 |
| "GitHub 上的插件也带这个 bug，要先深度维护" | 发现 5 个 P0，做路径参数化 + 一键装卸 |
| "你甚至可以直接跟它对话检验" | 端到端验证（`Updated instructions from: $DSH_HOME/AGENTS.md`）|
| "有没有实现路线图承诺的东西？看着 A 改 B" | 拆穿 89% 假数据，建立证据分层 |

**铁律：用户说"不对"时，先停下验证，不要用"已完成"回应。**

---

## 10. 被证伪 / 不要再试（避免重踩）

- **`!!js [...]` 返回数组 + 复杂表达式**：YAML flow sequence + 逗号切碎 → dsh 启动失败。要么双引号包整个表达式，要么从 patch 删掉让 DEFAULTS 接管。
- **"给 dsh 窗口单独降帧"解决 3D/CUDA 竞争**：真凶是 WorkBuddy + dwm；已改为全局限帧。
- **依赖环境变量继承（InteractiveToken 计划任务）**：新设的用户级 `DSH_HOME` 可能要重新登录才生效。改为 wrapper 脚本显式 `$env:DSH_HOME` + 用户级变量双保险。
- **靠 `pnpm install` 修好手工改动**：lock 不更新就会把新代码覆盖回旧 commit；且 install 被 shim 中断会留下比不装更糟的半装状态。

---

## 11. 固化为每次改动后的检查清单

1. 改的是哪一份？→ 确认运行路径，SSOT 派生，hash 校验三副本。
2. 声明"完成"用的是哪一级证据？→ 目标 L4/L5，不用 L1/L2 冒充。
3. 单测 PASS 之外，真实 sid 的 trace / 独立产物有没有命中？
4. 破坏性操作有可逆点吗？回滚命令是什么？
5. Windows 脚本 ASCII-only / 带 BOM？`Parser::ParseFile` 验过吗？
6. 清理逻辑在 Force kill 下还成立吗？有没有第三重保险？
7. 子任务的产出我独立复核过吗（路径 + hash + 语法）？
8. CHANGELOG 写的东西，代码里真的有吗？

---

## 12. 一句话总结

> 这轮最值钱的不是修好了哪几个 bug，而是发现**我们一直在用"代码存在 + 单测通过"证明"真实运行生效"**——89% 的假 trace 把这个幻觉撑得很漂亮。
> 从此验收只认真实运行的证据，改动只认一个权威源，清理只认不依赖 `finally` 的三重保险。
