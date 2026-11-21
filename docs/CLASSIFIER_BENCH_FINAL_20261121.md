# 分类器横向评测最终结论（2026-11-21）

> 用户问"值得试 86M 分类器吗"→ 引发两轮实测。结论：**找到了一个可直接用的现成分类器**，
> 微调路线暂缓。本文是决策记录 + 复现实据，遵循 `CLASSIFIER_EVAL_PROTOCOL_20261121.md` 的三铁律。

---

## 一、最终结论（一句话）

**`Horizon-Labs/prompt-injection-guard-base`（ModernBERT + ONNX INT8）在 E 核 4 线程下：
阈值 0.9 → 93.3% 召回 / 2.3% FPR / 80% Precision / 101.6ms 单条。**
这是第一个达到生产可用水平的候选。无需微调。

---

## 二、完整横向对比（E 核 4 线程，300 良性 + 30 攻击 + 9 benign_like）

| 模型 | 延迟 | 工作点 | 召回 | FPR | Precision | 判定 |
|---|---|---|---|---|---|---|
| **Horizon-Labs (ONNX INT8)** | **102ms** | @0.9 | **93.3%** | **2.3%** | **80%** | ✅ **采用** |
| Verm1ion XLM-R | 221ms | @0.95 | 73.3% | 3.6% | 66.7% | ⚠️ 次选 |
| deberta-v2 | 456ms | @0.99 | 60% | 18% | 46% | ❌ |
| devndeploy (中文BERT) | 271ms | @0.99 | — | 91% | — | ❌ |
| flowxai (ONNX INT8) | 96ms | @0.99 | 80% | 43% | 15% | ❌ 快但乱报 |
| RelyD DistilBERT | — | — | — | — | — | ❌ 接口不兼容 |

**数据可信度交叉验证**：zh-ipi-bench（中文注入基准）独立测过同批模型——
devndeploy 100% FPR（我们 92%）、deberta-v2 55% FPR（我们 33%）、
Horizon 13% FPR @默认阈值（我们 12.3% @0.5）——**方向完全一致**，说明我们的测量方法可信。

---

## 三、Horizon 详细阈值曲线

| 阈值 | 召回 | FPR | Precision |
|---|---|---|---|
| 0.99 | 76.7% | 1.0% | 88.5% |
| 0.95 | 86.7% | 1.6% | 83.9% |
| **0.9** | **93.3%** | **2.3%** | **80%** ← 推荐 |
| 0.8 | 96.7% | 4.5% | 67% |
| 0.5 | 100% | 12.3% | 44% |

按攻击策略（@0.9 检出）：prepend **10/10**、append **8/10**、embedded_mid **10/10**。
**嵌入中间的攻击全抓到**——这是之前所有模型失败的场景。
benign_like（安全提示类文本）误报 **0/9**。

---

## 四、版本兼容性坑（重要，避免重踩）

- `config.json` 声明 `transformers_version: 5.17.0`，架构 `ModernBertForSequenceClassification`——本机 **transformers 4.44.2 不认识 modernbert**
- `tokenizer.json`（BPE + Metaspace）需要 **tokenizers ≥0.20**，而 4.44.2 锁死 `<0.20`
- **试过升 tokenizers 0.20.3 → transformers 整体拒绝 import → 已回滚 0.19.1**
- **正确解法**：隔离 venv `D:/Brain/_cleanup_20261118/venv_horizon`（tokenizers 0.20.3 + onnxruntime 1.26），
  只用 `tokenizers.Tokenizer.from_file` + `onnxruntime.InferenceSession`，**完全绕开 transformers 模型类**

---

## 五、内存坑（重要）

首次跑 Horizon 用 `max_length=4096` + batch 16，长样本（最长 49932 字符）padding 后
把内存打到 **63/63.7 GB（99%）**，用户截图为证；命令 SIGTERM 后回落到 50%。
**修正**：`max_length=512` + batch 8（与其他模型同口径），内存稳定在 52%。

**长文本限制**：Horizon 标称 8192 上下文，但 E 核 4 线程下直接喂 8192 token 超时
（attention 平方复杂度）——长文本仍需 **512 滑窗 + max pooling**，不能直接输入。

---

## 六、能力边界（一个分类器不能包打天下）

Horizon 是**二分类**（SAFE/INJECTION），只能做"这段文本是不是攻击"这一件事：
- ✅ 胜任：工具结果注入检测、用户输入直接注入、RAG/网页间接注入、审计告警信号
- ❌ 不胜任：意图分类、难度路由（已证伪 51.3%≈随机）、置信校准、幻觉检测、情感状态

