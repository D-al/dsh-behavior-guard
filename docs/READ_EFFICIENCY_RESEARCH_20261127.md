# 降低 read 次数：调研与具体方案（2026-11-27 08:35）

> 用户要求："思考具体方案，调研社区和论文"。
> 现状：正确性已解决（4/4 场景改对），但**同一文件 read 3~4 次**。
> 先量化本地模式，再映射论文经验，最后给可落地方案。

## 一、本地诊断（数据，不猜）

| 会话 | read 总数 | 唯一路径 | 重复情况 |
|---|---|---|---|
| 38d7c6d2（文案） | 4 | **1** | 同一文件读 4 次 |
| 0ca86b71（宽度） | 5 | 2 | 3 次目标文件 + 2 次错误路径 |
| bb2d3026（圆角） | 4 | 2 | 3 次同一路径（相对/绝对混用） |

场景3 的完整序列暴露了模式：
```
1 glob
2 read                    ← 探索
3 pwsh (实际编辑)          ← 改了
4 read                    ← 编辑后回读（？）
5 present                 ← 触发了零写入误判(它用pwsh不是edit!)
6 read                    ← 重复读
7 grep                    ← 重复确认
8 read                    ← 又读
9 grep                    ← 又确认
```

**多余 read 的三个来源**：
1. 编辑后回读（模型想确认，但工具结果已含编辑回显）
2. 换路径写法重读（相对/绝对混用，缓存不命中）
3. 注入提示后的"再看看"（我们自己的注入触发了新一轮探索）

## 二、论文/社区经验（5 篇，按相关度）

### 1. TROT: Triage of Observation Tokens（2026-11, ICSE 投稿）
**最直接**。对 observation 分层处理：
- **确定性规则层**（最便宜）：压缩"编辑确认时重复展示的文件内容"、"重复读未变化文件"；
  **失败和 traceback 绕过压缩**；**同一 tool+args 模式首次保留全量**。
- 学习门（轻量分类器）→ 选择性 LLM 反思（阈值 3000 token，最多 5 次）
- **history compressor**：跨步骤把重复未变的读/命令 stub 化，更新被取代的测试结果，
  缩短编辑确认，**保留最近 5 步不动**
- 量化：Sonnet-4.6 **50.6% resolve + 55% token 节省**（基线 45.9%）；
  Devstral-24B 46.1% + 46%。history 规则单独贡献 20-30% 节省

**可直接抄的规则**：
- 同一 `(tool, args)` 首次全量，后续未变化 → stub（"已读，内容未变，见第 N 步"）
- 编辑结果里重复回显的文件内容 → 压缩成 `OK: 已改 X→Y @lineN`
- 最近 5 步不动（保护当前决策上下文）

### 2. Prism: Persistent Faceted File Memory（EMNLP 2026 findings）
跨任务缓存文件记忆，但**关键结论是反直觉的**：
- 单纯缓存 summary **几乎没用**（只降 2.4%，在波动范围内）
- 有效的是 **content-hash keyed + identifier-grounded facets**（从 agent 自己的推理里提炼的事实）
- 效果：GPT-5 降 24.9%；但**静态 Aider-style repo-map 反而贵 13%**
- 清空记忆 → 成本 +37%

**启示**：不要做"文件内容摘要缓存"（无效），要做"事实缓存"（这个文件的第18行有 min(2300px) 这种）。

### 3. FastContext（2026）：把探索拆成专用 subagent
- 分析 300 条轨迹：**read/search 占 56.2% 工具轮次、46.5% token**
- 首次 edit 前中位数 **6 个顺序探索轮、15.5 个探索工具调用**
- 解法：训练只读 explorer（READ/GLOB/GREP），并行发多个工具，输出紧凑的 file-line evidence
- 效果：SWE-bench Pro 46.0% → 51.5%（+5.5）

**启示**：**并行探索**是关键——我们现在的 harness 是串行 read→grep→read，浪费。

