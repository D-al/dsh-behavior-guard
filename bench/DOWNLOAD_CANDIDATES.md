# 分类器候选下载清单（请帮忙下载）

沙箱环境下载被限速（huggingface.co 仅 20KB/s），已改用国内镜像 **hf-mirror.com**
（沙箱实测 145-262KB/s，你本机不受限速会更快）。全部非 gated、无需 token。
基准脚本已支持多分类和 ONNX。

> 如果 hf-mirror 某个文件 404，把域名换回 `huggingface.co` 即可（同一路径）。

## 下载方式

每个模型下完放到对应目录（我会在你下完后整理进 HF 缓存）。
最简单：**直接点下面的「权重链接」下载文件**，配置文件也可以用同样方式下（都很小）。

---

## 1. devndeploy/bert-prompt-injection-detector（中文 BERT，推荐优先）

- 页面：https://hf-mirror.com/devndeploy/bert-prompt-injection-detector
- 权重：https://hf-mirror.com/devndeploy/bert-prompt-injection-detector/resolve/main/model.safetensors
- 配置（6 个小文件）：
  - https://hf-mirror.com/devndeploy/bert-prompt-injection-detector/resolve/main/config.json
  - https://hf-mirror.com/devndeploy/bert-prompt-injection-detector/resolve/main/tokenizer.json
  - https://hf-mirror.com/devndeploy/bert-prompt-injection-detector/resolve/main/tokenizer_config.json
  - https://hf-mirror.com/devndeploy/bert-prompt-injection-detector/resolve/main/special_tokens_map.json
  - https://hf-mirror.com/devndeploy/bert-prompt-injection-detector/resolve/main/vocab.txt
- 架构：BertForSequenceClassification，12 层 768 维，~179M，标签 NORMAL/INJECTION（中文可用）

## 2. Verm1ion/injection-sentry-xlmr（多语言 XLM-R）

- 页面：https://hf-mirror.com/Verm1ion/injection-sentry-xlmr
- 权重：https://hf-mirror.com/Verm1ion/injection-sentry-xlmr/resolve/main/model.safetensors
- 配置：
  - https://hf-mirror.com/Verm1ion/injection-sentry-xlmr/resolve/main/config.json
  - https://hf-mirror.com/Verm1ion/injection-sentry-xlmr/resolve/main/tokenizer.json
  - https://hf-mirror.com/Verm1ion/injection-sentry-xlmr/resolve/main/tokenizer_config.json
  - https://hf-mirror.com/Verm1ion/injection-sentry-xlmr/resolve/main/special_tokens_map.json
- 架构：XLMRobertaForSequenceClassification，12 层 768 维，~278M，标签 SAFE/INJECTION

## 3. RelyD/prompt-injection-detector（DistilBERT，轻量）

- 页面：https://hf-mirror.com/RelyD/prompt-injection-detector
- 权重（二选一，先下 safetensors）：
  - https://hf-mirror.com/RelyD/prompt-injection-detector/resolve/main/model.safetensors
  - 备选 INT8：https://hf-mirror.com/RelyD/prompt-injection-detector/resolve/main/model_minilm_int8_fp16.pt
- 配置：
  - https://hf-mirror.com/RelyD/prompt-injection-detector/resolve/main/config.json
  - https://hf-mirror.com/RelyD/prompt-injection-detector/resolve/main/tokenizer.json
  - https://hf-mirror.com/RelyD/prompt-injection-detector/resolve/main/tokenizer_config.json
- 架构：DistilBertForSequenceClassification，调研称 INT8 p95 17.8ms（轻量候选）

## 4. flowxai/injection（ONNX INT8，最快，注意是 3 分类）

- 页面：https://hf-mirror.com/flowxai/injection
- 权重：https://hf-mirror.com/flowxai/injection/resolve/main/onnx/model.int8.onnx
- 配置：
  - https://hf-mirror.com/flowxai/injection/resolve/main/config.json
  - https://hf-mirror.com/flowxai/injection/resolve/main/tokenizer.json
  - https://hf-mirror.com/flowxai/injection/resolve/main/tokenizer_config.json
- 架构：XLMRobertaForSequenceClassification，**ONNX INT8**（需用 onnxruntime 测，我这边已装）
- 标签：0=direct_injection / 1=indirect_injection / 2=jailbreak / 3=benign（多分类，脚本已适配求和）
- 调研称 FPR=0.0021（最低），值得优先测

---

## 放哪

下载后告诉我放哪个目录即可（比如 `D:/Downloads/` 或桌面），我会自动整理进：
`C:/Users/Ad/.cache/huggingface/hub/models--<组织>--<模型名>/snapshots/main/`

或者你直接按这个结构放也行，我就能立刻开测。

## 已下好不用管的

- protectai/deberta-v3-base-prompt-injection-v2（738MB，已缓存，已测：短文本 E 核 362ms / @0.9 FPR 21.4% 不合格）
