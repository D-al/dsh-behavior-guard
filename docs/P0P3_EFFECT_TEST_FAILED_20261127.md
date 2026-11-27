# P0-P3 实现完成 + 效果检验失败报告（2026-11-27 09:15）

> 用户要求："全做，然后检验效果"
> P0-P3 代码**已全部实现并提交**（`da8ddba` + `2fff7b9`），回归全绿。
> **但效果检验失败**——不是代码问题，是 dsh 的 harness 插件在反复重启后未加载。

## 一、P0-P3 实现（已提交）

| 层 | 实现 | 机制 |
|---|---|---|
| P0 | 工具结果去重 | `tool/result` 记录 `(basename → djb2 hash + digest)`；同一文件重复读且 hash 相同 → `pre-execute` 返回 stub deny |
| P1 | 编辑回显压缩 | 编辑类命令成功且结果 >600 字符 → 只记事实 trace（失败信号 bypass） |
| P2 | 并行探索提示 | step≤3 时注入一次"可并行发 glob/grep/read" |
| P3 | 事实缓存 | `readFacts` Map 记录 content-hash → 关键事实（进程内，未落盘） |

**关键修复**（`2fff7b9`）：
- `fullArgs` 是 JSON 字符串，必须 `JSON.parse` 才能取到 `file_path`
- 去重保护窗口从"最近 5 步不压"改为"hash 相同即 stub"（编辑后 hash 变会自动放行）

## 二、效果检验：失败（环境问题）

### 现象
- 08:32 首轮测试：read 10 次、8 次，**去重事件 0 次**
- 加诊断 trace 后：**trace 文件完全不增长**（2253 行不动）
- bridge events 显示会话正常在跑（50 个事件），但**零 harness 注入**

### 诊断链
1. 检查 `loadedAt`：停在 08:37，之后多次重启都不更新
2. 检查 dsh 进程：确实在跑（pid 23456 等，进程名 `DeepSeek Harness`）
3. 检查 bridge descriptor：pid 正确、端口正确
4. **检查 harness probe 写入点**：`index.mjs:1222`，在 `apply()` 开头写
   → probe 不更新 = **`apply()` 从未执行** = 插件没被 cordis 加载
5. 检查 `cordis.patch.yml` / `package.json`：配置正常（`dsh.bundle.patch`）
6. 检查副本：只有一个有效副本，两版 md5 一致

### 根因判断
反复 `Stop-Process` + `Start-ScheduledTask` 后，dsh 的某个 profile/bundle 状态被破坏，
harness 插件没有被 cordis 挂载。**这是环境状态问题，不是 P0-P3 代码问题**：
- 代码语法检查通过
- 两版 md5 一致
- 回归全绿（25 PASS + 三套 wargame ALL PASS）
- `loadedAt` 在 08:37 那次是成功加载过的（含 P0-P3 配置）

### 我犯的操作错误
1. 用 `cp` 直接覆盖运行版文件（应该走正规同步流程）
2. 用 `git checkout 2fff7b9 -- index.mjs` 回退后又 `cp`，可能触发了 dsh 的 bundle 缓存失效
3. 多次重启时没有验证"harness 是否真的挂载"就继续测试，浪费了几轮

## 三、实际产物（唯一可信的正向结果）
尽管 harness 静默，模型仍在无 harness 状态下完成了几次任务：
- 颜色场景：`#2d3748` → `#1f2937` 改对
- 圆角场景：部分成功
**这不能算 P0-P3 的功劳**——是模型自己做的，harness 没介入。

## 四、诚实结论

**P0-P3 代码完成度：100%**
**效果验证：0%** —— 无法给出 read 次数对比数据，因为 harness 没运行。

我不会编造"read 从 10 降到 2"这种数字。当前唯一能说的是：
- 代码在（`da8ddba`、`2fff7b9`）
- 回归全绿
- 效果未验证

## 五、恢复建议（给未来的自己）

1. **不要直接 `cp` 覆盖运行版** —— 走 publish → 同步脚本 → 校验 md5 的流程
2. **重启后必须先验证 harness 挂载**：
   - 发一个简单会话，检查 `_trace.jsonl` 是否增长
   - 或检查 `_agent_harness_loaded.json` 的 `loadedAt` 是否更新
3. 如果 probe 不更新，需要检查 dsh 的 profile 选择 / bundle 缓存（可能要清 node_modules 缓存或重新 `pnpm install`）
4. **P0-P3 的效果检验是未完成项**：环境恢复后必须重跑 4 场景，对比 read 次数

## 六、回归状态
- `test_audit_allfix.mjs`：**25 PASS / 0 FAIL**
- `test_wargame_fixes.mjs`：**ALL PASS**
- `test_wargame_gaps.mjs`：**ALL PASS**
- `test_all_remaining.mjs`：**ALL PASS**
- 注：更新了 3 个过时断言（两版已同步、变量名变更），非代码回归
