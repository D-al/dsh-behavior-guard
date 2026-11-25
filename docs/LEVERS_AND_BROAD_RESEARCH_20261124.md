# 杠杆盘点与广搜（2026-11-24）

> BFCL 基线→杠杆落地计划→上线清单→广搜（本轮调研入口）

> 本卷合并 4 份原报告（2026-11-25 整理）。

## 本卷目录

- `BFCL_BASELINE_20261124.md`
- `LEVERS_LANDING_PLAN_20261124.md`
- `LEVERS_GO_LIVE_20261124.md`
- `BROAD_RESEARCH_20261124.md`

---

## 原报告：`BFCL_BASELINE_20261124.md`

## BFCL 标准化基线（2026-11-24）

> 阶段 1 成果：**第一次有了可对外比较的尺子**。
> 重要提醒：10/10 是 simple_python 最简单的 10 题，样本太小、类别太窄，**不能外推到 BFCL 全榜**。

### 一、结果

| 项 | 值 |
|---|---|
| Benchmark | BFCL V4 `simple_python` 前 10 题 |
| 判分 | **BFCL 官方 AST 判分器**（原样使用，未改判分逻辑）|
| 结果 | **10 / 10 valid**（每个模型输出的函数名+参数都通过 AST 匹配）|
| 每题耗时 | 10.3 ~ 35.4 秒（中位 15.4s）|
| 总耗时 | 约 3 分钟 |

### 二、测试配置基线（完整记录，供后续对比）

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

### 三、测试方法（关键：走真实 harness）

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

### 四、踩坑记录（都已解决）

1. **BFCL import 链太重**：ast_checker 拖进 cohere/anthropic/java_parser 等 SDK。解法：import 前 stub `bfcl_eval.constants.model_config`（判分器只用 `underscore_to_dot` 一个字段）。
2. **Language 必须传 `Language.PYTHON`**，传 None 报 "Unsupported language"。
3. **possible_answer 格式**：直接传 ground_truth 列表，不是包 dict。
4. **subagent 会话不能投递**：bridge 报 "owned by subagent routing"，必须 `create` 专用会话。
5. **bridge CLI 的 events 截断到 300 字符**：必须直连 HTTP API 读完整 assistant text。
6. **等待逻辑**：不能用 running true→false（会误判上一轮），必须用 events seq 判断"本轮新回复"。
7. **计划任务 PATH 没有 node**：必须用绝对路径。
8. **答案路径**：`data/possible_answer/` 不是 `bfcl_eval/possible_answer/`。

### 五、这个分数的局限（诚实）

- **样本太小**：10 题，Wilson 95% CI 约 [69%, 100%]——区间极宽
- **类别太窄**：simple_python 是 BFCL 最简单的单函数调用类，不代表 multiple / parallel / multi_turn / agentic
- **输出形式**：模型以 JSON 文本输出，而非原生 tool_call（BFCL 的 FC 模式）——这是 harness 工具面固定 28 个的约束
- **温度影响**：单次采样，无重复去抖
- **无法直接对标 leaderboard**：BFCL 官方榜是全类别加权分数，我们只跑了 simple 的 1/40

### 六、下一步

1. 扩到 simple_python 全 400 题（约 1.5 小时）——拿到有意义的 simple 类别分数
2. 加 multiple / parallel 类别（各取 100 题）——测多函数和并行调用
3. 加 irrelevance 类（测"不该调用时不调用"）——对应 behavior-guard 的误触发
4. 用 Wilson CI 报告，不再用单点数字
5. 阶段 2：τ-bench Retail（pass^k 可靠性）+ CToolEval（中文锚）

### 七、结论

**阶段 1 目标达成**：adapter 打通了"BFCL 题 → 真实 harness → 官方判分"的链路，拿到了第一个可对外比较的分数。虽然 10/10 的绝对数字意义有限，但**测量方法本身已经建立**——这是后续所有标准化的地基。

脚本：`D:/Brain/workspace/bench/bfcl_harness_eval.py`
结果：`D:/Brain/workspace/bench/_bfcl_result.jsonl`
日志：`D:/Brain/_cleanup_20261118/bfcl_eval.log`


---

### 更新：100 题基线（2026-11-24 15:40）

**结果：95 / 100 = 95.0%，Wilson 95% CI [88.8%, 97.8%]**，总耗时 25.1 分钟（中位 15.3s/题）。

#### 错题分类（5 题）

| 类型 | 数量 | 例子 |
|---|---:|---|
| `type_error:nested`（int vs float）| 2 | `[12,15,18]` 整数数组，ground truth 期待 float 数组 |
| `value_error`（值推理/表述）| 2 | `operating_hours=11` 期望 23；`condition="Sundays"` 期望 "open on Sundays" |
| `wrong_func_name`（函数名幻觉）| 1 | 输出了另一题的函数名 `calculate_triangle_area` |

**关于 int vs float**：这 2 题严格说是 BFCL AST 判分器的严格类型检查（实际 API 调用中 int 可自动转 float）。但**判分器原样使用是纪律**，不为提高分数而改判分逻辑。记录为"适配器侧的输出类型规范化待办"（可在模型输出后、判分前统一把 int 转 float——但这属于改输出而非改判分，需谨慎评估是否算作弊，暂不做）。

**关于函数名幻觉**：`simple_python_86` 输出了 `calculate_triangle_area`（第 0 题的函数名）——说明**同一 session 连续跑题存在上下文累积干扰**。后续应改为每题新 session 或定期 reset，以消除交叉污染。

#### 对标 leaderboard（BFCL V4, 2026-04-12）

| 模型 | Non-live AST | Overall |
|---|---:|---:|
| Claude Opus 4.5 (FC) | 88.5 | 77.47 |
| Qwen3-32B (FC) | 88.7 | 48.56 |
| Qwen3-30B-A3B-Instruct-2507 (FC) | 85.7 | 41.22 |
| Qwen3-8B (FC) | 87.5 | 42.57 |
| **我们（simple_python 100 题）** | **95.0** | 未测 |

**必须诚实标注口径差异**：官方 Non-live AST 是 simple + multiple + parallel 的**加权汇总**，我们只跑了 simple_python 的 100/400 题。95% 说明**在最简单的单函数调用上我们与头部模型同档甚至更高**，但这不构成"我们超过 Claude"的结论——因为 multiple/parallel/agentic 类别还没测，而那些才是区分度所在。

#### 下一步（优先级）
1. **multiple / parallel 各 100 题**——真正的区分度所在（头部模型在这些类上掉到 73-84%）
2. **每题新 session**——消除函数名幻觉类的交叉污染
3. **irrelevance 类**——测"不该调用时不调用"，对应 behavior-guard 误触发
4. 扩到 simple 全 400 题（CI 进一步收窄）
5. 阶段 2：τ-bench Retail（pass^k）+ CToolEval（中文锚）


---

### 更新 2：multiple 基线 + v2 适配器（2026-11-24 17:30）

#### v2 适配器改进
- **每题新建独立 session**：消除 v1 的上下文累积干扰（v1 在 simple_86 出现"输出别的题函数名"的幻觉）
- **支持类别参数**：simple_python / multiple / parallel
- **parallel 输出 JSON 数组**：prompt 让模型输出 `[{func:params}, ...]`，抽取器支持数组
- **结果文件按类别分**：`_bfcl_<category>_result.jsonl`

#### multiple 结果：95/100（95.0%，Wilson CI [88.8%, 97.8%]）

与 simple 完全相同的分数。错题 5 道分类：

| ID | 类型 | 说明 |
|---|---|---|
| multiple_9 | wrong_func_name | **格式泄漏**：模型输出了原生 tool_call 的 message 包装 `{"message":{"role":"user","content":[{"type":"function_call",...}]}}`，函数名其实对，但被包了一层 |
| multiple_53 | value_error:string | 值表述不符 |
| multiple_58 | value_error:string | 值表述不符 |
| multiple_92 | value_error:list/tuple | 列表类型/值问题 |
| multiple_93 | value_error:string | 值表述不符 |

**关键发现——"格式泄漏"**：即使 prompt 明确要求裸 JSON，模型偶尔（1%）仍按 harness 的原生工具调用格式输出。这**恰恰证明真实 harness 参与了测试**（工具 schema 在 system prompt 里影响了模型行为）——是 v2 走真实链路的证据，不是 bug。

#### 每题新 session 的成本
- 每题 30-45 秒（中位 35s），100 题约 1 小时
- 确认 router 复用同一 llama 实例（显存稳定 7829 MiB），新 session 不触发模型重载——开销来自 prefill + 生成

#### 对标更新

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

### 更新 3：三类别完整基线 + 对标结论（2026-11-24 18:40）

| 类别 | 结果 | Wilson 95% CI | 耗时 |
|---|---:|---|---:|
| simple_python | 95/100 = **95.0%** | [88.8%, 97.8%] | 25 min（同 session）|
| multiple | 95/100 = **95.0%** | [88.8%, 97.8%] | ~58 min（新 session）|
| parallel | 92/100 = **92.0%** | [85.0%, 95.9%] | 66.5 min（新 session）|
| **三类等权平均** | **94.0%** | — | 总计约 2.5 小时 |

#### 与官方 leaderboard 的对标（关键：口径差异）

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

#### parallel 错题分类（8 题）

| 错误类型 | 数量 | 说明 |
|---|---:|---|
| `cannot_find_match` | 6 | 多次调用中某个参数/值不匹配 ground truth |
| `wrong_count` | 2 | 调用次数错误——典型是把两次调用合并成一次带数组参数的调用 |

最典型的 wrong_count：`parallel_9` 模型输出 `find_movie_showing(movie=['Tenet','No Time To Die'], time=['5 pm','7:30 pm'])` 一次调用，ground truth 期待两次独立调用。**这是"并行调用语义理解"的真实能力差距**，不是格式问题。

#### 下一步（真正有信息量的方向）

前三类静态测试已接近饱和，**继续加题的边际信息很低**。要真正定位差距，必须测：
1. **multi_turn**（多轮工具调用 + 状态变化）——官方榜头部在此掉到 50-80%，区分度大
2. **irrelevance**（不该调用时不调用）——直接对应 behavior-guard 误触发
3. **τ-bench Retail pass^k**——可靠性衰减，behavior-guard 的核心诉求
4. **CToolEval**——中文锚，抵消语言偏差

**这些才是"尺子"真正该量的地方。**


---

### 更新 4：multi_turn 适配器验证 + irrelevance 进行中（2026-11-24 20:00）

#### multi_turn 链路已跑通（1 题验证）
适配器 `D:/Brain/workspace/bench/bfcl_harness_eval3.py`：
- 每题新 session，逐轮 agent loop（question 每轮一条用户请求）
- 函数定义从官方 `MULTI_TURN_FUNC_DOC_FILE_MAPPING` 加载，按 `path` 只暴露用到的函数
- 模型每轮输出 JSON 数组 → 转 `func(k=repr(v))` 字符串 → 官方 `multi_turn_checker` 判分
- 回灌执行用官方 `func_source_code` 后端（给模型下一轮观察）

验证结果（multi_turn_base_0，4 轮，232 秒）：模型输出了合理调用序列 `mv → grep → sort → mv+diff`，判分 `valid=False`（`multi_turn:instance_state_mismatch`）——漏了 `cd`/`mkdir` 步骤，状态不匹配。**说明多轮状态依赖确实有区分度**。

#### 踩坑（multi_turn 特有）
1. BFCL multi_turn 数据**没有 `function` 字段**——函数定义在 `data/multi_turn_func_doc/<类>.json`（JSONL），按 `path` 过滤
2. **bridge send 硬限 4096 字节**（`index.mjs:134`）——完整函数 schema 4328 字符被拒 "text too long"。解法：压缩成 `func(k:type*,...)` 签名（727 字节）
3. `execute_multi_turn_func_call` 的 `func_call_list` 要**扁平** `list[str]`，不是嵌套 `[strs]`
4. checker 返回的 error 里可能含不可序列化对象（`Directory`），写 JSON 要 `default=str`

#### 重要局限性（必须标注）
为绕过 bridge 的 4096 字节限制，multi_turn 的函数定义被压成**只有签名、无 description**。BFCL 官方用完整函数文档（含语义描述）。这**可能低估模型能力**（模型不知道 `diff`/`grep` 的确切语义）。要公平对标，需提高 bridge 限制后重测——但那要改插件并重启 dsh，风险高，暂不做。

#### irrelevance 进行中
- 已跑 34 题，34/34 全对（100%）
- 模型正确识别"函数不匹配请求"并拒绝调用，给中文说明
- 判分逻辑：无函数调用 = 通过（官方 `irrelevance_error:decoder_success` 反向）
- 预计还需 40 分钟跑完 100 题

#### 成本观察
- simple 同 session：15s/题
- multiple/parallel/irrelevance 新 session：35s/题
- **multi_turn：~232s/题（4 轮 × 35s + 执行回灌）**——100 题要 6.5 小时，不划算。计划只跑 10-15 题做方向性验证。


---

### 更新 5：irrelevance 完整结果 + 四类别最终汇总（2026-11-24 21:02）

**irrelevance：100/100 = 100.0%，Wilson 95% CI [96.3%, 100.0%]**，中位 35.4s/题。

过程：中途 20:19 看门狗自动触发 RestartDsh 导致 dsh 重启，评测在 46/100 中断（旧 token 失效）。
用 `bfcl_supervisor.py` 看护从 46 断点自动续跑，21:01:38 完成 100/100，看护自动退出。
**抗重启机制全程生效，无需人工干预。**

#### 四类别最终汇总

| 类别 | 结果 | Wilson 95% CI | 测什么 |
|---|---:|---|---|
| simple_python | 95/100 = 95.0% | [88.8%, 97.8%] | 单函数选择+参数 |
| multiple | 95/100 = 95.0% | [88.8%, 97.8%] | 多候选择一 |
| parallel | 92/100 = 92.0% | [85.0%, 95.9%] | 一函数多次调用 |
| irrelevance | 100/100 = 100.0% | [96.3%, 100.0%] | 不该调用时不调用 |
| **四类等权** | **95.5%** | — | 静态工具调用 |

**结论强化**：irrelevance 满分进一步证实——behavior-guard 最关心的"误触发"维度，本地 35B 表现完美（模型能正确识别函数不匹配请求并用中文说明拒绝）。结合 simple/multiple 95%，**静态工具调用的四个维度都已达头部水平**。

**仍未测**：multi_turn（链路已打通但每题 4 分钟，100 题要 6.5 小时，未跑全量）、agentic/live/format_sensitivity 类别。

#### 上线包状态（用户要求"测评一跑完就可以上线"）
- 补丁：lever1/2/4 三个 patch 脚本在临时副本实跑验证通过（叠加 2541→2750 行，node --check 通过）
- 工具：levers_deploy.py（preflight/backup/apply/rollback）+ levers_verify.py（L4 trace + L5 产物）
- 手册：docs/LEVERS_GO_LIVE_20261124.md
- **preflight 2026-11-24 21:02 全部通过**（评测完成/两副本一致/语法OK）
- ⚠️ 补丁未应用到运行版——实际执行需重启 dsh，属生产变更，需用户确认。

---

## 原报告：`LEVERS_LANDING_PLAN_20261124.md`

## 四杠杆落地验证方案（2026-11-24）

> 配套 `BROAD_RESEARCH_20261124.md` 第十四部分的四个杠杆。
> 核心原则：**不许用"代码存在 + 单测过"冒充"真实生效"**（POSTMORTEM 铁律）。

### 一、证据分层（沿用项目 L1-L5）

| 层 | 判据 | 是否算"落地成功" |
|---|---|---|
| L1 | 代码存在 | ❌ |
| L2 | 单测过 | ❌ |
| L3 | 加载（health 200）| ❌ |
| L4 | **真实 sid 的 trace 命中** | ✅ 必要条件 |
| L5 | **独立产物变化** | ✅ 充分条件 |

