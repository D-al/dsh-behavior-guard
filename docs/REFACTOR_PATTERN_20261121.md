# 函数外置模式（2026-11-21 建立，供 agent 自己复用）

> 目标：让 agent 能安全地自修改——把嵌套函数逐步外置成"纯函数 + 单测 + 转发/内联 + 集成测试"四段式，
> 每次改动都有机器可验的等价证据，而不是靠人肉小心。
> **2026-11-21 晚更新**：实际落地证明"import 转发"比"复制函数体内联"更安全，已成为默认方案。

## 四段式模式（stateOf 之外的示范：taskProfile）

**第一步：外置纯函数** → `tools/task_profile.mjs`
- 无副作用、无外部依赖、只吃参数返回结构
- 顶部注释写明"为什么外置"（根因）+ 设计原则（确定性/零 LLM/fail-closed）

**第二步：写单测** → `tools/test_task_profile.mjs`
- 覆盖正常/边界/失败三类
- 每个断言是真行为断言，不许 `|| true` / `>=0` 恒真（今晚抓到 6 处这类假绿）
- **必须真的 0 FAIL 才能停**（executeReadOnly 卡曾带 5 FAIL + JSON.parse 崩溃就停了，是反例）

**第三步：接入 index.mjs（默认 import 转发）**
- **默认方案：import 转发**——在 index.mjs 顶部 `import { fn as _fn } from './tools/xxx.mjs'`，
  函数体改成 `return _fn(args)`。实例：`collectCorrectorInput`(index.mjs:25/1415)、
  `buildTrailText`(index.mjs:26/1228)。比复制函数体安全，避免 Unicode 转义/正则事故。
- **前提**：tools/ 文件必须与 index.mjs 同目录（node_modules 里同步存在），相对路径能解析。
- **旧方案"复制函数体内联"仍有风险**：`formatCorrection`/`formatExecutorResult` 用此方式完成，
  但中途踩过 Unicode 转义把中文写成 `\U884c`（大写 U + 4 位）导致字符损坏。

**绝对禁止（血泪教训）**：
- ❌ 正则替换含 `\n` 的 JS 模板字面量——会把转义序列变成真实换行，语法崩
- ❌ "整文件重建"——曾把 node_modules 里的 index.mjs 写成 **0 字节**，差点废掉运行副本
- ❌ 手写 Unicode 转义——中文必须用源文件原样，不手写 `\uXXXX`
- 卡住 3 次就止损：放弃接线，只提交 tools/ 三件套（formatExecutorResult 曾这么做，之后再补转发）

**第四步：动态集成测试** → `tools/test_task_profile_integration.mjs`
- 不只测纯函数，要测"接入守卫后行为真的变了"
- import 路径写 `'../index.mjs'`（相对权威源 tools/ 目录），**不要写死 `../node_modules/dsh-agent-harness/index.mjs`**——那是从 node_modules 工作目录写的，复制到权威源就断链

## 为什么改成 import 转发（原"为什么内联"已过时）

原设计担心"插件从 node_modules 加载，相对 import 会指错三副本不同步"——实际验证：
只要 tools/ 文件与 index.mjs 同目录且同步（本机 node_modules 里已同步），
`./tools/xxx.mjs` 能正确解析。而复制函数体内联带来的 Unicode 转义/正则清空风险远大于同步风险。
**结论：默认 import 转发；tools/ 版是唯一真相，index.mjs 只做转发。**

## 进度（2026-11-21 晚）

| 函数 | 状态 | 落地方式 |
|---|---|---|
| `taskProfile` | ✅ 完成 | 外置+单测 |
| `formatCorrection` | ✅ 完成 | 复制内联（ec0a7e4）|
| `formatExecutorResult` | ✅ 完成 | 三件套(a56d164)+内联(5e21f55) |
| `buildTrailText` | ✅ 完成 | 三件套(dfe48e5)+import 转发(440dce6) |
| `collectCorrectorInput` | ✅ 完成 | import 转发(03316cb) |
| `executeReadOnly` | ❌ 失败待重做 | 单测 5 FAIL+崩溃，未提交，残留已隔离到 cleanup |
| `guardDecide` | ⏳ 未做 | 中难度（cfg/state）|
| `stateOf` | ⏳ 未做 | 高难度（4 依赖）|
| `callLLM`/`runAudit`/`runCritic` | ⏳ 未做 | 最高难度，最后做 |

## 黄金基线

`data/baseline/trace_pre_refactor_20261121.jsonl`（3.5MB）+ `trace_report_pre_refactor.txt`。
每个函数外置后跑对照，确认 trace kind 分布与基线一致（不能只看单测全绿——今晚证明单测会假绿）。

## 反向检验铁律（2026-11-21 深度维护总结）

1. **dsh 进程启动后不热重载**——落盘的改动对当前进程不生效，必须重启才验证。
   07:54 启动后当晚所有 commit 的 index.mjs 修改，进程内存里一行都没跑。
2. **node --check 抓不到未定义函数**——`_verifyGate` 未定义调用能通过语法检查，运行时才 ReferenceError。
   接线后必须真实触发一次（或至少静态检查 import/定义配对）。
3. **权威源 ≠ 运行版**——agent 常在 node_modules 里改文件却不 commit，运行版会变成"半成品垃圾场"。
   每次验收必须 sha256 比对两版 + `git status` 确认 commit 落地。
4. **docs/ 与卡状态会滞后**——反向检验时必须源码级核对，不能信文档宣称。
