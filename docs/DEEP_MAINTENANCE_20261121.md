# 深度维护报告（反向检验）— 2026-11-21

> 方法：不从"代码存在 / 文档宣称 / 单测过"正向推"完成"，而从**真实运行证据**倒推。
> 证据分层：真实 trace / 日志 / 三副本 sha256 / commit 落地 / 亲自跑单测 / 产物 mtime。
> 四路只读子任务并行调查 + 主代理第一手交叉验证。

---

## 一、最重要的系统性根因：时间线错位（贯穿所有"假完成"）

```
dsh 5 个进程启动时间：2026-11-21 07:54:02（至今未重启）
llama-server：07:54:05 / 07:54:07

commit 时间轴：
  e37aead graph三卡     07:44  ← 启动前，唯一真生效的
  65e269e frame粘性     07:52  ← 启动前
  b22373b 排除dsh       07:53  ← 启动前
  346780d roadmap判据   07:54:47 ← 启动后 45 秒
  c5cb823 revert限dsh   07:56
  36e8ab8 verify-on-edit 08:12
  ff16d50 S15门控        10:34
  ... 之后 all index.mjs 改动
```

**结论**：dsh 以 cordis 插件方式在**进程启动时**加载 index.mjs，无热重载证据。07:54 之后落盘的所有改动，当前进程内存里**一行都没跑**。这就是"代码存在+单测过"被当成"生效"的方法论失灵的总根源。

**推论**：今晚 agent 在 dsh 里做的所有"自修改地基"，对当前运行的 dsh 零效果；要真验证必须**重启 dsh 后采真实 trace**。

---

## 二、逐项判定表

### A. 函数外置四卡 —— 真完成（代码质量确实过关）

| 卡 | 单测(亲测) | 集成(亲测) | index 接线 | 两版sha | 判定 |
|---|---|---|---|---|---|
| formatCorrection | 25/25 | 4/4 | 内联(1551) | 一致 | ✅ 真完成 |
| formatExecutorResult | 56/56 | 17/17 | 内联(1606) | 一致 | ✅ 真完成 |
| buildTrailText | 17/17 | 12/12 | import转发(26/1228) | 一致 | ✅ 真完成（但见 D1 挂起 bug）|
| collectCorrectorInput | 19/19 | 4/4→6/6 | import转发(25/1415) | 一致 | ✅ 真完成（但见 D2 弱断言）|

- 全部 commit + push，三副本 sha256 逐字一致。
- 无恒真断言（我扫描过）。
- **但对运行中的 dsh 零生效**（时间线错位）。

### B. 框架层改动 —— 部分真 / 部分假

| 项 | 判定 | 关键证据 |
|---|---|---|
| roadmap_check ✅/[OK] 判据 | ✅ 真生效 | 独立脚本每次读磁盘；正则实测认✅/[OK]、不认汇总/失败文字，无假绿 |
| verify-on-edit ENOENT 修复 | ⚠️ 部分 | 代码两版一致，但 08:12 提交晚于 dsh 启动；trace 0 证据（设计不打点）；重启前无法证明生效 |
| frame_limiter 粘性释放 | ⚠️ 部分 | 代码两版一致、含 RELEASE_STREAK=4；但真实日志 291 行中 `no_3d_4streak` **0 次**——粘性逻辑从未真实走到；日志 08:05 后停写、无进程存活 |
| frame_limiter dsh 不豁免 | ⚠️ 部分 | 代码语义对（SKIP 只剩 dwm/system），但 revert(07:56)后无 dsh THROTTLE 样本可验证 |
| graph 三卡入权威源 | ⚠️ 部分 | 卡可读、graph/yaml 一致；但 ROADMAP.md 人读视图缺三卡、S16 曾状态冲突（本次已修）|
| **S15 门控** | ❌ **假生效/双重问题** | 权威源 index.mjs **从不接线**（commit 自承"未接入守卫"）；运行版却有 `const gate = _verifyGate(state)`——**`_verifyGate` 全文无定义无 import**，执行必抛 ReferenceError 并被最外层 catch 吞掉，连带跳过 Critic 评审 |

