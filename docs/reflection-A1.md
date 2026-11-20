# Reflection: A1 — 会记路（机器判据 + dry-run 核验）

> 本卡由 agent 在**新会话**里 claim 并做主体分析（识别判据矛盾、提出"给归档项补真实自动判据"方案，
> 该方案由用户弹窗拍板）。观察者完成了 12 张 done card 的机械写入、判据格式修复与收尾提交。
> 中途两次因 35B `bad allocation` / 终端 ENOENT 退化，换了两次会话。

## 1. 卡面两问

### Q1: 回测里有没有"判据 PASS 但其实没做"的假阳性？

**有，而且差点发生。** 我给 12 张归档卡配判据时，第一版把 `S_FORGET`（可控遗忘）指向
`test_controllable_forgetting.py`——直接跑看起来"9/11 PASS、rc=0"（我用管道 `| tail` 看输出，
退出码被管道吞了）。写进 dry-run 后它显示 `rc=1 PASS=9`，实际是 **9/11 通过、2 个测试真 FAIL**
（"watcher 有月度 decay 调用" / "watcher 有假记忆自检"）。

如果我当时按"看起来 rc=0"就宣称完成，这就是典型的"判据 PASS 但没做"假阳性——
归档项本身没全过，却被当成 done card 塞进判据链。**修复**：把 S_FORGET 换成 `S_OUTCOME`
（对应 `test_outcome.mjs`，实测 6/6 全过、rc=0），不用过关测试凑数。

**教训**：看脚本退出码必须绕开管道（`set -o pipefail` 或直接跑取 `$?`）；管道会吞掉 rc 制造假绿。

### Q2: 哪些判据太松/太紧，需要调阈值？

**太紧（误拒）**：`test_pass` 判据原本只匹配 stdout 里 `^PASS`（裸行），但我自己的 dry-run 输出
格式是 `[PASS  ] ID ...`（方括号）——导致 `verify A1` 一直显示 `rc=1 PASS=0`，明明 dry-run
的 SUMMARY 是 PASS=16。修复：`roadmap_check.py` 的 test_pass 正则改为同时匹配 `^PASS` 和 `^\[PASS\s*\]`。

**太松（误报）风险**：如果判据用 `file_exists` 指向一个必然存在的文件（如 `tools/roadmap_check.py`
本身），所有卡都会 PASS——这正是卡片 caveat 禁止的。我给 12 张归档卡全部用 `test_pass` 真跑测试，
`min:1` 要求 stdout 至少一行 PASS 且 rc=0，避免了恒真判据。

## 2. 判据矛盾的解决（本卡最核心的决策）

**矛盾**：A1 判据要求 `dry-run PASS>=16`，但 dry-run 统计全部 23 张卡——当时只有 4 张 done 卡
能 PASS、15 张未完成卡是 manual、4 张 FAIL。**要达到 16 必须加 12 张 done card**，而 §7 归档的
S1-S9 等项根本不在权威块里（只在 Markdown 表格里）。

**用户拍板**（弹窗）：选"给完成卡补真实自动判据"——保持统计全部卡，把 §7 归档项加进权威块作为
done card + 真实测试判据，不用"只数归档项"的取巧方案。已按此实现：12 张新卡全部指向真实全过的
test 脚本，dry-run SUMMARY = PASS=27 FAIL=11 MANUAL=15（未完成卡仍 FAIL/MANUAL，零误报）。

## 3. CritBank 教训

```yaml
signal: "归档项 S_FORGET 的测试实际 9/11 FAIL，但用 `python xxx | tail` 看时退出码被管道吞掉，误以为全过"
lesson: "看脚本是否通过必须取真实退出码——管道会吞 rc 制造假绿。判据指向测试脚本时，必须用 test_pass（rc==0 且有 PASS 行）而不是肉眼看输出；给归档卡补自动判据前先逐脚本验证 rc，别拿没全过的测试凑数"
source: "reflection-A1.md"
trigger: "任何把现有测试脚本接入自动判据的卡"
action: "对每个候选测试独立跑一次并取 $?（不用管道），确认 rc=0 且 PASS 行齐全再写进 verify"
priority: high
```

第二条：

```yaml
signal: "test_pass 判据只匹配裸 ^PASS 行，自己的 dry-run 输出是 [PASS  ] 格式，导致 verify 假 FAIL"
lesson: "判据的输出格式匹配必须覆盖所有 emits PASS 的工具：裸 'PASS xxx'（test_*.mjs）和 '[PASS  ] ID'（dry-run）。格式不匹配会让真完成被判 FAIL，比假绿更打击自治信心"
source: "reflection-A1.md + tools/roadmap_check.py"
trigger: "实现/审查 test_pass 类判据时"
action: "用两个不同格式的工具各跑一次 verify，确认都能识别 PASS"
priority: medium
```

第三条（递归类）：

```yaml
signal: "A1 原判据是跑 roadmap_check.py --dry-run，但 dry-run 遍历到 A1 时又执行这条判据 → 无限递归，verify 6 分钟不停"
lesson: "判据 cmd 绝不能调用包含自己的命令（自引用）。需要'统计全部卡'这类判据时，写独立回测脚本（tools/backtest_archive.py）——它只验目标产物、不读判据配置、不调用 dry-run，7 秒跑完无递归"
source: "reflection-A1.md + tools/backtest_archive.py"
trigger: "任何 test_pass 判据的 cmd 设计"
action: "确认 cmd 不会间接调用自己；给回测脚本单独计时（应远小于 verify 超时）"
priority: high
```

## 4. 终态验收（全绿）

```
roadmap_check --graph: 41 nodes / 22 edges / 0 cycle
roadmap_check --dry-run: PASS=27 FAIL=11 MANUAL=15（未完成卡无误报）
roadmap_check --verify A1: 2/2 PASS（rc=0 PASS=13）
backtest_archive.py: 13/13 PASS / 0 FAIL（7 秒，零递归）
self-test 14/14 | a35_real_diff 4/4 | run_all 17/17
```
