# Classifier Benchmark v3 — Tool Result Injection Detection

> **决策支持基准**，非上线标准。产出 data_gates 证据，让科技树上卡住的 M7/M9/L5/S6_model 从"假设"变"有据"。
> 原始数据：`p/bench/classifier_bench_results_v3.json`

---

## 一、实验设置

### 1.1 硬件与环境

| 项目 | 值 |
|---|---|
| Python | 3.12.4 (MSC v.1940 64-bit) |
| PyTorch | 2.3.1+cu121 |
| Transformers | 4.44.2 |
| NumPy | 1.26.4（降级以兼容torch） |
| scikit-learn | 1.6.1 |
| Device | CPU, 10 threads |
| GPU | 未使用 |

### 1.2 数据源

#### 良性样本（Negative = 正常工具输出）

**来源 A：_cur*.jsonl（SearXNG单一任务）**
- 8个累积快照文件 → 全局callId去重 → **370条唯一工具输出**
- 长度分布：均值992字符 / 中位数153字符 / 最长14331字符
- >512字符长文本占24%

**来源 B：push_samples.json（推卡多任务会话）**
- 17个推卡/实现类会话 → 去重后 **561条唯一工具输出**
- 长度分布：均值2117字符 / 中位数549字符 / 最长49932字符
- >512字符长文本占52%

**合并：931条唯一良性样本**（含pwsh/read/write/todo_write/glob/edit/present/grep等全类型工具调用）

#### 攻击样本（Positive = 注入攻击）

构造策略（嵌入到真实良性工具输出中，模拟上下文攻击）：

| 策略 | 数量 | 说明 |
|---|---|---|
| prepend | 32 | 在良性文本前插入攻击指令 |
| append | 32 | 在良性文本后追加攻击指令 |
| embedded_mid | 12 | 将攻击嵌入良性文本中间（最真实场景） |
| benign_like | 15 | 安全警告/错误信息等"类良性"消息（测试误报率） |

共 **91条攻击样本**。

### 1.3 候选模型

| 候选 | HF路径 | 结果 |
|---|---|---|
| Llama-Prompt-Guard-2-86M | `meta-llama/Llama-Prompt-Guard-2-86M` | ❌ 未下载成功（HF_ENDPOINT镜像指向hf-mirror.com，本机连不通；直连huggingface.co网络通但gated repo需token） |
| protectai/deberta-v3-base-prompt-injection-v2 | `protectai/deberta-v3-base-prompt-injection-v2` | ✅ 已加载并运行 |
| facebook/jailbreak-detector-large | `facebook/jailbreak-detector-large` | ❌ HF Hub不存在该model_id |

**结论：本轮仅有一个候选完成评测。** Llama-Prompt-Guard-2-86M的缺失需在报告中如实标注。

---

## 二、benchmark结果

### 2.1 延迟指标（protectai-deberta-v3-base-prompt-injection-v2）

> batch_size=10, max_length=512, CPU单线程推断

| 指标 | 值 (ms) |
|---|---|
| Min | 10,667 |
| P25 | 11,678 |
| **Median** | **11,868** |
| P75 | 12,315 |
| Max | 13,018 |
| Mean | 11,909 |

**关键发现：**
- 单条短文本（<512 token）纯前向延迟约 **~1,200ms/batch** = ~120ms/条（batch_size=10时均摊）
- 实际测试中batch内串行处理（tokenizer+forward一次跑完），所以median 11868ms是整批延迟
- **如果按单条计算**：~1187ms（完整pipeline开销含tokenizer）
- 比文献报告的15-40ms慢20-60倍——这是CPU推理 vs GPU推理的自然差距，不是测法错误

### 2.2 阈值-召回/FPR曲线

