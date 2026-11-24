# BFCL 标准化基线（2026-11-24）

> 阶段 1 成果：**第一次有了可对外比较的尺子**。
> 重要提醒：10/10 是 simple_python 最简单的 10 题，样本太小、类别太窄，**不能外推到 BFCL 全榜**。

## 一、结果

| 项 | 值 |
|---|---|
| Benchmark | BFCL V4 `simple_python` 前 10 题 |
| 判分 | **BFCL 官方 AST 判分器**（原样使用，未改判分逻辑）|
| 结果 | **10 / 10 valid**（每个模型输出的函数名+参数都通过 AST 匹配）|
| 每题耗时 | 10.3 ~ 35.4 秒（中位 15.4s）|
| 总耗时 | 约 3 分钟 |

## 二、测试配置基线（完整记录，供后续对比）

```
模型:      Qwen3.6-35B-A3B-UD-Q4_K_XL (GGUF, commit 94f3af3)
引擎:      llama.cpp master 94f3af3 自编（MSVC, FA on）
harness:   dsh-agent-harness v2.9 + behavior-guard
投机:      MTP draft-mtp, nmax=5
线程:      8 (t8, 6P+2E)
MoE cache: 1350 MiB, cpu-share=1.0, prefill 分档
上下文:    98304 (96K), KV K=q8_0 / V=q4_0
压缩:      thresholdRatio=0.65, retainTokens=16384, headroom=16384
工具面:    28 个（本测试未调用任何真实工具，模型以 JSON 文本输出函数）
产物:      token_embd.weight 已 offload 到 CPU
```

## 三、测试方法（关键：走真实 harness）

```
BFCL 题目 → 包装成 prompt（函数 schema + 用户请求 + "只输出 JSON"）
         → dsh-session-bridge 投递到真实 dsh 会话（create 专用会话）
         → 经过 harness 完整注入（system prompt / AGENTS.md / skills / tools schema / 门控）
         → 35B 生成
         → events API 抓 assistant/message 的 text
         → 抽 JSON
         → BFCL 官方 ast_checker 判分
```

**这不是直连 llama-server**——behavior-guard / 海马体 / 注入层都真实参与了。这正是现有 agentlab/projectlab 缺失的构念效度。

## 四、踩坑记录（都已解决）

1. **BFCL import 链太重**：ast_checker 拖进 cohere/anthropic/java_parser 等 SDK。解法：import 前 stub `bfcl_eval.constants.model_config`（判分器只用 `underscore_to_dot` 一个字段）。
2. **Language 必须传 `Language.PYTHON`**，传 None 报 "Unsupported language"。
3. **possible_answer 格式**：直接传 ground_truth 列表，不是包 dict。
4. **subagent 会话不能投递**：bridge 报 "owned by subagent routing"，必须 `create` 专用会话。
5. **bridge CLI 的 events 截断到 300 字符**：必须直连 HTTP API 读完整 assistant text。
6. **等待逻辑**：不能用 running true→false（会误判上一轮），必须用 events seq 判断"本轮新回复"。
7. **计划任务 PATH 没有 node**：必须用绝对路径。
8. **答案路径**：`data/possible_answer/` 不是 `bfcl_eval/possible_answer/`。

## 五、这个分数的局限（诚实）

- **样本太小**：10 题，Wilson 95% CI 约 [69%, 100%]——区间极宽
- **类别太窄**：simple_python 是 BFCL 最简单的单函数调用类，不代表 multiple / parallel / multi_turn / agentic
- **输出形式**：模型以 JSON 文本输出，而非原生 tool_call（BFCL 的 FC 模式）——这是 harness 工具面固定 28 个的约束
- **温度影响**：单次采样，无重复去抖
- **无法直接对标 leaderboard**：BFCL 官方榜是全类别加权分数，我们只跑了 simple 的 1/40

## 六、下一步

