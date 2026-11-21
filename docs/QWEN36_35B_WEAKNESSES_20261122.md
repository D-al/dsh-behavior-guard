# Qwen3.6-35B-A3B 弱点调研（2026-11-22）

> 起因：用户问"工具调用能力弱能否通过分类器改善"。结论：**不能**（层面错误——
> 分类器检测文本属性，不增强模型能力）。本文记录调研证据与对此前错误结论的修正。

## 一、重要修正：单次工具调用不弱，弱在长链路

此前引用 Noometry "Agentic & Tool Use 23.8/100（排名 139/165）"断言"工具调用弱"——
**这个结论过于简化**。Noometry 是聚合分（含 terminal-bench、长链路 agent），
BFCL 测的是单次函数调用，两者不矛盾。

| 来源 | 数字 | 说明 |
|---|---|---|
| OpenCSG Maniac 2-bit 仓库 | UD-Q4_K_XL（用户同款）BFCL 复合 0.6696 = BF16 的 **98.8%** | llama.cpp --jinja + bfcl-eval，量化几乎无损 |
| Tileward 原版 | BFCL 500 tasks **76.3%** | TWFP4 压缩后 75.9%，无显著差异 |
| 官方模型卡 | "Qwen3.6 excels in tool calling capabilities" | 无 Limitations 章节 |
| UD-Q4_K_XL 分项 | `multi_turn_miss_param` **0.340**（BF16 0.360）| 真正的短板：多轮缺参修复 |

**结论**：Q4_K_XL 量化对单次调用几乎无损；公开 BFCL 不支持"工具调用天生弱"。
弱点集中在**多轮长链路**（本该拒答却硬调、本该追问却瞎猜、推理循环）。

## 二、分类器能否改善工具调用：不能

分类器输出 SAFE/INJECTION，既不识别工具调用正确性，也不能改写模型输出。
改善工具调用的是 **harness 脚手架**（已在线）：
D1 重复探测 / D2 同参双败 / verify-on-edit / formatCorrection / 只读代执行 / Critic。

印证项目核心经验：**harness 杠杆 > 模型选择**——榜单测裸模型，实际用的是带脚手架系统。

## 三、其他弱点（确证数字）

1. **通用 agent / 持续行动力**：VITA-Bench 35.6（Qwen3.5-27B 41.8 / Gemma4-31B 43.0）、
   DeepPlanning 25.9、Tool Decathlon 26.9（27B 31.5）、τ³-Bench 67.2。
   SWE-bench Verified 73.4 < 27B 稠密 75.0。
2. **幻觉**：AA-Omniscience 正确率 **18.82%**、幻觉率 **50.5%**（猫目/AA）。
3. **长上下文**：AA-LCR 60.8-71.67%，榜首 Kimi K3 88.7%。262K 是窗口规格非有效推理质量。
4. **推理 / 新知识**：HLE 20-22.24%、SciCode 36.57%、Terminal-Bench Hard 35%、
   CritPt 0.29%（很新基准谨慎解读）。数学反而强：AIME26 92.7、GPQA 84-86。
5. **领域差异极端**：τ²-Bench Telecom 95.32% vs τ³-Banking **9.28%**。
6. **中文**：C-Eval 90.0（27B 90.5）——未找到中文特有弱点数据。
7. **4-bit 量化风险区**：NVFP4 在 Miss Func (-7.0) / Parallel Multiple (-12.5) 掉分，
   但格式解码失败次数几乎不变（4733 vs 4739）——掉的是答案质量不是格式。
   我们 UD-Q4_K_XL 属同类风险区：若观察到"该拒答时硬调工具"，是量化已知代价。

## 四、社区实测（传闻/个案，非基准）

- Unsloth GGUF 讨论 #5：BF16/Q6/Q8 均出现 "tool calls fail sometimes"；
  有用户加 **`--swa-full`** 后解决（怀疑 DeltaNet/滑窗缓存重计算，日志 "Forcing full prompt re-processing"）。
- r/LocalLLaMA：重复失败的工具调用、不回读上下文、多轮跳过工具调用；27B 稠密更稳。
  b8954-b8967 web-search 路径损坏（主线已修）；MoE routing drift 影响重系统提示下的遵循。
- OpenClaw DC：多数"工具调用失效"其实是 GGUF chat template 错配；
  换修复模板 + `--jinja` 后"基本没问题"；另需 `--ctx-size ≥ 65536` 防 schema 截断、temp≈0.6。
- ToolCall-15：正确配置 100%，开 MTP 掉到 97%（社区实测，非官方）——我们生产开 draft-mtp/NMAX5，
  若有工具调用失败线索可 A/B 关 MTP，但会牺牲 decode 速度。

## 五、对我们配置的排查优先级

**chat template + `--jinja` → `--swa-full` → `--ctx-size ≥ 64K` → `presence_penalty`**

`presence_penalty` 是官方唯一暗示的软肋对策（抑制 endless repetitions），但调高会语言混杂。
优先排查配置，不急着换量化——量化已被证明对单次工具调用几乎无损。

## 六、待核实的结构差异

调研报告称官方模型卡为 **40 层、256 专家每 token 8 路由 + 1 共享（共 9）**、
30 线性 + 10 全注意力层、262K 原生（YaRN 至 1.01M）；
我们记忆里是"41 层 / top8 / 31 层 DeltaNet + 10 层吃 KV"。
可能是计数口径差异（是否含 embedding/output 层）——待读本机 GGUF header 核实，暂不改记忆。

## 来源
- 官方：[Qwen 模型卡](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)、[Qwen 博客](https://qwen.ai/blog?id=qwen3.6-35b-a3b)
- 基准：[OpenCSG UD-Q4_K_XL BFCL 实测](https://opencsg.com/models/ManiacLabs/Qwen3.6-35B-A3B-2bit)、
  [Tileward](http://tileward.com/research/a-smaller-qwen3-6-35b-a3b)、
  [AA/SpringPrompt](https://springprompt.com/benchmarks/artificial-analysis?focus=alibaba-qwen3-6-35b-a3b&metric=lcr)、
  [Noometry](https://noometry.com/models/qwen3-6-35b-a3b)、[猫目/AA](https://www.maomu.com/models/alibaba--qwen3635ba3b)
- 社区：[Unsloth 讨论](https://www.aifasthub.com/unsloth/Qwen3.6-35B-A3B-GGUF/discussions/5)、
  [vLLM 工具调用实测](https://allanchan339.github.io/bug-fixes/2026/04/20/Qwen36-35B-A3B-tool-calling.html)、
  [OpenClaw DC](https://openclawdc.com/blog/local-model-says-it-did-it-but-didnt)
