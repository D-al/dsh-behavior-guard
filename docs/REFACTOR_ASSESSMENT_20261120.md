# 重构评估：基于三份地图的结构性诊断（2026-11-20）

> 用户问："根据决策链/路线图/资产图，整个项目是否值得重构？目的是更清晰、更干净、
> 减少屎山程度；必要时考虑把 autostart 插件和探针合并进来。"
>
> 本文是**证据化评估 + 方案对比**，不是重构执行。承重改动必须由用户拍板（决策主体纪律）。

## 1. 屎山测量（不是感觉，是数字）

| 指标 | 实测 | 判读 |
|---|---|---|
| `index.mjs` 行数 | **2247** | 单插件偏大 |
| 顶层符号（const/function/class/export）| 47 | 中等 |
| **单个 `apply()` 跨度** | **714→1719+，~1500 行** | ⚠️ 核心问题：一个函数塞 40+ 逻辑块 |
| `ctx.on()` 事件钩子 | 3（session/event、turn-stopping、pre-step）| 钩子少，但每个回调巨大 |
| 顶层功能区块注释（`// ──`）| 14 | 说明作者已在用注释分块——但注释不是模块边界 |
| `apply()` 内二级逻辑块 | **40+**（S1-S9/D1-D5/L0-L3/P0-P2/G4/G6/Critic/Planner…）| 每次合并插件就往里塞一段 |

**根因明确**：屎山不是写坏的，是**长出来的**——
`behavior-guard` → `turn-continuation-guard` → `task-continuity` → `frame_limiter` 每次合并，
都把整段逻辑贴进同一个 `apply()`。这与 `lineage/DECISION_CHAIN.md` 的 I03（单权重多角色）决策一致：
我们选择"单模型多角色"而非多 agent，代价就是**所有角色的逻辑挤在一个进程的一个函数里**。

> 这是"合成心智"架构的**结构性代价**：单 write 者 + 共享 state 换来了权限清晰，
> 但换来了代码集中。重构不是否定这个决策，而是给它补上模块边界。

## 2. 三份地图指向的同一个结论

- **决策链**：地基决策（A 类实测）全在配置/参数层，架构决策（I/K 层）是"外置器官"——
  器官已经长出来了，但**器官之间没有物理边界**（全在 apply 里）
- **资产图**：16 项资产里，器官类（CritBank/skills/rubrics/mind_state）已经是外置文件，
  **只有执行逻辑还内联在 index.mjs**——外置了一半，一半没外置，这是不一致
- **路线图**：25 张卡 multi 链（M1-M10）说"器官间流动"，但代码层面器官间靠共享 state 耦合，
  流动靠 if/else 判断而非接口——**路线图要的连接，代码还没提供**

三份地图都指向：**该给器官补物理边界了**。

## 3. 重构选项对比

| 方案 | 做法 | 收益 | 风险 | 建议 |
|---|---|---|---|---|
| **A. 不动，只加文档地图** | 保持单文件，靠 ASSET_MAP 索引 | 0 风险 | 屎山继续长；新合并更难 | ❌ 治标不治本 |
| **B. 内部分块（低风险）** | 把 apply() 内 40+ 块抽成顶层纯函数，apply 只做编排；按 hook 分成 3 个 handler 文件 | 可读性大增、可单测、合并新机制有地方放 | 中（需行为等价验证）| ✅ **推荐先做** |
| **C. 全量模块化（中风险）** | index.mjs 拆成 src/{guards,learning,identity,observability}/ + 入口 apply | 结构最清爽 | 高（改动面大，生产在跑）| ⚠️ B 验证稳定后再考虑 |
| **D. 合并 autostart** | 把 dsh-llama-server-autostart（675+309行）并入本插件 | 单一仓库、统一升级 | ⚠️ **见 §4，不建议** |
| **E. 合并探针** | a16_watch/freeze_watch/speed_probe 等收进 tools/evidence | 资产归位 | 低 | ✅ 可做（部分已做）|

## 4. 为什么不建议合并 autostart（D 方案）

证据：
1. **职责正交**：autostart 管"拉起/关闭 llama-server 进程 + 帧率限制"（系统层），
   behavior-guard 管"agent 行为治理"（认知层）。合并后一个插件两种生命周期，反而更乱。
