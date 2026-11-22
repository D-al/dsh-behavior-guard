# A6「验收可信度加固」落地草稿（待调研补充后定稿）

## 已本地验证的事实（2026-11-22 09:30）

### 门禁覆盖缺口（BLIND-1）
- `tools/test_*.mjs` 34 个：run_all.sh 用 glob 自动全纳入 ✓
- `tools/test_*.py` 12 个：**只有 1 个显式在 run_all（8%）**，11 个从未被 CI 跑
- 还有 `self_harness_gate.py` 带 self_test 但命名不符（上轮已手动纳入）
- 实锤：S22 改坏 self_harness_gate.py 时 43/43 全绿
- 实锤：`test_controllable_forgetting.py` 8/11 真 FAIL，潜伏至今；A1 reflection 明确记录
  "当时选择换成别的测试绕开，没修"——坏测试因不在门禁而永久潜伏

### 恒真断言（BLIND-2/3）
全库扫描 4 处：
- tools/test_new_guards.mjs:167 (`inj !== null || true`)
- tools/test_new_guards.mjs:170 (`check(..., true, true)`)
- tools/test_build_trail_text_integration.mjs:99 (`check(..., true)`)
- tools/test_task_profile_integration.mjs:75 (`check(..., true)`)
MUTATION_AUDIT.md 第2节早就记录过 new_guards 两处，备注"等空闲时段用 mock fetch 重写"——一直没做。

### 项目已有的社区解法本地版（关键！）
- `docs/VERIFY_DESIGN_STANDARD_20261121.md`：10 条判据 checklist，来源明确写着
  **mutation testing / 契约测试 / SWE-bench / τ-bench / RRSI / OverclaimBench**
  - 第1条可失败性、第2条存在≠生效、第4条环境终态>自报、第6条负向断言、第9条量化审计
- `lineage/MUTATION_AUDIT.md`：已做过故障注入反向测试，抓出过恒真断言
- `tools/check_verify.py`：已检测判据四类病（自引用/格式不匹配/恒真/sid污染）
- `tools/test_mutation_guards.mjs`：mutation harness 已有

**结论：方法论不缺，缺的是"接进自动推卡流程"+"门禁覆盖审计"这一环。**

### 原型验证：第五类病检测可行
```
[GATE-COVERAGE] mjs_glob=True mjs_total=34
[GATE-COVERAGE] py_total=12 py_explicit=1 missing=11
[VERDICT] FAIL: 测试未纳入门禁
```
已验证用 `re.findall(r'tools/(test_[\w]+\.py)', run_all_text)` vs `glob('test_*.py')`
可精确检出缺失。可直接写进 check_verify.py。

## A6 落地方案草稿（4 判据）

1. **py 测试全纳入门禁**：run_all.sh 把显式 py 列表改为 glob 自动发现
   - 前置：修 test_controllable_forgetting.py（3 个过时断言：状态表 9→10、watcher 函数名改了）
   - 预期门禁数 44 → 55
2. **check_verify.py 加第五类病**：`not-in-gate`（测试文件存在但 run_all 不跑）
   - 原型已验证，输出 missing_list
3. **清 4 处恒真断言**：用真行为断言替换（new_guards 两处需 mock fetch）
4. **行为断言规范文档**：明确"必须调用真实被测系统，禁止源码 grep / MockState 重写冒充"
   - 真范例：tools/test_disabled_tools.mjs（真调 apply()+emit）
   - 反范例：self_harness_gate.py 里的 Python MockState 重写 JS 逻辑

## 待调研补充
- 社区对 5 个问题的成熟做法（test discovery、mutation testing、verifier-actor 分离、retry budget、data lineage）
- 与已有 VERIFY_DESIGN_STANDARD 10 条的映射（避免重复造轮子）
