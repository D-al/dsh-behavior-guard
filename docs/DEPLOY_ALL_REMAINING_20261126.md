# 部署：攻防演练暴露缺陷的全部可修项（2026-11-26 18:2x）

> 依据 FULL_WARGAME_20261126.md + 三个子任务设计报告。
> 用户要求"全部修好"——但按证据决定修哪些：**不盲目全改**。

## 修了什么（代码侧 8 项 + 机制同步 2 组 + 数据闭环 1 项）

### patch_all_remaining.py（7 锚点，两版）
1. **FSM 死代码**：补 `fsmSignalEnabled: false` 声明（此前从未声明 → 恒 undefined 死代码；显式 false 保留代码供未来启用，不直接启用以避免未验证行为改变）
2. **hardGateInjected 死字段**：删除（今日重构后无人读）
3. **双副本 sha 泛化**：不再硬编码 `hardware-monitor-plugin`，从路径自动推断插件名 → `node_modules/<插件名>/<相对路径>`（子任务3指出原实现只对单一插件生效）
4. **性能伪优化硬规则**（H 类盲区）：正则检测 assistant 正文的加速主张（加速/快了/提升/speedup/N%快/t/s涨），若无端到端验证工具调用（speed_probe/projectlab/agentlab/P1-P5）→ semanticFail → safetyBlock 持续拦。依据项目铁律"decode t/s 误导，必须端到端验证"
5. **e2e 验证标记**：在验证命令分支置 `e2eVerifiedThisTurn`，每轮重置
6. **学习信号过滤**：`_pending_learn` 86% 是 s1 测试假数据 → 消费端过滤 `^(s1|s2|budget-|test-)` sid，生产数据才进校准
7. （skill 卡关键词单独改文件）

### sync_missing_mechanisms.py（仅运行版，3 锚点 + 2 工具文件）
8. **M3 反模式锁** `s6PatternLock`：全历史 pattern_lock 159 次、trace-only 零风险 → 同步
9. **工具失败自愈** `extractFailure/healHint`：全历史 tool_failure 10 次、当前会话 22 次 FAIL 未被接住 → 同步
- 工具文件 sha256 两版一致（fc96d1bc / f16f147e）

### patch_critbank_state.py（matchCritbank，两版）
10. **CritBank 状态消费闭环**：子任务2复核指出断点不在"反馈没消费"，而在 `matchCritbank()` 只读数组、**不读 `_critbank_state.json`** → `crit_decay.py` 标记的 retired 教训照样注入。修复：读状态表（mtime 缓存）+ 过滤 retired/superseded 条目。

### skill 卡（独立文件）
11. `dsh-ui-slots.md` keywords 补口语化触发词：左边/左侧/那个入口/点进去看/选项卡/模仿它们/没看到入口/接着弄——让 turn11 那种模糊指令能命中（此前关键词只有 slot/sidebar 等专业词，零加载）

## 明确不修（有证据支撑的决定）

| 项 | 不修理由 | 来源 |
|---|---|---|
| 注入分类器（S24 classifier） | 全历史 323 次注入中 99% 命中是压测灌水，真实会话仅 7 次；同步会引入未验证的 steer 通道 | 子任务1 |
| GPU guard 从 dry_run 改 apply | 故意 dry_run（设计如此），真实启用需先解决 WDDM 信号不可靠问题 | 子任务3 |
| frame_limiter 粘性释放 | 代码是兜底逻辑，正常路径下不可达（0 次触发不代表坏） | 子任务3 |
| 审计反馈对照组 | 自评无对照组是真问题，但构建独立复核的成本收益低 | 子任务2 |
| 历史污染数据一次性清洗 | 消费端过滤已足够，清洗 23,743 行历史数据风险大于收益 | 子任务2 |

## 验证
- `test_all_remaining.mjs`：8 项代码修复 + 2 组机制同步 + skill 关键词 + 幂等标记，全部 PASS
- 回归 `test_wargame_fixes.mjs` / `test_wargame_gaps.mjs`：ALL PASS
- `replay_attack.mjs`：7/7 攻击动作仍有对应防线
- 两版 `node --check` 通过；工具文件 sha 一致
- dsh 已重启（18:22）

## 诚实边界
- 性能伪优化规则是**正则启发式**："提升""快了"等非性能语境可能误报（已限定需同时无 e2e 工具调用，降低误报）
- skill 卡关键词补口语词后**未实测**是否真能命中 turn11 那种指令（关键词匹配是 `hay.includes`，需用户指令含这些词）
- 双副本 sha 泛化后的路径推断在跨盘符/软链场景可能失效
- CritBank 状态消费依赖 `crit_decay.py` 正确维护状态表；目前状态表 10 条全 active，过滤功能无实际 retired 数据可验
- 所有修复仍是**静态+单元级验证**，零真实会话触发证据（延续 FULL_WARGAME 的核心警告）