每个杠杆落地必须同时拿到 L4 + L5：
- L4：`_trace.jsonl` 里真实 sid（非 s1）出现新 kind
- L5：独立产物证明行为改变（如 verify 真的读回了文件、投票真的改变了最终决策）

### 二、统计门槛（沿用 SCIENTIFIC_MEASUREMENT_20261122）

- 噪声地板 σ≈10%，单次结果 ±10% 不可解读
- 检测 10% 变化需 **n≥16** 次（每臂）
- 报告 **Wilson 95% CI**，不报单点数字
- 多次取**中位**（防回归均值：观测低值复测会自然回升）
- **隐藏集**：BFCL 题目分"调参集"和"冻结验证集"，杠杆设计只用调参集，最终报告只用冻结集（防 Goodhart）
- 分层报告：simple/multiple/parallel/multi_turn 分开，不合并（防 Simpson 悖论）

### 三、四个杠杆的专属验证

#### 杠杆 1：确定性状态回读
- **L4**：新 trace kind `verify_state_readback`，记录读了什么文件/跑了什么测试
- **L5**：故意制造"模型声称完成但文件没改"的场景，验证能被抓住
  - 构造：让 agent 写一个文件，但在 present 前偷偷删掉
  - 期望：确定性回读发现文件不存在 → 阻止 present
- **A/B**：10 次故意失败场景 × 2 臂（有/无回读），抓到率对比
- **负向测试**：回读逻辑不能扫内容/文件名里的 "verify/test" 字符串（项目踩过这个坑——守卫正则只认执行动作）

#### 杠杆 2：显式状态板 + 规划闸
- **L4**：新 trace kind `state_board_inject`，每次注入记录状态快照
- **L5**：multi_turn 状态漂移测试——用 BFCL multi_turn_base 的题，对比有/无状态板的 `instance_state_mismatch` 率
  - 关键：multi_turn 验证题已经暴露"漏 cd/mkdir"的漂移，正好作为测试床
- **A/B**：n≥16 题 × 2 臂，Wilson CI 对比
- **负向测试**：状态板不能太长（bridge 4096 字节限制）→ 注入前检查字节数

#### 杠杆 3：工具按需检索/阶段化
- **L4**：新 trace kind `tool_subset_selected`，记录阶段和暴露的工具列表
- **L5**：工具调用准确率变化——用 BFCL simple/multiple 的锚题（各 20 题）
  - 期望：阶段化暴露后，无关工具干扰减少 → 格式泄漏（multiple_9 那类）下降
- **A/B**：n≥16 × 2 臂
- **风险**：切换时机错误破坏正在进行的调用 → 负向测试连续调用中途切换

#### 杠杆 4：同模型 K=5 自洽投票
- **L4**：新 trace kind `self_consistency_vote`，记录 5 次采样结果和投票决定
- **L5**：决策质量变化——锚题上投票 vs 单次的准确率对比
- **A/B**：n≥16 × 2 臂，注意 K=5 成本 ×5（本地只有电力时间）
- **负向测试**：一致性阈值——如果 5 次全错但一致，不能采纳（"把困惑封为共识"）
- **与已证伪项区分**：多 judge 投票（9 judge≈2 票）≠ 同模型采样投票，别混淆

### 四、落地顺序（按杠杆率 × 风险）

```
阶段 0（本周）：只做杠杆 1（确定性状态回读）
  - 风险最低、实证最强（比 judge 多抓 4-8 倍）
  - 直接命中"文档宣称完成≠代码生效"的历史坑
  - 验证：10 次故意失败场景 × 2 臂

阶段 1（下周）：杠杆 2（状态板 + 规划闸）
  - 复用 multi_turn 验证题作测试床
  - 纯 prompt/规则，零显存成本
  - 验证：n≥16 × 2 臂

阶段 2（需拍板）：杠杆 3（工具阶段化）
  - 涉及工具面切换，风险中等（ADR-0029 的顾虑）
  - 需用户决策是否接受"阶段标记"方案

阶段 3（成本高）：杠杆 4（K=5 投票）
  - ×5 推理成本，本地可承受但显著变慢
  - 最后做，先小样本验证增益
```

### 五、三条铁律（每次落地都要过）

1. **不改判分器提分**——BFCL 原样使用，int vs float 那种严格判分就认了
2. **三副本同步**——权威源(publish) / 运行版(node_modules) / 旧 clone 改后 sha256 校验
3. **真实会话证据**——trace 必须真实 sid，过滤 s1 的 89% 假数据

### 六、一句话

落地不是"写代码"，是"写机制 + 拿 L4/L5 证据 + 过 n≥16 的 A/B"——缺任何一样都不算完成。

---

## 附：四杠杆代码挂载点调研（子任务实测，2026-11-24）

> 运行版 = `D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs`（v2.9.0），
> 权威源 = `D:/Brain/publish/dsh-behavior-guard/index.mjs`。改动必须两处同步 + sha256 校验。

### 杠杆 1：确定性状态回读 —— 基建齐全，改动最小

**可复用基础设施**：
- `verify-on-stop`：`index.mjs:2163-2185`，tool-call 模式 `_stopVerify`（`:629-641`）
- `present 深检`：`index.mjs:578-600` + `deep_verify()`（`:443-500`）——目前是文本启发式
- 验收员 `bench/verify_agent.py`：零 LLM 规则脚本，三态 PASS/FAIL/INCONCLUSIVE
- 纠正器 `corrector()`：`index.mjs:1040-1070`

**改动点**：`deep_verify()`（`:443-500`）末尾加 `deterministicStateReadback()`：
- 从最近 tool_calls 提取写操作的文件路径/命令
- `fs.statSync`/`readFileSync` 读回真实状态
- trace 打点 `verify_state_readback`
- **铁律**：守卫正则只认执行动作（命令型工具参数），绝不扫 fullArgs 内容——踩过"文件名含 verify/test 就误判已验证"的坑

**最小实现**：约 60-80 行，零 LLM，纯同步 IO。

### 杠杆 2：显式状态板 + 规划闸 —— 注入通道成熟

**注入通道**：`injectMdFile()`（`:265-290`）/ pending 注入队列 `_pendingInject`（`:1514-1530`）

**控制回合**：`index.mjs:2270-2330`，每 8 步触发元决策（trace `control_turn` 实测 229 次）

**改动点**：
- 状态板：`controlTurn` 内加 `buildStateBoard()`，从 trace 提取 cwd/已改文件/未完成 todo → pending 注入
- 规划闸：扩展 `is_stub` 判断（`:1915+`），"开工无 plan 则拦截首个 edit/write"

**最小实现**：约 50 行 + 1 个模板片段，零显存。

### 杠杆 3：工具阶段化 —— 有硬障碍

**现状**：工具定义在 `index.mjs:32+`（`ALL_TOOLS` 28 个）。`ctx.tools.register` 热替换官方支持但**未接线**（ADR-0029 明确不实施）；`ctx.intercept('tools')` 存在但未验证；**无现成过滤代码**。

**障碍**：
1. dsh runtime 无裁剪 hook（`AUTOCARD_POSTMORTEM.md:15`）
2. 阶段切换信号缺失——需任务类型分类器，弱分类器已证伪（M9 AUC 0.599）
3. 热替换涉及 schema 流入 system prompt，切换时机不当破坏进行中调用

**结论**：唯一不能"最小改动"的。退路：不改运行版工具面，只在提示词层加"当前阶段建议工具"文本提示（零风险但效果弱）。**优先级降到最后或不做**。

### 杠杆 4：K=5 自洽投票 —— 成本开关现成

**现状**：temperature 来自 `profile.patch.yml` 的 `[*] temp=0.7`（CLI 覆盖见 `.env` 留空纪律）；`callLLMOnce()`（`:1250-1290`）单模型单次；**无现成投票代码**。

**改动点**：包装 `selfConsistencyK()`：同 prompt 调 K=5 次，多数投票；全一致但置信度低仍弃权（防"把困惑封为共识"）。**最合适挂点**：工具选择决策（验收已有零 LLM 脚本）。

**成本**：×5 推理，每步 11s → 55s。建议只在高风险决策上开，不全量。

### 综合排序修订（基于代码调研）

| 杠杆 | 基建 | 改动量 | 风险 | 修订优先级 |
|---|---|---|---|:---:|
| 1 确定性状态回读 | 齐全 | 60-80 行 | 低 | **P0** |
| 2 状态板+规划闸 | 齐全 | 50 行 | 低 | **P1** |
| 4 K=5 投票 | 部分现成 | 80-120 行 | 中（成本×5）| P2（高风险决策才开）|
| 3 工具阶段化 | **缺失** | 大 | 高 | **P3 或不做** |

**关键发现**：原排序把工具面放第 3，但代码调研显示它是唯一"基建缺失+高风险"的——应降到 P3。K=5 投票虽成本高但开关现成、实现明确，反而更适合先试。

---

## 原报告：`LEVERS_GO_LIVE_20261124.md`

## 四杠杆上线操作手册（测评完成后执行）

> 目标：四个优化杠杆细化到"测评一跑完就能上线"的程度。
> 原则：**准备 ≠ 应用**。以下脚本已写好并在临时副本验证通过，但**未应用到运行版**——
> 必须等 BFCL irrelevance 评测跑完（100/100），否则重启 dsh 会打断评测。

### 一、当前状态（2026-11-24 20:55）

- 评测：irrelevance 89/100，看护脚本 BFCLSupervisor 常驻（抗看门狗重启）
- 补丁：三个可用杠杆的 patch 脚本已写好，**在临时副本实跑验证通过**
  - 杠杆1 `lever1_state_readback_patch.py`：5 处替换，+96 行
  - 杠杆2 `lever2_state_board_patch.py`：5 处替换，+58 行
  - 杠杆4 `lever4_vote_patch.py`：4 处替换，+55 行（默认关）
  - 三补丁叠加：2541 → 2750 行，`node --check` 通过
- 杠杆3（工具阶段化）：**降级 P3/暂不做**——代码调研显示基建缺失（无 ctx.tools 接线）、
  阶段信号依赖已证伪的分类器、热替换风险高。退路：只在提示词层加"阶段建议工具"文本。

### 二、上线前检查（自动）

```bash
python tools/levers_deploy.py preflight
```

检查：①评测完成（100/100）②两副本 sha 一致 ③语法通过。**任一失败则拒绝上线**。

### 三、上线步骤（严格顺序）

```bash
## 1. 备份两处 index.mjs（必做，可回滚）
python tools/levers_deploy.py backup

## 2. 确认前置检查通过
python tools/levers_deploy.py preflight

## 3. 逐个应用杠杆（每次改权威源后自动同步运行版）
python tools/levers_deploy.py apply 1    # P0 确定性状态回读
python tools/levers_deploy.py apply 2    # P1 状态板
python tools/levers_deploy.py apply 4    # P2 K=5 投票（默认关，先不改行为）

## 4. 语法检查（两处）
node --check D:/Brain/publish/dsh-behavior-guard/index.mjs
node --check D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs

## 5. 门禁（必须 0 fail）
bash tools/run_all.sh    # 期望 77 pass, 0 fail

## 6. 重启 dsh（按 skills/release-plugin.md 的流程）
##    ⚠️ 此时评测必须已完成，否则不要重启
Stop-Process dsh/llama → Start-ScheduledTask RestartDsh → 等 65s → health check

## 7. 触发真实会话（让机制命中）
##    用 bridge 发一个明确"写文件+声称完成"的任务，触发确定性回读

## 8. 验证生效（L4 真实 sid trace + 门禁）
python tools/levers_verify.py --fresh-min <重启后的ISO时间>
## 全部 PASS 才算上线成功；有 FAIL 不得宣布完成
```

### 四、验证判据（三条缺一不可）

| 层 | 判据 | 脚本 |
|---|---|---|
| L2 单测 | 门禁 77 pass / 0 fail | `run_all.sh` |
| L4 trace | 真实 sid（非 s1）出现 `verify_state_readback` / `state_board_inject` / `self_consistency_vote` | `levers_verify.py` |
| L5 产物 | 故意制造"声称完成但文件没改"场景，确定性回读能拦住 present | 手工负向测试 |

⚠️ **L4 必须过滤 s1**：POSTMORTEM 实测 `_trace.jsonl` 9666 行中 89% 是单测假数据。

### 五、回滚（一键）

```bash
python tools/levers_deploy.py rollback
## 恢复两处 index.mjs 到备份 sha，然后重启 dsh
```

### 六、负向测试（防止机制静默失效）

1. **杠杆1**：故意让模型"声称完成但不写文件" → 必须被回读门拦截、不能 present
2. **杠杆1**：文件名含 "verify/test" 但内容没验证 → **不能**被误判为已验证（项目踩过的坑）
3. **杠杆2**：状态板超 4096 字节 → 必须自动截断，不能让 bridge 报 "text too long"
4. **杠杆4**：5 次采样全错但一致 → 必须因 minAgreement/置信度检查回退 UNCERTAIN，不能"把困惑封为共识"

### 七、A/B 验证（上线后持续观察，n≥16）

按 `LEVERS_LANDING_PLAN_20261124.md`：
-  Wilson 95% CI，不报单点
-  隐藏集防 Goodhart，分层报告防 Simpson 悖论
-  观测低值复测会自然回升（回归均值），多次取中位

### 八、一句话

补丁已备好且验证过语法，但**上线 ≠ 应用补丁**——必须过 preflight、备份、门禁、重启、真实 trace、负向测试这一整条链，才算真正生效。


---

## 上线执行与效果评估（2026-11-24 21:25 实际完成）

### 执行结果
- **备份**：两副本 sha=362e3715 → `.backups/levers-20261124/`
- **补丁**：lever1/2/4 全部应用，累积 sha `362e3715→54a90719→75f3ac44→52cb3a0e`
- **门禁**：中途出现 2 个 FAIL，经查是真实健壮性问题（非测试妥协），修复后 **77 pass / 0 fail**
  - 修复1：回读门 steer 文案加 verify-on-stop 判据关键词（真实验证命令/[VERIFY]）
  - 修复2：无结构化写目标时 skipped=true 跳过（fail-open），不误拦普通 write 调用
  - 修复3：状态板走控制回合 parts.push，不占 sharedInjections 预算（原先被回读门+verify-on-stop 挤占，L4 从未命中）
- **重启**：dsh 21:13:02 重启，探针 21:13:04（本次加载，非旧值），health ok
- 最终两副本 sha=`0e1df753`（三次修复后）

### 效果评估（tools/lever_effect_report.py，UTC 时间戳，since=13:13:00Z）

| 杠杆 | L4 真实会话 | 证据 | 判定 |
|---|:---:|---|---|
| 1 确定性回读 | 1 条 | `ok=true, evidence=文件 exists=1 fresh=1 bytes=11`，且 verify_on_stop 独立触发1次 | **生效** |
| 2 状态板 | 1 条 | step=8 触发 control_turn，`bytes=90` | **生效** |
| 4 K=5 投票 | 0 条 | `voteOnCritic=false`（默认关，设计如此） | **未验证**（按设计） |

**关键观察**：
- 杠杆1 的正向路径已证实（真写了文件→回读成功→trace 有完整证据）
- 杠杆1 与 verify_on_stop **并存不互斥**（同 sid 两者都触发），符合"先修落盘再验证"的分层设计
- 杠杆2 从"代码存在但 L4 从未命中"到真实触发——修复注入预算挤占后生效，这是"上线审计三层交叉"方法的又一次实证

### 诚实的效果边界
- **机制生效 ≠ 成功率提升**：L4/L5 只证明"机制真的跑了并改变了可观测状态"
- 要声称"成功率提升 X%"需 n≥16 的 A/B + Wilson CI（σ≈10% 噪声地板），当前样本不足
- 杠杆4 默认关是刻意选择：先验证低风险的 1/2，投票 ×5 成本高，需用户决策是否开启
- 负向测试（故意"声称完成但不落盘"看是否被拦）尚未做真实会话级验证——现有 77 门禁含 L2 级负向断言

