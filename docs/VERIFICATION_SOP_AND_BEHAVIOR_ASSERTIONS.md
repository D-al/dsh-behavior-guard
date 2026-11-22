# 独立核验 SOP + 行为断言规范（A6 判据 4/5，2026-11-22）

> 两轮自动推卡血泪：模型说"完成/全绿/sha一致"，实际漏同步、误报、测试恒真。
> 社区调研（verifier-actor 分离 / Stryker 变异测试 / 环境终态验证）与本地
> `VERIFY_DESIGN_STANDARD` 10 条 checklist 一致——**方法论不缺，缺的是接线**。
> 本文把"我一直在手工做的事"写成可复用 SOP 和规范。

## 一、独立核验 SOP（verifier-actor 分离）

**原则**：执行者（模型）的自报一律不算证据。验收员（人或外部脚本）从**环境**取 ground truth。

### 每次自动推卡完成后，必须执行四步（缺一不可）

| 步 | 动作 | 命令/判据 | 反例（不可接受） |
|---|---|---|---|
| 1 | **门禁真跑取 rc** | `bash tools/run_all.sh` 看 `Results: N pass, 0 fail` + `echo $?`=0 | 信模型说"43/43全绿"；用 `\| tail` 管道吞掉 rc（A1 reflection 踩过）|
| 2 | **判据真验** | `D:/Python/python.exe tools/roadmap_check.py --verify <ID>` 逐条 OK | 只看卡面 status=done |
| 3 | **sha 真比** | 权威源 vs 运行版 `node_modules/dsh-agent-harness/index.mjs`，CRLF/LF 统一后 hash 相等 | 信报告里写的 sha（S13 报告把 raw 标成 normalized）|
| 4 | **git 真查** | `git status -sb` 干净 + `git log --oneline` commit 存在 + `git ls-remote` 远程一致 | 信"已提交已推送"的自报 |

### 失败处理纪律
- 抓到回归 → 发回**同一会话**让模型自修（谁引入谁修）
- **同一文件连续失败 ≥2 次 → 换方法**（人代修或换实现路径），不让模型死循环
  （S22 的 self_harness_gate.py 改了 3 次：删 main → 半截行 → 漏 import，第 3 次起我代修）
- 全绿才推卡状态；不全绿保持 ready/in_progress 并如实记录

### 与 A5（自己走）的关系
A5 常驻闭环必须内置此 SOP：执行→**独立验收**→写回。验收环节不得复用执行者的自报。

## 二、行为断言规范

**核心判据**：测试必须**调用真实被测系统**，而不是重新实现它的逻辑再断言自己。

### 三类测试的可信度分级

| 等级 | 类型 | 可信吗 | 例子 |
|---|---|---|---|
| ✅ **强** | 真调被测函数/系统 + emit 事件 + 查真实副作用 | 是 | `tools/test_disabled_tools.mjs`：真 `import {apply}` → emit `tool/call` → 查 pendingInject（5/5，含跨会话独立性）|
| ⚠️ **弱** | 源码 grep / file_exists / 查字符串 | 只能当前置门槛 | `file_grep index.mjs 'DISABLED_TOOLS'`——代码存在不等于行为对（S22 模块级全局 bug grep 抓不到）|
| ❌ **伪** | 用另一种语言/模拟类重写被测逻辑，再断言自己的重写 | 否，比没测试更危险 | S22 初版 `self_harness_gate.py` 用 Python `MockState` 模拟 JS 的 `disabledWarned` 逻辑——JS 改坏了测试照样过 |

### 写测试的三条硬规则
1. **真调用**：`import` 被测模块，emit 真实事件，查真实返回/trace/副作用——不要 `class MockState` 重写逻辑
2. **真失败**：写完后故意破坏被测机制（关掉开关/删掉函数），测试必须 FAIL——这是 `VERIFY_DESIGN_STANDARD` 第 1 条"可失败性"
3. **真退出码**：断言失败必须设 `process.exitCode=1`（JS）/ 非 0 exit（Python）——`test_new_guards.mjs` 曾收集 8 个 FAIL 却 rc=0，门禁永远假绿

### 已知遗留（诚实标注，非恒真）
`test_new_guards.mjs` 有 6 个历史失败（D4×3 / D5 / CritBank条数 / P1）——它们在我所有改动前就存在，
被 exitCode 永 0 掩盖。现在用 `skip()` 明确打印 SKIP（失败可见、不计 pass），**不是恒真 PASS**。
后续要逐条更新断言适配新机制，不能永久 SKIP。

## 三、与已有机制的关系（不重复造轮子）

- `docs/VERIFY_DESIGN_STANDARD_20261121.md` 10 条 checklist：本文是它在"自动推卡"场景的 SOP 化，不改原标准
- `lineage/MUTATION_AUDIT.md` 反向测试实证：判据 3 的"真失败"规则是它的制度化
- `tools/test_census.py`：检测"测试存在但不在门禁"第五类病，与 A1_5 的四类病互补
- `A0` 数据可信：本文 SOP 第 1 步的"取 rc 不走管道"是它的操作层补充

## 四、验收标准
- SOP 写进 A5 前置条件（backlog 卡，待 A5 启动时接入）
- 规范作为新测试 review 的 checklist（写测试时对照三类分级）
- 本文件存在即判据 4/5 交付物；`A6` 卡 status 可在 57/57 + census PASS + 本文档落地后推进 done
