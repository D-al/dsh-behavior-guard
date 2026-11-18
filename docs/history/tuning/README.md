# 调优历史说明书

> 用户特别要求归档的部分：10-13～11-10 的硬件/引擎/采样/温度调优日志。
> 原始日志 2679 行在 `D:/Brain/workspace/memory/2026-10-*.md` 与 `2026-11-0*.md`；
> 这里按主题蒸馏，**每个决策链都保留"当时判断 → 证据 → 翻转/确认"**。

## 专题索引

| 文档 | 内容 |
|---|---|
| [DECISIONS.md](DECISIONS.md) | 10 条调优决策的完整链条（含 2 条翻案、2 条证伪）|
| [EVIDENCE.md](EVIDENCE.md) | 关键实测数据与实验条件（暖态协议、显存账、性能基线）|
| [EXPERIMENT-TEMPLATE.md](EXPERIMENT-TEMPLATE.md) | 以后做调优实验怎么记录（可复制模板）|

## 四组主线

1. **引擎选型** — Ollama / llama-server / vLLM 对比 → [ADR-0001](../../../decisions/0001-adopt-llama-server.md)
2. **显存与量化** — fp16 KV OOM → q8_0 + FA → 8G 卡跑 35B → [ADR-0002](../../../decisions/0002-q8-kv-flash-attention.md)
3. **专家层与缓存** — 整层挪 GPU 证伪 → 40/2736 翻案 → [ADR-0003](../../../decisions/0003-ncpu-moe-40-cache-2736.md) / [0004](../../../decisions/0004-reject-whole-layer-gpu.md)
4. **采样与行为** — 中文锚点自述句、温度 U 形、moe-cache-cpu-share 伪优化 → [ADR-0006/0007/0008](../../../decisions/README.md)

## 为什么把失败也留着

调优化最大的价值不是"选对了什么"，而是"**排除了什么、为什么排除**"。
本目录刻意保留 2 条翻案（用户坚持复测才纠正的误判）和 2 条证伪（看似纯赚实则有害）——
这些是花时间买来的资产，也是"任何加速必须端到端验证"这条铁律的来源。
