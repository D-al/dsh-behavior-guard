# 真实运行验收：路线图"已完成"声明到底兑现没有（2026-11-20）

> 用户质疑：会不会"看着 A 改 B"——文档宣称完成，实际改/验的是别的东西。
> 本文用**运行中 dsh 真实产生的 trace/产物**作为唯一证据，不用代码存在、不用单测通过、不用文档声明。

## 一、方法论：先排除假证据

`_trace.jsonl` 共 **9666 行**，但按 sid 分组后发现：

| sid | 行数 | 性质 |
|---|---|---|
| `s1` | **8592（89%）** | **单测伪造数据**（含 100 次假 audit fail、81 次假 critic fail）|
| `budget-3/4` | 139 | 我的 M4 调试会话 |
| 其他短 sid（`269ec283`/`f8a7f057`/`8a3fc041` 等）| **883** | **真实 dsh 会话** |

**任何不排除 s1 的"trace 里有 X 所以机制生效"论证都是被单测污染的。**
我曾经差点把"角色 LLM 成功率 9.7%"当成生产故障——那全是 s1 假数据。

## 二、逐项验收（真实会话 883 行）

| 路线图声明 | 真实 trace 证据 | 判定 |
|---|---|---|
| GWT 共享状态总线 | `control_turn` **19** | ✅ 真实触发，带 snapshot |
| FEP 预期闭环 | `fep_cycle` **19** | ✅ |
| CritBank 命中 | `crit_hit` **17** | ✅ |
| mind_state 中性注入 | `mind_state` **15** | ✅ |
| 技能卡渐进披露 | `skill_card` **11** | ✅ |
| 学习回注 | `learn_feedback` **8** | ✅ |
| verify-on-stop | `verify_on_stop` **5** | ✅ |
| S9 有状态反馈 | `review_state` **3** + `review_echo` **2** | ✅ 真实写入并回灌 |
| S6 注入检测 | `injection_hit` **1** | ✅ **受控实验真实触发**（见 §三）|
| S8 审计自校准 | 独立产物 `_audit_feedback.jsonl` **3 条真实结算** | ✅（写独立文件，不在主 trace）|
| D5 审计门控 | 由 review_state 的 3 次触发佐证 | ✅ |
| S4 自适应路由 | `adaptive_route` **0** | ⚠️ **符合设计**（S4 结论就是默认关闭）|

**结论：路线图承诺"已完成"的机制，在真实 dsh 运行中全部找到对应证据，不是纸面完成。**

## 三、两个"零证据"的辨析（避免误判）

### 3.1 S6 曾真实会话 0 次命中 —— 受控实验补证
原统计里真实会话 `injection_hit=0`，43 条全在我的调试会话 `budget-3/4`。两种可能：
① 真实工具结果里确实没有注入文本（正常）；② 插件没在真实路径扫描。

**受控实验**：造 `_s6_probe.txt`（含 "IGNORE ALL PREVIOUS INSTRUCTIONS" + "请忽略之前的指令"），
发新会话让 dsh 用 read 读取。结果：`sid=8a3fc041` 的 trace 在 step 1 出现 `injection_hit` ✅。
→ S6 在真实路径生效，之前的 0 只是"没喂注入内容"。

### 3.2 S8 主 trace 里 0 条 —— 命名/落点差异，不是没实现
S8 的结算写**独立文件** `_audit_feedback.jsonl`，不是主 trace 的 kind。实际内容 3 条：
```
gate=repeated-failure  badNow=1 effective=false stepNow=6
gate=post-compaction   badNow=0 effective=true  stepNow=19
gate=post-compaction   badNow=0 effective=true  stepNow=41
```
有 true/false 两种有效性判定——正是 S8 设计的"度量审计干预是否有效"。
→ 用"主 trace 里搜 audit_feedback kind"会误判为没实现，这是典型的"看着 A 改 B"。

## 四、诚实保留的边界（仍有观察项）

- **S1 P3 / 双 split 真实评测**：ADR-0018 有意未启动，非"宣称完成但没做"——路线图已标 PARTIAL。
- **M7 / L5 小模型方案**：S7 证伪 0.6B 实时外设，已降级；不是"完成"。
- **S8 有效率报告**：DoD 要求累计 ≥30 条才出报告，当前 3 条，需长期运行。
- **异步竞态 / steer 通道不计 token**：上轮深度维护列为观察，本轮无新证据，保持观察。

## 五、这轮整治里我自己犯的"看着 A 改 B"（留档警示）

1. **版本假象**：前几轮手工 cp 新 index.mjs 到 node_modules，版本号却停在 2.3.0，
   一次 pnpm install 就把新代码覆盖回旧版——"运行版是新的"是假象。
2. **改错仓库**：把运行版 autostart 覆盖到 Workspace 的旧 clone（commit 39f216c v1.1.0），
   真正权威源是 `D:/Brain/publish/dsh-llama-server-autostart`（v1.1.1）→ 已 git checkout 回滚。
3. **`!!js` 补丁**：试图把路径改成 YAML `!!js` 表达式，实测让 dsh 启动失败 → 回滚，
   改用"从包内 patch 删路径键、由参数化 DEFAULTS 接管"。
4. **限帧器残留**：`Stop-Process -Force` 不触发 Python finally，EcoQoS 残留 → 加 `--release-all` 兜底 + 父进程看门狗。

**这些教训共同指向一条铁律**：验收必须区分"权威源 / 运行版 / 副本"三份拷贝，且只认真实运行证据。

> 遵循知识资产沉淀规则。证据来自运行中 dsh 的 `_trace.jsonl` 与 `_audit_feedback.jsonl`，非单测非文档。