2. **独立发布节奏**：autostart 有自己的 CHANGELOG/package.json/consistency_guard 项，
   更新频率与 behavior-guard 不同（各 6 次提交 vs 独立历史）。
3. **风险不对称**：autostart 崩 = 推理服务没了；behavior-guard 崩 = 行为约束失效。
   合并 = 单点故障面积扩大——这违反"分层解耦"的工程常识。
4. **但有交集**：frame_limiter（推理期限帧）与 guard 的"活性判据"都关心 GPU 调度——
   这个交集靠**接口**协作（读同一 state），不靠合并代码。

**建议**：保持两个插件独立，但**在 ASSET_INDEX 登记两者关系**，让 agent 知道"GPU 争抢时查 autostart/frame_limiter"。

## 5. 探针合并（E 方案）——可做，但分类处理

| 探针 | 性质 | 处置 |
|---|---|---|
| `freeze_watch.py` / `learn_watcher.py` | 常驻守护（计划任务）| 保持 tools/，但登记进 ASSET_INDEX |
| `speed_probe.py` / `entropy_probe.py` | 按需诊断 | 收进 `tools/evidence/`（与 rw_funnel 同族）|
| `a16_watch.py` | 一次性盯梢脚本（SID 硬编码）| ⚠️ 不要收编——它是临时工具，硬编码会话 ID，收进来反而制造垃圾 |
| `trace_timeline.py` / `token_audit.py` 等 | 证据分析 | 保持在 tools/，补"工具目录"（ASSET_INDEX 已登记部分）|

原则：**按"可复用性"分流，不是按"名字像不像工具"**。

## 6. 推荐路线（分阶段，每阶段可独立验证/回滚）

### 阶段 1：B 方案（内部分块）— 推荐立即做
1. 把 `apply()` 内 40+ 块按职责归到 6 组：
   `guards/`（L0-L3、D1-D5、verify-on-edit）、`learning/`（outcome捕获、CritBank、S8/S9）、
   `identity/`（GWT、mind_state、心智拼图）、`observability/`（trace、五元组）、
   `review/`（Critic、Planner、验收）、`continuity/`（P0/P1压缩与闹钟）
2. 每组抽成顶层 `function handleXxx(ctx, state, event)`，apply 只做注册和分发
3. **行为等价验证**（基础设施已齐，2026-11-20 核实）：
   - `run_all.sh`（18 项）+ `self_harness_gate.py`（14 项）—— 静态/回归门禁
   - `tools/trace_report.py` —— 改前后各出一份 trace kind 分布报告，对比数量/时间戳
   - `tools/replay_good.py` —— 从真实 session.v4.jsonl 还原某步 payload 重放，**不改服务端即可 A/B**
   - 真实基线：`D:/Brain/workspace/bench/_trace.jsonl`（3.5MB）—— 改前先存档为黄金基线
   - 判据：改后 run_all/self_harness 全绿 + trace kind 分布一致（±5%）+ replay 关键步输出一致
4. 每抽一组 commit 一次，可逐个回滚

### 阶段 2：E 方案（探针归位）+ 关系登记
- 按 §5 分类收编；ASSET_INDEX 加 autostart 关系条目

### 阶段 3：C 方案（物理模块化）— 仅在阶段 1 稳定运行 ≥1 周后
- 拆成 `src/` 多文件，需重做一致性守卫清单（现在 key_files 指向 index.mjs）

## 7. 重构的"不做什么"（明确边界）

- ❌ 不改行为逻辑（只搬位置，不改 if/else）——**行为等价是铁律**
- ❌ 不合并 autostart（§4 证据）
- ❌ 不在重构期开新卡/新机制（避免边拆边长）
- ❌ 不动 `.workbuddy/`（项目数据，非代码）
- ❌ 不碰 junction 机制（ADR-0016 承重）

## 8. 一句话结论

**值得重构，但不是推倒重来，而是"给已经长出的器官补模块边界"**——
阶段 1 的低风险内部分块（apply 分组成 handler）能解决 80% 的可读性问题，
且不改变任何行为；autostart 保持独立（正交职责 + 风险隔离），探针按可复用性分类归位。
每阶段独立可验证可回滚，符合"承重决策用户拍板"的身份纪律。

> 等待用户拍板：是否执行阶段 1？
