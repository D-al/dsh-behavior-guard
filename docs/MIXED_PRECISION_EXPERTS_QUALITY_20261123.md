# 混合精度专家：质量代价充分调研（2026-11-23）

> 问题：把 CPU 侧 40 层专家降比特（Q4_K → Q3_K/Q2_K），质量与当前模型比差多少？
> **结论：Q3_K 是安全区间（PPL +2~2.4%，官方动态量化自己就在用），Q2_K 不可取（PPL +7% 拐点，同结构实测编码能力 −26）。但更重要的是：PPL 在 agent 任务上会失明，验收必须用工具调用准确率。**

## 一、当前模型在量化谱系里的位置（第三方实测，APEX 团队）
| 量化档 | BPW | PPL | ΔPPL | HellaSwag |
|---|---:|---:|---:|---:|
| UD-Q4_K_XL（**我们现在的**） | 4.75 | **6.735** | +0.22% | 82.3% |
| APEX I-Compact（Q4 边缘/Q3 中间） | 4.5 | 6.857 | +2.0% | 79.7% |
| UD-Q3_K_M（全 3-bit） | 3.85 | 6.883 | +2.4% | 78.7% |
| APEX I-Mini（中间层 IQ2_S） | 3.5 | 7.238 | **+7.7%** ← 质量拐点 | 74.2% |

**关键洞察**：我们已经在"量化甜点"上（+0.22%）。放弃 4.75→4.5 只差 0.25 bpw，却要付 +2% PPL。**降到 3.85 bpw 是 +2.4% PPL——这是官方 Unsloth 自己都在发布的档位（UD-Q3_K_M），说明是可接受的工程选择。**

## 二、致命警示：同结构"只降专家"的实测反例
社区 `kyumly/Qwen3.6-35B-A3B-MoE-expert-IQ2` 与我们要做的**结构完全相同**（只降专家，attention/shared/embed/output 保 BF16）：
- 2.25-bit 专家 → **LiveCodeBench −26 分、GPQA −13.6 分**
- 结论：**Q2 级专家在编码/推理任务上会断崖**

对比 Gordon-35B-A3B-mixed-q2k-imat（宣称 PPL 仅 +0.59%，decode 51→78）：
- 该 repo **几乎无独立验证**（2 likes / 31 downloads），README 里正则自相矛盾
- 其 PPL +0.59% 与 kyumly 的编码 −26 分**并不矛盾**——PPL 对结构化任务失明

## 三、为什么不能只看 PPL
- arxiv 实测：tool calling 中"**是否该调用工具**"比"调哪个工具"更脆弱（量化最先崩的是决策边界，不是格式）
- Qwen3-27B pilot：Q4 无损，**Q3 开始掉 parallel_multiple 4pp**，Q2 掉更狠
- 合同抽取任务：**连 2-bit 都几乎无损** → 说明**任务类型决定安全线**

## 四、推荐配方（如果要做）
只降 CPU 侧 40 层的 `ffn_{up,gate,down}_exps` 到 **Q3_K**（不是 Q2），其余保持：
```bash
# 示例（需按实际张量名调整 regex）
llama-quantize --imatrix imatrix.gguf \
  --tensor-type "blk\.(0|1|2|...|39)\.ffn_(up|gate|down)_exps=Q3_K" \
  --output Qwen3.6-35B-A3B-mixed-q3k.gguf \
  原模型.gguf Q4_K_M
```
- 收益：40 层专家 18.3 GiB → 约 13.7 GiB（−25%），DDR 读和 PCIe 传输同步下降，**预计 decode +23~29%**
- 端到端：预计 **−5~8%**（因为 prefill 占比大，稀释收益）
- 必须用 imatrix；必须保留 attention / shared_expert / output 在 Q4+/Q6

## 五、两个比量化更值得先做的事（调研附带发现）
1. **MTP 可能让 function-calling 掉 40%**（protolabs 在自己的部署里测到 agentic function-calling 准确率下降约 40%，疑似模型在 MTP 生成的 token 上训练不足）
   - 我们有 `MTP on` 的 A/B 数据（decode +8%），但**没有做过工具调用准确率的 A/B**
   - **建议先做这个**：同一组工具调用任务，MTP on vs off 比准确率。如果真掉 40%，那 MTP 的 +8% decode 完全不值得
2. **KV cache q4_0 可能已经在偷质量**
   - DuoNeural 报告：KV q4 会破坏 Gated DeltaNet 的 SSM 状态（DeltaNet state 存在 KV cache 里，低位量化会累积漂移）
   - 我们正是 `--cache-type-v q4_0` + 31 层 DeltaNet！
   - **建议试 `q8_0`**：KV 从 22.5 MiB 增到 45 MiB（8192 cells），显存代价小，可能提升长上下文质量

## 六、结论（对 agent 场景）
| 方案 | 质量风险 | 建议 |
|---|---|---|
| 保持 Q4_K_XL（现状） | 无 | ✅ 当前最优 |
| 只降专家到 **Q3_K** | PPL +2.4%，工具调用可能 −2~4pp | ⚠️ 可试，但必须用 agent 任务验收 |
| 只降专家到 Q2_K | PPL +7.7%，编码 −26 分 | ❌ 不要 |
| KV q4_0 → q8_0 | 风险降低 | ✅ **建议先试这个**（几乎零质量风险，显存代价小） |

**验收铁律**：不能用 PPL 或 decode t/s 验收量化。必须用我们真实的 agent 任务（工具调用准确率、多轮任务完成率）。
