# 路线图拆分实施记录（2026-11-20）

> 用户："我倾向于让它自动爬卡，所以按最有效的方式来。"
> 依据 [三维度分析](ROADMAP_SPLIT_ANALYSIS_20261120.md) 的结论：把分析中的阶段 1 + 阶段 2 一次做完。
> 决策逻辑：自动爬卡会持续产生写回，维护收益会反复兑现——值得一次付清迁移成本。

## 1. 拆分后的三文件架构

| 文件 | 角色 | 体积 | 谁写 |
|---|---|---|---|
| `ROADMAP.md` | **人读视图**：§1-§8 + HUMAN_PROGRESS 自动表 | 973 → **245 行** | 人写正文；`--apply` 只写 HUMAN 块 |
| `ROADMAP_GRAPH.md` | **机器真相源**：裸 YAML 权威块（16 items + 7 rungs）| 新建 **400 行** | `--apply/--claim` 写状态 |
| `CAPABILITY_LADDER.yaml` | **语义镜像**：what/why/caveats/reflection 等 | 739 行 | `--apply` 只同步 status/evidence 元数据 |

外加 `test_sids.json`：测试 sid 黑名单**唯一真相源**（A0 交付物，原 3 份副本归一）。

## 2. 具体改动

1. **建 `ROADMAP_GRAPH.md`**：从 ROADMAP.md 搬出整个 `GRAPH_BEGIN/END` 块（含前置说明，标记外的说明不影响执行器）。
2. **`roadmap_check.py` 改双文件读写**：
   - 新增 `GRAPH_FILE` 常量；`load_ladder()` 改读它
   - `save_authoritative()` 拆两次写：GRAPH 写块、ROADMAP 只写 HUMAN 表（**物理隔离：apply 碰不到 §1-§8 叙述**）
   - `test_sids()` 优先读 `test_sids.json`，保留 meta/顶层 fallback（旧生产副本未同步时 fail-safe）
   - 输出文案同步改文件名
3. **消除语义死副本**：从机器块删除 11 类语义字段（title/what/why/unlocks/benefit_to_self/cost/caveats/reflection/abort_if/preconditions/instrumentation_needed）共 **177 处**——执行器运行时本就从 LADDER 合并，行为零变化；`--card M8` 实测语义完整。
4. **test_sids 三份归一**：GRAPH 顶层 + GRAPH meta + LADDER meta 全删，只留 `test_sids.json`；注释扶正为"single source of truth"。
5. **引用点同步**：`package.json`（tarball files）、`GUARD_MANIFEST.yaml`（key_files）、`setup/sync-to-profile.ps1`（生产同步清单）、`README.md`（导航第 5 条指向新文件）。

## 3. 验收（拆分后全绿）

```
graph: 30 nodes / 22 edges / 0 cycle
next: M8 | card M8: 语义完整（what/why/caveats/reflection 均在）
verify M1: 3/3（real-sid evidence_cited=1）
dry-run authority 行: ROADMAP_GRAPH.md（语义镜像: CAPABILITY_LADDER.yaml；人读视图: ROADMAP.md）
apply 双写测试: ROADMAP 无块 / GRAPH 有块 / HUMAN 指向新文件 / 可重新 load
self_test 14/14 | a35_real_diff 4/4 | run_all 17/17 | git diff --check 0
test_sids(): 11 项（单一源）
```

## 4. 容错性收益兑现（对照分析时的预测）

- **写操作物理隔离已成真**：`save_authoritative()` 不再对 ROADMAP.md 做任何 `re.sub` 块替换——A3_5 那次"agent 重写文件误伤 self_test"类事故，在路线图上已无对应面。
- **死副本归零**：what/why 32/32 重复 → 机器块内 0 份，唯一存在 LADDER。
- **test_sids 承重 bug 根治**：3 份 → 1 份 + 读取端兼容；"以谁为源都返回 11 项"。

## 5. 遗留（可延后，不阻塞自动爬卡）

- `docs/CONSISTENCY_GUARD_DESIGN_20261120.md` 里若干示例措辞仍写"ROADMAP 内嵌块是唯一真相"——是设计文档的叙述，不影响运行。
- `test_sids.json` 的 fallback 保留（旧生产副本未同步时兜底），待确认所有副本一致后可简化。
- 生产同步脚本里有 box-drawing 字符（`══`），与"ASCII-only"注释不符——历史遗留，字节级改动已避开。
