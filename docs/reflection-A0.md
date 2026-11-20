# Reflection: A0 — 数据可信 · sid 黑名单

## 问题 1: 过滤后真实数据占比多少？还有哪种假数据没被黑名单抓到？

**操作过程**: 过滤前 trace 中 s1 类假数据占绝对多数（约 90%+）。由于 `test_sids.json` 是黑名单模式（显式列出要排除的 sid），而非白名单模式（只保留已知真 sid），所以：

- **已覆盖**: 单元测试注入的 sid (`s1`)、以 `outcome-`/`budget-*` 为前缀的批量生成 sid、`inject-test` 注入的 sid
- **未覆盖**: 
  - 其他测试框架生成的 sid（如 pytest session id、CI job id）
  - 手动触发但未标记为测试的会话
  - 未来新增的单测类型如果有新前缀

**结论**: 黑名单策略能去除大部分已知假数据，但不完整。如果后续发现过滤后真实样本仍不足支撑判断，需要切换到白名单模式（维护一个"已知真 sid"集合）。

## 问题 2: 有没有真实 sid 被误过滤？

**风险评估**: 低风险但非零。具体关注点：

| 黑名单项 | 误过滤可能性 | 说明 |
|---------|-------------|------|
| `s1` | 极低 | 这是单测专用短名 |
| `outcome-` | 低 | 仅当真实会话刻意用此前缀时 |
| `budget-1..4` | 极低 | 预算测试专用 |
| `b7332eb6` | **中等** | 看起来像 hash，如果是真实会话 ID 会被误杀 |
| `r`, `fb`, `b`, `inject-test` | 极低 | 太短/太特定 |

**建议**: 监控 `_learn_feedback.jsonl` 中的 sid 分布，如果发现某个被过滤的 sid 在反馈中有异常高频出现，应将其从黑名单移除并加入白名单。

---

## 可复用教训 (CritBank 格式)

```yaml
signal: "A0_sid_filter_blacklist_risk"
lesson: "黑名单过滤可能误杀真实 sid；若黑名单项包含 hash-like 字符串（如 b7332eb6），需定期 review 是否命中真实会话"
source: "reflection-A0.md"
trigger: "每次修改 test_sids.json 或添加新的过滤逻辑时"
action: "检查 _learn_feedback.jsonl 中被过滤 sid 的频率，确认是否为误杀"
priority: medium
```

---

## 实施细节

- **改动了 4 个文件**:
  1. `test_sids.json` — 新建黑名单
  2. `tools/learn_watcher.py` — 加 blacklist + 过滤
  3. `tools/weakness_miner.py` — 加 blacklist + 过滤
  4. `tools/trace_report.py` — 加 blacklist + 过滤
- **验证结果**: `roadmap_check.py --verify A0` 全部通过 (4/4 OK)
- **语法验证**: Python ast.parse 三文件均无报错
- **风险**: 黑名单只覆盖已知测试 sid，不保证去除了所有假数据
