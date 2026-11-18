# 新功能使用指南（2026-11-18 凌晨新增）

> 醒来后 5 分钟能上手：这些机制**自动生效，不需要你做任何事**——但知道它们存在，能帮你判断输出为什么长这样。

## 一、你会看到的新注入（都是 harness 打的标签）

| 注入标签 | 何时出现 | 含义 / 你该怎么做 |
|---|---|---|
| `[harness 控制回合]` | 每 8 步 | 模型被要求做一次元决策（已确立/已排除/下一步候选）。**看到它说明长任务在自检** |
| `[harness 技能可用]` | 任务命中技能关键词 | 附了一个手册路径（如发布插件 7 步）。模型可能会去 read 它 |
| `[harness 危险操作]` | 命令含 rm -rf / reset --hard 等 | 模型被要求先说明"删什么、为什么、有没有更安全的办法" |
| `[harness 操作提示]` | 覆盖写 / git checkout -- 等 | 提示先核对路径、必要时备份 |
| `[harness 产物深检]` | present 前 | 确定性检查发现问题（占位符/缺依赖/重复段落…）|
| `[harness 语法检查]` | write/edit 后 | 刚写的 .py/.json/.yml 有语法错 |

## 二、三个新工具

### 1. 看会话成本（trace）
```bash
cd D:/WorkBuddyWorkSpace/2026-10-13-20-41-43/bench
python trace_report.py           # 最近 3 个会话
python trace_report.py --all     # 全部
```
输出：步数 / 工具调用分布 / 失败率 / **LLM 调用（审计+评审）次数与累计耗时** / 重试次数。
→ 这个能直接回答"审计到底值不值"。

### 2. 看技能库
```bash
ls bench/skills/
```
现有 7 个：release-plugin / debug-llama-server / verify-artifact / web-fetch / git-workflow /
session-debug / harness-debug。
→ 想让模型"以后遇到这类任务都按这个流程做"，就新建一个 md（frontmatter 写 name/summary/keywords）。

### 3. 配置一致性检查
```bash
python config_check.py
```
比对 `.env.llama` 与 `llama-router-preset.ini` 的 23 个重叠键（true/1 等价归一）。
→ 上次它抓到 2 处真不一致（n-cpu-moe 41/40、moe-cache-mib 900/1350），已修。

## 三、如果你想调整

| 想做的事 | 改哪里 |
|---|---|
| 关掉某个机制 | `D:/Brain/dsh-data/profiles/desktop/cordis.patch.yml` 里 agent-harness 的 config（如 `controlEnabled: false`）|
| 改控制回合频率 | `controlEverySteps`（默认 8）|
| 技能卡太多/太少 | 改 `bench/skills/*.md` 的 keywords，或 `maxSkillCardsPerSession` |
| 改审计触发阈值 | `noProgressSteps`（默认 6）、`specAcceptanceMin`（MTP 信心阈值 0.65）|
| 关掉危险操作提示 | `dangerGuardEnabled: false` |

改完一律：`pnpm update dsh-agent-harness` → 重启 → 看探针时间戳。

## 四、怎么看"改得好不好"

1. **短任务**：`python tools/agentlab.py`（7 项，约 4 分钟）
2. **长任务**：`python projectlab.py P5`（交付级，约 7-15 分钟）
3. **真实会话**：跑一个任务后 `python trace_report.py` —— 看 LLM 调用占比、工具失败率

⚠ **单次结果有 ±10% 波动**（模型温度 0.6 单次采样），判断好坏至少 2 次取中位。

## 五、当前版本
`dsh-agent-harness v2.14.0`（v2.9 双向合流 → v2.10 短期四目标 + 权限代劳 → v2.11 长期地基 GWT/FEP）
版本史见 [CHANGELOG.md](../CHANGELOG.md)，目标状态见 [ROADMAP.md](../ROADMAP.md)。