1. 扩到 simple_python 全 400 题（约 1.5 小时）——拿到有意义的 simple 类别分数
2. 加 multiple / parallel 类别（各取 100 题）——测多函数和并行调用
3. 加 irrelevance 类（测"不该调用时不调用"）——对应 behavior-guard 的误触发
4. 用 Wilson CI 报告，不再用单点数字
5. 阶段 2：τ-bench Retail（pass^k 可靠性）+ CToolEval（中文锚）

## 七、结论

**阶段 1 目标达成**：adapter 打通了"BFCL 题 → 真实 harness → 官方判分"的链路，拿到了第一个可对外比较的分数。虽然 10/10 的绝对数字意义有限，但**测量方法本身已经建立**——这是后续所有标准化的地基。

脚本：`D:/Brain/workspace/bench/bfcl_harness_eval.py`
结果：`D:/Brain/workspace/bench/_bfcl_result.jsonl`
日志：`D:/Brain/_cleanup_20261118/bfcl_eval.log`


---

## 更新：100 题基线（2026-11-24 15:40）

**结果：95 / 100 = 95.0%，Wilson 95% CI [88.8%, 97.8%]**，总耗时 25.1 分钟（中位 15.3s/题）。

### 错题分类（5 题）

| 类型 | 数量 | 例子 |
|---|---:|---|
| `type_error:nested`（int vs float）| 2 | `[12,15,18]` 整数数组，ground truth 期待 float 数组 |
| `value_error`（值推理/表述）| 2 | `operating_hours=11` 期望 23；`condition="Sundays"` 期望 "open on Sundays" |
| `wrong_func_name`（函数名幻觉）| 1 | 输出了另一题的函数名 `calculate_triangle_area` |

**关于 int vs float**：这 2 题严格说是 BFCL AST 判分器的严格类型检查（实际 API 调用中 int 可自动转 float）。但**判分器原样使用是纪律**，不为提高分数而改判分逻辑。记录为"适配器侧的输出类型规范化待办"（可在模型输出后、判分前统一把 int 转 float——但这属于改输出而非改判分，需谨慎评估是否算作弊，暂不做）。

**关于函数名幻觉**：`simple_python_86` 输出了 `calculate_triangle_area`（第 0 题的函数名）——说明**同一 session 连续跑题存在上下文累积干扰**。后续应改为每题新 session 或定期 reset，以消除交叉污染。

### 对标 leaderboard（BFCL V4, 2026-04-12）

| 模型 | Non-live AST | Overall |
|---|---:|---:|
| Claude Opus 4.5 (FC) | 88.5 | 77.47 |
| Qwen3-32B (FC) | 88.7 | 48.56 |
| Qwen3-30B-A3B-Instruct-2507 (FC) | 85.7 | 41.22 |
| Qwen3-8B (FC) | 87.5 | 42.57 |
| **我们（simple_python 100 题）** | **95.0** | 未测 |

**必须诚实标注口径差异**：官方 Non-live AST 是 simple + multiple + parallel 的**加权汇总**，我们只跑了 simple_python 的 100/400 题。95% 说明**在最简单的单函数调用上我们与头部模型同档甚至更高**，但这不构成"我们超过 Claude"的结论——因为 multiple/parallel/agentic 类别还没测，而那些才是区分度所在。

### 下一步（优先级）
1. **multiple / parallel 各 100 题**——真正的区分度所在（头部模型在这些类上掉到 73-84%）
2. **每题新 session**——消除函数名幻觉类的交叉污染
3. **irrelevance 类**——测"不该调用时不调用"，对应 behavior-guard 误触发
4. 扩到 simple 全 400 题（CI 进一步收窄）
5. 阶段 2：τ-bench Retail（pass^k）+ CToolEval（中文锚）


---

## 更新 2：multiple 基线 + v2 适配器（2026-11-24 17:30）

### v2 适配器改进
- **每题新建独立 session**：消除 v1 的上下文累积干扰（v1 在 simple_86 出现"输出别的题函数名"的幻觉）
- **支持类别参数**：simple_python / multiple / parallel
- **parallel 输出 JSON 数组**：prompt 让模型输出 `[{func:params}, ...]`，抽取器支持数组
- **结果文件按类别分**：`_bfcl_<category>_result.jsonl`

