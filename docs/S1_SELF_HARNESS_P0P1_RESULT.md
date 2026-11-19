# S1 技能自进化闭环：P0+P1+P2 落地结果（2026-11-19）

> 按 ADR-0018 四阶段方案，本轮落地 P0（白名单+门禁）、P1（弱点挖掘）、P2（最小协议验证）。
> P3（与 learn_watcher 合并常态化）按方案要求"需 P0-P2 验收后才启动"，本轮不做。

## 一、P0 可编辑面白名单 + acceptance gate ✅

- `surfaces.json`：6 个可编辑 surface（prompt 措辞 ×3、阈值 ×2、技能草稿 ×1），
  8 类**永远禁改**的安全面（权限预设、L0-L3、D1-D5、verify 闸门、GWT/FEP、CritBank protected、AGENTS 安全底线、权重/引擎参数）。
- `tools/self_harness_gate.py`：纯统计门禁，零 LLM：
  - `accept()`：论文规则"任一 split 不退化 且 至少一个提升"，repeats≥2，decline 合法。
  - `variance_ok()`：基线 pass-rate 极差 <10%（样本少时保守）。
  - `surface_check()`：候选只改白名单内一个面，碰禁改面直接拒绝。
  - `--self-test` **11/11 通过**（accept / reject / no-op / repeats 不足 / 方差宽窄 / 面校验）。

## 二、P1 弱点挖掘 ✅

- `bench/weakness_miner.py`：从真实 `_trace.jsonl`（**6970 行**）抽失败签名
  `(terminal_cause, criticality, agent_mechanism)`，**精确匹配聚类**（论文做法，不用 embedding），
  按 support × actionability 排序，产出 `_evidence_bundle.json`。
- 实测聚类结果：

| 失败签名 | support | 机制 | 优先级 |
|---|---|---|---|
| tool_failure | 213 | tool-execution | 426 |
| audit_unavailable | 89 | role-llm | 356 |
| corrector_unavailable | 81 | role-llm | 324 |
| critic_unavailable | 68 | role-llm | 136 |

- **13 条 `recovered_friction` 进 protected 段**——"上下文不堪但靠 harness 救回来"的案例，
  按论文是**要保护的成功行为**，不是修复对象。
- 与论文对照：Self-Harness 给 Qwen3.5-35B 找到的改进（打断重复失败、工具出错后仍产出产物）
  与我们的 `tool_failure` 聚类高度重合，互相印证。

## 三、P2 最小协议验证 ✅（真实跑通）

- `bench/self_harness_proposer.py`：读 evidence bundle → **本地 35B 亲自当 proposer** → 产候选 → 面校验 → 输出 patch 到隔离目录（`_self_harness_candidates/`），**不自动部署**。
- 真实调用结果：35B 产出合法 JSON 候选：
  - surface=`SURF-PROMPT-CONTROL`（白名单内）
  - 对应 `tool_failure`（support=213）
  - 改动："工具失败时追加降级执行策略说明"
  - `surface_check: allowed=true`
- **又踩 thinking token 坑**：初版 `max_tokens=600` 导致 content 空 → 提到 1200 + reasoning 兜底才成功
  （与 S5-② Critic、S7 小模型同源）。

## 四、边界与未完成

- **没有跑双 split 真实评测**（train 16 / heldout 8 × 2 repeats ≈ 2-4 小时/轮）——
  P0 门禁的 pass-rate 方差 <10% 用历史 bench 数据无法严格验证，本次只验证了统计函数本身。
- **没有自动写回**：候选只落隔离目录，符合 ADR-0015/0018 的人工审批原则。
- P3 常态化（合并 learn_watcher 夜间循环）按 ADR-0018 不启动。

## 五、产物清单
- `surfaces.json`（仓库根）
- `tools/self_harness_gate.py`（11/11 单测）
- `bench/weakness_miner.py` → `bench/_evidence_bundle.json`
- `bench/self_harness_proposer.py` → `bench/_self_harness_candidates/candidate-1.json`

> 遵循知识资产沉淀规则：每个阶段做到哪、哪些没做、为什么不做，都留档。
