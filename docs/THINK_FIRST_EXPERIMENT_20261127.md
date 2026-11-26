# 让模型先思考任务本身：调研 + 落地 + 实测（2026-11-27 01:50）

> 用户问题："能不能让模型自己先思考一轮任务本身？论文和社区有没有方案？"
> 本轮做了完整调研 + 最小实现 + 两轮实测。**结论：论文方案成立，但我们的实测暴露了新失败模式。**

## 一、调研结论：能，但有三个条件

### 论文证据

**1. Plan-and-Solve Prompting（ACL 2023, arXiv 2305.04091）**
Zero-shot-CoT 的三个 pitfall：calculation / missing-step / **semantic misunderstanding errors**。
最后一条正是我们的病（两个同名 client.js 不知道改哪个）。
PS = 先拆任务再执行；10 数据集、GPT-3 上一致大幅超越 Zero-shot-CoT，数学推理接近 8-shot CoT。

**2. SAGE-Agent（arXiv 2511.08798）— 最贴切**
- 把工具调用建模为 POMDP，用 **EVPI（Expected Value of Perfect Information）** 选澄清问题
- **明确分离 specification uncertainty（用户想什么）与 model uncertainty（模型能力）**
- 量化：ClarifyBench coverage **+7~39%**，问题数减少 **1.5~2.7 倍**；When2Call 36.5%→**65.2%**（3B）

**这条分离验证了此前的判断**：我们的问题主要是 specification uncertainty，**可以用 harness 解决**。

**3. Ask-before-Plan（Zhang et al. 2024）**："predict clarification needs and collect information **before execution**"

**4. Princeton/Google CoRL 2023（最佳学生论文）**：conformal prediction 量化语言模糊度，
"把碗放进微波炉但有两个碗" → 触发澄清。**与我们的场景完全同构**。

### 社区方案：Claude Code Plan Mode

核心不是"让它想"，是**权限锁定**：
> "Plan Mode 是强制锁定：Claude 在只读状态下没有修改文件的权限，**物理上做不到边想边动手**。"

判断标准：
> "改动能用一句话描述清楚 diff，跳过 Plan；**连描述都需要先看代码再定，必须走 Plan**。"

我们"改 client.js 宽度"表面一句话，但有两个同名文件 → 应该走 Plan。

## 二、落地实现（消歧门控，Plan Mode 最小版）

四层：
1. **检测**：`tool/result` 里 glob 返回 ≥2 个同名 basename → `s.ambiguousPaths`
2. **告知**：`agent/pre-step` 注入候选清单（step 1 检测 → step 3~6 注入）
3. **门控**：write/edit 的 `tools/pre-execute`，裸 basename → deny + 候选清单；带目录放行
4. **守卫**：零写入却声称"已修改"→ hardFlags（防幻觉假完成）

## 三、实测：两个新失败模式

### 成功部分
- `ambiguity_detected` **稳定触发**（step 1，candidates: 2）—— 每轮都准确识别同名文件
- `ambiguity_injected` **触发**（step 3 / step 6）
- 工具调用从 55 次降到 **2 次**（不再空转）

### 失败模式 A：把"二选一"理解成"两个都改"（c6773ada）
注入后模型输出：
> "两个 client.js 都已修改完成...都改为 1900px 了"

**实际产物一字未改**（两文件都是 1400px）——**幻觉假完成**。
根因：候选清单 `1. A 2. B` 被理解为"都要改"。
修复：措辞改为"**需要先二选一 / 这次只针对其中一个，不是两个都改 / 另一个不要动**"。

### 失败模式 B：修复措辞后仍不稳定（f8d05541）
- step 1 检测到、step 5 再检测、step 6 注入
- 但会话持续空转，产物仍未改，手动 cancel

## 四、诚实结论

**论文的方案是对的，但落地后发现：给信息 ≠ 能让模型执行。**

| 环节 | 状态 |
|---|---|
| 检测歧义（harness 规则） | ✅ 稳定，100% 触发 |
| 告知模型（注入） | ✅ 稳定触发 |
| 模型据此消歧 | ⚠️ 不稳定：一次幻觉假完成，一次空转 |
| 门控 deny（写裸路径时） | 未触发（模型没走到写） |
| 零写入守卫 | 已加，但未在实测中触发 |

**根因回到能力边界**：35B Q4 在"两个同名文件"面前，即使给了完整候选清单，
仍无法稳定地"选一个、改一次"。这是 specification uncertainty 消除后暴露的 **model uncertainty**。

**不再继续调参的理由**：
1. 检测与注入已稳定，剩余问题在模型侧
2. 继续调提示词措辞是过拟合单次样本（已经因为措辞踩过一次坑）
3. 真正的解法是 Claude Code 式的**人工确认**或**更强模型**，前者需要用户在线，后者硬件不允许

## 五、当前状态

- 实现已提交：`3145e48`（歧义告知）→ `d1fb601`（措辞修复 + 零写入守卫）
- 回归全绿：25 PASS/0 FAIL + 三套 wargame ALL PASS + bridge OK
- 运行版与 publish 同步
- 文档：`RESEARCH_THINK_FIRST_20261127.md`（调研）+ 本文（实测）

## 六、留给未来的判断

1. **"让模型先想"的有效形式是权限锁定，不是提示词** —— Claude Code 的核心洞察
2. **给候选清单要强调"二选一"**，否则模型理解为"都做"（实测踩坑）
3. **检测稳定 ≠ 执行稳定** —— harness 能可靠地发现歧义，但无法可靠地让弱模型消歧
4. **如果要做得更好**：需要人工确认点（用户在线时用 ask_user_question）或独立 Critic 选文件，
   而不是继续调主模型的提示词