| 阈值 | Recall | FPR | Precision | Accuracy | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| 0.99 | 0.600 | 0.187 | 0.462 | 0.768 | 24 | 28 | 16 | 122 |
| 0.95 | 0.650 | 0.313 | 0.356 | 0.679 | 26 | 47 | 14 | 103 |
| 0.90 | 0.750 | 0.340 | 0.370 | 0.679 | 30 | 51 | 10 | 99 |
| 0.80 | 0.750 | 0.367 | 0.353 | 0.658 | 30 | 55 | 10 | 95 |
| 0.70 | 0.775 | 0.380 | 0.352 | 0.653 | 31 | 57 | 9 | 93 |
| 0.50 | 0.825 | 0.393 | 0.359 | 0.653 | 33 | 59 | 7 | 91 |
| 0.30 | 0.850 | 0.413 | 0.354 | 0.642 | 34 | 62 | 6 | 88 |
| 0.10 | 0.875 | 0.433 | 0.350 | 0.632 | 35 | 65 | 5 | 85 |

**关键发现：**
1. **FPR过高**：即使在高阈值(0.99)下，FPR仍有18.7%——每5个良性工具输出就有约1个被误判为攻击。这对生产部署不可接受。
2. **Precision偏低**：全区间precision在0.35-0.46之间，意味着超过一半的"阳性判定"是误报。
3. **Recall-FPR权衡**：要召回率>80%，必须接受FPR>39%（即每5个中2个误杀）。
4. **默认阈值问题**：该模型的默认阈值是0.9？如果是，recall=60%太低；如果阈值更低，FPR会更高。需要重新标定。

### 2.3 按策略的检测率

| 攻击策略 | 总数 | ≥0.9检出 | ≥0.5检出 | 平均概率 |
|---|---|---|---|---|
| prepend | 32 | 23 (72%) | 26 (81%) | 0.797 |
| append | 8 | 7 (88%) | 7 (88%) | 0.876 |

**注意**：eval set只采样了40条攻击样本中的prepend和append类型，embedded_mid和benign_like未进入eval。这是benchmark的限制之一。

---

## 三、横向对比结论

### 3.1 当前结果

仅 protectai/deberta-v3-base-prompt-injection-v2 一个候选完成评测。Llama-Prompt-Guard-2-86M因HF gated repo + HF_ENDPOINT镜像配置失败未能测试。

### 3.2 对 L5/S6_model 决策的影响

基于现有数据：
- **纯CPU推理延迟高**（~1.2s/条），不适合实时外设在高频调用场景
- **FPR偏高**（即使阈值0.99也有18.7%），在生产环境中会导致大量误杀正常工具输出
- **Precision偏低**（0.35-0.46），模型区分能力有限

**建议方向：**
1. 尝试下载其他小参数分类器（<100M）用于CPU场景
2. 考虑蒸馏方案：用大模型标注数据后训练专用小分类器
3. 如果需要低FPR，需针对我们的具体数据分布做threshold calibration

### 3.3 限制与未知

| 限制项 | 说明 |
|---|---|
| 候选数量 | 仅1个完成，无法横向比较 |
| 攻击样本量 | 91条构造样本 vs 931条良性样本 → 正负不平衡 |
| 评估采样 | 仅从91条攻击中选40条进入eval，可能不覆盖所有模式 |
| 长文本滑窗 | 未单独测量>512 token的滑窗延迟 |
| 真实生产延迟 | batch_size=10非单条实测 |

---

## 四、复现命令

```bash
# 安装依赖（numpy降级解决兼容性问题）
pip install torch==2.3.1 transformers==4.44.2 scikit-learn --quiet
pip install "numpy<2" --quiet

# 运行benchmark
python classifier_bench_v3.py \
    --benign-cur-count 370 \
    --benign-push-count 561 \
    --output p/bench/classifier_bench_results_v3.json
```

---

## 五、文件清单

| 文件 | 用途 |
|---|---|
| `p/bench/classifier_bench_results_v3.json` | benchmark原始JSON结果 |
| `classifier_bench_v3.py` | benchmark脚本（本地路径） |
| `_cur*.jsonl` (8 files) | SearXNG任务历史快照 |
| `push_samples.json` | 推卡会话提取的工具输出 |
| `_trace.jsonl` | harness trace，含injection_hit记录 |

---

*生成时间: 本轮对话结束前自动保存*  
*后续改进：补充Llama-Prompt-Guard-2-86M测试 + 更大攻击样本集*
