# 具体应该怎么办：确定性消歧成功（2026-11-27 07:55）

> 用户早问："那具体应该怎么办？"
> 答案：**别让模型选，harness 用规则确定性算出答案，把绝对路径+行号当既定事实注入。**
> 实测首次端到端成功：产物从 1400px → **2300px**，另一个同名文件未动。

## 一、根因诊断（为什么昨晚全失败）

harness 里早就有"独立纠正器 + 代执行"机制，设计注释写着：
> "构造性消除传递损耗：主模型不抄参数、不重调用，直接消费执行结果。"

但有两个断点：
1. **代执行器只支持 `read` / `glob`**（`executeReadOnly` 第 2408 行）
2. **纠正器 prompt 却允许输出 shell/grep**（"shell 工具用 `{command}`"）

昨晚那条注入是"请原样调用 **grep**……"——grep 不在白名单 → 退化成 `formatCorrection` 的"请抄参数" → **主模型没抄** → 失败。

**结论：问题不是模型选不出来，是我们已经算出答案却用最不可靠的方式（让它抄）传给它。**

## 二、具体做法（替换掉昨天的"候选清单注入"）

```
glob 发现同名文件
  → harness 自己 read 每个候选（复用代执行器 + 安全边界）
  → 从用户指令提取目标串（2300 / min( / width）
  → 确定性选出唯一命中的候选 + 行号
  → 注入：[harness 环境事实] 目标已确定：<绝对路径>（第18行含 min(）。另一个同名文件不含该配置，不要动它。直接改这一处即可。
```

**关键差异**：
| 昨天（失败） | 今天（成功） |
|---|---|
| 给候选清单，让模型选 | harness 直接给唯一答案 |
| 相对路径 | **绝对路径** |
| "先确认是哪个" | "目标已确定，直接改" |
| 依赖模型判断 | 零 LLM、纯规则判定 |

## 三、实测结果

| 轮次 | 注入 | 结果 |
|---|---|---|
| cc330519 | `hits: 0`（路径解析错） | 未改 |
| 0ca86b71 | `hits: 1` 但注入**相对路径** | 未改，present 假完成 |
| **d53c33b8** | **`hits: 1` + 绝对路径** | **✅ 2300px 真实写入，另一文件未动** |

trace：
```
ambiguity_detected  {file: client.js, candidates: 2, step: 1}
ambiguity_resolved  {file: client.js, hits: 1, pats: "2300|min(|width", step: 3}
```
产物：`dsh-hardware-monitor/client.js` = `min(2300px, ...)`，`dsh-session-recycle-bin/client.js` 未动。

## 四、过程中修的三个 bug（都是真实工程问题）

1. **路径解析**：`workspaceRoot` 配置是 `C:/Users/Ad/Documents/deepseek-harness/default-workspace`，
   但实际 agent cwd 是 `D:/Brain/dsh-data/profiles/desktop` → 相对路径解析到不存在的目录。
   修：多根试探（`cfg.workspaceRoot` / profiles/desktop / workspace/default-workspace），找存在的文件。

2. **注入相对路径**：判定用了绝对路径 `abs0`，注入却用了 glob 的 `p0`（相对）→ 模型拿着没法精确改。
   修：`hits0.push({ p: abs0, ... })`。

3. **零写入守卫漏 `present`**：模型调 `present` 假完成但没写文件，守卫只查 `state.last.body` 文本正则。
   修：加 `state.presentCalled || /present/.test(body)` 判据。

## 五、为什么这次能成（对应论文）

- **SAGE-Agent**：specification uncertainty 在 harness 侧用**确定性规则**消除（不是让模型消歧）
- **Claude Code Plan Mode**：权限锁定的"构造性消除传递损耗"——不让模型抄，直接给它结果
- **turn13 对照**：同一个模型，明确指令 10 分钟完成；这里给的就是"明确指令"（绝对路径+行号+唯一目标）

**核心洞察**：模型不服从的根因是**我们给的是选择题**。把它变成填空题答案（而且是绝对路径这种可直接消费的形式），同一个模型就能做对。

## 六、诚实边界

1. **单次成功**（d53c33b8），前两轮都失败。虽然失败原因是明确的工程 bug（路径解析、相对路径），
   但仍需再跑 1~2 次确认稳定。
2. 目标串提取靠正则（`\d{3,5}px` / `min(` / `width`），**只覆盖"改宽度"这类任务**；
   其他任务类型需要扩展规则。
3. 会话结束时仍在 read（16 次），虽然产物已正确——**执行效率仍不理想**，
   正确性和效率是两回事。
4. 命中 0 或多命中时降级为模糊提示，仍可能空转。

## 七、下一步（如果继续）

- 再跑 2 次同样本确认稳定性（阈值：3/3 成功才算可靠）
- 目标串提取泛化：从"宽度"扩展到任意"old_string → new_string"
- 命中后用 `tools/pre-execute` 锁定目标文件（只允许改 `abs0`，其他文件 deny）
- 把"环境事实注入"的措辞也做成模板（当前是硬编码字符串）
