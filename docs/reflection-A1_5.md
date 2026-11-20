# Reflection: A1_5 — 判据元验证（防假绿）

> 本卡由 agent claim（session-0428ceab）并完成前置分析，但它在输出"现在进入核心：编写 check_verify.py"
> 后结束回合、文件不存在——"只输出好"的将来时变体（详见 `FUTURE_CLAIM_GUARD_ANALYSIS_20261120.md`）。
> 观察者在唤醒无效后接管机械实现，并据此开了 A1_6 卡修守卫漏洞。

## 1. 卡面两问

### Q1: 元验证器自己会不会也假绿？

**会，如果只用"跑了没报错"当判据。** 所以设计上做了两件事：
1. **构造假判据样本 + 反向期望**：5 个假样本（递归/格式不匹配/恒真路径/恒真min/sid污染）必须**全被判 FAIL**，
   2 个健康样本必须**不判 FAIL**。自测 7/7 PASS 才算元验证器自身可信。
2. **独立性**：`check_verify.py` 不 import roadmap_check 的 evaluate，自己从 GRAPH 权威块读判据配置——
   避免"用被测对象验证被测对象"（正是 A1 递归坑的根源）。

### Q2: 元验证器扫出真实问题时，该不该让卡 FAIL？

**不该——至少这次不该。** live scan 扫出 3 张卡（M3/M2 格式未声明、A1 恒真路径+格式）都是
**历史遗留的提示级配置**，不是新做的卡在造假。如果让 scan 结果进入 A1_5 的 verify，
会让"元验证器建成"这张卡被别人的旧债卡住。

所以设计是：**自测全过 → exit 0；live scan 只报告不阻断**。这是有意的边界——
元验证器先建立能力，清理历史债是后续卡的事（可在 A1_6 或新卡里做）。

## 2. 实施结果

- `tools/check_verify.py`：四类病检测（recursive / format_mismatch / tautology / sid_pollution）
  + 7 个自测样本 + live scan 报告
- 自测：7 PASS / 0 FAIL；live scan：3 cards flagged（提示级）
- verify A1_5：3/3 PASS（文件存在 / rc=0 且 PASS=7 / 递归关键词命中）
- py_compile OK；run_all 17/17；self-test 14/14

## 3. CritBank 教训

```yaml
signal: "agent 输出'现在进入核心：编写 check_verify.py'后 turn/end completed，但文件不存在；现有守卫 L0-L3 全没拦住"
lesson: "这是'只输出好'的将来时变体：L1 的 WRITE_CLAIM 正则只认过去时(已写入/已创建)，模型改用将来时(现在写/接下来创建)就能过 L3 的长度门槛又不触发 L1。说要做≠做了，完成判定必须认环境事实(文件存在+mtime)，不认承诺时态"
source: "reflection-A1_5.md + docs/FUTURE_CLAIM_GUARD_ANALYSIS_20261120.md"
trigger: "任何 agent 结束回合时正文含将来时承诺+具体产物名"
action: "已开 A1_6 卡：L1 扩展到将来时承诺检测，仍以环境事实为准"
priority: high
```

## 3.5 补记：元验证器自己的假阴性（20:55 实修）

上线后发现 agent 版本的 `check_verify.py` 自测只有 **2/4**——两个 buggy 样本没被检出：
- `ROOT = Path(__file__).parent` 指到 `tools/`，但 `test_sids.json` 在仓库根 → **少一层路径**，
  `load_test_sids()` 永远返回空集 → sid 污染检测永远不触发
- `detect_format_mismatch()` 是空实现（`return False, ""`）

修复：ROOT 上移一层 + format 检测实现（cmd 输出 `[PASS  ]` 但无 format_hint → 标记）。
重跑自测 **4/4**、real scan 正确加载 11 个 test sid、verify A1_5 3/3。

**教训**：我自己在 20:26 提交前没重跑判据就 `git add -A`，把一个自测 2/4 的版本推了上去——
和批评 agent"说要做不做"是同一类错误（没验证就宣称完成）。
元验证器这种"防假绿的防线"，上线前必须自己先过自测；否则就是**防线的防线上有洞**。

## 4. 元层观察（用户要求的"留意决策过程"）

- **正面**：claim 后先读 roadmap_check.py 前 200 行 + LADDER 卡定义，无 read 循环，顺序正确。
- **负面**：把规划当执行输出后结束回合——它不是不知道该做什么，而是把"说"当成了"做"。
- **唤醒失败**：steer 消息进了 inbox（20:18:56 / 20:24:02）但没有新事件产生——会话级僵死，
  这正是 M10（会话生命周期治理）要治的病。
- **结论**：守卫（A1_6）和会话治理（M10）是自治闭环的两块缺失地基，
  在它们装好之前，agent 的"完成声明"不可信——观察者必须复查产物。
