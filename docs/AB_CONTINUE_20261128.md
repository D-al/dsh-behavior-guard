# 判优实验续跑阶段报告（2026-11-28 14:15）

> 用户："继续跑 A，记录它的错误类型，尤其是新的错误类型"
> **结论：续跑遇到 dsh 高频冻死（45%）的硬障碍，未能达到 n=105/组。**
> 有效样本增至 108 组（off31/on34/inject43），方向仍一致但未达 95% 显著（Holm p=0.13）。

## 一、错误类型体系（用户核心需求，已完成）

### 1.1 建好了什么

`tools/error_taxonomy.py`（536 行）：15 类错误类型，三层优先级（root>behavior>surface），
每会话最多记 3 类（1 primary + ≤2 secondary），带 suppress 关系避免重复归因。

基线 `bench/_error_baseline.json`（85 组）：

| 类型 | 基线次数 | 严重度 |
|---|---:|---|
| HARD_STOP_LOOP | 23 | 高 |
| PROBE_LOOP | 19 | 中 |
| TOOL_DETOUR | 6 | 中 |
| FAKE_VERIFY | 3 | 高 |
| TOOL_FAILURE_UNHEALED | 3 | 中 |
| INJ_INTERRUPT / EDIT_ANCHOR_MISMATCH | 各 2 | 高/低 |
| VERIFY_NO_CHANNEL / DOING_RIGHT_BLOCKED / SIDE_EFFECT_DAMAGE | 各 1 | 中/高/高 |

### 1.2 建立过程中的关键纠错：85% 是误报

初版基线显示 `VERIFY_NARRATION_LOOP` 72/85 = **85%**，且"inject-on 97% vs off 70%"——
看起来是回注副作用的重大发现。

**查原文后发现是误报**：正则扫了 harness 注入文本（`[注入]...先用 glob 确认真实路径`）
和模型正常推理（"确认刚才改动生效"），而且判据 `>=2次 + 无edit/write` 太宽
（本任务本就不要求 write）。

修正：① 新增 `assistant_text` 过滤注入行 ② 判据收紧为 ≥3 次 + 完全无 read 调用。
结果：**72 → 0**，那个"张力"结论被证伪。

这再次验证项目铁律：**守卫正则只认执行动作，绝不扫注入内容**。
详见 `docs/ERROR_TAXONOMY_BASELINE_20261128.md`。

### 1.3 续跑中的错误类型记录

`tools/ab_error_recorder.py` 每会话写 `bench/_ab_error_log.jsonl`，新类型写 `bench/_ab_novel_types.jsonl`。

续跑 44 条错误日志：
- **新类型告警：0**（狭义 5 类 + 广义 5 类都没出现）
- 命中类型：`PROBE_LOOP` ×1、`FAKE_VERIFY` ×1（均在 inject-on 组，且都是基线已有类型）
- **95% 会话无错误类型**——因为续跑会话绝大多数没有硬停/工具失败（基线时代的 19 个硬停都在旧数据）

诚实解读：**没有观察到新错误类型**，但这不等于"不存在"——因为续跑样本本身很干净，
且冻死会话（total=0）被排除在错误归类之外。

## 二、续跑遇到的硬障碍：dsh 高频冻死

### 2.1 现象

- 小批量测试（9 会话）：**4 个冻死**（running=true 永久卡住），自动重启后仍冻死
- 上一批长跑（37 会话）：**21 个 total=0**（58% 冻死）
- 卡死会话永远不结束，runner 每次等满 150 秒超时

### 2.2 已做的处理

1. runner 加超时检测：150s 超时 → 标记冻死、不记录污染数据
2. 连续 2 次冻死 → 自动重启 dsh 清理
3. 污染数据标记 `invalid=True`，不删除原始记录
4. 尝试用计划任务跑（项目记忆推荐"沙箱派生进程被 CPU 限速"）——
   但计划任务 Result=1，两次尝试均失败（参数解析 + 环境权限），放弃

### 2.3 数据清理

`_ab_reflection_result.json` 中 21 个冻死记录已标记 invalid。
当前**有效样本 108 组**：off 31 / on 34 / inject-on 43。

## 三、当前统计（108 组有效）

| 对比 | 硬停率 | Fisher p | Holm p | 判定 |
|---|---|---|---|---|
| off vs on | 26% vs 24% | 1.000 | 1.000 | 无差异 |
| **off vs inject-on** | **26% vs 7%** | 0.044 | **0.131** | 不显著 |
| on vs inject-on | 24% vs 7% | 0.052 | 0.131 | 不显著 |

方向一致（inject-on 硬停率最低），但**未达 95% 把握**。
按当前效应量仍需 n≈105/组，还差约 70/62 组。

## 四、诚实结论

✅ **错误类型体系建成并验证**（含一次重要的误报纠错）
✅ **新类型检测在运行**，续跑 44 条日志无新类型告警
✅ **108 组有效数据**，方向一致指向 inject-on
❌ **未达 95% 把握**（Holm p=0.13）
❌ **未完成 n=105/组**（dsh 冻死率 45% 使长跑不可行）

## 五、下一步选项

**A. 修复 dsh 冻死再跑**（推荐但需要环境排查）
- 冻死根因未明：可能是 llama-server 实例崩溃/router 切换、WDDM 显存压力、或 dsh 事件循环卡死
- 需要先解决稳定性，再跑 70+/组

**B. 接受当前方向性结论**
- 硬停 26%→7%（降 19pp）、质量指标同向、新类型 0
- 用"方向性证据"决策，明确标注未达统计显著

**C. 换任务/环境重跑**
- 用更短的任务降低单次推理时长，减少冻死窗口
- 但会改变实验条件，需重新建基线

## 六、产物

- `tools/error_taxonomy.py` / `_error_baseline.json`：15 类错误分类 + 基线
- `tools/ab_error_recorder.py` / `ab_error_summary.py`：记录与实时摘要
- `tools/ab_randomized_runner.py`：加了冻死检测 + 自动重启 + 污染标记
- `docs/ERROR_TAXONOMY_BASELINE_20261128.md`：误报纠错记录
- `bench/_ab_error_log.jsonl`（44 条）/ `_ab_novel_types.jsonl`（空）/ `_ab_reflection_result.json`（129 条，21 条 invalid）
