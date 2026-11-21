# 新候选：Horizon-Labs/prompt-injection-guard-base

zh-ipi-bench 中文注入基准的第一名（80% 检出 / 13% 误报 / AUROC 0.94），
明显优于我们测过的所有模型（deberta-v2 33%FPR、devndeploy 92%FPR、Verm1ion @0.95 73%召回/3.6%FPR）。

仓库非 gated，7301 下载。有现成的量化 ONNX，正好走 onnxruntime 快速路径。

## 优先下载：量化 ONNX（611 MB）—— 只要这个

https://hf-mirror.com/Horizon-Labs/prompt-injection-guard-base/resolve/main/onnx/model_quantized.onnx

## 配置文件（我这边网络不稳，麻烦一起下，都很小）

- config.json：
https://hf-mirror.com/Horizon-Labs/prompt-injection-guard-base/resolve/main/config.json
- tokenizer_config.json：
https://hf-mirror.com/Horizon-Labs/prompt-injection-guard-base/resolve/main/tokenizer_config.json
- special_tokens_map.json：
https://hf-mirror.com/Horizon-Labs/prompt-injection-guard-base/resolve/main/special_tokens_map.json

注：tokenizer.json (34MB) 我已经下到缓存了，你不用下。

## 备选（如果 ONNX 效果不好）：PyTorch 权重 1173 MB

https://hf-mirror.com/Horizon-Labs/prompt-injection-guard-base/resolve/main/model.safetensors

## 放到哪

像上次一样放桌面文件夹（建议新建 `C:/Users/Ad/Desktop/horizon/`，避免和之前的文件混），
告诉我路径，我归位到 HF 缓存并立刻跑 E 核实测。

## 注意

这个基准是"中文间接注入"，和我们的场景（工具输出里的注入）高度吻合。
但它的 carrier 是 issue/rag_doc/email/web_html/tool_output 五类，我们只关心 tool_output——
评测时我会单独报 tool_output 子集的数字。
