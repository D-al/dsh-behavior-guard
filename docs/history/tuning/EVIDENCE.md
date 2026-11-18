# 调优实测数据（证据）

> 所有数字均来自当时真实会话，实验条件一并记录以便复现。
> 暖态协议：warmup 2-3 次 + 5 次取中位；单次 ±10%；判优至少 2 次。

## 显存账（96K 上下文）

| 项 | MiB |
|---|---|
| 非专家权重 | 2326 |
| KV (q8_0/q4_0) | 780 |
| DeltaNet 状态（不可压）| 377 |
| MoE cache | 1022 |
| 主 compute | ~550 |
| MTP | 600 |
| 安全线：空闲 ≥450；186 必卡（WDDM 换页 → 1~2 t/s）|

## 性能基线（暖态）

| 上下文 | decode | prefill |
|---|---|---|
| 20K | 27.2 t/s | 800 t/s |
| 60K | 23.9 t/s | 781 t/s |

## 关键 A/B

| 实验 | 结果 | 结论 |
|---|---|---|
| moe-cache-cpu-share=1.0 | decode +37%，端到端慢 2.4× | 否决 |
| n-cpu-moe 39 + cache 2400 | decode -9.5% | 否决 |
| n-cpu-moe 40 + cache 2736 | prefill 1019 vs 569 | 采纳（+79%）|
| 温度 0.1 / 0.7 / 0.9 | U 形，0.7 最优 | 定 0.7 |
| 4B vs 8B 冷启 | 4B 56.7s vs 8B 6.9s | 4B 弃用 |
| nmax 7 | 26.73 < 27.31 | 弃用 |
| KV q8_0 vs fp16 | fp16 32K 即 OOM | 必用 q8_0 |
| ik 的 DRY | 慢 2.6× | 弃用 ik |

## 复现条件

- 硬件：i7-12650H / 64G DDR4-3200 / RTX 4060 Laptop 8G / E: NVMe
- 引擎：自编 b12244 + autoparser 2 行补丁
- 模型：Qwen3.6-35B-A3B UD-Q4_K_XL 21.28GiB + mmproj-F16
- 基准：`python bench/speed_probe.py <2k|20k> <次数> <warm>`；`projectlab.py` P1-P5