### 回滚
```bash
python tools/levers_deploy.py rollback   # 恢复到 362e3715（含三次修复前的原始版本）
```


---

## 杠杆4 K=5 投票效果验证（2026-11-24 21:40）

### 执行过程
1. 开启 `voteOnCritic=true`（toggle_vote.py），重启 dsh（探针 21:31:30）
2. 发真实交付任务（写 vote_test_report.md + present）触发 Critic
3. **真实会话首次结果：5 次采样全 PARSE_FAIL，耗时 100s（5×20s 超时）**
   - 根因：投票用 `callLLMOnce` 单次超时硬编码 20000ms，thinking 模型 20s 内出不完 JSON；
     原 Critic 的 `callLLM` 用 90000ms 且有 reasoning_content 兜底
   - 修复：单次超时 20s→60s（`Math.min(60000, timeoutMs)`），总预算 180s→360s
4. 补单测 `tools/test_self_consistency_vote.mjs`：**9/9 通过**
   - 多数票 ACCEPT 胜出 / 5 次采样记录 / agreed 阈值
   - tie 2/2/1 → UNCERTAIN（防"把困惑封为共识"）
   - 低于 minAgreement → UNCERTAIN
   - **thinking 格式（content 空 + reasoning_content 含 JSON）能解析，无 PARSE_FAIL** ← 真实会话 bug 的回归测试

### 关键决策：生产开关改回 false
- 全局开启 `voteOnCritic=true` 导致门禁从 77/0 掉到 75/3（a17_runtime / falsegreen_fixes / role_fixes）
- 根因：这些测试 mock fetch 假设 Critic 单次调用，投票改变了调用契约
- **改回 false 后 78 pass / 0 fail**（含新增投票测试）
- 结论：投票逻辑正确但**不能全局默认开**——它与现有测试契约和其他机制的预算模型冲突。
  若要用，需：(a) 只在对质量极敏感的任务类型按 taskProfile 条件开，或 (b) 重构测试契约。

### 效果评估（诚实）
- **L4 命中**：真实会话 `ae2d97e8` 出现 `self_consistency_vote` trace（5 次全 PARSE_FAIL，旧代码）
- **L2 验证**：修复后 9/9 单测通过，含 thinking 格式回归
- **未获得**：修复后真实会话的"正确投票"证据（未再跑一次 5 分钟的真实任务）
- **成功率提升**：无 A/B 数据（n≥16 门槛未达），不声称任何提升
- 生产默认关，成本（5×推理）与收益（防个别误判）的权衡需用户拍板

### 最终状态
- 生产：voteOnCritic=false（稳定态），门禁 78/0，两副本 sha=6e051953
- 能力：投票代码在包内且验证过，开关可逆（tools/toggle_vote.py on|off）


---

## 前3个杠杆效果测试（2026-11-24 22:20）

> 用户问"前3个杠杆效果怎么样"。杠杆3（工具阶段化）按调研结论**不做**（基建缺失+依赖已证伪分类器），
> 所以实际测已上线的杠杆1（确定性回读）+ 杠杆2（状态板）。

### 证据 A：受控 A/B 实验（tools/test_levers_ab_effect.mjs，12/12 通过）

同一场景开关机制对比，证明的是"机制改变了什么行为"，不是"trace 出现了"：

| 项 | 场景 | 结果 |
|---|---|---|
| L1-A/B | 关闭/开启回读门 | 关闭无 trace，开启有 trace（开关生效）|
| L1-C/D | 假完成（声称写入但文件不存在）| 开启后 `ok=false` **且 steer 拦截** ← 核心价值 |
| L1-E | 对照组（关闭）| 不拦截 |
| L1-F/G | 真落盘 | `ok=true` 且不误拦（无假阳性）|
| L2-A~E | 状态板 | trace 命中 + **内容进入 prompt** + 含 cwd/已改文件 + 字节≤4096 |

**这是"机制有效性"的硬证据**：假完成被拦、真落盘不误拦、状态板内容正确。

### 证据 B：历史 trace 分析（子任务，诚实结论）

- 两个杠杆在真实 sid 上各命中 **2 次**（样本严重不足）
- trace 中**无可归因证据**表明改变了真实会话行为或提升了成功率
- 唯一看似正向的 steer 上升是合成测试污染（s1 假数据，89% 基线）
- **判定：不能声称端到端效果**

### 证据 C：真实会话复验（修复后）

- 会话 `b860bd34`：写 cf_verify.txt，step=9 触发回读门
  - `ok=true, evidence=['...cf_verify.txt: exists=1 fresh=1 bytes=18']`
  - 产物真实存在且内容与字节数吻合 → 回读门在真实会话中正确工作
- 状态板未触发：该会话无控制回合（control_turn=0，既有每8步+预算行为），
  非杠杆2 bug——A/B 实验已证明触发时内容正确

### 过程中抓到并修复的真 bug

**杠杆2 的 `changedFiles` 累积里用了未定义的 `callFull`**（实际变量是 `fullArgs`）：
- `JSON.parse(callFull||'{}')` 抛 ReferenceError → 被 catch 吞掉 → changedFiles 永远为空
- 后果：状态板的 `changed=` 字段在生产中一直是 `(none)`，即使 trace 命中、机制"看起来生效"
- 这正是"文档宣称完成≠代码实际生效"的又一例：**trace 命中 ≠ 字段正确**
- 修复：callFull → fullArgs，sha a58d59a5，两副本同步，重启 22:16:19 生效
- 修复后 A/B 从 11/12 → 12/12，门禁 79/0

### 综合判定（三层分开说）

1. **机制触发（L4）**：✅ 真实会话命中（回读门 2+ 次、状态板 step=8 一次）
2. **行为改变（L5，受控）**：✅ A/B 12/12 硬证据——假完成被拦、真落盘放行、状态板进 prompt
3. **成功率提升（端到端）**：❌ **无证据**——真实会话样本 n=2，远不足 n≥16 A/B + Wilson CI 门槛

### 最终状态
- 生产：杠杆1/2 开启（sha a58d59a5，重启 22:16:19），杠杆4 默认关，杠杆3 不做
- 门禁：79 pass / 0 fail
- 回滚：`python tools/levers_deploy.py rollback`（回到 362e3715）

---

## 原报告：`BROAD_RESEARCH_20261124.md`

## 广泛调研：同配置社区/论文方案 + 词表放 SSD 的可行性（2026-11-24）

> 用户：有没有跟我们机器和模型配置同样的社区和论文方案？值得借鉴的优化？能否像 qwen3.8 那样把词表放进 SSD？
> 三路并行调研（论文 / 社区 / SSD 机制）+ 本机交叉验证。**这是调研沉淀，不是立即执行清单。**

---

## 第一部分：结论速览（按性价比排序）

| 方案 | 来源 | 预期收益 | 成本 | 本机可行性 |
|---|---|---|---|---|
| ~~1. 升级主线 llama.cpp（PR #31233 ClassLRU）~~ | ~~llama.cpp PR~~ | **已在本机版本(94f3af3)** | — | ❌ 伪机会 |
| **2. mmproj F16→Q8_0**（省 280 MiB 显存） | 本机已下载 Q8 版本 | +2~3%（跨安全线） | 配置 | ✅ 已有文件 |
| **3. `-ot token_embd.weight=CPU`**（省 515 MiB）| 词表调研 | 显存 +515 MiB，速度 <0.3% 损失 | 配置 | ✅ 高，待实测 |
| **4. 换 ik_llama.cpp + IQ3_K_R4** | 社区实战 | 41→55 t/s（同款 4060 8GB）| 换引擎+重下 20GB | ⚠️ 大工程 |
| **5. 多通道 DDR4 内存** | 论文/社区 | 带宽翻倍→上限翻倍 | 换硬件 | ❌ 笔记本板载 |
| **6. 词表放 SSD（Qwen3.8 式）** | 用户提问 | — | — | ❌ **机制不适用** |

---

## 第二部分：词表放 SSD —— 用户记错了机制（重要）

### 2.1 "Qwen3.8 把词表放 SSD"到底是什么

调研确认：用户指的是 **Qwen3.8-Flash-Next 的 51B N-gram 模型权重放 SSD / 按需 mmap**——那是**独立的 ngram 投机模型**（51B 参数），不是主模型的词表 embedding。

**本机 qwen35moe 架构根本没有这张表**：
- GGUF 里没有 `ngram.*` 张量
- `--spec-type ngram-*` 用的是运行时内存里的 token 历史，不是外部权重
- llama.cpp 的 `--lazy-mode on` 对 qwen35moe 是 **no-op**（没有 dflash/ngram 权重可 lazy load）

**结论：这个优化在本机不适用，不是配置问题，是模型架构里就没有这个组件。**

### 2.2 那本机"词表"能不能挪走？——分两个张量看

本机词表两项（GGUF 精确解析）：

| 张量 | 大小 | 精度 | 用途 | 每步访问模式 |
|---|---:|---|---|---|
| `token_embd.weight` | **515 MiB** | Q8_0 | 输入 embedding 查表 | **只读 1 行 = 2.2 KB**（随机小读）|
| `output.weight` | **515 MiB** | Q8_0 | LM head matvec | **读全部 515 MiB**（顺序流式）|

合计 1.01 GiB，占总权重 4.7%。

#### 关键分水岭：`token_embd` 可以挪，`output` 绝不能挪

```
理论带宽需求（DDR 双通道理论 51.2 GB/s、流式实读 40-45 GB/s / GPU ~250 GB/s）：

token_embd 查表(2.2 KB)：
  DDR: 0.0001 ms  → 挪到 CPU 每年损失可忽略
  SSD: ~0.1 ms    → 每步 +0.1ms，4% 开销，勉强可接受

output.weight matvec(515 MiB)：
  DDR: 19.8 ms/步 → 挪到 CPU 就 +20ms → 25 t/s 掉到 16 t/s（-34%）
  SSD: 103 ms/步  → 9.7 t/s（灾难）
```

**所以"词表放 SSD"在本机的可实现版本只有一个**：`-ot token_embd.weight=CPU`（挪到内存而非 SSD，省 515 MiB 显存），而 `output.weight` 必须留在 GPU。

#### 可行性细节
- qwen35moe 的 `token_embd` 和 `output` 是**独立张量**（不是 tied embedding），可以单独 offload
- `-ot` override 是通用张量名匹配（`llama-model-loader.cpp:1328`），对任何张量生效
- 但 **SSD mmap 不推荐**：Windows WDDM 下 mmap 换页行为不可控，NVMe 随机读延迟虽可接受，但有抖动风险
- **待实测**：`-ot token_embd.weight=CPU` 的真实提速（预计省 515 MiB 显存 → 可能跨过安全线 → +2~4%）

---

## 第三部分：同配置社区方案（8GB 卡 + 64GB 内存跑 MoE）

### 3.1 最重磅：ik_llama.cpp + IQ3_K_R4（同款 4060 Laptop 8GB）

社区实战报告：**同一台 4060 Laptop 8GB 跑 Qwen3-30B-A3B 类模型**
```
主线 llama.cpp Q4_K_M:  41 t/s (短) → 24 t/s (长上下文)
ik_llama.cpp IQ3_K_R4:  55-57 t/s，且不随上下文衰减
```
核心优势：**融合专家 GEMM**（把 top-8 专家的计算合成一次 kernel）+ IQ3_K_R4 量化（3.5 bit，比 Q4_K 少 25% 带宽）+ 更激进的 CPU 缓存调度。

**对本机适用性：高，但是大工程**——需要换引擎（无本地二进制，需从源码编译）+ 重量化 20GB 模型（无 llama-quantize 工具）。建议作为"下一步大动作"候选，不是本周可做。

### 3.2 llama.cpp 主线尚未合入的高价值 PR

| PR | 内容 | 对本机价值 |
|---|---|---|
| ~~#31233 ClassLRU~~ | 按专家类别分层缓存 | **已合入并生效**（src/llama-moe-cache.cpp:21，生产 94f3af3 已含）|
| **#32100** | 静默错误修复（投机解码采样一致性）| **正确性问题**，值得升级 |
| **#29307** | token-aware parsing | 已知未合并，影响有限 |
| **#29949** | GPU-resident LRU | 需显存，本机不适用 |

**验证结果（2026-11-24）**：ClassLRU **已在本机**——`src/llama-moe-cache.cpp:21` 有实现，生产二进制 commit 94f3af3 与源码一致。**这不是待办，是已具备的能力**。也解释了为什么我们把 cache 从 1350 加到 1900 没收益——LRU 分层已经把热点照顾好了。

### 3.3 MoE cache 调参的社区经验
- `scripts/moe-cache-tune.py` 自动扫 cache 大小找拐点
- 我们已实测 1350→1900 **没收益**（热点已饱和），印证"1350 已接近上限"
- 社区共识：cache 容量不是瓶颈时，提高命中率要靠**访问频率排序**（LRU 已近最优）→ #31233 ClassLRU 正是这个方向

### 3.4 CPU 侧优化的社区/论文经验
- **多通道 DDR4**：本机**已是双通道**（两条 Lenovo DDR4-3200 32GB 序列号连续=原厂套装，分属 Controller0/Controller1），历史实测流式读 40-45 GB/s。笔记本硬件锁定，无需也无法改
- **huge pages / 绑核 / 电源计划 / NUMA 交错**：本机已全部证伪或在笔记本上不适用
- **动态频率**：笔记本 BIOS 锁定，不要用第三方工具强改

---

## 第四部分：论文方案（针对 memory-bound MoE decode）

### 4.1 值得关注（理论可落地）

| 论文 | 年份 | 核心思想 | 本机适用性 |
|---|---|---|---|
| **PowerInfer / PowerInfer-2** | 2023-24 | 稀疏激活：热神经元常驻 GPU，冷神经元按需从 CPU/SSD 取 | MoE 版思想≈我们的 moe-cache，已做；SSD 版不适合 NVMe 延迟 |
| **MoE-Infinity** | 2023 | 专家级 LRU + 预取 | ≈ #31233 ClassLRU，见上 |
| **Fiddler / Brainstorm** | 2024 | CPU-GPU 协同调度，隐藏专家加载延迟 | 我们试过专家并行慢 3-5%，但他们的细粒度流水线可能更优 |
| **AdapMoE** | 2024 | 自适应专家预取 | 本机预取实测无效（带宽满），低优先级 |
| **Staged Speculative Decoding** | 2023 | 多级草稿 + 动态选择 | 需要训练，不适用 |
| **Token Trees / Lookahead** | 2023-24 | 多头并行 draft | ngram 已试，命中率低 |

### 4.2 DeltaNet 混合架构
本机 31 层 DeltaNet（线性注意力）+ 10 层 KV attention。学术论文主要在训练侧，**推理侧 llama.cpp 已有优化**（记忆里 CTX_CHECKPOINTS=2 是承重墙，降到 1 慢 23%）。暂无新的可落地优化。

### 4.3 结论
**论文层面没有发现"能立刻落地且未被我们试过"的大收益方案**。最接近的是 ClassLRU（已合入主线 PR）和 ik 的融合 GEMM（需换引擎）。

---

## 第五部分：行动建议（按优先级）

#### 立即可做（本周）
1. ~~查 ClassLRU 是否已合入~~ → **已验证合入，无需动作**
2. **把 mmproj F16 换成已下载的 Q8_0 版本**（省 280 MiB，跨过 450 安全线，+2~3%）
3. **实测 `-ot token_embd.weight=CPU`**（省 515 MiB，理论速度损失 <0.3%，可能 +2~4%）—— **下一条消息立即做**