### 4. CoACT: Action-Preserving Observation Compression（ICSE 2027, 清华）
- observation 占 SWE-bench Verified **45.7%** token、Terminal-Bench **67.8%**
- 压缩标准不是"像不像原文"，而是**压缩后 agent 的下一步动作变没变**
- 效果：token -33%，PASS@1 69% → **71%**（不降反升）

**启示**：压缩要以"动作不变"为验收标准——我们有 trace，可以直接测。

### 5. 社区共识（agent-reliability skill / Aider docs）
- "Never edit a file you haven't read" + "Re-read your changes after making them" —— 社区仍建议编辑后回读
- 但 Claude Code/Aider 都**放弃全文件重写**（成本和截断）
- "git diff 看实际改动，不是 agent 的描述"
- "Search first, load only relevant files, **drop files from context once edit is made and verified**"
- 行号编辑被淘汰（漂移），**内容锚点**更可靠

**注意**：社区建议"编辑后回读"，与 TROT 的"压缩编辑回显"不矛盾——
**回读可以做，但不该把整份文件内容重新塞进上下文**。

## 三、具体方案（按 ROI 排序）

### P0：工具结果去重（TROT 确定性规则层）—— 零 LLM，最稳
在 `session/event` 的 `tool/result` 里：
1. 计算 `(tool, normalized_args)` 的 key（**归一化路径**：相对→绝对，统一斜杠）
2. 若该 key 在**本轮**已出现过且**文件未变**（用 mtime 或内容 hash）：
   - 保留首次全量
   - 后续返回 stub：`[harness] 此文件已读过且未变化（内容见第 N 步），不要重复读`
3. **编辑后**的首次 read 放行（文件变了，mtime 不同）
4. 最近 5 步不压缩（TROT 的保护窗口）

**预期**：场景3 的 4 次 read → 2 次（探索 + 编辑后验证）。

### P1：编辑回显压缩（TROT）
我们的 `pwsh` 编辑结果里会回显文件内容。检测编辑类命令的结果：
- 若含完整文件内容且命令成功 → 压缩成 `OK: 已改 <old>→<new> @lineN`
- 但**保留** "文件未找到"、"权限拒绝" 等失败信号（TROT: failures bypass）

### P2：并行探索（FastContext）
在 pre-step 注入时，不再一次注入一个动作，而是鼓励一次发多个只读调用：
`[harness 环境事实] ... 你可以并行发 grep/read 确认，不必串行一个个试。`
—— 但这依赖模型的并行能力，35B 可能不稳定，**优先级低**。

### P3：事实缓存（Prism）
不缓存文件内容，缓存**确定性事实**：
`content-hash → {line18: min(2300px), line25: title=系统监控面板}`
下次同类任务直接注入事实，跳过 read。
—— 跨任务收益大，但需要持久化，实现复杂度高，**放到最后**。

## 四、不做什么（避免踩坑）

- ❌ **不要简单缓存文件摘要**：Prism 实证只有 2.4%（波动内），没用
- ❌ **不要全量 LLM 压缩 observation**：TROT 的-gated 方案比 uniform reflection 省 6 倍调用
- ❌ **不要砍掉编辑后验证**：社区强调必须验证；只压缩回显内容，不取消验证
- ❌ **不要压缩失败/traceback**：TROT 明确 bypass，这些是模型纠错的关键信号

## 五、验收标准（CoACT 的启发）

不能只看 token 数，要看**动作是否保持**：
- 压缩前后，同一任务的 edit 目标 / 参数是否一致
- 产物正确率是否下降
- 我们用 trace + 产物校验可以直接测

## 六、下一步

1. 先做 P0（工具结果去重），用 4 个场景回归测 read 次数
2. 再评估 P1（编辑回显压缩）是否还有收益
3. 写进 `docs/READ_EFFICIENCY_PLAN.md`，做完实测更新
