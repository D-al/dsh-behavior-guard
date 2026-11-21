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