### multiple 结果：95/100（95.0%，Wilson CI [88.8%, 97.8%]）

与 simple 完全相同的分数。错题 5 道分类：

| ID | 类型 | 说明 |
|---|---|---|
| multiple_9 | wrong_func_name | **格式泄漏**：模型输出了原生 tool_call 的 message 包装 `{"message":{"role":"user","content":[{"type":"function_call",...}]}}`，函数名其实对，但被包了一层 |
| multiple_53 | value_error:string | 值表述不符 |
| multiple_58 | value_error:string | 值表述不符 |
| multiple_92 | value_error:list/tuple | 列表类型/值问题 |
| multiple_93 | value_error:string | 值表述不符 |

**关键发现——"格式泄漏"**：即使 prompt 明确要求裸 JSON，模型偶尔（1%）仍按 harness 的原生工具调用格式输出。这**恰恰证明真实 harness 参与了测试**（工具 schema 在 system prompt 里影响了模型行为）——是 v2 走真实链路的证据，不是 bug。

### 每题新 session 的成本
- 每题 30-45 秒（中位 35s），100 题约 1 小时
- 确认 router 复用同一 llama 实例（显存稳定 7829 MiB），新 session 不触发模型重载——开销来自 prefill + 生成

### 对标更新

| 模型 | Non-live AST 汇总 | 我们 |
|---|---:|---:|
| Claude Opus 4.5 (FC) | 88.5 | — |
| Qwen3-32B (FC) | 88.7 | — |
| Qwen3-30B-A3B (FC) | 85.7 | — |
| **我们 simple_python** | — | 95.0% |
| **我们 multiple** | — | 95.0% |

两个单类别都是 95%，但**官方 Non-live AST 是加权汇总**，我们还没法直接比。等 parallel 完成后可算三类别的等权平均作为粗略对照。

**诚实提醒**：simple 和 multiple 都 95% 且 CI 完全重叠，说明前两类对当前模型区分度低——真正的区分度可能在 parallel（多调用）和后续 agentic/multi_turn 类。


---

## 更新 3：三类别完整基线 + 对标结论（2026-11-24 18:40）

| 类别 | 结果 | Wilson 95% CI | 耗时 |
|---|---:|---|---:|
| simple_python | 95/100 = **95.0%** | [88.8%, 97.8%] | 25 min（同 session）|
| multiple | 95/100 = **95.0%** | [88.8%, 97.8%] | ~58 min（新 session）|
| parallel | 92/100 = **92.0%** | [85.0%, 95.9%] | 66.5 min（新 session）|
| **三类等权平均** | **94.0%** | — | 总计约 2.5 小时 |

### 与官方 leaderboard 的对标（关键：口径差异）

BFCL V4 官方榜 Non-live AST（simple+multiple+parallel 加权汇总）参考：
- Claude Opus 4.5 (FC): 88.5
- Qwen3-32B (FC): 88.7
- Qwen3-30B-A3B-Instruct-2507 (FC): 85.7
- Qwen3-8B (FC): 87.5

**我们三类等权 94.0% 表面上高于所有头部模型，但不能这样解读**：
1. 我们每类只跑 100 题（simple 400 / multiple 200 / parallel 200 的子集），官方是全量
2. 我们的测试是 **JSON 文本输出**，官方 FC 列是**原生 tool_call**——机制不同
3. 每题新 session（干净上下文），官方可能有不同的上下文管理
4. **前两类（simple/multiple）区分度低**——95% 且 CI 完全重叠；真正的区分度在 parallel（92%）

**诚实的结论**：
- 在**静态离线单轮工具调用**这个窄范围内，我们的 35B + harness 表现**与头部模型同档甚至略高**——这与社区"BFCL simple 类已接近饱和"的观察一致
- 真正拉开差距的是 **multi_turn / agentic / live / format_sensitivity** 类别（官方榜 Overall 从 94 掉到 41-77）——这些我们**还没测**
- 所以"我们在哪"的答案是：**静态工具调用已达头部水平，但 agentic 维度完全未知**。不能因为 94% 就自我感觉良好——这正是 ROADMAP L2 backlog 警告的陷阱。