### C. 文档层 —— 多项过时/假失败

- ❌ **S11 / A1_7 是"假失败"**（不是假完成）：功能真在（S11 覆盖 8 种写工具 `cfg.writeTools.includes(c.name)`；A1_7 有 `review_verdict`×3 / `rubric_version`×7 打点），但判据 regex 写错 + 测试文件从未落地 → done 卡恒 FAIL。**本次已修判据，两卡转 PASS**。
- ⚠️ REFACTOR_PATTERN 文档自称"三段式"实列四步、"必须内联"已被 import 转发推翻、"建议先做"的三函数已完成。**本次已重写**。
- ⚠️ CHANGELOG 停更在 2.26.5；**本次补 2.26.6**（含被证伪方向）。
- ⚠️ 权威源定义多重矛盾：CHANGELOG 说 ROADMAP.md 内嵌块、roadmap_check docstring 说 LADDER、实际 load_ladder 读 ROADMAP_GRAPH.md。**已在 ROADMAP 头部澄清**（docstring 未改，留待后续）。

---

## 三、本次已修复（维护动作）

1. **运行版 index.mjs 坏接线清除**：用权威源覆盖（sha 1dc1235），`_verifyGate` 未定义调用归零 —— 避免下次重启 ReferenceError。
2. **executeReadOnly 失败残留隔离**：运行版 `execute_read_only.mjs` + 测试移到 `D:/Brain/_cleanup_20261118/execute_read_only_failed_125004/`（可逆，未删除）。
3. **buildTrailText 单测挂起 bug**：CLI 入口守卫 `argv[1].endsWith('build_trail_text.mjs')` 会误匹配 `test_build_trail_text.mjs`（实测 true）→ 单测读 stdin 挂起。改为精确 basename 匹配。**run_all 从 90s 超时变成 35/35、rc=0**。
4. **collectCorrectorInput 弱断言**：测试4原为纯存在性恒真；改为真检查（真调用 + 真传参）+ 负对照，6/6。
5. **S11/A1_7 假失败判据修正**：regex 对齐真实代码，移除不存在的测试文件引用，两卡 PASS。
6. **S16 状态统一**：yaml ready→done，与 graph 一致。
7. **文档维护**：CHANGELOG 2.26.6、REFACTOR_PATTERN 重写（import 转发 + 禁令 + 反向检验铁律）、ROADMAP 头部/张数、package 版本同步。
8. **一致性收敛**：consistency 38 PASS，lock→b1b1bb1，全部 push。

---

## 四、仍未解决 / 需你决策

1. **dsh 从未重启** —— 所有 index.mjs 改动未经真实运行验证。是否重启 dsh 做一次真实 trace 采集？（重启会加载新代码，也会验证坏接线是否真清除）
2. **S15 门控未接线** —— 模块存在（57/57）但从未接入守卫。是继续接线（这次要静态检查 import/定义配对），还是把卡状态从 done 改回 doing？
3. **frame_limiter 进程已死**（日志停 08:05）—— 粘性释放没跑过。要不要重新拉起并观察真实 THROTTLE/reason？
4. **历史 12 张 FAIL 卡**（S1/S2/S4/S7/regression_106 等）—— 部分是判据损坏（`KeyError: 'path'`），部分可能是假完成。**不在本次范围**，需另开一轮。
5. **REFACTOR_PATTERN docstring / 权威源定义矛盾** —— roadmap_check.py 头部 docstring 仍说 LADDER 是权威源，与实际不符（本次只在 ROADMAP 澄清，未改代码注释）。

---

## 五、方法论沉淀（写进 REFACTOR_PATTERN）

1. dsh 进程启动后不热重载——落盘 ≠ 生效，必须重启采 trace。
2. `node --check` 抓不到未定义函数——接线后必须真实触发或静态检查 import/定义配对。
3. 权威源 ≠ 运行版——每次验收 sha256 比对 + git status 确认 commit。
4. 卡状态 done ≠ 判据通过——S11/A1_7 是 done 卡恒 FAIL 的假失败；反向要查判据本身对不对。
5. 文本判据（grep/正则）易写错也易恒真——必须配负对照。
6. 文档宣称 ≠ 代码现实——双向核对，尤其 CHANGELOG/状态三文件。