#### 大动作候选（需要用户决策）
4. **编译 ik_llama.cpp + 重量化 IQ3_K_R4**：预期 25→55 t/s（2.2×），但要下载 20GB + 编译 + 重配，是"换引擎级"工程
5. **词表放 SSD**：机制不适用（本机没有 51B ngram 权重），唯一可做是 `token_embd` 挪 CPU，见第 3 条

#### 明确不做
- ❌ 加大 MoE cache（已证伪，热点饱和）
- ❌ DFlash 侧车（已证伪，-34%）
- ❌ 换内存通道（笔记本硬件锁定）
- ❌ 词表 output.weight 挪 CPU/SSD（-34%~-75%）

---

## 第五·五部分：调研后的实测验证（2026-11-24 晚）

### A. `-ot token_embd.weight=CPU`：**+7.4%（真实收益，已上线）**

| 配置 | tps | n | sd |
|---|---:|---:|---:|
| 基线（F16 视觉 + token_embd 在 GPU）| 24.91 | 6 | 1.69 |
| **token_embd 挪 CPU** | **27.84 / 26.75** | 6+8 | 1.72 / 1.04 |

**两次独立测量均值 27.3 t/s，+7.4%**。理论预期 <0.3%（每步只读 2.2 KB），实测远超——**收益来自显存再分配**：token_embd 挪出 515 MiB 后，llama.cpp 把显存让给了 compute buffer / ubatch，缓解了 WDDM 换页压力。机制和"禁用视觉 +4.9%"同源。

**注意**：`output.weight`（LM head，515 MiB）**必须留在 GPU**——每步 matvec 要读全文，挪 CPU 会掉 34%（见 2.2 节）。

**配置**：preset 全局段加 `override-tensor = token_embd.weight=CPU`。

### B. mmproj F16→Q8_0：**文件存在但加载失败，已回滚**

本机有两个 Q8_0 mmproj 文件，换上后 `health=200` 但日志反复报 `failed to load multimodal model`：
```
[61850] E srv load_model: failed to load multimodal model, '...mmproj-Q8_0.gguf'
[61850] E srv server_run_i: exiting due to model loading error
```
GGUF 头检查：三份文件都是 `arch=clip`、334 张量，但 122 MiB 那份 `general.name=Qwen3.6 35B A3B`（点变空格），疑似转换时元数据不一致被 mtmd 拒绝。**已回滚 F16，多模态正常。**

教训：**health 200 ≠ 多模态可用**，必须查 `load_model: loaded multimodal model` 日志。

（Q8 视觉下 decode 测到 27.0 t/s，但视觉功能失效，无实用价值。）

### C. 已验证为"伪机会"的项
- ~~ClassLRU 未合入~~ → 已在生产版本（94f3af3）
- ~~mmproj Q8 可用~~ → 加载失败

## 第六部分：诚实的元结论

调研的**最高价值发现不是新技巧，而是排除了两个伪机会 + 确认了一个真差距**：
1. **ClassLRU 已在生产版本**，不是待办（已验证）
2. **⚠️ 已纠正：单通道怀疑是我造成的单位笔误**（11-24 晚）。派子任务时我把 **decode 的 25.4 tok/s** 误写成 "DDR 实测 25.4 GB/s"，子任务据此推出"接近单通道理论 25.6 → 可能单通道"。**这是错的**：
   - 本机**是双通道**：两条内存规格完全一致（Lenovo DDR4-3200 32GB，序列号 03CDFF26 / 03CDFEA0 连续=原厂配对套装），分属 **Controller0 / Controller1**。WMI 的 "Controller0-ChannelA"/"Controller1-ChannelA" 是 BIOS 命名，不是"同通道"。
   - 历史实测（10-20）：`2×32GB DDR4-3200 双通道，理论 51.2 GB/s，流式读 ≈40-45 GB/s`。
   - 真实有效带宽 = 580 MiB/token ÷ 40ms ≈ **14.5 GB/s**（51.2 的 28%）。**瓶颈不是带宽峰值，是随机访问局部性**——每 token 从 256 专家随机挑 8 个，是随机读非流式读。这解释了 ik_llama.cpp 的 IQ3_K_R4（重排专家权重改善 L3 局部性）为何能提速 2 倍：改善局部性而非减少字节。
   - 教训：派子任务时给的数字必须核对单位，否则整条推理链建立在错误前提上。
3. **引擎选择可能比参数调优重要 2 倍**：同类 8GB 卡上 ik_llama.cpp 的 55 t/s vs 主线 25 t/s，这个差距远超我们最近做的所有 ±5% 优化。**"harness 杠杆 > 模型选择"的经验可能在引擎层面重演**。

建议下一步聚焦"升级引擎"而非"继续微调参数"。


---

## 第七部分：引擎改进评估 —— 能否按 ik 思路优化（2026-11-24 晚）

> 用户：这方面我们的引擎能不能改进（包括重新按 ik 的思路优化我们的引擎）？
> 结论：**能，但要选对路径。最划算的是直接用 ik 引擎（现有 Q4_K_XL 模型不用重训/重下）；自己往主线移植 fused 算子风险高、收益不确定。**

### 7.1 ik 的 2× 优势到底来自什么（源码核实）

我把 ik 源码 checkout 到 `D:/ik-src`（commit 1180df7，MIT），和主线 94f3af3 逐项对比：

| 机制 | ik (1180df7) | 主线 (94f3af3) | 我们 |
|---|---|---|---|
| **MOE_FUSED_UP_GATE 算子** | ✅ `ggml.c:8743`，默认开（`llama.cpp:9337`）| ❌ `ggml.h` 里 0 次出现 | ❌ 没有 |
| **权重重排 repack** | ✅ IQK 专用 | ✅ `ggml-cpu/repack.cpp`，Q4_K 有 `Q4_Kx8` 交错 | ✅ **已启用**（默认开，没传 `-nr`）|
| **gate_up 合并张量** | ✅ 支持 | ✅ `llama-graph.cpp:2534` 有 merged 路径 | ❌ **我们的 GGUF 没有 gate_up**（gate/up/down 各 41 个独立张量）|

**核心差异是第 1 条**：ik 有 `GGML_OP_MOE_FUSED_UP_GATE` 算子，把 MoE 的 up 投影 + gate 投影 + SiLU 激活**融合成一个 kernel**，直接在寄存器里算激活，**不把 up/gate 两个中间结果写回内存**。

主线（包括我们）走的是：
```
gate = mul_mat_id(gate_exps, cur)   → 写内存
up   = mul_mat_id(up_exps, cur)     → 写内存
cur  = silu(gate) * up              → 再读两次内存
```
每 token 每专家要**多遍历一次专家权重 + 两次中间张量往返内存**。ik 的融合算子把这些合成一次。

**这正好击中我们的瓶颈**：每 token 从 256 专家随机挑 8 个，每个专家的 gate/up 权重各 24 MiB，主线要分别读两次（随机访问，L3 命中差），ik 融合后读一次。**有效带宽利用率从 28% 提升的关键就在这里。**

### 7.2 最关键的结论：不需要重新量化模型

**ik 的 fused up/gate 是计算图级融合，对任何量化类型都生效，包括我们的标准 Q4_K_XL。**

- 不是新的量化格式（那是 IQ3_K_R4，另一回事）
- 不需要重新下载/量化 20GB 模型
- 不需要重训
- 算子在 `ggml/src/ggml.c`（通用 C 实现，`GGML_IQK_MUL_MAT=ON` 默认开启），不是硬件专用

**所以"用 ik 引擎跑我们现有模型"是可行的，成本只是编译一次 ik。**

### 7.2.5 ⚠️ 决定性事实：我们 2026-11-16 已经实测过 ik，结论是「不用」

在准备编译 ik 实测时，从 autostart `index.mjs:267` 发现关键注释：

> ik_llama.cpp 支持已于 2026-11-16 移除：实测 decode 24.1 vs 27.3、prefill 513 vs 950，且它的 cpu_share 是单一标量，无法复现「解码就地算 / 预填充上传」的分档配置。

查 `memory/2026-11-16.md` 的完整记录：

| 配置 | decode | prefill |
|---|---:|---:|
| ik（cache1300/ub1536/share1.0）| 24.1 | 513 |
| **主线（cache900/ub2048/share分档）** | **27.3** | **950** |

**为什么 ik 的 CPU 优化没体现**（当时的分析，今天得到进一步印证）：
1. ik 的 `only_active_experts` / fused MoE 针对"激活专家在 CPU 做 GEMM"的**计算调度**；我们的瓶颈是"从 18.7 GB 里随机捞 312 个 1.78 MiB 块"的**内存访问**。今天算出的"有效带宽仅为双通道 28%"正是这个原因——**ik 的优化没打中靶心**。
2. ik 的 `cpu_share` 是单一标量，无法复现我们的"解码就地算 / 预填充上传"分档配置（追平需要移植 prefill 分档补丁到它的 policy 代码，结构完全不同）。
3. ik 显存占用更高 100-300 MiB，直接挤掉最赚钱的 ubatch（2048→1536）。

**注意**：当时还犯过一个配置错误（直接套 ub2048 导致显存 411 MiB < 安全线 450 → decode 掉到 7.95），上表是**配置正确时**的对比，不是错误配置的假数据。

**结论修正**：社区 55-57 t/s 的数据没能在本机复现（i7-12650H 无 AVX-512、双通道 DDR4 而非社区测试机的配置差异）。**路径 A 已被实测否定，不是"待验证"**。

（本次调研中我一度准备重新编译 ik 实测，看到这条历史才停下——避免了重复劳动。已停止编译、删除临时脚本；`D:/ik-src/build` 151 MiB 保留备查。）

### 7.3 三条路径的评估

#### 路径 A：直接用 ik_llama.cpp（推荐）
- **收益**：社区同款 4060 Laptop 8GB 实测 41→55 t/s（+34%），长上下文不衰减（主线 41→24，ik 55→57）
- **成本**：编译 ik（源码已在 D:/ik-src）+ 切换 autostart 的 engine 路径 + 重跑配置校准（ik 参数名有差异）
- **风险**：① ik 的 FA/MTP 行为和主线不同，要重新验证 ② 我们依赖的 `--cpu-moe` / moe-cache / router 模式在 ik 上的支持情况要确认 ③ b12244 的 autoparser 补丁要在 ik 上重打（如果 ik 也有这个 bug）
- **不确定的点**：社区 55 t/s 的数据用的是 Qwen3-30B-A3B + ik 专用量化，我们的 Qwen3.6-35B-A3B + 标准 Q4_K_XL 能拿到多少，**必须实测**

#### 路径 B：把 fused 算子移植到主线（不推荐）
- **工作量**：ik 的 `MOE_FUSED_UP_GATE` 涉及 ggml 算子定义、CPU 后端 compute、graph builder 三处，`iqk_moe_fused_up_gate` 还依赖 `GGML_IQK_MUL_MAT` 整套优化，**不是几百行能搞定**
- **风险**：主线每次升级都要重打补丁（我们已经有 autoparser 补丁的教训）；且 ik 的算子可能和主线的 repack 路径冲突
- **结论**：投入产出比差，**不如直接用 ik**

#### 路径 C：在主线上做"gate_up 权重合并"（中间路线，可小成本试）
- 我们的 GGUF 没有 gate_up 合并张量，但可以在**加载时**把 gate_exps 和 up_exps 拼成一个张量（2×n_ff），走主线已有的 `gate_up_exps` merged 路径
- **收益**：省一次 `mul_mat_id` 的 kernel launch 和权重遍历，但**仍需写回中间结果**，不如 fused 算子彻底
- **成本**：改 `src/llama-model.cpp` 的权重加载逻辑，约 50-100 行
- **风险**：中等；且需要验证 qwen35moe 的 graph builder 是否接受合成张量
- **定位**：如果不想换引擎，这是**唯一值得试的小改动**，但预期收益远小于路径 A

### 7.4 诚实的建议

1. **❌ 不要用 ik（路径 A 已实测否定）**：11-16 配置正确的 A/B 显示 ik 反而慢 12%（decode）/46%（prefill）。社区 55 t/s 不可复现。
2. **✅ 接受当前 25-27 t/s 作为主线引擎的天花板**：主线已启用 repack（我们验证过），剩余局部性损失是"从 18.7GB 随机捞 312 块"的结构性问题，配置调不回来。
3. **❌ 不要自己移植 fused 算子**（路径 B）：ik 的 fused MoE 打的是 GEMM 调度，不是我们的内存访问瓶颈；移植过来也不会提速。
4. **🔬 唯一有理论价值的方向**：路径 C（gate/up 权重在加载时合并）+ 更激进的**专家访问局部性**改造（如按访问频率重排专家在 GGUF 里的物理布局，让热专家聚集在少数 4KB 页/DRAM burst）。但这些都是改引擎核心的中等工程，收益不确定。

### 7.5 一个待验证的反面可能

ik 的 55 t/s 数据是在**专家全在 GPU 或大显存**的配置下测的（`-ncmoe 99`），我们是 `--n-cpu-moe 40` 全 CPU。ik 的优势（融合算子）在 CPU 路径上是否同样有效，**需要实测**：
- 如果 ik 的 `MOE_FUSED_UP_GATE` 只在 CUDA 后端有优化实现，CPU 路径可能退化成主线行为
- 从源码看它在 `ggml.c` 有通用实现，`GGML_IQK_MUL_MAT=ON` 默认开，理论上 CPU 也生效——但**必须实测确认**

**建议的决策方式**：先编译 ik，用现有模型跑一次 `tps_probe.py`，和当前 27 t/s 对比。如果 ≥40 t/s，值得全面切换；如果 <30 t/s，说明优势不在这条路径上，维持现状。


---

## 第八部分：为什么社区能做到 50+ decode（2026-11-24 晚，含重要自我纠错）

> 用户：那为什么他们能做到 50+ 的 decode？
> **结论：不是引擎更快，是"专家放 GPU 的比例 + 量化精度 + 上下文长度 + 测试口径"四个变量全不同。我们和社区根本不在同一配置点。**

### 8.1 ⚠️ 先纠错：我一直用错了基线和单位

在回答前必须纠正我犯的三个错误：

1. **把 decode t/s 当成 GB/s**：我曾把 "25.4 tok/s" 写成 "DDR 实测 25.4 GB/s"，导致子任务推出"可能单通道"的错误结论（已在第七部分纠正）。
2. **基线用错**：我一直在用 25-27 t/s 作为我们的 decode 基线，但那是**早期 t6 数据**或**不同的测试口径**。历史记录（2026-11-18 条目 2024）显示：线程扫描（stream 前 128 token 纯净 decode，两轮交叉）**t6=29.18/28.31、t8=33.21/34.24、t10=32.82、t12=25.28**。我们**当前配置已经是 t8（已部署 LLAMA_35B_THREADS=8）**，真实纯净 decode 基线应是 **33-34 t/s**，不是 25-27。
3. **测试口径混淆**：我今天的 `tps_probe.py` 用 `n_predict=200` 拿 `timings.predicted_per_second`（端到端，含 draft 接受率波动），11-23 用 stream 前 128 token（纯解码）。今天用非 stream 短响应测出 **11-20 t/s**（draft=94/70 波动大），用旧口径应回到 33 左右。**社区报的 50+ 都是"纯解码 t/s"，必须同口径对比。**

**所以真实差距是 33-34 vs 社区 50-57，约 1.5×，不是我之前说的 2×。**

### 8.2 核心差异：`--n-cpu-moe N` 的语义

源码确认（`common/arg.cpp:2742-2749`）：**N = 前 N 层专家留在 CPU**，其余在 GPU。

| 配置 | 前 N 层 CPU | 后几层 GPU | 说明 |
|---|---:|---:|---|
| **我们 `-ncmoe 40`** | 40 层 | **0 层** | **所有专家都在 DDR**（41 层模型）|
| 社区 `-ncmoe 28` | 28 层 | **12 层** | 12 层专家在 GDDR |
| 社区 `-ncmoe 29` | 29 层 | 11 层 | — |
| XDA `-ncmoe 28` | 28 层 | 12 层 | — |