### parallel 错题分类（8 题）

| 错误类型 | 数量 | 说明 |
|---|---:|---|
| `cannot_find_match` | 6 | 多次调用中某个参数/值不匹配 ground truth |
| `wrong_count` | 2 | 调用次数错误——典型是把两次调用合并成一次带数组参数的调用 |

最典型的 wrong_count：`parallel_9` 模型输出 `find_movie_showing(movie=['Tenet','No Time To Die'], time=['5 pm','7:30 pm'])` 一次调用，ground truth 期待两次独立调用。**这是"并行调用语义理解"的真实能力差距**，不是格式问题。

### 下一步（真正有信息量的方向）

前三类静态测试已接近饱和，**继续加题的边际信息很低**。要真正定位差距，必须测：
1. **multi_turn**（多轮工具调用 + 状态变化）——官方榜头部在此掉到 50-80%，区分度大
2. **irrelevance**（不该调用时不调用）——直接对应 behavior-guard 误触发
3. **τ-bench Retail pass^k**——可靠性衰减，behavior-guard 的核心诉求
4. **CToolEval**——中文锚，抵消语言偏差

**这些才是"尺子"真正该量的地方。**


---

## 更新 4：multi_turn 适配器验证 + irrelevance 进行中（2026-11-24 20:00）

### multi_turn 链路已跑通（1 题验证）
适配器 `D:/Brain/workspace/bench/bfcl_harness_eval3.py`：
- 每题新 session，逐轮 agent loop（question 每轮一条用户请求）
- 函数定义从官方 `MULTI_TURN_FUNC_DOC_FILE_MAPPING` 加载，按 `path` 只暴露用到的函数
- 模型每轮输出 JSON 数组 → 转 `func(k=repr(v))` 字符串 → 官方 `multi_turn_checker` 判分
- 回灌执行用官方 `func_source_code` 后端（给模型下一轮观察）

验证结果（multi_turn_base_0，4 轮，232 秒）：模型输出了合理调用序列 `mv → grep → sort → mv+diff`，判分 `valid=False`（`multi_turn:instance_state_mismatch`）——漏了 `cd`/`mkdir` 步骤，状态不匹配。**说明多轮状态依赖确实有区分度**。

### 踩坑（multi_turn 特有）
1. BFCL multi_turn 数据**没有 `function` 字段**——函数定义在 `data/multi_turn_func_doc/<类>.json`（JSONL），按 `path` 过滤
2. **bridge send 硬限 4096 字节**（`index.mjs:134`）——完整函数 schema 4328 字符被拒 "text too long"。解法：压缩成 `func(k:type*,...)` 签名（727 字节）
3. `execute_multi_turn_func_call` 的 `func_call_list` 要**扁平** `list[str]`，不是嵌套 `[strs]`
4. checker 返回的 error 里可能含不可序列化对象（`Directory`），写 JSON 要 `default=str`

### 重要局限性（必须标注）
为绕过 bridge 的 4096 字节限制，multi_turn 的函数定义被压成**只有签名、无 description**。BFCL 官方用完整函数文档（含语义描述）。这**可能低估模型能力**（模型不知道 `diff`/`grep` 的确切语义）。要公平对标，需提高 bridge 限制后重测——但那要改插件并重启 dsh，风险高，暂不做。

### irrelevance 进行中
- 已跑 34 题，34/34 全对（100%）
- 模型正确识别"函数不匹配请求"并拒绝调用，给中文说明
- 判分逻辑：无函数调用 = 通过（官方 `irrelevance_error:decoder_success` 反向）
- 预计还需 40 分钟跑完 100 题

### 成本观察
- simple 同 session：15s/题
- multiple/parallel/irrelevance 新 session：35s/题
- **multi_turn：~232s/题（4 轮 × 35s + 执行回灌）**——100 题要 6.5 小时，不划算。计划只跑 10-15 题做方向性验证。
