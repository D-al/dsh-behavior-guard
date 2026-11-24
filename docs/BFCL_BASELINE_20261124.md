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
