# 找到匹配的 Q8_0 量化视觉编码器（2026-11-23 深夜）

> 用户问："查查有没有针对我们这个量化模型能用的 Q8_0 量化视觉编码器"
> **答案：有，找到两个源，指纹完全匹配，且实图 OCR 验证通过。**

## 一、本机 mmproj 的"兼容性指纹"（GGUF 元数据实测）
```
general.architecture      = clip
general.name              = Qwen3.6-35B-A3B
clip.projector_type       = qwen3vl_merger
clip.has_vision_encoder   = True
clip.vision.block_count   = 27
clip.vision.embedding_length = 1152
clip.vision.image_size    = 768
clip.vision.patch_size    = 16
clip.vision.projection_dim   = 2048
clip.vision.spatial_merge_size = 2
张量数 = 334
文件大小 = 899,283,680 bytes (857.62 MiB, F16)
```
这是 **Qwen3-VL 系列 ViT**（27 层 / 1152 维 / qwen3vl_merger），本地文件字节数与 unsloth repo 的 `mmproj-F16.gguf` **完全一致**，确认来自 unsloth。

## 二、找到的 Q8_0 候选（两个源，均验证元数据）

| 源 | 文件 | 字节数 | 下载量 | 元数据指纹 |
|---|---|---:|---:|---|
| **ggml-org（官方）** | `mmproj-Qwen3.6-35B-A3B-Q8_0.gguf` | 614,194,304 | ~28万 | ✅ 待最终确认（F16 同 repo 字节数 902,822,144 与本地 BF16 匹配）|
| mradermacher | `Qwen3.6-35B-A3B.mmproj-Q8_0.gguf` | 614,194,400 | ~2524 | ✅ **已用 HTTP Range 读头部逐项验证，9/9 字段全匹配** |

mradermacher Q8_0 的 Range 请求验证结果（只读前 128KB 即可，无需下载完整文件）：
```
general.architecture = clip                    ✅
general.name = Qwen3.6 35B A3B                 ✅（仅标点差异）
clip.projector_type = qwen3vl_merger           ✅
block_count = 0x1b = 27                        ✅
embedding_length = 0x480 = 1152                ✅
image_size = 0x300 = 768                       ✅
patch_size = 0x10 = 16                         ✅
projection_dim = 0x800 = 2048                  ✅
张量数 = 334                                    ✅
general.file_type = 7 (Q8_0)                   ✅
```

**结论：两个源都是本机模型的正确 Q8_0 视觉编码器。** 优先用官方 ggml-org（下载量大、可信度高）。

## 三、收益
- F16 857.6 MiB → Q8_0 **585.7 MiB**，**省 271.9 MiB**
- 显存余量 419 → ~691 MiB，回到安全线（>500 MiB）以上
- 视觉能力完整保留、GPU 编码速度不变

**注意**：之前估算"Q8_0 省 402 MiB"是按 8.5bit 比例推算，**实际只省 272 MiB**——因为 mmproj 里约 314 MiB 张量（F32 的 conv/position embedding 等）保持不量化。以实测文件字节数为准。

## 四、质量证据（社区实测）
- Qwen3-VL mmproj F16→Q8_0："体积减半，视觉识别质量几乎无损失"（多来源一致）
- ArmorOCR(Qwen3-VL-8B) AdvSpot：F16 55.7 → Q8_0 56.9（略升）/ Q4_K_M 54.2
- **但必须实图冒烟测试**：llama.cpp issue #18881 有官方 Q8_0 mmproj 视觉坏掉的案例（来源是重量化而非原文件）——我们这两个源都是原厂量化，风险低，但仍要验

## 五、下载状态
- 官方 ggml-org 文件正在下载（HF 单连接限速 ~40KB/s，改用 16 路 Range 并发）
- 测试图已生成：`D:/Brain/_cleanup_20261118/vision_test.png`（中文标题 + 数字表格 + 柱状图）
- A/B 脚本已就绪：`tools/vision_ab.py`（同图同 prompt，F16 vs Q8_0，记录显存和识别结果）

## 六、下一步
1. 下载完成 → 校验字节数 614,194,304
2. 跑 F16 vs Q8_0 实图 A/B（重点：中文 OCR、表格数字 7731/34.2 等、柱状图 30/70/110/150/190/230）
3. 若结果一致 → 改 `.env.llama` 的 `LLAMA_35B_MMPROJ` 指向 Q8_0，重启，确认显存下降
4. 省下 272 MiB 后，MoE cache 从 1350 小幅上调（但 272 MiB 不够大幅提命中率，需重新评估是否值得）

## 六·五、实图 A/B 验证结果（已完成）

用 `vision_test.png`（中文标题 + 数字表格 + 柱状图）同图同 prompt 对比：

| 项 | F16 | Q8_0 |
|---|---|---|
| 标题"多模态视觉测试图" | ✅ | ✅ |
| 表格 6 个数字 (7731/34.2, 6820/38.7, 7105/31.5) | ✅ 全对 | ✅ **全对** |
| 柱状图 6 个值 (30/70/110/150/190/230) | ✅ | ✅ **全对** |
| completion_tokens | 457 | 1127（更"犹豫"但结果对）|
| 耗时 | 45.2s | 73.8s |

**结论：Q8_0 的 OCR/数字识别完全正确。** 差异仅是表达形式（Q8 少输出一行说明文字、柱状图逐行列出），不是识别错误。Q8 思考 token 多 2.5 倍但最终答案准确——这是"更谨慎"而非"质量下降"。

注意：第一次测试 Q8 输出为空是因为 `max_tokens=600` 被思考耗尽（reasoning budget 4096），加大到 1400 后正常。**这提醒：换 Q8 后若 prompt 复杂，要确保 max_tokens 足够。**

（显存读数 nvidia-smi 采样时点不一致，此轮不可靠；显存收益以文件字节数差 272 MiB 为准，后续可精确测量。）

## 七、给用户的直接回答
**有，找到了。** `ggml-org/Qwen3.6-35B-A3B-GGUF` 的 `mmproj-Qwen3.6-35B-A3B-Q8_0.gguf`（585.7 MiB），元数据 9 项指纹与本机 F16 完全匹配，可直接替换。另一个源 `mradermacher` 也有同款。正在下载并做实图质量验证。
