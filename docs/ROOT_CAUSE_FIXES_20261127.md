# 源码级根因修复报告（2026-11-27 11:02）

> 用户要求："全部整理修复一下，有哪些是可以从源码级别修复根本原因的，都做了"
> 做法：派 3 个只读子代理分别盘点 harness 缓解项、llama.cpp 上游、测试/技术债，
> 然后按"能否根治"分类执行。

## 一、最重要发现：一个真实的运行时 BUG

`index.mjs` 里 `DATA_BOUNDARY` 常量被误插进 `formatCorrection` 的 if 块内部（块级作用域），
而顶层 `formatExecutorResult` 引用它 → **代执行成功时抛 `ReferenceError`，纠正器直接失效**。
现有测试全测 tools 规范副本或只做字符串匹配，从未覆盖内联版，所以一直没暴露。

**根治方式**：不是把常量挪位置，而是**删除内联副本、改为 import 规范副本**——
一次性消灭这个 bug + 双份代码漂移（已实测 `DANGEROUS_ARG` 两版不等价，内联版缺 curl/wget 模式）。

验证：`node --input-type=module import` → `module loaded OK` / `APPLY OK`；删了 78 行重复代码。

## 二、已从源码级根治（8 项）

| # | 问题 | 根治（非缓解） | 验证 |
|---|---|---|---|
| 1 | format 双份副本漂移 + DATA_BOUNDARY ReferenceError | index.mjs 改为 `import { formatCorrection }` / `import { formatExecutorResult }`，删除两个内联函数 | F24 + 真实 import/APPLY OK |
| 2 | realpath 失败 fail-open（`catch{return norm}`） | 改 `return null` fail-closed | F22 |
| 3 | TOCTOU：realpath 后路径重解析 | 新增 `readSafeFile()`：`openSync` + `fstatSync` + `readSync`，并校验 realpath 身份四元组（dev/size/mtime/ctime） | F23 + fd 读取实测 |
| 4 | criticAccepted 一次 ACCEPT 同时关闭 Critic + D4 | D4 条件移除 `criticAccepted`，改为只看**独立验收**（spawn/verify_agent）；低置信 REJECT 强制触发 D4 | F21 + 每轮重置 |
| 5 | llama.cpp 构建脚本 SRC 路径失效（`D:\llama-b12244-src` 不存在） | 自动探测 SRC（env → engine → 旧路径），fail-fast | 实测探测到 engine 路径 |
| 6 | autoparser 空白补丁每次升级手工重打 | `build_b12244.py` 内自动幂等补丁：**函数体限定**、内容匹配（非行号）、目标漂移 fail-fast | 幂等 `already-applied` ×2 + 漂移 fail-fast exit=3 |
| 7 | CRLF/LF 混用导致 diff 全文件噪声 | 新增 `.gitattributes` 显式 `eol=lf`（bat/ps1 保持 crlf） | Python 文本读写后 `git diff` 为空 |
| 8 | 攻防演练断言过时（10 个假阳性） | 老脚本迁入 `tools/archive_tests/` 并标注历史；新脚本 `tools/wargame_fixed_verify.mjs` 为唯一权威，补 F21-F24 达 24 项 | 24/24 PASS |

## 三、评估后**不做**的项（有理由）

### D5 判定前移合并注入（子代理建议做）
子代理建议把 D5 判定移到所有 early return 前，与 pendingInject 合并注入。
**我的判断：这是优化不是根治，不做。**

理由：
- 当前 `auditDebt` 快照（3629）在所有**清 trail**的分支（3672 pendingInject / 3698 pendingCorrector）之前，
  其他 20+ 个 early return 都不清 trail——**证据不丢这一点已经是根治的**
- 合并注入需要把 10-20s 的 audit LLM 塞进安全信号分支，延迟安全提示
- 会改变消息形态、预算记账拆分、需同步多个测试，风险 > 收益
- D5 门控下一轮仍会触发，没有漏审

### 代执行内容提示注入（部分根治）
- **已做**：`DATA_BOUNDARY`/`DATA_END` 边界标记、规范副本单一真相源
- **不做**：过滤/转义内容本身。证据必须原样保留（设计原则），且 `createMessage` 只有 user 通道，
  真正的 role 隔离需要改 dsh 引擎消息模型——超出本项目边界
- **诚实结论**：强提示注入仍可能影响弱模型，这是残余风险

### format reason 改枚举 schema
corrector 已启用 constrained JSON（上一轮），reason 仍有自由文本但已过 `sanitizeReason`。
改枚举需改 prompt schema 并影响纠正质量，收益不明确。

## 四、无法从本项目源码根治（诚实边界）

1. **上游 llama.cpp 空白 bug**：一手核实 b12244 与 v1.0.0 该文件字节一致，上游从未单独修。
   #29307 虽于 2026-11-22 合并，但是破坏性重构（改了 `p.until()`/`trigger_rule()` 语义、删 `p.ac()`），
   补丁需按新 API **重做**而非"自动套用"。#29949 仍是 OPEN Issue。
   → 本项目能做的是"自动化补丁 + fail-fast"，不能是"永久消除补丁"。
2. **模型行为方差**：同任务同注入，一次第 4 步 edit 成功、一次 18 步不 edit。
   这是 35B Q4 的能力边界，不是 harness 源码能修的。
3. **D4 present-gate 增加拦截**：移除 criticAccepted 短路后，D4 触发率上升（有
   `maxPresentGatePerSession` 预算保护）。真实会话 `d1722ae1` 出现 handoff_gate 拦截、
   产物未改——这是守卫生效，不是 bug，但需要观察误拦率。
4. **TOCTOU 四元组在 Windows 上 `ino` 不可用**，用 dev+size+mtime+ctime 代替；
   理论上高频写入文件可能误判（fail-closed 安全侧），100% 保证需 Win32 `GetFinalPathNameByHandle` native addon。

## 五、验证结果

```
test_audit_allfix.mjs           25 PASS / 0 FAIL
test_wargame_fixes              ALL PASS
test_wargame_gaps               ALL PASS
test_all_remaining              ALL PASS
test_format_correction          全部通过
test_format_executor_result     全部通过
test_collect_corrector_input    19/19
wargame_fixed_verify            24 PASS / 0 FAIL
模块 import + apply             OK
两版 sha256 一致                OK（4 个文件）
真实 dsh 重启 probe             updated 02:57:23
真实会话 trace                  写入正常（ambiguity_detected/skill_card/handoff_gate）
```

## 六、提交链

```
rootfix: eliminate inline formatCorrection/formatExecutorResult duplicates
rootfix: fail-closed realpath + fd-based readSafeFile (TOCTOU)
rootfix: D4 independent verification
rootfix: autoparser patch automation + SRC auto-detect
rootfix: .gitattributes unified LF
rootfix: archive stale wargame assertions; promote verified script (24 checks)
```

## 七、给未来的铁律

1. **"加标记/加快照"是缓解，不是根治**——判断标准是：攻击者能否绕过？能绕过就是缓解。
2. **纯函数必须单一真相源**——内联副本 + 规范副本 = 必然漂移 + 未覆盖 bug。
3. **补丁自动化的三要素**：内容匹配（非行号）+ 函数体限定 + 目标漂移 fail-fast。
4. **`.gitattributes` 显式 eol** 才能根治 Windows `core.autocrlf` 噪声（`* text=auto` 不够）。
5. **每次改完 index.mjs 必须手动 `import` 验证**——上次孤儿 import 导致 harness 静默的教训。
