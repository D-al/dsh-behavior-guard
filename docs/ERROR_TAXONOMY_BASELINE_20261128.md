# 错误类型基线修正记录（2026-11-28 11:20）

> 用户："继续跑 A，记录它的错误类型，尤其是新的错误类型"

## 一、建立分类体系

`tools/error_taxonomy.py`（536 行）：15 类错误类型，三层优先级 root(3) > behavior(2) > surface(1)，
显式 suppress 关系 + 每会话最多 3 类（1 primary + ≤2 secondary），避免单会话被判 10 类。

基线来自已有 85 组 v2 数据，写入 `bench/_error_baseline.json`。

## 二、建立过程中的重要发现：85% 是误报

初版基线跑出来：

| 类型 | 总次 | 占比 |
|---|---|---|
| VERIFY_NARRATION_LOOP（空想验证循环） | **72/85** | **85%** |
| HARD_STOP_LOOP | 23 | 27% |
| PROBE_LOOP | 19 | 22% |

而且显示"inject-on 组空想验证 97%（29/30）vs off 70%"——看起来是回注机制的副作用：
"注入让模型更爱说验证却没真验证"。

**但这是误报。** 直接看会话原文发现：
1. 正则扫到了 **harness 注入文本**：`[注入][harness 工具自愈] ... 先用 glob 确认真实路径`
2. 模型正常推理"我得先确认刚才那次改动到底生效了没有"被计为"空想验证"
3. 判据 `>=2 次确认措辞 + 无 edit/write` 太宽——**这个任务本来就不要求 write**

这正好踩中项目铁律：**守卫正则只认执行动作，绝不扫注入内容**（记忆里 2026-11-18 踩过同样的坑）。

## 三、修正

1. `Ctx` 新增 `assistant_text`：过滤掉 `[注入]` / `[harness` 开头的行
2. `VERIFY_NARRATION_LOOP` 判据收紧为：
   - 只看 assistant_text
   - `>=3` 次确认措辞
   - **完全没有 read 工具调用**（连读回都没做才是真"空想"）
3. 自检用例同步更新，11/11 PASS
4. 基线重建：VERIFY_NARRATION_LOOP **72 → 0**，从"最高频类型"变成"狭义新类型"

**修正后基线（85组）**：

| 类型 | 总次 | off | on | inject-on |
|---|---:|---:|---:|---:|
| HARD_STOP_LOOP | 23 | 10 | 10 | 3 |
| PROBE_LOOP | 19 | 8 | 8 | 3 |
| TOOL_DETOUR | 6 | 3 | 2 | 1 |
| FAKE_VERIFY | 3 | 1 | 1 | 1 |
| TOOL_FAILURE_UNHEALED | 3 | 0 | 0 | 3 |
| INJ_INTERRUPT | 2 | 1 | 1 | 0 |
| EDIT_ANCHOR_MISMATCH | 2 | 1 | 1 | 0 |
| VERIFY_NO_CHANNEL | 1 | 1 | 0 | 0 |
| DOING_RIGHT_BLOCKED | 1 | 0 | 0 | 1 |
| SIDE_EFFECT_DAMAGE | 1 | 0 | 0 | 1 |

**那个"张力"结论（inject-on 空想验证更多）被证伪**——它是误报产物，不是机制副作用。
这再次说明：**看到反直觉数据时，先看原始文本，不要急着写结论。**

## 四、新类型定义

- **狭义**：基线 0 次 → `FORCED_HELP` / `INTENT_DRIFT` / `RECALL_BLIND` / `REPEAT_WRITE_SPIN` / `VERIFY_NARRATION_LOOP`（修正后）
- **广义**：基线 0<count<3 → `DOING_RIGHT_BLOCKED` / `EDIT_ANCHOR_MISMATCH` / `INJ_INTERRUPT` / `SIDE_EFFECT_DAMAGE` / `VERIFY_NO_CHANNEL`

续跑中一旦命中狭义新类型，写入 `bench/_ab_novel_types.jsonl` 告警。

## 五、记录机制

- `tools/ab_error_recorder.py`：每会话抽取 trace + 会话文本 → 分类 → 基线比对 → 写 `bench/_ab_error_log.jsonl`
- runner 已接入，每会话记录 `error_codes` / `novel_narrow` / `novel_broad`
- 新类型单独写 `bench/_ab_novel_types.jsonl`

## 六、诚实边界

- 15 类多重比较下 Holm 校正后均不显著，基线分组差异只作方向性信号
- 基线来自单一任务族短会话，`VERIFY_NARRATION_LOOP` 修正后为 0 不代表该错误类型整体不存在
- 分类器依赖会话文本正则，新会话文本缺失会漏检
- 若 runner 在基线修正前缓存了旧基线，事后需按新基线重算 `novel_*` 标记（原始数据保留，可重算）
