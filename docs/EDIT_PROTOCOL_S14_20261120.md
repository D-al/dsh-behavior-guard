# Edit Protocol Upgrade — S14 (降低复现负担)

**日期**: 2026-11-20  
**任务**: S14 — 编辑协议升级·降低复现负担  
**路线图**: `tools/roadmap_check.py` → S14

---

## 一、根因分析

### RoPE 偏移导致长上下文精确匹配退化

位置编码（RoPE / ALiBi 等）在长序列中引入的位置偏差会导致模型对精确字符匹配的敏感度下降。具体表现是——当 `old_string` 超过数百字符后，模型生成的文本会出现逐字漂移（character-level drift），而非语义级改写。

**关键文献**:

| 论文 | 发现 |
|---|---|
| arXiv:2607.16072 | RoPE 1D 偏移在长上下文中导致精确字符匹配能力严重退化 |
| arXiv:2510.12487 (Diff-XYZ, NeurIPS 25w) | "smaller open models benefit little from any formatting choice"——小模型对格式不敏感，但对精确锚点依赖度高 |
| Aider 基准测试 2024-06 | GPT-4o vs 35B 模型在小任务代码复现不一致率高达 59% |
| Claude Code #26996 | tab vs 空格缩进差异导致 edit 失败循环（6+ 分钟无进展） |

### Diff-XYZ 结论摘要

Diff-XYZ 实验表明：
- **小模型（≤35B）** 对格式选择几乎不受益，但对**最短唯一锚点**的匹配成功率显著高于长锚点。
- **大模型** 同样受位置编码影响，只是阈值更高（约 1300+ 字符才出现明显漂移）。
- 核心对策：**最小化锚点长度 + 压缩会话后强制重读**。

---

## 二、S14 协议内容

详见 `config/AGENTS.md` 中的「编辑协议：降低复现负担」小节。要点如下：

### 策略矩阵

| 场景 | 方法 |
|---|---|
| 短文件 (<400 行) | `write` 全文件（整块输出） |
| 长文件 (≥400 行) | near-read ±5 行 → 最短唯一锚点 → `edit` |

### 锚点规则
1. 从目标行第一个非空白字符起取到唯一为止
2. 排除注释、空行、无关行
3. 注意 tab/CRLF/NBSP 字节级一致性
4. 拿到 `old_string` 后立即发 edit，不要延迟

### 压缩/长会话后强制重读
触发条件：>50 步连续调用 / 行数不符 / 用户反馈丢失  
动作：重新 read 目标行 ±5 行，确认后再 edit

### Edit Doctor 模式
失败时三步：停止重试 → 重读 ±10 行 → 报告字节级差异（TAB/SPACE/CRLF/NBSP/DRIFT）→ 只重发修正后的短块；两次失败问用户。

---

## 三、验证

- `tools/test_edit_protocol.py` — 6/6 检查项 PASS
- `roadmap_check.py --verify S14` — 见 CI 输出

---

## 四、证据来源

1. arXiv:2607.16072 — RoPE position encoding offset in long contexts
2. arXiv:2510.12487 — Diff-XYZ, NeurIPS 2025 Workshop
3. Aider benchmark 2024-06 — model consistency rates
4. Claude Code issue #26996 — whitespace-induced edit loops
5. C-010 — truncation recovery via re-read strategy (~1300 char old_string baseline)