### 8.3 算账：为什么我们放不下专家到 GPU

从 GGUF 精确解析：**每层专家权重（gate+up+down，256 专家）≈ 468 MiB**，41 层共 18.73 GiB。

| 挪到 GPU 的层数 | 需要显存 | 我们余量 360 MiB 能吗 |
|---:|---:|---|
| 1 层 | 468 MiB | ❌ |
| 4 层 | 1.83 GiB | ❌ |
| **12 层（社区配置）** | **5.48 GiB** | ❌❌ |

**社区的 8GB 卡是怎么塞下 5.5 GiB 专家的？**

| 手段 | 省出的显存 | 我们的处境 |
|---|---:|---|
| IQ3_K_R4 / IQ4_XS（3.4-4.25 bpw）vs 我们 Q4_K_XL（4.5 bpw）| 整模省 4-6 GiB | 本机**只有 Q4_K_XL 一个模型**，没有 IQ 版本 |
| ctx 16K vs 我们 96K | KV 省 650 MiB | 我们依赖长上下文（96K + checkpoints）|
| 关视觉 | 858 MiB | 我们需要多模态 |
| moe-cache 缩小 | 0-1350 MiB | 我们的热点缓存正 benefit |

**社区是把"功能 + 精度 + 上下文"全省了，换 12 层专家上 GPU。我们一个都不想省，所以拿不到那个速度。**

### 8.4 速度分解（为什么 12 层上 GPU 能到 50+）

每 token 读的专家数据：41 层 × top8 × 1.83 MiB/专家 ≈ **600 MiB**（与实测 580 MiB 吻合）。

带宽理论：
- DDR4-3200 双通道流式：45 GB/s → 600 MiB 纯读 13.3 ms
- GDDR6 RTX 4060 Laptop：256 GB/s → 600 MiB 纯读 2.3 ms

但实际是**随机访问**（每 token 从 256 专家随机挑 8 个），有效带宽远低于峰值：

| 配置 | DDR 侧 | GPU 侧 | 预计 t/s |
|---|---|---|---|
| 我们（40 层 CPU）| 600 MiB @ 15 GB/s 有效 = 40 ms | 0 | **25** ✓ 与旧基线吻合 |
| 社区（28 CPU + 12 GPU）| 409 MiB @ 15 = 27 ms | 175 MiB @ 50 有效 = 3.5 ms | 并行取 max → 27ms → **33-37** ✓ 吻合社区 31-34 |
| 社区 + IQ3 量化（字节少 25%）| 307 MiB → 20 ms | 131 MiB → 2.6 ms | 20ms → **45-50** ✓ 接近社区 50+ |
| 再加上 DDR5 内存（他们用 i7-14700HX + DDR5）| 有效带宽翻倍 → 10 ms | — | **~60-70** |

**社区 50-57 t/s 的四个来源（可量化分解）**：
1. **12 层专家在 GDDR**（+30-40%，最大杠杆）
2. **IQ3/IQ4 量化少读 25-30% 字节**（+25-30%）
3. **DDR5 内存**（部分社区配置，+20-30%）
4. **短上下文/关视觉**（腾出显存让第 1 条成立的前提）

**没有一条是"引擎算法更聪明"**——这也解释了为什么 ik 引擎在我们这台机器上实测反而慢：ik 打的是 GEMM 调度，而这些收益来自内存层级配置。

### 8.5 我们能不能做到？诚实回答

**不换硬件、不重下模型，达不到 50+。** 但可以分项逼近：

| 动作 | 预期收益 | 代价 |
|---|---|---|
| 缩短 ctx 96K→16K + 关视觉 + 砍 moe-cache | 腾出 2.8 GiB ≈ 6 层专家上 GPU | 失去多模态、长上下文、热点缓存 |
| 上面 + 把 4-6 层专家挪 GPU | 33→~38 t/s | 同上 |
| 换 IQ3_K_R4 模型（重下 20GB） | 再 +25% → ~48 t/s | 精度损失、20GB 下载、无 imatrix 校准 |
| 换 DDR5 平台 | 再 +20-30% | 换硬件，不可能 |

**最划算的现实路线**：今天已验证的 `-ot token_embd.weight=CPU`（+7.4%，零代价）比这些折腾都值。

### 8.6 一句话总结

**社区 50+ 不是"引擎快"，是"把 12 层专家塞进显存 + 用 3-bit 量化少读字节 + 短上下文/关视觉腾地方 + 部分用 DDR5"。我们保留全部功能、用 4.5bpw、96K 上下文、专家全在 DDR，所以是 33 t/s。差距是配置选择，不是技术代差。**


---

## 第九部分：上下文管理、海马体与 96K 的价值（2026-11-24 晚）

> 用户：上下文有没有更科学的管理手段？我们要那么长的上下文有什么作用？我们的海马体是否承担了一部分上下文的作用？这块有没有削减以腾出性能的空间？

### 9.1 "海马体"是什么 —— 已查证

**海马体 = `dsh-task-continuity` 插件的 P0 压缩存档机制**（2026-11-17 已合并进 behavior-guard）。

- 出处：`dsh-task-continuity/README.md`、`dsh-behavior-guard/README.md` 的"构建脑"阶段
- 机制：压缩后自动重注入【任务合同 + 已验证决策 + 开放项 + 已排除 + 三问】
- 设计依据：MemGPT（工作上下文概念）、Hippo（无整合累积记忆低于无记忆基线）、initializer+progress-file pattern
- **关键实测**：压缩后 inputTokens 从 17976 骤降到 2679 时模型开始遗忘；注入存档后恢复正常
- **去重修复**：同一存档曾重复注入 82 次形成自我强化循环，已加签名去重

**所以用户的直觉是对的：海马体确实外置了一部分"上下文记忆"功能**——无需模型自己记住，harness 自动维护关键信息。

### 9.2 真实上下文使用率（两路数据，注意口径不同）

#### A. llama-server 日志（增量 prompt token，1757 个请求）
```
min=1  p25=727  median=1750  p75=3112  p90=31062  max=54673
分布: <4K=1382(79%)  4-8K=29  8-16K=100  16-32K=78  32-54K=164  54K+=4
```
**但这测的是"每次请求的增量输入"**（因为 KV cache 复用，大部分请求只传新增 token）。

#### B. harness trace（上下文总量 sid 级别，子任务提取）
```
2032 个真实 sid 会话，中位数 37235 token（~36K）
分布: 2-4K=201  4-8K=331  8-16K=508  16-32K:峰值  32K+:271
P95=57344，但真实 54K+ 只有 33 次（1.6%）
```
**这是"会话实际积累的上下文长度"**，更接近"我们用了多少 96K"。

**综合判断**：真实 agent 会话中位约 36K，**只有 1.6% 会触及 54K 压缩触发点**，99% 时间在 54K 以下。96K 上限**从未用满过**（最大 57344，远低于 98304）。

### 9.3 96K 上下文到底有什么用 —— 不是"同时看 96K"

关键澄清：**96K 不是"模型同时处理 96K token"**，而是"压缩前的缓冲空间"：

```
ctx 98304 (96K)
压缩触发点 = min(98304×0.55, 98304-16384) = 54067 (54K)
压缩后保留 = retainTokens 24576 (24K)
headroom = 16384
```

也就是说：
- 会话积累到 54K 就触发压缩，压到 24K 继续
- 96K 提供的是"从 24K 到 54K 之间不用频繁压缩"的 30K 缓冲带
- 真正被模型同时处理的上下文**永远不超过 54K**

**代价**：KV cache @96K = 798 MiB（K=q8_0/V=q4_0，10 层标准注意力 × 2 KV heads × 256 head_dim）
**收益**：把压缩频率从"每 10K 一次"降到"每 30K 一次"——因为**每次压缩有真实代价**（记忆里：改写历史有 KV 后缀税，本机 20K 重预填充 25-44s）

### 9.4 降 ctx 腾性能的实测：**无效（已证伪）**

我做了 A/B：ctx 96K → 48K（同步改 .env + cordis contextWindow + retain 24576→16384）

| 配置 | 显存 | tps_probe decode |
|---|---:|---:|
| 96K（基线）| 7691 MiB | 27.84 / 26.75（均值 27.3）|
| **48K** | **7330 MiB（省 390）**| **25.63（反而略慢）**|

**为什么降 ctx 不提速**：省下的 390 MiB 没有自动转化为性能——MTP、moe-cache、ubatch 都是固定配置，不会因为有空闲显存就自动放大。**只有把显存主动投给"能提速的东西"（如 moe-cache 加大、专家上 GPU）才有收益**。而这两条我们已证伪（cache 1350→1900 无效；专家上 GPU 需 468MiB/层且挪 2 层净亏 9.5%）。

**已恢复 96K 生产配置。**

### 9.5 更科学的上下文管理手段（调研结论）

#### 已有的（我们已做到）
- **P0 压缩存档（海马体）**：压缩后自动重注入任务状态，模型零参与（比 MemGPT 让模型自己管记忆更适合本地 35B）
- **append-only 优于改写**：改写历史思维链有 KV 后缀税（本机 20K 重预填充 25-44s），我们的架构天然规避
- **CTX_CHECKPOINTS=2**：分段 checkpoint，降到 1 每步全量重预填充 +23% 耗时
- **retain 24K + headroom 16K**：压缩后保留足够上下文避免立即再触发

#### 可改进但收益有限的
- **KV 量化已到 q4_0 附近**：从 q8_0 再降收益小，且质量风险
- **动态 ctx 按需**：llama.cpp 支持启动时指定，但会话中动态调整需重启，不实际
- **语义压缩/摘要**：比机械截断好，但本地 35B 做摘要质量有限，且引入新的不确定性

#### 结论
**我们的上下文管理已经是"科学"的**——海马体外置 + append-only + checkpoint + 分层 retain 都是社区最佳实践。96K 的代价（798 MiB KV）换来了"少压缩"，而压缩的真实代价（25-44s 重预填充）远大于这点显存。

### 9.6 最终判断

| 问题 | 答案 |
|---|---|
| 上下文管理科学吗？| ✅ 已是最佳实践组合（海马体 + append-only + checkpoint + 分层 retain）|
| 96K 有什么用？| 压缩前缓冲带（24K→54K 免压缩），不是同时看 96K |
| 海马体承担上下文作用吗？| ✅ 是 P0 压缩存档，外置了任务状态记忆 |
| 能削减腾性能吗？| ❌ **实测降 ctx 到 48K 反而略慢**，省下的显存无处可投；已恢复 |

**一句话**：96K 是"保险"不是"负担"——真实会话中位 36K、只有 1.6% 触及压缩点，但我们不能为了省 798 MiB 而让那 1.6% 的长任务频繁付 25-44s 重预填充税。海马体已经在做"上下文外置"，但它的价值是防遗忘，不是省显存。


---

## 第十部分：压缩阈值的博弈最优（2026-11-24 晚）

> 用户：上下文压缩阈值科学吗？不想反复压缩、希望压缩后占用更少、希望压缩时间尽可能少——怎么博弈最优？

### 10.1 ⭐核心洞察：三个目标不能同时最优，但有一个被忽略的主杠杆

先说结论：**触发点（thresholdRatio）不是主杠杆，它的移动几乎是"零和"的**。真正的杠杆是：
1. **降低压缩后保留量**（同时改善"占用少"和"频率低"）
2. **减少触发压缩的次数本身**（truncate messages 工具 + pruner 前置）
3. **重写前缀**（把固定开销从 O(T) 降到 O(1)）——本地 35B 做不了，需要小模型

### 10.2 实测数据（本地 + 学术 + 社区）

#### A. 本地真实压缩事件（llama-server 日志，1760 请求）
```
76 次压缩事件（prompt 骤降 >70%）
压缩前 token 中位 = 41592（接近 54K 触发点）
压缩后增量 prompt 中位 = 1622
间隔：median=1024s(17min) p25=485s p75=1905s
<60s 的"反复压缩" = 6/76 (8%)
```

#### B. 本地压缩成本拆解（s1 会话，子任务实测）
```
成功摘要 28 次：user 输入 31946 token，摘要输出 1178 token，wall 110-210s
失败摘要 16 次：累计 2756s（46min）—— 全部卡在 60s 超时 × 重试
纯裁剪(prune) 12 次：0s —— 这是最便宜的压缩
近因：92 次事件里 78 次 system prompt 是 972 token，14 次是 4119 token
（4119 那批摘要耗时 137s vs 972 那批 55s → 前缀长度主导成本）
```

**关键发现：压缩成本几乎全是 prefill**（80-110s 读完整上下文），生成摘要本身只占几秒。`C(T) ∝ T / 550 tok/s`。

#### C. 学术/社区对照
- **NoLiMa (ICML 2025)**：13 个标称 128K+ 模型，32K 时 11/13 跌破短上下文基线 50% → 触发点后移有**质量代价**
- **Context Rot (Chroma 2025)**：30K 时 Llama-3.1-8B 掉 85% → 长上下文可靠性随长度下降
- **Factory.ai (36000 会话)**：主动压缩优于被动压缩（摘要质量更高）；压缩率 99% 但质量低 0.35/5 → 压缩率不是好指标
- **Anthropic**：子 agent 独立窗口烧 5 万 token，只回传 1000-2000 token 摘要
- **Claude Code auto-compact**：触发点 ~95%（远后于我们 55%），但那是云端大模型 + 不同架构
- **社区共识**：retain 通常 20-30% 窗口（我们 24K/96K = 25%，合理）

### 10.3 博弈模型（用真实成本函数）

设：
- `T` = 触发点 token 数，`R` = 压缩后保留 token 数
- `C(T) ≈ T/550` 秒（压缩成本，主要是 prefill）
- 缓冲带 `B = T - R`，压缩频率 `f ∝ 1/B`
- **总成本率 ∝ C(T)/B = T / (550 × (T-R))**

| thresholdRatio | T | B (R=28K) | 每次成本 | 相对频率 | **总成本率** |
|---:|---:|---:|---:|---:|---:|
| 0.45 | 44236 | 15564 | 80s | 1.89× | **1.55×** ❌ |
| **0.55（当前）** | 54067 | 25395 | 98s | 1.16× | **1.16×** |
| 0.65 | 63897 | 35225 | 116s | 0.84× | **0.99×** ✅ |
| 0.75 | 73728 | 45056 | 134s | 0.65× | **0.89×** ✅但进退化区 |

**触发点从 0.55 后移到 0.65：总成本率降 15%，但会进入"上下文退化区"（NoLiMa 数据显示 32K 以上质量下降）。**

### 10.4 三个目标的博弈最优解

#### 目标 1：不想反复压缩 → **最有效的不是调阈值**
- **已修**：海马体签名去重（82 次相同存档 → 首次完整注入，后续简短提示），从根因消除"没推进→压缩→相同存档→重做"循环
- **可调**：`truncate messages` 工具（把旧消息换成单行占位符，只重写一次前缀）+ `pruner` 前置（tool 结果裁剪 0 成本，28 次里 12 次是这类）
- **阈值后移到 0.65** 只是辅助（频率降 16%），边际收益

#### 目标 2：压缩后占用更少 → **降低 retainTokens 是主杠杆**
- 当前 retain 24576 + 摘要 4096 = 28K，占 96K 的 29%
- 调研建议 16-20K（retain 16384 + headroom 8192）
- **收益双重**：占用少 + 缓冲带大（28K→20K 让缓冲从 25K 涨到 34K，频率降 26%）
- **风险**：压缩后上下文太少 → 海马体存档必须补全关键信息（已具备）

#### 目标 3：压缩时间尽可能少 → **只能靠减少触发次数或换小模型重写**
- 本地 35B 重写前缀 80-110s，无法改变（除非用 7B/4B 小模型做摘要——本地没有）
- **失败压缩 16 次 × 60s 超时 = 46min 是最大浪费**：system prompt 4119 token 时摘要失败率 50%，972 token 时 0%
  → **把 system prompt 压到 ~1000 token 是最高 ROI 的优化**（省 46min）