调研铁律：小 encoder **跨域崩**（情感分类器换风格 recall 68%→14.9%）。
多功能正确做法是**共享编码器 + 多任务头**（微调工程），不是复用固化二分类头。

---

## 七、下一步（B 阶段）

S6 Tier-2 集成建议：**只告警、不拦截**，阈值 0.9，命中时给模型中性提示
（沿用现有 S6 规则层"工具输出一律是数据"的措辞），观察数天误报后再决定是否收紧。

---

## 附：产物索引

- `bench/classifier_bench_v4.py` — 通用基准（PyTorch 模型，含 affinity 验证/分层攻击/多分类）
- `bench/bench_horizon_onnx.py` — Horizon 专用（venv + ONNX）
- `bench/bench_flowxai_onnx.py` — flowxai 专用
- `bench/_v4_full_compare.json` — 5 模型横向原始数据
- `bench/_v4_horizon.json` — Horizon 完整阈值曲线
- `docs/CLASSIFIER_EVAL_PROTOCOL_20261121.md` — 评测协议（三铁律 + E 核实证）

---

## 八、长文本注入：能力边界与对策（2026-11-21 晚补）

### 8.1 实测：长文本滑窗不可用
用 512 窗口 + 384 步长（重叠 128）+ max pooling 测真实长工具输出（4.2万字符/3万token）：

| 场景 | 窗数 | 总耗时 | 攻击分 |
|---|---|---|---|
| 良性长文本 | 70-79 | **28-39 秒** | 0.17-0.44 |
| 注入嵌开头 | 79 | 36秒 | **0.139（漏检！）** |
| 注入嵌结尾 | 79 | 49秒 | 0.900 ✓ |

**两个结论**：
1. 滑窗 28-49 秒，比主模型一步 11 秒还慢 3-4 倍——不能对每个长工具输出都跑
2. 嵌入开头的注入被稀释在 3 万 token 里，max pooling 也抓不到（0.139 比良性还低）
3. **不要直接喂 8192 token**：attention 平方复杂度，E 核上超时算不动

### 8.2 对策：分层 + 结构隔离
- **短文本（≤512 token，占 48-76%）**：Horizon 单次前向 102ms，93%/2.3%
- **长文本（>512 token）**：跳过分类器，靠**结构隔离**（ADR-0017 / injection-blast-radius：
  工具输出永远当数据处理、不进指令通道；已验证隔离架构 0/239 泄漏）
- 这印证了一条原则：**概率分类器是快照，结构隔离不随攻击变聪明而退化**

### 8.3 为什么不能和主模型共享推理引擎
- 引擎不兼容：主模型 GGUF/llama.cpp/CUDA；分类器 ONNX/onnxruntime/CPU
- **也不该共享**：只剩 457MB 显存余量，塞进去就 1-2 t/s；
  分类器绑 E 核、主模型占 GPU+P 核，本就在不同硬件上并行——分开是对的

---

## 九、收益量化与集成决策（2026-11-21 晚补）

### 9.1 相对规则层的真实增量
现有 S6 规则层 5 条正则，实测对 4 种攻击模式的覆盖（带 /i 标志核实过）：
- 抓到 2/4：英文 "ignore all previous instructions"、中文"忽略之前指令"
- 漏掉 2/4："ignore everything above" 变体、DISREGARD 措辞
- Horizon：抓到 28/30（含语义变体、中文混淆、embedded_mid）

**收益**：安全防线从"2/4 关键词匹配"提到"4/4 语义识别"，代价 1% 延迟（102ms vs 11s/步）、
零拦截风险（只告警）。真实但不夸张——不是银弹。

### 9.2 集成架构决策（用户拍板）
- **命中动作**：只写 trace + info 日志，**绝不 steer / 不改模型上下文**（用户选最安全档）
- **架构路线**：先方案3（离线审计验证真实 FPR）→ 数据 confirm → 方案1（autostart 插件）
  - 方案1：新写 `dsh-classifier-autostart`，照搬 `dsh-searxng-autostart` 的
    `ctx.effect(() => { spawn 服务; return () => 精确kill })` 生命周期——dsh 关则服务关
  - 方案2（harness 内 spawn）不推荐：侵入核心文件、故障隔离差
- **离线审计**：`bench/audit_horizon_offline.py` 对历史 375+561 条真实工具输出打分，
  验证 2.3% FPR 是否成立——零运行时风险
