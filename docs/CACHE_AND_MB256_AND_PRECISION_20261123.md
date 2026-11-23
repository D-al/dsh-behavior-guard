# 方案1/方案2 实测 + 混合精度调研（2026-11-23 下午）

> 用户三项要求：① 试方案1（cache 加大）② 试 max_batch 32→256 + share 随批衰减 ③ 充分调研混合精度质量

## 一、方案1：cache 1350→1800（配 NCMOE 40→41 腾显存）

### 1.1 机制验证：成功且比预想好
| 配置 | VRAM used | cache 实际值 | host experts |
|---|---:|---:|---:|
| A: NCMOE 40 / cache 1350 | 7837 MiB | 1345.67 MiB | 18726 MiB |
| C1: NCMOE 41 / cache 1700 | **7816 MiB** | **1696.40 MiB** | 19190 MiB |
| C2: NCMOE 41 / cache 1600 | 7853 MiB | ~1596 MiB | 19190 MiB |

- **cache=1800 装不下**：needs 7185 MiB > free 7106 MiB，实例直接退出（status 0）
- **NCMOE 41 净省 11 MiB 显存**：把最后一层专家（+464 MiB host）挪到 CPU，腾出的显存刚好够 cache +350 MiB，总占用反降 21 MiB
- **所以 1700 是可行上限**（不是 1800）

### 1.2 性能：噪声淹没了差异（诚实记录）
| 配置 | decode (5次中位) | e2e (3次中位) |
|---|---:|---:|
| A: 40/1350 | 29.639 (sd 3.10) | 29.327 (sd **17.36**，含 59.03s 异常) |
| C1: 41/1700 | 31.456 (sd 1.37) | **35.208** (sd 0.66) |
| C2: 41/1600 | 25.722 (sd 2.23) | 28.497 (sd 0.92) |

**三组数据互相矛盾**：C1 decode 最快但 e2e 最慢；C2 decode 最慢但 e2e 最快；A 有一个 59s 异常值。
- 配置间差异（decode 25.7~31.5，e2e 28.5~35.2，约 ±20%）与测量噪声同量级
- 违反记忆铁律"单次 ±10%，判优至少 2 次"——这里波动远超 10%

**可能原因**：① share=1.0 时 CPU 帮算，CPU 调度受其它进程干扰大 ② 笔记本功耗/温度墙 ③ 每轮 e2e 的 cache 起始状态不同 ④ 测试间隔太短，热态未稳定

**结论：方案1 机制可行（cache 确实能加到 1696 MiB 且总显存不涨），但收益无法用当前测量条件证明。不建议在噪声未排除前切换。**

### 1.3 尝试过的更可靠判据（都失败）
- **命中率日志**：`log_stats()` 只在 `~impl()` 析构时打印，`terminate()` 强杀不触发；`CTRL_BREAK_EVENT` 对 llama-server 无效
- **官方 tune 脚本**：按单模型模式算显存（`room = free - used - 512`），我们 21GB 模型单模型模式 room<0，直接退"no room for cache larger than 512"

## 二、方案2：max_batch 32→256 + share 随批衰减

### 2.1 源码分析（预期收益有限，甚至负面）
改了两处（`src/llama-moe-cache.cpp`）：
```cpp
static constexpr int64_t max_batch = 256;   // was 32

// share 随批衰减
const int64_t n_tok_share = sel->src[0]->ne[1];
uint32_t share_q = 0;
if (has_cpu && g.lru.n_filled == g.lru.n_slots && n_tok_share > 0 && n_tok_share <= max_batch) {
    share_q = n_tok_share <= 32 ? cpu_share_q
             : (uint32_t)((uint64_t)cpu_share_q * 32 / (uint64_t)n_tok_share);
}
```

**三道硬约束让预期收益很小**：
1. **n_slots 门槛**：`std::min(n_tokens*n_expert_used, slot_map->ne[1]) > n_slots` 仍会 return nullptr。我们 n_slots≈754，每 token 8 专家 → 实际只能到 **~94 token**，改 256 大部分范围进不去
2. **n_zero=8 限制**：每层最多 8 个专家能交 CPU 算（`if (z >= n_zero) skip`）。中等批 miss 几百个，只有 8 个能分流，衰减后的 share 基本无效果
3. **上游警告**：源码注释明写 "large batches ... would evict the experts used in generation"——中等批进 cache 会挤掉 decode 的热专家，**可能反而拖慢 decode**

### 2.2 实测结果（已完成）

工作负载特意用 **60 token 增量**（在 patch 有效窗口 33..94 内），20K 首轮 + 60token×3，5 次中位：

| 配置 | e2e | decode |
|---|---:|---:|
| baseline (max_batch=32) | **26.604s** (sd 0.433) | 31.1 t/s |
| patch (max_batch=256) | 26.727s (sd 0.737) | 32.9 t/s |

**e2e 持平**（+0.46%，在噪声内），decode 的 +5.8% 未体现在端到端。

- **结论：补丁无实质收益，不采用。** 与源码分析的三道约束完全吻合
- 编译方式：在已完整编译的 build-gdn 上增量重编（只 7 个目标，1 分钟），避免全量 CUDA 重编（该环境下被 WorkBuddy 抢 CPU，速度只有正常 1/15）

## 三、混合精度专家：质量调研（已完成，详见 MIXED_PRECISION_EXPERTS_QUALITY_20261123.md）

**一句话结论：Q3_K 是安全区间，Q2_K 不可取，且 PPL 在 agent 任务上会失明。**

关键证据：
- 我们当前 UD-Q4_K_XL 在量化谱系里已是甜点（PPL 6.735，+0.22%）
- 官方 Unsloth 自己发布 UD-Q3_K_M（全 3-bit，PPL +2.4%）→ 3-bit 是工程可接受档
- **致命反例**：`kyumly/Qwen3.6-35B-A3B-MoE-expert-IQ2` 结构与我们要做的完全相同（只降专家），2.25bit → **LiveCodeBench −26 分、GPQA −13.6 分**
- PPL +7.7% 是质量拐点（APEX I-Mini 的 IQ2_S 中间层）

推荐配方（若做）：只降 40 层 `ffn_{up,gate,down}_exps` 到 **Q3_K**，attention/shared/output 保 Q4+/Q6，必须用 imatrix。预计专家 18.3→13.7 GiB（−25%），decode +23~29%，端到端 −5~8%。

**两个比量化更优先的发现**：
1. **MTP 可能让 function-calling 掉 40%**（protolabs 实测）——我们只测过 MTP 的 decode +8%，**从未测过工具调用准确率**。建议先做这个 A/B
2. **KV cache q4_0 可能让 DeltaNet 状态失稳**（DuoNeural 报告）——我们有 31 层 DeltaNet 且 `--cache-type-v q4_0`，建议试 q8_0（显存代价小）

## 四、下一步建议（按 ROI）
1. **先做 MTP 工具调用准确率 A/B**（零成本，可能发现 MTP 在伤害 agent 质量）
2. **试 KV q4_0→q8_0**（零成本，几乎无质量风险）
3. 方案1 若要确认，需要**严格测试条件**：关闭 WorkBuddy/frame_limiter、固定 seed、交叉顺序、每配置 10+ 次
4. 方案2 等编译测试结果
5. 混合精度 Q3_K 需重做 GGUF（=换模型文件），需用户决策