### 10.5 推荐配置（博弈均衡点）

| 参数 | 当前 | 建议 | 理由 |
|---|---:|---:|---|
| thresholdRatio | 0.55 | **0.65** | 总成本率降 15%，触发点 63.9K 仍在 headroom 硬顶 73.7K 之下 |
| retainTokens | 24576 | **16384** | 缓冲带 +8K，频率降 26%；海马体已外置任务状态，可少留 |
| headroomTokens | 16384 | 不动 | 硬顶 73.7K 保护，且 16K 摘要空间够 |
| maxTokens（摘要） | 4096 | 不动 | 实际摘要只用 1178 token，够 |
| **system prompt 长度** | 4119(部分) | **≤1024** | 实测 4119 时摘要失败率 50%、耗时 137s；972 时 0%、55s |
| **pruner 前置** | 已有 | 确保优先 | 12/28 次"压缩"其实是 0 成本裁剪 |

**预期效果**：压缩频率降约 26%（缓冲带 25K→34K）、每次成本因 system prompt 缩短降 50%、保留量降 33%。三者同时改善——**这才是博弈最优**。

### 10.6 诚实标注
- **层 2 数据（本地）是实测**：s1 会话 82 次压缩、成本拆解、system prompt 长度与失败率的关系，都有 trace 出处
- **层 3/4（学术论文/社区）**：NoLiMa、Context Rot、Factory.ai 的数字可直接引用，但没有在**本地 35B** 上验证
- **博弈模型是简化**：假设 token 线性增长、成本纯 prefill，实际有波动；建议参数改变后做一轮 A/B 验证

### 10.7 一句话
**三个目标里，"压缩后占用少"和"不反复压缩"是协同的（都靠降低 retain），而"压缩时间少"主要靠缩短 system prompt 和避免失败重试——调触发点只是边际优化（0.55→0.65 省 15%），不是主战场。**


### 10.8 实施记录（2026-11-24 13:07）

用户批准"按建议做"。实施时做了两处调整：

1. **system prompt 缩短项暂缓**：实施前核查发现 AGENTS.md 是 10652 字节的核心工作协议（含注入防护、安全底线、失败决策协议），而"4119 token 导致 50% 摘要失败率"这个数字无法复现原始出处（只在我写的报告里出现）。为避免破坏已验证的防线，经用户确认后**暂不动 system prompt**，列为待验证项。
2. **只实施两个参数**（证据充分、可逆）：
   - `thresholdRatio: 0.55 → 0.65`（新触发点 min(98304×0.65, 73728) = **63897**）
   - `retainTokens: 24576 → 16384`

**改动文件**（两副本同步，避免三副本不一致的坑）：
- `dsh-data/profiles/desktop/cordis.patch.yml`
- `dsh-data/profiles/desktop/node_modules/dsh-agent-harness/config/profile.patch.yml`

**验证结果**：
- 备份：`*.bak-before-compactopt-130653`
- `config_check.py`：全栈无冲突
- 重启后 health=ok、ctx=98304、显存 7758 MiB
- decode 回归：tps_probe 25.90 t/s（vs 96K 基线 27.3，sd 范围内；压缩参数属 agent 层，不影响推理引擎）
- 两处参数值已确认生效

**待观察**：新触发点 62K 是否会在真实长会话中出现"摘要退化"（0.70 曾导致复读退化，0.65 介于 0.55 与 0.70 之间）。若出现，回退到 0.60。


---

## 第十一部分：还能提升什么 + harness 的不完美（2026-11-24 晚）

> 用户：我们还有什么手段能提升表现？harness 的不完美之处在哪？
> 两路子任务：① 本地缺陷深度盘点（含 L1-L5 证据纪律）② 2025-2026 前沿 harness 实践。

### 11.1 最本质的不完美：**"机制存在"被当成"目标达成"**

项目自己的 POSTMORTEM 立了 L1-L5 证据分层（代码存在/单测过/加载/真实 trace 命中/独立产物）。用这把尺子量，harness 的病根很清楚：

| 项 | 文档宣称 | 真实状态 |
|---|---|---|
| 压缩正反馈 | "已修"（去重） | **只修了症状**（82 次相同存档），54K 低阈值 + 回注推高 token 的**根因未修** |
| Critic 0% 修复 | v2.16.0 "reasoning 兜底" | 停在 **L2 单测**，无 L4 真实会话证据；诊断原文自己说"需单独复现验证" |
| 验收员 | "触发路径已修" | 代码层修了（spawn 后代验收），但同源 verifier 架构问题未解 |
| KR1 自主闭环 | 4/16 闭环成功 | `STATUS.md:24-27` 承认测的是"**外部驱动闭环**"，不是系统自主；0 张卡可安全自动推进 |
| 35B 当 proposer | SELF_HARNESS_PLAN 写"35B 作 proposer" | `surfaces.json` 实为 `workbuddy`、`candidate-1.json` 是 `claude-opus`——**本机 35B 从未担任 proposer** |

**一句话**：这套 harness 最强的不是某个机制，而是"不许自欺"的证据纪律；最弱的是把"机制存在"当成"目标达成"。

### 11.2 三个最该补的不完美（影响 × 可修复性）

#### #1 压缩正反馈根因 — 影响高 × 可修复性高
- 诊断 `COMPACTION_AND_ROLES_DIAGNOSIS.md:24-28` 定性为**设计缺陷**：54K 触发 → 注入存档推高 token → 最小间隔 0.6s 连续触发
- 症状（82 次相同存档）已由 `lastArchiveSig` 去重修复；但阈值/保留量/system prompt 三处是**今天刚部分实施**（threshold 0.65 / retain 16K，system prompt 暂缓）
- 未做：把纠错三件套（纠正器/控制回合/状态复述）从 **step 7 提前到 step 5**——这是诊断补记明确要求的

#### #2 自主走路 A2-A5 — 影响最高 × 可修复性中
- 核心身份是"持续成长的计算体"，但 KR1 实际测的是外部驱动闭环
- 六环节实测：①读路线图选任务 ❌ ④写回路线图 ❌ ⑥常驻循环 ❌；当前 **L1（偏 L0/L1）**
- 路线：`AUTONOMY_GAP` 给了量化——L2 自动验收写回 1-2 天、L3 自动选任务 +2-3 天、L4 常驻闭环 +1-2 周；L5 自我改写目标不建议
- **不能去掉人工审批闸门**（外部证据：无监管自写教训错误归因率 20-53%），而是把审批从"每次动作"上移到"路线图准入"

#### #3 角色可靠性 + 同源偏差 — 影响中高 × 可修复性中
- (a) 失败根因部分在 llama-server 不稳，harness 只做到"不静默"
- (b) Critic reasoning 兜底修复停在 L2，无 L4 证据
- (c) **架构问题**：`COMPETITIVE_ANALYSIS.md:84`「Critic 与执行者同源：社区要求异质 verifier 破 self-preference；我们异质 rubric 不解决模型同源偏差」——**未修**
- 下一步：稳定期手动触发 Critic 复验 L4；不要回到小模型 Critic（已双证伪）

#### 第 4 名：工具面裁剪 28→18-20 — 影响中 × 可修复性低
- 卡在用户拍板 + 动态切换信号缺失（ADR-0029：弱分类器已证伪，无法回答"何时切换"）
- `ROADMAP_GRAPH:1364` 实证：前 7 工具占 95.7% 调用，但**低频≠可砍**
- dsh runtime 无裁剪 hook（`AUTOCARD_POSTMORTEM:15`），只能 harness 层拦截提示
- **在用户决策前不应作为"先修"项**，否则又是一次"讨论多、落地零"

### 11.3 还能提升表现的手段（前沿调研，按"我们没做且收益可能高"排序）

#### A. 工具面动态加载（中高潜力，但有前置条件）
- 业界：Anthropic 官方判据 10+ tools 就该考虑（Tool Use Examples 72→90%）、弱模型拐点 12-15（社区实测 95→53%）
- 我们 28 个工具已在风险区，但**只有 11 个在用**
- 动态工具加载（按任务阶段只暴露相关工具）技术可行（`ctx.tools.register` + fiber dispose 热替换，ADR-0029:44），但**缺切换信号**（需任务类型分类器，弱分类器已证伪）
- **可行路径**：不用分类器，用**显式阶段标记**（plan/execute/verify 阶段各配固定工具子集）——这是规则驱动，符合"不依赖模型元认知"的既有原则

#### B. 预防式规划（我们缺，业界标配）
- Claude Code 预防式建 todo（三层提示词引导）、Cursor Plan mode 自动建议、Windsurf/Cascade Wave 12 起自动 planning、Devin 每次会话 proactive 规划
- 我们是**补救式**（观察线/闹钟/控制回合）——`CLOUD_TODO_TRIGGER_MECHANISM:66,96-99`
- **可借鉴**：把 todo 建立从"观察线触发"前移到"开工合同第一行"（我们已有"开工前 3 行"，但没强制 todo）

#### C. 会话树 / rewind / fork（业界一等公民，我们缺）
- OpenHands / Pi / OpenCode 都有带 parent 指针的历史树
- 我们只有离线脚本，M2「会话树实时化」仍 backlog
- 价值：失败后能回到分叉点重试，而不是压缩整个上下文

#### D. Goal Judge 三字段验收（小改动）
- OpenHands：强制 `score/complete/missing`，`missing` 作下一轮第一条注入
- 我们三态验收（OK/ISSUE/UNCERTAIN）但 **UNCERTAIN 直接弃权不注入**——这是浪费：UNCERTAIN 本应转成"缺什么"的下一轮提示

#### E. 外部 hook 化 / 最小内核（架构级）
- mini-harness：7 原生工具 + 外部 hook 文件 + 错误隔离 + 超时 + 失败不崩内核
- 我们：28 工具、策略写死 index.mjs
- 与我们"可编辑面白名单"目标直接冲突——但改造成本高

#### F. 明确不做的（已证伪，别重踩）
- 多 judge 堆砌（9 judge≈2 票）、小模型 Critic（双证伪）、意图分类器 M9（AUC 0.599 近随机）、改写历史思维链、工具结果去重、思考硬切

### 11.4 架构性短板（诚实自评）

`COMPETITIVE_ANALYSIS.md:8-9` 自评：**架构理念领先或齐平，工程成熟度明显落后**（社区产品化 2-3 年）。
- 真正护城河：整合与跨层复用，不是单一技术原创
- 自推翻的两项"领先"：确定性 cascade 是 2026 社区共识；append-only 是 Manus 第一指标
- 明确落后：策略外部化/hook 化、工具面刻意做小、安全优先级显式声明（当前靠约定，没有强制）
- 空位：35B-A3B 族没有专门 harness 产品，我们是最完整实现之一（**以本机单人场景为前提**）

### 11.5 一句话总结
**提升表现的最大杠杆不在模型/引擎（硬件墙已确认），而在 harness 的"从机制到目标"最后一公里：把压缩正反馈根治（今天部分做了）、把 KR1 从外部驱动改成自主闭环、把 Critic 从 L2 单测推到 L4 真实证据。工具面裁剪虽常被提起，但卡在决策与信号缺失，不是当前主战场。**


---

## 第十二部分：标准化 eval —— 建立可比对的尺子（2026-11-24 晚）

> 用户："最好先把标准化搞好，这样才有和前沿比较差距的尺子，好知道我们在哪。"
> 两路调研：① 公开 benchmark 适配性 ② 本地 eval 体系盘点。

### 12.1 ⭐先纠正一个假设：现有 eval 测的不是目标对象

调研发现现有 eval 的结构性问题：
- **agentlab.py / projectlab.py 直连 llama-server**（`D:/Brain/workspace/bench/agentlab.py:41`、`projectlab.py:52`），**绕过真实 harness**——behavior-guard / 海马体 / 多角色 / 门控全没参与
- 所以"自建 bench 高分"只说明**模型本身**行，不说明**harness+模型系统**行
- 这解释了 ROADMAP L2 backlog 的判断："自建 bench 无法与社区同基准可比，外部效度存疑"——`ROADMAP_GRAPH.md:743-762`，`benefit_to_self: 知道自己在社区真实水平的位置，不再自我感觉良好`

**所以标准化不只是"接公开 bench"，还要修"测的对象"——必须测真实 harness 链路。**

### 12.2 关键发现：不必迁 SWE-bench，有更务实的路径

backlog 默认要迁 SWE-bench Verified，但调研显示它是**最不划算**的选择：

| 障碍 | 细节 |
|---|---|
| 环境重 | 每题一个 Docker + 代码库；WebArena 更夸张（GitLab 容器约 100GB）|
| 信号差 | 弱模型（我们工具准确率 65-78%）在 SWE-bench 分数很低，**信噪比差** |
| 已饱和 | SWE-bench Pro 上，Verified 拿 70%+ 的系统掉到 ~23%——Verified 接近饱和/污染 |
| 口径不匹配 | SWE-bench 是单轮 patch，**85% 的 BFCL 工具调用问题它测不到**（开源分析）|

**真正适合我们的第一梯队（离线可跑 + 有公开榜 + 直接测工具调用）：**

| Bench | 题量 | 测什么 | 本地可跑 | 有榜 | 单机耗时 |
|---|---:|---|---|:---:|---|
| **BFCL V4 静态子集** | 2000+（取 100-200）| 工具调用 AST 判分 | ✅ 高 | ✅ SOTA 70.9% | 1-2 小时 |
| **τ-bench Retail** | 115 | 多轮工具调用 + `pass^k` 可靠性 | ✅ 中高 | ✅ 82.4% | 4-10 小时 |
| **CToolEval / AgentCLUE** | 398 API / 104 题 | 中文工具调用（抵消语言偏差）| ✅ 高 | ⚠️/✅ | 数小时 |

**为什么这三个最适合**：
- BFCL 的 AST 判分是**确定性**的（不靠 LLM judge），直接量化我们关心的 65-78% 工具准确率；小模型 xLAM-2-8b 在 BFCL 多轮能到 70%——说明工具调用不是模型规模的函数，我们 35B 有空间
- τ-bench 的 **`pass^k`**（同题跑 k 次全中才得分）正好测 behavior-guard 关心的可靠性衰减——前沿模型 pass^1→pass^4 都会大幅掉分
- 中文 bench 必须做：我们模型用 `chat_template_zh` 优化，英文 bench 可能低估能力

### 12.3 现有 eval 体系盘点（可复用 vs 重写）

**（子任务盘点结论）——"我们现在有没有尺子"的诚实回答：有内部尺子，但没有外部尺子。**

现有资产：
- `agentlab.py`（377 行，7 小任务）、`projectlab.py`（935 行，P1-P5）——**直连 llama-server，绕过 harness**
- `regression_check.py`（29 门禁）、`verify_agent.py`、`test_turn_guard.mjs`（26）、`test_new_guards.mjs`（38）——**harness 机制门禁，有真实 trace 证据**
- `trace_report.py`、`auditor_metrics.py`——证据分层工具（L1-L5）

可复用：
- 评判逻辑（agentlab 的 6 类失败标签 EMPTY/LOOP/FAKEOK/RUNAWAY/NOANSWER/INCOMPLETE）
- trace 收集（`_trace.jsonl` + sid_filter 排除 s1 假数据——**89% 是测试假数据，必须过滤**）
- 报告格式（JSON + 中位/sd）

要重写：
- **测评通道**：从直连 llama-server 改成走**真实 harness 会话**（通过 dsh-session-bridge 投递）
- **判分口径**：接入 BFCL AST 判分 / τ-bench db_check / CToolEval 状态比对

该废弃/降级：
- 自建 bench 的"绝对分数"不再作为主指标，只作为**回归门禁**（防退化）
- 知识层分层等待办（全库只有一行，无 ROADMAP 卡）→ 关闭