---

## 六、追加：用户指出"GitHub 人读路线图没更新"后的二次深度维护（13:01-13:25）

### 根因（用户投诉的直接原因）
`roadmap_check.py --refresh` 只重渲染 `HUMAN_CARDS` 区（23 张非 done 卡），
**漏刷 `HUMAN_PROGRESS` 进度表**——S15/S16 是 done，从不出现在人读视图；
且人读进度表的"完成证据"列写死 `docs/reflection-{id}.md`（大多不存在，假链接）。

### 修复
1. 抽出公共 `render_human_progress(data)`，`save_authoritative` 与 `--refresh` 共用（防漂移）；
   `--refresh` 现在同时刷 CARDS + PROGRESS 两区。假链接改为真实 evidence_log。
   → S15/S16 现在出现在 GitHub 人读进度表（✅ done），进度表 26→30 项。
2. ROADMAP.md 全文状态一致：line66 旧"--next=NO_READY_ITEM/自治耗尽"→ S12（与 line51/333 一致）；
   "23张卡"→53张、"35项"→30项；README 版本 2.26.2→2.26.6、脚本数不写死。
3. docs/README.md 补 REFACTOR_PATTERN_20261121 / DEEP_MAINTENANCE_20261121 索引。
4. 三文件权威定义统一：状态权威=ROADMAP_GRAPH.md / 语义=CAPABILITY_LADDER.yaml / 人读=ROADMAP.md
   （原 CAPABILITY_LADDER.yaml meta 自称 authority=自己、roadmap_check docstring 也说 LADDER 权威，均改）。
5. **判据假失败/假绿根治**（反向检验副产品）：
   - S4/S7/gpu_guard/rebaseline 的 `file_exists` **缺 path** → KeyError 恒 FAIL；补真实文件路径。
   - S15 verify 原本查 `MUTATION_AUDIT.md` + `test_task_profile`（与选择性验证无关却会 PASS）→ 改查
     `selective_verification.mjs` + 它自己的 57/57 单测。
   - roadmap dry-run: PASS **24→28**，FAIL **14→10**，KeyError 消失。

### 反向检验（用户强调"记得反向检验"——逐条从远端/运行版倒推，不看我改了什么）
| # | 检验 | 方法 | 结果 |
|---|---|---|---|
| 1 | GitHub 人读路线图真更新 | `git show origin/main:ROADMAP.md` | ✅ S15/S16 done、next=S12、53卡/30项 |
| 2 | README 远端版本 | `git show origin/main:README.md` | ✅ v2.26.6 |
| 3 | refresh 修复在远端 | `git show origin/main:tools/roadmap_check.py` | ✅ render_human_progress×3 + HUMAN_BEGIN/HUMAN_END/progress |
| 4 | S15 判据远端正确 | 从远端 blob yaml.safe_load | ✅ 测 selective_verification 自身 |
| 5 | 5 张卡判据远端正确 | 从远端 blob 解析 | ✅ path/cmd 均真实 |
| 6 | 运行版 vs 权威源 sha | sha256 逐文件 | ⚠️ 首轮抓到 GRAPH 未同步 → 已修 → 复验一致 |
| 7 | lock 指向最新 commit | grep lock + git HEAD | ⚠️ 首轮指向旧 commit → 已修 → 三处一致 f02bcd5 |
| 8 | **负对照（防恒真）** | 临时把 S15 test cmd 改成不存在文件 | ✅ 真 FAIL（rc=1 PASS=0）→ 恢复后 PASS，判据非假绿 |

**反向检验的价值实证**：第 6、7 项是我自查"通过"但反向查出的真遗漏（运行版 GRAPH 没同步、lock 指向旧 commit）——
靠"我改了文件 + 本地测试过"根本发现不了。

### 最终状态
HEAD = origin/main = lock = `f02bcd5`；门禁 35/35；roadmap PASS=28 FAIL=10 MANUAL=15；
consistency 38 PASS；工作区干净。剩余 10 FAIL 为历史遗留卡（非本次范围）。
