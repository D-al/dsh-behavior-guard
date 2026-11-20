# 将来时承诺守卫（A1_6，2026-11-20）

> 根因：A1_5 推卡时 agent 输出"现在进入核心：编写 check_verify.py"后结束回合、文件不存在。
> 守卫 L0-L3 全漏——L1 的 `WRITE_CLAIM` 只认过去时（已写入/已创建），
> 将来时（现在写/接下来创建）能过 L3 的长度门槛又不触发 L1 的路径校验。

## 1. 设计：把将来时承诺当成"声明"

guardDecide 的 L1 原本只校验**过去时声明**的文件存在+mtime。修复方式是扩展"什么算声明"：

```
WRITE_CLAIM  过去时：已写入/已保存/已创建/生成到/written to...
FUTURE_CLAIM 将来时：现在/接下来/下面/马上/立即 + 写/创建/生成/编写/实现/建立 + 路径
WILL_CLAIM   我将/I'll + 写/创建/... + 路径
```

三个正则合并为 `CLAIM_PATTERNS`，`claimedPaths()` 遍历所有模式提路径 →
L1 对提取到的路径做**环境校验**（存在 + 本轮 mtime 新鲜）。

**关键**：不是"文本匹配到就放行"，而是匹配到承诺后**仍以环境事实为准**——
承诺了产物但文件不存在 → 触发纠错消息，不允许蒙混过关。

## 2. 实现位置

- `index.mjs:593-596`：三个正则定义
- `index.mjs:622`：`CLAIM_PATTERNS` 数组
- `index.mjs:624-636`：`claimedPaths()` 遍历所有模式
- `index.mjs:1547`：`guardDecide` L1 调用 `claimedPaths()`（原有逻辑不变）

## 3. 测试矩阵（tools/test_future_claim_guard.py，8/8 PASS）

测试从 index.mjs **提取正则本身**（单一源，避免测试复制正则导致漂移），用 Python re 验证：

| 样本 | 期望识别 | 结果 |
|---|---|---|
| 我已写入 tools/check_verify.py | ✅ 声明 | PASS |
| 现在编写 tools/test_future_claim_guard.py | ✅ 声明 | PASS |
| 接下来创建 docs/FUTURE_CLAIM_GUARD_20261120.md | ✅ 声明 | PASS |
| 马上实现 ./tools/foo.mjs | ✅ 声明 | PASS |
| 我将写 ./tools/bar.py | ✅ 声明 | PASS |
| 下一步我会考虑优化一下（无产物）| ❌ 不识别 | PASS |
| 正在分析现有逻辑，稍等（无产物）| ❌ 不识别 | PASS |
| 这是一个纯咨询问题 | ❌ 不识别 | PASS |

## 4. 测试抓到的真 bug（接管的价值）

agent 写的 `WILL_CLAIM` 原正则要求 `(?:我将|I'll)\s+`（强制空格），
但中文"我将写"没有空格 → **中文分支永远不匹配**（"I'll write" 也缺英文动词）。
测试第 5 项 FAIL 暴露了它，已修：去掉强制空格 + 补英文动词 write/create。
修复后 8/8 PASS。

这正是"文档宣称完成 ≠ 实际生效"的又一例——如果我只做 node --check 就 apply，
会留下一个"看着有正则、实际漏拦中文我将承诺"的假防线。

## 5. 误判边界

- "下一步我会考虑..."（无具体产物）→ 不拦（正常规划）
- 中文路径 / 无扩展名 → 当前正则只认绝对路径或带 .py/.mjs/.md 的相对路径，故意保守
- 重复/长文本 → 逐行匹配，每行独立判定

## 6. 沉淀

这是"只输出好"的将来时变体的治本防线。与 A1_5 的 check_verify.py（查判据假绿）
形成互补：A1_5 管"判据会不会骗人"，A1_6 管"完成声明会不会骗人"。