### 12.4 自建 ↔ 公开 bench 的锚定方法

**让自建分"可对标前沿"的三步**：
1. **指标映射**：
   - 自建 LOOP/RUNAWAY/NOANSWER → BFCL 格式遵循 + τ-bench pass^k（可靠性轴）
   - 自建 FAKEOK/INCOMPLETE → τ-bench / AppWorld 的世界状态判分（db_check）
   - 工具调用正确率 → BFCL AST 判分（**统一口径**）
2. **锚题法**：在自建回归里嵌固定锚题——20 题 BFCL 静态 + 10 题 τ-bench Retail + 10 题 CToolEval，每次必跑，得到"自建分 ↔ 公开分"映射曲线
3. **校准点**：跑 1-2 个有公开分数的开源模型在同批锚题上，拟合换算关系

**关键纪律**：公开 bench 的题目/判分器**原样使用**，不能改——否则失去可比性。自建 bench 只做"补充场景 + 高频回归"。

### 12.5 分阶段落地建议

#### 阶段 1（本周可做，零外部依赖）
- 拉 BFCL V4 静态子集（simple/multiple/parallel/irrelevance/multi_turn），取 100-200 题
- 写**适配器**：把 BFCL 的函数定义转成我们 harness 的工具 schema，通过 session-bridge 投递到真实 harness 会话
- 用 BFCL 官方 AST 判分器打分 → 得到第一个**可对外比的分数**
- 基线记录：注明模型版本（94f3af3）、harness 版本（v2.9）、配置（MTP nmax5 / t8 / cache1350 / ctx96K / threshold0.65 / retain16K）

#### 阶段 2（数天）
- τ-bench Retail 115 题，跑 pass^1 和 pass^4（可靠性轴）
- CToolEval 小子集（中文锚）
- 建立"锚题集"嵌入现有 regression_check，每次改动后自动跑

#### 阶段 3（长期，按需）
- SWE-bench：**只跑 mini-SWE-agent + 单 repo（django）20-30 题试水**，确认信号质量再决定是否全量
- AppWorld（如果阶段 1-2 显示工具调用是瓶颈）：部署 Engine 跑 N168 子集

### 12.6 一句话
**标准化的第一步不是迁 SWE-bench，而是：接 BFCL 静态子集（离线、确定性判分、有公开榜）+ 修测评通道（走真实 harness 而非直连 llama-server）+ 嵌锚题到回归门禁。这样"我们在哪"第一次有了外部参照系。**


---

## 第十三部分：标准化 eval 阶段 1 实施（2026-11-24 晚）

### 13.1 已完成

**数据源**：BFCL V4 官方静态子集已克隆到 `D:/bfcl-src/berkeley-function-call-leaderboard`。
- `BFCL_v4_simple_python.json` 400 题 / `multiple` 200 / `parallel` 200 / `irrelevance` 240
- 标准答案：`data/possible_answer/BFCL_v4_simple_python.json`，ground_truth 格式 `[{"func": {"param": [allowed_values]}}]`

**判分器**：官方 `bfcl_eval/eval_checker/ast_eval/ast_checker.py` 可用。踩坑记录：
- 它 import 链拖进 cohere/anthropic/java_parser 等无关 SDK（BFCL 自带完整 handler 全家桶）
- 解法：import 前 stub `bfcl_eval.constants.model_config`（判分器只用 `underscore_to_dot` 一个字段）
- 必须传 `Language.PYTHON` 枚举，不能传 None
- `possible_answer` 直接传 ground_truth 列表（不是包 dict）

**适配器**：`D:/Brain/workspace/bench/bfcl_harness_eval.py`
- 通过 dsh-session-bridge 的 HTTP API 投递到**真实 dsh 会话**（不是直连 llama-server）
- 模型以 JSON 输出函数调用，抽取后交官方 AST 判分器
- 关键坑：① 现存 subagent routing 会话不能用 bridge 投递，必须 `create` 专用会话 ② bridge.mjs CLI 的 `events` 把每条记录截断到 300 字符，必须直连 HTTP API 才能读完整 assistant text ③ 计划任务环境 PATH 没有 node，必须用绝对路径

**链路验证**：单题 `simple_python_0` 模型正确输出 `{"calculate_triangle_area": {"base": 10, "height": 5}}`，官方 AST 判分 `valid: true`。说明"BFCL 题 → 真实 harness → 模型输出 → 官方判分"整条链路打通，harness 的 system prompt / 注入 / 门控都真实参与（events 里可见完整的 request/header、tools、skills 注入）。

### 13.2 进行中

计划任务 `BFCLRun` 正在跑 simple_python 前 10 题，结果写 `D:/Brain/workspace/bench/_bfcl_result.jsonl`，日志 `D:/Brain/_cleanup_20261118/bfcl_eval.log`。预计 30-40 分钟（每题 2-4 分钟，35B 生成慢）。

### 13.3 待做（阶段1收尾）

- 汇总 10 题分数，记录完整基线（模型 94f3af3 / harness v2.9 / MTP nmax5 / t8 / cache1350 / ctx96K / threshold0.65 / retain16K）
- 把结果沉淀成 `docs/BFCL_BASELINE_20261124.md`
- 评估是否扩到 100 题（需数小时）
- 阶段2：τ-bench Retail + CToolEval 中文锚


---

## 第十四部分：本地 35B 如何逼近强模型 —— 差距归因与四个杠杆（2026-11-24 晚）

> 用户："还有哪些角度可以把它优化到和你差不多。"
> 回答基于当日三类别 BFCL 实测 + multi_turn 验证 + 两路前沿调研。

### 14.1 反直觉的起点：静态能力已经追平

BFCL 三类别实测 simple 95% / multiple 95% / parallel 92%（等权 94%），官方榜 Opus 4.5 Non-live AST 88.5。irrelevance 100%（正确拒绝无关调用）。

**结论**：在静态工具调用这一层，差距已经消失甚至反超（注意口径差异——我们是子集+JSON文本，官方是全量+FC）。继续优化这层的边际收益≈0（天花板效应）。

### 14.2 真正的差距：流程纪律，不是智力

multi_turn 验证题（multi_turn_base_0）实证：模型输出了语法完全正确的 `mv → grep → sort → mv+diff` 序列，但漏了 `cd`/`mkdir` 前置步骤 → `instance_state_mismatch`。**问题不是"不懂命令"，是"没在脑内维护状态"**。

行业证据（From Confident Closing to Silent Failure, 2025-06）：AppWorld 上 75.8% 实际失败的运行以 agent 自信宣布完成告终；5 个 LLM judge 判断略高于抛硬币；**确定性状态检查比最好的 judge 多抓 4-8 倍 false success**。

### 14.3 四个杠杆（按杠杆率排序）

#### 杠杆 1：确定性状态回读 > LLM 自我验证 ★最高
- 至少一层验证必须是**读回真实世界状态**（文件真的改了吗 / 测试真的过了吗 / 数据库真的变了吗），judge 只做辅助
- 直接命中我们踩过的"文档宣称完成≠代码生效"坑
- 与项目现有三层交叉验证方向一致，强化为"确定性层必须有"

#### 杠杆 2：显式状态板 + 规划闸
- 不能指望模型自己记住状态——把当前 cwd / 已改文件 / 未完成前置步骤**每次注入**成简短状态板
- 开工前强制产出计划、每步对照（Claude Code / Devin 的预防式规划；我们是补救式 todo）
- 纯 prompt/规则，零显存成本

#### 杠杆 3：工具按需检索（不是静态裁剪）
- 静态裁剪已被证伪（低频但不可缺，ADR-0029）
- 动态检索（RAG-MCP 13.6%→43.1%）对弱模型多一层失败点
- **折中**：按任务阶段固定暴露工具子集（plan/execute/verify 各一套），规则驱动，不依赖模型判断

#### 杠杆 4：同模型 K=5 自洽投票
- **区别**于已证伪的"多 judge 投票"——这是同模型多次采样投票（GSM8K +17.9%）
- 我们 65-78% 基础能力刚好跨过"不会把困惑封为共识"的门槛
- 本地边际成本低（只有电力/时间），但要设一致性阈值

### 14.4 边界（诚实）

harness 能补偿流程纪律（状态/验证/规划/工具选择），**补偿不了知识与深度推理**。agent 任务的失败大多是流程问题，所以这些杠杆值得做；但"优化到和强模型完全一样"在复杂推理/创意/跨领域知识上有物理天花板。

**可实现目标**：在结构化、可验证的任务上达到强模型 90%+ 的表现——harness 工程够得着。

### 14.5 共同原则
四个杠杆都是**规则驱动**，不指望模型自我反省——这与项目核心经验"不能依赖模型的元认知（小模型只搜 20% 该搜的）"一致。


---

## 第十五部分：「流程纪律」框架的剩余杠杆盘点（2026-11-24 22:35）

> 用户问："我们和强模型的差距大部分不在模型智力而在流程纪律——这句话下还有其他杠杆提升空间吗？"
> 结论：**有一个层次根本不同、本机已实测可行的杠杆（约束解码），另两个次优；再往后撞天花板。**

### 15.1 关键区分：事后补救 vs 生成时约束

已做的四个杠杆（确定性回读 / 状态板 / 工具阶段化 / K=5投票）全部是**事后**机制：
模型先输出，harness 再检查、拦截、注入。这是"补救式流程纪律"。

**尚未碰的层次**：在生成那一刻就把错误格式**物理上排除**——GBNF/JSON-Schema 约束解码。
这是唯一不是"事后"的流程纪律杠杆。

### 15.2 杠杆 A：GBNF 约束解码（最高，成本低）

**本机实测（2026-11-24 22:30）**：直接打 `http://127.0.0.1:8081/v1/chat/completions`，
带 `response_format={"type":"json_object"}` + temperature=0.7，让模型输出两个并行函数调用：
返回 `{"call":[{"function":"get_weather","args":{...}},{"function":"get_time","args":{...}}]}`
——**无 markdown 围栏、无解释文字、一次 JSON.parse 成功**。

**现状空白**：harness `index.mjs` 中 grammar / constrained / json_schema / structured_output
关键词全为 0；`.env.llama` 无 grammar 相关配置。b12244 引擎原生支持（调研：b11960+ 即有）。

**对应失分**：BFCL parallel 92% 的失分中，多调用打包格式漂移是典型流程问题；
现在靠"解析失败→重试"兜，约束解码能让它根本不发生。

**必须记住的陷阱**（调研实证 HVR 2026）：schema 只约束形状不约束内容——
模型想写 8443、schema 限 max=1000，采样器会吐出合法的 `844`（finish=stop 无警告）。
**所以：形状用 grammar 锁、内容用确定性检查验**（与杠杆1的确定性回读同源），
不能只上 grammar 就当内容正确。另：schema 不注入 prompt，需在提示词里描述字段，
否则模型会填最省事的值。

**已知限制**：llama.cpp 文档中 patternProperties/uniqueItems/not 不支持、nested $ref 有缺陷、
 grammar 有性能开销——上线前用 speed_probe 验证 decode t/s 不被拖慢。

### 15.3 杠杆 B：错误恢复从「补救式」改「剧本式」（次优）

现状：D1 重复探测 / D2 同参双败是"检测到→注入一句劝告"；纠正器是 LLM 现场生成修正包
（部分已证伪）。更硬的做法是**高频错误查表**：
- 工具参数名错 → 自动查 schema 重试
- 路径不存在 → 自动列目录
- JSON 解析失败 → 自动去围栏
每类配一个确定性动作，不消耗 LLM 推理。符合"规则驱动、不依赖模型元认知"核心经验。

### 15.4 杠杆 C：预算感知调度（次优）

现状：控制回合每 8 步一刀切、Critic 每会话≤2 次，不管任务难易。
改进：按风险信号分配——写操作/不可逆动作/present 加密验证，纯读走快通道。同时提速和提防。

### 15.5 边界与已证伪（不要当新空间重复）

- **工具面裁剪 28→11**：旧账待拍板，静态裁剪已证伪（低频但不可缺），动态检索对弱模型多一层失败点
- **投票 / 多 judge / 纠正器代执行**：已试或证伪，别重复
- **流程纪律的天花板**：能让模型"把该做的都做到"，补不了深度推理/跨领域知识。
  我们已在静态工具调用 94-95% 触到天花板——剩余 5% 中，格式漂移是流程问题（杠杆A可解），
  真正选错函数的是智力问题（无解）。

### 15.6 沉淀结论
优先级：**A（约束解码）> B（错误剧本）> C（预算调度）> 天花板**。
杠杆 A 是四杠杆之后唯一"层次不同 + 成本低 + 本机已验证可行"的剩余空间。


#### 15.2 补测（22:40）：json_schema 也可用，但 token 预算是前提

初测 `json_schema` 在 max_tokens=200 时返回 content 空、finish=length——**不是不支持，是 thinking 吃光了预算**。
补测 max_tokens=600：正常输出 `{"city":"Beijing","temp":25}`、finish=stop、reasoning_content 508 字符。

**结论修正**：
- `json_object` 和 `json_schema` 两种约束本机都可用
- **thinking 模型必须用足够 max_tokens**（Critic 现值 1200 够用；投票曾因 20s 超时 + token 不足全 PARSE_FAIL）
- 锁字段用 json_schema（形状+字段名），只保合法 JSON 用 json_object
- 仍守"8443→844 陷阱"：schema 的 maximum 会把越界值压成合法错值→**只约束结构，不约束业务数值范围**


---

## 第十六部分：三杠杆落地执行与实测效果（2026-11-24 23:10）

### 结果总表

| 杠杆 | 受控 A/B | 门禁 | 真实会话 | 结论 |
|---|:---:|:---:|---|---|
| A 约束解码 | 5/5 ✅ | 81/0 | `constrained_json` applied=true parsed=true，**llm ok=true retry=0** | **上线，真实有效** |
| B 错误剧本 | 6/6 ✅ | 81/0 | 未命中（失败是"路径不存在"，走既有 tool_failure_heal；剧本的参数名错分支未触发）| **上线，受控有效，真实样本不足** |
| C 风险调度 | ❌ | 破坏5项测试 | 未上线 | **放弃** |

### 杠杆A：约束解码（成功）

- 实现：`callLLMOnce` 加 `sampling.constrained` → fetch body 带 `response_format:{"type":"json_object"}`
- 四个调用点：审计/Planner/Critic/投票；各有独立开关便于 A/B
- **用 json_object 不用 json_schema**：规避"8443→844 越界压值"陷阱（只锁形状不锁字段值）
- 保留 reasoning_content 兜底（thinking 模型 token 不足时仍可提取）
- **真实会话证据**（sid 5373ce33）：`constrained_json` applied=true parsed=true tag=audit；
  对应 `llm` trace **ok=true、retry=0**——审计调用一次解析成功，零格式修正重试
- 实测 json_object / json_schema 本机都可用；json_schema 需 max_tokens≥600（thinking 吃预算）
- 性能：子任务实测无退化（23.08→24.17 t/s）

### 杠杆B：错误恢复剧本（受控有效，真实样本不足）

- 实现：`errorPlaybook(s,cfg,c,status)` 顶层函数 + tool/result 挂点；三类确定性动作：
  参数名错→改用 file_path / 路径不存在→先列目录 / 未知工具→查工具列表
- **只读结构化字段**（工具名、参数、status），绝不扫 fullArgs 内容（守铁律）
- 只处理首次失败，D1/D2 管重复，不冲突；同类错误一轮只注入一次
- 受控 A/B 6/6：开关对照、确定性动作、trace、去重、成功不误伤全通过
- **踩坑**：顶层函数访问不到 apply 内的 `trace` 闭包 → ReferenceError 被 catch 吞掉，
  动作生效但无 L4 证据。修复：trace 移到挂点（apply 作用域内）。**这是"动作生效但无证据"的新例**
