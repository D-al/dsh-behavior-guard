# FA 是否真启用 + DFlash 侧车实测（2026-11-24 凌晨）

## 一、怎么保证 FA 真启用了

### 1.1 四层证据

| 层 | 证据 | 说明 |
|---|---|---|
| **编译期** | `GGML_CUDA_FA=ON`<br>`GGML_CUDA_FA_QUANTS=q4_0-q4_0,q8_0-q8_0,f16-f16,bf16-bf16,q8_0-q4_0` | 我们的 KV 组合 **K=q8_0 / V=q4_0 在列表里**，FA kernel 编译时就实例化了 |
| **启动参数** | autostart `index.mjs:303` 硬编码 `-fa on` | router 命令行可见 `-fa on`，传给子实例 |
| **运行时** | `llama_context: flash_attn = enabled`（2 次） | `llama-context.cpp:433` 打印，主模型 + MTP draft context |
| **预热** | `warmup: flash attention is enabled` | 视觉模块实跑过 |

### 1.2 为什么拿不到 probe 日志
`llama-context.cpp:707` —— **只有 `--flash-attn auto` 才调 `resolve()` 做后端能力探测**（会打印 "Flash Attention enabled / not supported"）。强制 `on` 时直接信任用户，跳过探测。我们之前一直是硬编码 `on`，所以没有 probe 日志。

### 1.3 实测：FA 影响很小（1.2%）

为了量化，我把 FA 改成可配置（`LLAMA_35B_FA`），做了 A/B：

| 配置 | 长 prompt prefill（3240 token） |
|---|---:|
| FA auto/on | **806 tok/s** |
| FA off | 796 tok/s |
| 差异 | **1.2%（噪声内）** |

**但 FA off 时模型加载/预热慢了 3 倍以上**（on 时 60-90s，off 时 >3 分钟未完成）。

### 1.4 结论
- **FA 确实启用了**，但它的价值不在 decode/prefill 速度（瓶颈在 CPU 专家，只有 10 层 attention 在 GPU）
- 真正的价值是：① **模型加载/预热速度**（差 3 倍）② KV cache 可以 q8_0/q4_0 量化（省显存）
- **不建议关闭**，也不需要再优化——它已在最优配置

---

## 二、DFlash 侧车实测（重点）

### 2.1 找到正版侧车并成功转换

`z-lab/Qwen3.6-35B-A3B-DFlash`（正式发布版，0.4B，736 MiB BF16），参数完全匹配：

| 项 | 侧车 | 本机模型 |
|---|---|---|
| vocab_size | 248320 | 248320 ✅ |
| hidden_size | 2048 | 2048 ✅ |
| num_target_layers | 40 | 40 ✅ |
| block_size | 16 | — |
| 层数 | 6 | — |

转换成功（只需 target 的 config.json + tokenizer，不需要 70GB 权重）：
```bash
PYTHONPATH=gguf-py python convert_hf_to_gguf.py dflash_draft \
  --target-model-dir dflash_draft/target --outtype bf16 --outfile DFlash.gguf
```
产物 782MB，元数据验证：`arch=dflash`, `block_size=16`, `block_count=6`, `embedding_length=2048`。

### 2.2 实测结果：**不如 MTP**

| 配置 | tps 中位 | sd | 接受率 |
|---|---:|---:|---:|
| **MTP（nmax=5，生产）** | **24.56** | 0.56 | 0.846 |
| DFlash（侧车全在 CPU，ngl=0） | 11.98 | 0.49 | 0.899 |
| DFlash（侧车半 GPU，ngl=3） | 16.25 | 1.83 | 0.880 |

**DFlash 接受率更高（0.88-0.90 vs 0.85），但速度只有 MTP 的一半到三分之二。**

### 2.3 为什么慢

1. **侧车 736 MiB 在 CPU**：每步 draft 要读几百 MB 走 DDR，**和主模型抢同一条带宽**（这正是我们最稀缺的资源）
2. ngl=0→3 提升 35%（11.98→16.25），说明 **offload 到 GPU 明显有效**，但 736MB 放不进 404MB 余量
3. **验证成本随 token 线性增长**：block_size=16 意味着验证时要处理最多 16 个 token，MoE 每个 token 路由不同专家 → 最多读 128 个专家（而 MTP nmax=5 只需 40 个）
4. 文献的 1.77-2.06× 是 **B200 上专家全在 GPU** 的场景，与我们的 CPU-MoE 完全不同

### 2.4 要让它有希望达到什么条件
- **必须全放 GPU**（ngl=6），需要 ~736 MB，当前只有 404 MB
- 需要量化到 Q4_K（~184 MB）才放得下 —— **但本机没有 llama-quantize 工具**（build/bin 只有 llama-server + dll）
- 即使全放 GPU，按 ngl=0→3 的 +35% 斜率外推，最多 ~21-23 t/s，**仍低于 MTP 的 24.56**

### 2.5 结论
**DFlash 在本机（CPU 专家 + DDR 带宽受限）不如 MTP，不建议切换。** 侧车文件保留在 `D:/GGUF_Download/dflash_draft/`，将来换硬件（专家上 GPU 或更大显存）时可用。

---

## 三、本轮最重要的方法论发现：**CLI 覆盖 preset**

排查过程中发现，`spec-*` 参数改了 preset 完全不生效——因为 **autostart 从 `.env` 读 specType/nmax，以 CLI 参数传给 router，而 CLI 优先级高于 preset**。

```
autostart index.mjs:386-390  →  args.push('--spec-type', p.specType, '--spec-draft-n-max', p.nmax, ...)
                                ↑ p.specType 来自 .env 的 LLAMA_35B_SPEC_TYPE
```

**要改 spec 参数必须改 `.env`，不是 preset。**

这是今晚第三次踩"配置层级"的坑：
1. mmproj 路径 → 被 preset 覆盖（改 .env 无效）
2. flash-attn → 被 autostart 硬编码 `-fa on` 覆盖（改 preset 无效）
3. spec-* → 被 CLI 覆盖（改 preset 无效）

**通用教训：改任何 llama 参数前，先用 `Get-CimInstance Win32_Process` 看 router 的实际命令行，确认参数来源（CLI / preset / 硬编码）。**

---

## 四、短答

**怎么保证 FA 启用了？**
四层证据（编译期 FA_QUANTS 含我们的 q8_0-q4_0、启动 `-fa on`、`llama_context: flash_attn = enabled`、warmup 日志）+ 实测确认（FA off 时模型加载慢 3 倍）。已在最优配置，deccode/prefill 收益仅 1.2%（因为瓶颈在 CPU 专家）。

**DFlash 侧车能用吗？**
能跑通（正版侧车、转换成功、DFlash 加载正常），但**实测比 MTP 慢**（11.98/16.25 vs 24.56）。原因是侧车 736MB 在 CPU 抢 DDR 带宽，且 block=16 的验证成本随 token 线性增长。要发挥需全放 GPU，但显存不够且没有量化工具。**维持 MTP。**
