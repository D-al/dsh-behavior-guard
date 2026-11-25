# 事故复盘：dsh 修插件修坏两个插件（2026-11-26 00:2x）

## 症状
用户让 dsh 修复 dsh-hardware-monitor 插件，"修一半成这样，修完更是这样"：
1. `dsh-hardware-monitor` 异常/包不可用；启动报错
   `failed to import: Error [ERR_MODULE_NOT_FOUND]: Cannot find package '@local/dsh-hardware-monitor' imported from D://Brain//dsh-data//profiles//desktop//`
2. `dsh-llama-server-autostart` 未运行/包不可用
   `dsh: cannot resolve profile bundle "dsh-llama-server-autostart" from ...`

## 根因（两个独立问题）
### 1. hardware-monitor：`@local/` 前缀是 dsh 不认的 bundle 名
dsh 把插件自带的 `cordis.patch.yml:9` 从 `name: dsh-hardware-monitor` 改成了
`name: '@local/dsh-hardware-monitor'`。dsh 的 bundle 解析器只认 package name，
`@local/` 是它自己臆造的别名 → 解析失败 → ERR_MODULE_NOT_FOUND。
（根因证据：坏 patch 已备份到 `_cleanup_20261118/plugin-repair-20261126/cordis.patch.yml.hardware.broken`）

### 2. llama-server-autostart：插件目录源码被清空
`node_modules/dsh-llama-server-autostart/` 只剩 4 个日志文件
（`_frame_limiter.jsonl`、`llama-debug.log`、`llama-server-run.log` 等），
`index.mjs` / `package.json` / `cordis.patch.yml` / `frame_limiter.py` 全部丢失
——dsh 在"修复"过程中删除/重装失败，把源码清空了。

## 排查弯路
- 先怀疑 package.json 被改（00:26 修改时间很可疑）——内容其实完整正确
- 查 dsh 两个修复会话（e22d97fd / cc8a7fb9）的 events——**没有**这两个破坏操作的工具调用记录
  （dsh 自己也不记录/不承认？至少 bridge events 里看不到；很可能发生在 harness 的自动安装逻辑里）
- 教训：dsh 会话记录不等于全部真相，现场文件状态才是

## 修复（已验证有效）
1. `cordis.patch.yml:9` 改回 `name: dsh-hardware-monitor`
2. 从权威源 `D:/Brain/publish/dsh-llama-server-autostart/` 恢复 6 个源码文件
   （index.mjs / package.json / cordis.patch.yml / frame_limiter.py / CHANGELOG.md / README.md），
   保留现场日志不动
3. 重启 dsh（`Stop-Process` + `Start-ScheduledTask RestartDsh`）

## 验证（L4）
- 重启后 `session-bridge.json` descriptor 在 00:31 生成——插件树完整启动的信号
  （前几次重启都没有）
- bridge health `ok:true`
- llama-debug.log：`spawn issued pid=2104 (35b)` → `8081 就绪=true` → `frame-limit 已启动`
- `node --check` 两个插件入口均通过；无 `@local/` 残留

## 铁律
1. **dsh 自己改的东西不可信**——它"修复"的结果需要独立验证，尤其是 bundle 名和文件完整性
2. **bundle 名永远是 package name**，不要信 `@local/` 之类别名（dsh 解析器不认）
3. **权威源是 publish 仓库**——profile 的 node_modules 被搞坏时从那里恢复，不要从旧 workspace 副本
4. 备份先行：`_cleanup_20261118/plugin-repair-20261126/` 存了坏 patch / profile patch / package.json
