# 三道防线落地报告（2026-11-26 01:0x）

> 对应方案：`GUARD_PLAN_PLUGIN_SAFETY_20261126.md`
> 复盘：`POSTMORTEM_HARNESS_BLINDSPOT_20261126.md`（含重大更正）

## 总览

| 防线 | 实现 | 状态 | 验证 |
|---|---|---|---|
| 1. 文件监听层 watcher | `tools/plugin_guard.py` + autostart 插件拉起 | ✅ 已上线 | E2E：坏 bundle 名 3s 内自动改回；关键文件删除自动恢复 |
| 2. compaction 保留自我纠错 | `tools/patch_self_correction.py` 打补丁到两版 index.mjs | ✅ 已打补丁 | 事故 seq 481 原话能捕获；正常思考不误报；去重分支前注入 |
| 3. 副作用识别 + DANGER_BLOCK | `tools/patch_side_effect_guard.py` 两版补丁 | ✅ 已打补丁 | EPERM 原文命中；事故 seq646 Copy-Item 命中；正常操作不误报 |

**关键设计约束**：profile 默认 `danger-full-access` + `approval: never`（全局，非会话特例），
所以防线1 跑在 dsh 进程外——这是唯一不受权限配置影响的层。

## 防线1：plugin_guard.py（独立 watcher）

- **生命周期**：由 `dsh-llama-server-autostart` 插件用 `spawn` 拉起，与 frame_limiter 对称：
  - bootAll 完成后 `startPluginGuard()`
  - dispose 时 `stopPluginGuard()`
  - 传 `--parent-pid`：watcher 每轮检测父进程，父死自动退出（防孤儿）
  - **无开机自启**（用户明确要求与 dsh 同生命周期；Startup 里的 PluginGuard.vbs 已撤销）
- **三条规则**：
  1. bundle 名合法性：patch 里每个 `name:` 必须等于插件 package.json 的 name；
     `@local/` 前缀显式禁止（即使符合 scoped 包名格式——这是 selftest 抓到的坑）
  2. 关键文件存在性：3 个核心插件的关键文件缺失 → 从 publish 权威源自动恢复
  3. 变更哈希审计：append-only 写 `D:/Brain/workspace/bench/_plugin_guard.jsonl`
- **E2E 证据**：
  - 注入坏名 `@local/dsh-hardware-monitor` → 3s 后自动改回，日志 `BAD_BUNDLE` + `CHANGED`
  - 移走 `frame_limiter.py` → 自动从权威源恢复，日志 `AUTO_RESTORE` + `MISSING`
  - 重启 dsh：`01:01:14 PARENT_GONE parent=1944` → `01:02:05 START`（新 pid=3792）——同生命周期确认

## 防线2：compaction 保留未闭环自我纠错

根因：事故 seq 481 的自我纠错是 **reasoning block**，`summarizeAssistant()` 只读 text + tool-call，
主动丢弃 reasoning；P0 存档去重分支还会 `parts.length=0` 清空全部——这正是事故扩大的机制。

四处改动（两版 index.mjs，幂等补丁）：
1. 状态加 `openCorrections: []`
2. `summarizeAssistant()` 读 reasoning/thinking block（新增返回字段 `reasoning`）
3. `assistant/message` 监听里 `captureOpenCorrection(s)`：
   - 检测"应该改回/恢复/猜错了/可能是个问题"等自我纠错模式
   - 检测"已经改回/修复"等完成模式 → 标记 resolved（保留历史供审计）
   - 保守策略：宁可漏报不可误报；同一线索去重，上限 20 条
4. 存档注入：在**去重分支之前** push `【未闭环的自我纠错】`，并纳入 archiveSig
   （纠错状态变化必须视为"新存档"，否则又被去重清掉）

验证：事故 seq481 原话 → 捕获；"路径猜错了，应该改成..." → 捕获；正常思考 → 不捕获；已完成 → resolved。

## 防线3：副作用识别 + DANGER_BLOCK

1. **DANGER_BLOCK 新增**（`index.mjs`）：
   `/(?=.*Copy-Item)(?=.*-Recurse)(?=.*-Force)(?=.*node_modules)/i`
   ——用 lookahead 做到顺序无关（事故 seq646 的命令里 node_modules 在 -Recurse 之前）
2. **tool/result 钩子**新增 `detectSideEffectDamage()`：
   - 识别 `ERR_PNPM_EPERM`、`EPERM...rename`、`_tmp_N ->` 等确定性特征
   - 命中 → trace `side_effect_damage` + `pendingInject` 提示
     "不要当成普通权限问题忽略，先核对现场文件状态"
   - 只提醒不阻断（profile 默认 full-access，无法硬拦）
   - 注意：两版 tool/result 钩子结构不同（publish 是 S24 版、runtime 是 v3.1 老版），
     补丁脚本已用双锚点适配

## 诚实边界 / 未做项

1. **consistency_guard.py 的 --fix 未实现**：它与 plugin_guard 功能重叠（都是关键文件恢复），
   重复实现风险大于收益。保持其只读巡检定位；关键文件自动恢复由防线1承担。
2. **"纳入启动门禁"未做**：改 dsh 启动流程风险高，且防线1已经随 dsh 启动。
3. **自动恢复的局限**：只覆盖 3 个核心插件的关键文件（manifest 硬编码在 plugin_guard.py）；
   新增插件需手动加 `AUTHORITATIVE` + `CRITICAL_FILES` 映射。
4. **检测是保守的**：自我纠错识别只认中文/英文固定句式，句式变化会漏报——这是刻意选择
   （误报会刷屏，比漏报更有害）。
5. **防线2/3 改的是 harness 代码**：运行版与 publish 差 580 行的老问题仍在；
   补丁脚本对两版做相同局部修改，没有整文件覆盖（避免引入版本差异）。

## 验收：事故 5 节点回放

| 节点 | 新防线行为 | 实测 |
|---|---|---|
| seq 388 remove_bundle | 不拦（合法工具），watcher 记录 | ✅ 设计如此 |
| seq 389 pnpm EPERM 目录清空 | 防线3 识别副作用 + 告警；防线1 自动恢复关键文件 | ✅ EPERM 命中 / AUTO_RESTORE 实测 |
| seq 431 edit 成 @local | 防线1 校验 bundle 名失败 → 自动改回 | ✅ E2E 3 秒改回 |
| seq 456 compaction 剔除纠错 | 防线2 强制保留未闭环纠错 | ✅ 正则实测捕获事故原话 |
| seq 646 Copy-Item 覆盖坏 patch | 防线3 DANGER_BLOCK 命中 | ✅ lookahead 正则实测命中 |

## 文件清单

- 新增：`tools/plugin_guard.py`、`tools/patch_self_correction.py`、`tools/patch_side_effect_guard.py`
- 修改：`index.mjs`（publish + runtime 两版，各打两个补丁）
- 修改：`dsh-llama-server-autostart/index.mjs`（publish + runtime 两版，加 watcher 启停）
- 新增：`dsh-llama-server-autostart/plugin_guard.py`
- 撤销：Startup 的 PluginGuard.vbs（移到 `_cleanup_20261118/plugin-repair-20261126/`）