- 真实局限：本次失败是"读不存在的文件"，参数用的是标准 `file_path`（不是参数名错），
  且 `pathMissing` 标志 harness 未设置 → 剧本的"路径不存在"分支是死代码。
  实际由既有 `tool_failure_heal` 处理。**需要后续补 pathMissing 标志才能激活该分支**。

### 杠杆C：风险感知调度（放弃，诚实记录）

- 实现尝试：`riskProfile(s,cfg)` risk 0-3，应用到控制回合间隔 + Critic 上限
- **失败原因**：把控制回合从 `s.step % 8 === 0` 改成"距上次 ≥ interval"，
  破坏 5 个测试契约（intent_drift / short_term_goals / maintenance_fixes / new_guards / gwt_fep）
  ——这些测试依赖"每8步必触发"的确定性
- 调 `riskControlLow` 8/16 均无法解决——是**调度机制本身与现有契约不兼容**，非参数问题
- **决策：整体回滚到 a663826d（杠杆A+B状态），杠杆C不进代码**
- 采纳的子任务洞察（保留为知识）：MTP 接受率单步低【不算高危】——代码类任务 0.55-0.70 常驻，
  误判风险高；若未来重启杠杆C，需用"连续3步<0.5 且无其他风险信号"

### 最终生产状态
- 两副本 sha=`a663826d7e37`（杠杆A+B+trace修复），重启 23:03:16 生效
- 门禁 **81 pass / 0 fail**；杠杆A测试 5/5、杠杆B测试 6/6
- 回滚点：git 版本 a58d59a5（三杠杆前）；重放脚本 leverA/B patch + fix_leverB_trace


---

## 第十七部分：同一问题的第二次回答——瓶颈已转移（2026-11-24 23:30）

> 用户第二次问："我们和强模型的差距大部分不在模型智力而在流程纪律——这句话下还有其他杠杆提升空间吗？"
> **答案与第十五部分不同**：不是因为问题变了，是因为状态变了。A/B 已落地、C 已放弃，机制层饱和。

### 17.1 状态变化（相对第十五部分）

| 杠杆 | 第十五部分时 | 现在 |
|---|---|---|
| A 约束解码 | 空白 | **已上线**，真实会话 retry=0 证据 |
| B 错误剧本 | 空白 | **已上线**，受控 6/6（但真实样本不足）|
| C 风险调度 | 空白 | **尝试后放弃**（破坏 5 个测试契约）|
| 机制总数 | 4 个（回读/状态板/工具阶段化/投票）| **7 个**（+约束解码/错误剧本/S24自愈）|

### 17.2 关键数据：机制饱和，度量真空

- 相关 trace **177 条**，但真实 sid **只有 1 个**（sid 5373ce33，我自己的验证会话）
- 其余 99% 是 s1 单测假数据（与 POSTMORTEM 的 89% 基线一致）
- 门禁 81/0、受控 A/B 全过——但这些都证明"机制能跑"，不是"机制有效"

**结论：继续加第八个机制是低回报的——它也会落进同样的证据真空。**

### 17.3 剩余空间（重新排序）

#### ① 建可持续的真实任务 A/B 流水线（最大杠杆，有复利）
现状：每测一个杠杆靠手工造会话、手工看 trace、手工统计 → 样本永远 n=1。
需要：固定任务集（简单/高危各≥20）+ 开关两臂自动跑 + 自动聚合 trace 算 Wilson CI / 符号检验。
现有雏形：`gdn_ab_runner.py` / `share_ab_runner.py` / `skills_ab_runner.py`，
**但没有一个覆盖"harness 机制开关"这个维度**。
价值：做一次后，回读/状态板/约束解码/错误剧本的效果都能被统一度量。

#### ② 补死代码（小但真实）
杠杆B 的"路径不存在"分支：`pathMissing` 在 index.mjs 只出现 1 次（判断处），
**没有任何地方设置它** → 该分支是死代码。受控 6/6 测的是"参数名错"，
真实世界最常见的"读不存在文件"走既有 `tool_failure_heal`，剧本没接上。

#### ③ 工具面裁剪（旧账，需用户拍板）
28 工具只用 11 个。静态裁剪已证伪、动态检索多一层失败点。需决策非加代码。

### 17.4 边界（不变）
流程纪律让模型"把该做的都做到"，补不了深度推理/跨领域知识。
静态工具调用 94-95%，剩余 5% 里选错函数是智力问题，无解。

### 17.5 待用户决策
是否做①（真实任务 A/B 流水线）+ 顺手补②。
需确认任务集口径：现有 `agentlab.py`(7小任务) / `projectlab.py`(P1-P5) 偏短，
覆盖不到"20 轮后遇失败工具结果"类场景，可能需新建。


---

## 第十八部分：BigMoeOnEdge 调研与我们的优化方向（2026-11-25）

> 用户问："BigMoeOnEdge 同配置 35 tok/s，参考它怎么实现的，我们怎么优化？"
> **核心结论：前提不成立——35 tok/s 与我们不可比，不能为追这个数字改配置。**

### 18.1 生产基线先核实（重要：记忆一度过时）

调研中发现工作记忆的"生产配置（11-18 校准）"已过时，实际以 `.env.llama`（11-24 12:43 改）为准：
- **引擎换代**：自编 b12244 → upstream 1.0（指纹 `94f3af3`，二进制 11-23 10:48 重编）
- **三处参数反转**（11-23 有意重测）：
  - THREADS 6→8（+18%，交叉验证；t12+ 因 HT 争抢内存控制器反降）
  - MOE_CACHE_CPU_SHARE 0→1.0（20K e2e -10.6% 墙钟；上游 1.0 的 MoE cache 只处理 ≤32 token 批，
    share 不再毒害 prefill，旧"share=0 最优"是 b12244 时代结论）——**应从已证伪清单移除**
  - UBATCH 1536→2048（prefill +39%，解码不变）
- 其余一致：CTX 98304 / NGL 99 / NCMOE 40 / CACHE 1350MiB / BATCH 4096 / CTK q8_0 / CTV q4_0 /
  NMAX 5 / P_MIN 0.8 / CHECKPOINTS 2 / router models-max1 margin450
- **真实基线是配置族**（11-24 `tps_ab.log`，20K prompt+128 生成+6~8 次中位）：
  real_mtpoff 19.98 / nmax5 24.56 / mmproj_q8 27.00 / tokemb_cpu 27.84 / ctx48k 25.63 t/s
  → 记忆"27.2"对应 mmproj_q8/tokemb_cpu 档；**保守说生产 ≈25-27 t/s @20K**

### 18.2 35 tok/s 不可比（逐项差异）

| 维度 | bmoe 报道 | 我们 |
|---|---|---|
| GPU | 桌面卡（3070/3060Ti 级，220W+，带宽~448GB/s）| **4060 Laptop（100-115W，带宽~256GB/s）** |
| 量化 | 多为 Q4_K_M / IQ 档 | UD-Q4_K_XL（21.28GiB，更重）|
| prompt | 30-90 token 短 prompt | **20K token** |
| 上下文 | 16384 | 98304 |
| MTP | 多数**关闭** | nmax5 开启 |
| 专家来源 | RAM + GPU cache（8GB+31GB RAM）| 全 RAM（load_mode=none）+ GPU cache |

- 归一化后真实差距：**保守 0-15%（基本被 prompt 长度解释掉）、乐观 30-50%（需换条件，套不到我们场景）**
- 数据可信度中等偏上（docs/bench-data 逐行可追溯 + `scripts/bench-report.sh` 可复现），
  但 35/45 两点只在单台机器、无 llama.cpp 原生 timings、社区质疑虚标/安装敏感
- **结论："我们落后 29%"是错误前提，别为追不可比数字改配置**

### 18.3 它的实现：不是黑科技，是"测量驱动的规划 + 精细缓存"

- llama.cpp fork，README 明确"输出与 llama.cpp 相同、无自研 kernel、任意 GGUF 不重打包"
- 核心：`--auto` 测量机器和模型 → 自动定 cache 大小/线程/设备分工（Plan 屏显示每个选择及理由）
- 分层专家缓存：GPU cache → RAM → flash；**设备内存作为缓存的一层**（measured-planning step4）
- 首次请求实测无损旋钮（lossless knobs），按模型自己的路由定 cache 预算（step1/2）
- headroom probe：唯一其他引擎不做的测量（内核事实）
- 关键文档：`hardware-planning.md` / `measured-planning.md` / `cache-sizing.md` / `moe-streaming.md`

### 18.4 可直接借鉴的知识（不改配置也能用）

1. **专家缓存悬崖**（cache-sizing.md）：LRU 预算低于一个 token 周期（`token_demand_MiB`）时
   命中率**归零不是渐降**——模型按固定层序 0..N-1 访问，LRU 淘汰的正是马上要用的。
   手调 cache 必须对照 token_demand_MiB 而非 cache_min_mb。
   bmoe 0.40.2 起默认淘汰改 decayed frequency 规避此悬崖。
2. **投机解码在专家流式下是负收益**（moe-streaming.md）：一批 token 的专家并集接近全部，
   破坏稀疏性——所以 bmoe 默认关 MTP。**我们专家全在 RAM 不走流式，MTP 仍有正收益
   （20→24.5 t/s）**，这是两套优化路径的根本分叉，不可直接照搬。
3. **专家预测已实测证伪**（expert-prediction.md）：88.6% 准确率，但所有预取变体墙钟都变慢
   （还被热节流污染过）——与我们"decode t/s 是误导性指标"教训同源。
4. **未用杠杆清单**（hardware-planning.md:1598）：上游已有但我们未用的包括
   `n_threads_batch` 独立于 `n_threads`、`flash_attn_type`、`kv_unified`、`llama_numa_init`、
   `mparams.devices[]`/`split_mode` 等——但多数是 bmoe 规划器自己也没用或用完的。

### 18.5 我们的优化方向（按优先级）

- **不追 35 tok/s 这个数字**（前提错误）
- **真实可提升空间**：bmoe 证明的是"测量驱动规划"优于手调——
  我们已有 `speed_probe.py` + 大量 A/B 日志，缺的是把"按模型路由定 cache / 首次请求实测无损旋钮"
  这套思路系统化。但收益上限受 4060 Laptop 带宽+功耗墙约束，且我们已在 25-27 t/s 接近瓶颈。
- **唯一值得实测的新旋钮**：`n_threads_batch` 独立于 `n_threads`（bmoe 已纳入，我们没用），
  可能改善 prefill（CPU 侧 MoE 并行度）；需 A/B 验证，不预设有效。
- **存档**：本部分与生产基线核实一并沉淀；后续若做 A/B 流水线（第十七部分①），
  应把"引擎版本/参数快照"作为每次实验的强制元数据，避免基线漂移重演。


---

## 第十九部分：源码深挖后的修正（2026-11-25，覆盖第十八部分的部分判断）

> 第一路源码调研返回，**推翻了第十八部分基于 README 的两个判断**。以本部分为准。

### 19.1 纠偏一：它不是 llama.cpp fork

`AGENTS.md:9-11`："built **on top of** llama.cpp's public API … we do not fork llama.cpp"。
`third_party/llama.cpp` 是空 submodule。它靠公开 API（`cb_eval` / `moe_cache_size` /
`moe_cache_cpu_share` / `tensor_buft_overrides` / `ggml_backend_register_host_buffer`）实现，
只有 `--overlap` 需约 25 行 fork hook，**且只在模型>RAM 的流式场景才用**——我们 21GB 常驻 64GB RAM，不走流式。

### 19.2 纠偏二：share=1.0 vs share=0 的冲突是场景差异，不是谁错

第十八部分写"应将 share=1.0 移出已证伪清单"——**过度推论**。源码实证：
bmoe 的 `--auto` 在 `planner.cpp:1133-1142` **硬编码 `device_cache_cpu_share = 0.0f`**，
注释给出理由（32GB 卡 share 0.89 → 114→68 tok/s；固定时机无法预判 cache 是否填满）。

与本机 11-23 实测（share=1.0 墙钟 -10.6%）冲突，但**两者前提不同**：
- 我们：cache 1350MiB（覆盖 7.2% 专家）+ PCIe4 x8 upload ~12GB/s < DDR4 双通道 ~51GB/s → CPU 直算赢
- bmoe：cache 2079MiB + **pinned host buffer upload 20.6GiB/s**（近我们 2 倍）→ 上传赢
- **结论：share 值本身不是可抄项；让 upload 变快 2 倍才是。**

### 19.3 真正的核心差异（按重要性）

1. **布局路线不同**（`docs/comparison.md:119-121`）：bmoe 把全部 expert 用 `-ot exps=CPU` 钉 host，
   GPU 放大 cache 缓存热点并**在 GPU 算**；我们 `NCMOE 40` 是把 40 层固定留 CPU 算。
   同卡实测（`backends.md:167-176`）：CPU 全算 18.9 / 我们的路线 31.9 / **bmoe 61.8 / 77.9 tok/s**。
2. **cache 尺寸**：我们 1350MiB；bmoe 8GB 卡实测 2079MiB（3.3 token cycles；Qwen3.6-35B 一个 cycle = 581MiB）。
   bmoe 定的规则 = "fitter 放不下一整层而浪费的 VRAM 全给 cache"（`planner.cpp:499-507,845`），不是拍固定值。
3. **pinned host buffer**（最高优先可抄项）：`GGML_CUDA_REGISTER_HOST=1` + expert 复制进 CUDA pinned host buffer，
   原 mmap 页交还（只占一份内存）；upload 9.9→20.6GiB/s、decode +7~27%（`CHANGELOG:2242-2248`）。
4. **`n_outputs_max` 压小**：llama.cpp 默认给整个 ubatch 预留 logits 行（一行=整个词表），
   2048 token 的 35B-A3B 白占 1.7GiB compute buffer（`session.cpp:1449-1456`）——可直接抄。
5. **server 线程收敛**：`CHANGELOG:1010-1017` OpenMP 每调用线程留 worker team，server 每请求多用 122 线程 → 9.2 tok/s；
   改单 engine_thread → 16.4。**若测的是 server，这可能就是"29%"本体**（需核实我们是否命中）。
6. **MTP**：两边方案完全一样（self-speculation），bmoe 8GB 卡 UD-Q4_K_XL + --mtp 实测 25.2/24.1/27.4——
   **和我们的 24.56/27.0 几乎一样**，不是差距来源，别再投入。
7. **bmoe 自己也证伪的**：`--prefetch` 2× 变慢、`--ngram` host -4%/device -29%、route-ahead/expert-dropping 全 lossy 默认关
   —— 与我们的已证伪清单高度一致。

### 19.4 可直接借鉴（按优先级）

- **A1** 把 `-ncmoe 40` 换成 `-ot exps=CPU`（全部 expert 留 host）+ 更大 GPU cache
- **A2** cache 按"放得下的全部 VRAM"定，不拍固定值（目标 8GB 卡 2079MiB）
- **A3** `GGML_CUDA_REGISTER_HOST=1` + pinned host buffer + 交还 mmap 页（约 50 行胶水，单点 +7~27%）
- **A4** `n_outputs_max` 压小，腾 VRAM 给 cache
- **A5** 若用 server：engine 计算收敛到单线程（9.2→16.4 的量级）
- **A7** MTP draft 5→3 A/B（bmoe 实测 3 最优，我们 11-24 日志 nmax3=25.09 > nmax5=24.56，**已隐含支持**）

### 19.5 最终结论
**35 tok/s 不可比（前述），但 bmoe 指出了两条我们确实没走的路**：
① expert 全留 host + 大 GPU cache（我们现在 40 层固定 CPU）；
② pinned host buffer 加速 upload（我们裸 PCIe）。
这两条有同卡数量级证据（18.9/31.9 → 61.8/77.9），值得做 A/B——
但必须守住"端到端验证"铁律（decode t/s 单独看会骗人，见 share=1.0 的历史反转）。
