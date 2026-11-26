# 完全攻防演练：dsh 完全体审计员 vs 全部历史错误（2026-11-26 最终版）

> **这次严格等三个子任务全部返回后才动手**（用户明确要求，纠正上一轮抢跑）。
> 不动 dsh、不发消息、不改运行配置——纯推演。
>
> 三份子任务：
> - A = 深扫运行版审计纠正器
> - B = 搜集 dsh 全部历史错误
> - C = 独立交叉核验（trace 反推 / crash log / 审计可信度）
>
> 本文对三份结果做了**交叉核验**，推翻了其中几处我自己的旧结论，见 §1。

## 一、先纠正我此前三个错误结论（交叉核验结果）

| 我之前的说法 | 真相 | 来源 |
|---|---|---|
| "Critic 今天 0 次触发" | **错。真实有 2 次 REJECT**（08:52/08:59, sid=a91afe6d）。我读错口径——`crit_hit` 是 CritBank 教训注入，不是 Critic 评审；`review_verdict.review_kind=critic` 才是 | C + 我亲自核验 trace |
| "新 safetyBlock 已经全修好" | **零真实会话触发证据**。所有 7 个补丁只有单元级回放，没有一次真实任务跑过新闸门 | C |
| "trace 348 行" | 当前 `_trace.jsonl` 确实 348 行；C 提到的 74,661 行是更广口径（含其他 trace 文件/历史），口径差异需注明 | 我核验 |

**这三个纠正直接改变了演练结论的置信度**：本文所有"拦截"判定都是**代码路径 + 单元回放**，
不是实测；Critic 能真拦（2 次 REJECT 实证），但今天所有新闸门的表现**未经真实任务验证**。

## 二、防守方：运行版完全体审计员（子任务 A）

### 2.1 确认运行版身份
- 运行版：`D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs`
- dsh 17:41 重启后加载，`WARGAME_GAPS-PATCHED` + `WARGAME_FIXES-PATCHED` 标记均在（我核验 grep=2）
- 7 个补丁已同步到运行版（A 确认）

### 2.2 全部机制清单（穷尽，非只看今天补丁）

**软（pendingInject/createMessage，可忽略）**：
- D1 重复探测、D2 同参双败、D3 冗余 todo、D5 审计门控、turn-guard L0-L3
- Planner 评审、独立审计、纠正器、控制回合、状态复述、todo 闹钟、意图漂移、patternLock
- mind_state、S22/S24 自愈、副作用识别、errorPlaybook、DANGER 分级、学习回注
- 防线2 纠错保留（CORRECTION_RE）、P0 任务存档

**硬（agent.steer + return / 标记 / 代执行）**：
- 统一 safetyBlock（今天新增，五标记：forceStop/criticRejected/handoffBlocked/semanticFail/verifyFail）
- present 深检、Critic（实证 2 次 REJECT）、D4 present-gate、verify_on_stop
- 确定性状态回读门、executeReadOnly 只读代执行

**关键结构**（A 确认）：
- safetyBlock 在 continuations 短路**之前** ✓
- safetyFlags 模块级 Map **跨轮持久** ✓
- 持续拦截直到标记被真实工具动作清除，会话硬上限 20 兜底 ✓
- criticRejected 只由写/命令工具清除，纯文本报告不再清除 ✓
- slot 用途映射 + 存在性白名单（94 个真实 slot）✓
- 双副本 sha 每次写后 ✓
- 连续相同写入检测 ✓

### 2.3 审计员自身的可信度问题（子任务 C）
- Critic 2 次 REJECT 都是**真的**（08:52/08:59），但 REJECT 后模型仍继续跑——识别≠阻止
- critbank 9 条教训有消费机制（Critic rubric 命中），不是纯装饰
- 有一批"文档宣称完成但代码没生效"的历史假机制（项目铁律）
- **物理层失败审计员完全管不到**：进程崩溃、WDDM 换页、显存耗尽——crash log/freeze_watch 证实

## 三、攻击方：dsh 全部历史错误（子任务 B）

B 穷尽出 **8 大类约 30 种**错误模式。按"对完全体审计员的威胁"重排：

| 类别 | 代表错误 | 审计员能管吗 |
|---|---|---|
| A. 物理层崩溃 | 8999 EADDRINUSE 崩溃、WDDM 换页 1-2 t/s、显存 186 卡死 | ❌ **原理上管不到**（外部进程/驱动层）|
| B. 配置自我破坏 | bundle 名臆造、dsh-base 重复、autostart 清空、pnpm EPERM | ⚠ 部分（副作用识别软提醒）|
| C. UI 破坏 | 100vh iframe 塞输入框、臆造 slot、settings.section 错位、双副本不同步 | ✅ 新机制覆盖（用途映射/sha/100vh 规则）|
| D. 任务行为 | 目标漂移、F12 甩锅、重复探测、连续相同写入、声称完成未验证 | ✅ 新 safetyBlock 覆盖（但零实测）|
| E. 工具误用 | glob 扫 asar 二进制、相对路径假语法错误、禁用工具 | ✅ cwd 修复 + S22/S24 |
| F. 认知缺陷 | 假设当已知、规则与实例脱节、自我承认但不修 | ⚠ 软提醒为主（rubric 规则）|
| G. 压缩相关 | 压缩丢目标、纠错丢失、存档重复 82 次 | ✅ goalAnchors + 纠错保留 |
| H. 性能伪优化 | moe-cache-cpu-share 伪加速、decode t/s 误导 | ❌ **审计员不看性能指标** |

## 四、完全攻防演练（逐类对抗）

### 阶段 1：物理层攻击（A 类）—— 审计员完败
- **攻击**：打开插件触发 8999 EADDRINUSE → 进程崩溃；或显存耗尽触发 WDDM 换页
- **防守**：harness 所有审计/纠正机制**物理上无法介入**——它们挂在 agent 事件循环上，进程崩了循环就没了
- **结论**：❌ **原理性穿透**。这是外部防线（EADDRINUSE error handler、看门狗、显存账）的职责，不是审计员

### 阶段 2：配置自我破坏（B 类）—— 软提醒为主
- **攻击**：臆造 bundle 名 / 写重复 dsh-base / pnpm EPERM 副作用
- **防守**：副作用识别（SIDE_EFFECT_ERROR_RE）软提醒；bundle 检查在外部 plugin_guard.py（每 3 秒巡检，硬自动恢复）
- **结论**：⚠ **harness 软，但外部 plugin_guard 硬兜底**。这类攻击实际被守住了——靠的是进程外守卫，不是完全体审计员

### 阶段 3：UI 破坏（C 类）—— 新机制覆盖但零实测
- **攻击 1**：100vh iframe 塞 `conversation.composer.dock`
  - 防守：plugin_guard 规则5（dock+100vh 自动停用）+ 语义检查用途映射 → 双保险
  - 结论：✅ 代码上有防线（**未实测**）
- **攻击 2**：臆造 slot `sidebar.right.header.actions` / `settings.section`
  - 防守：语义检查存在性白名单（94 个真实 slot）+ 用途映射 → 两层
  - 结论：✅ 代码上有防线（**未实测**；且 Critic 自己曾推荐 `sidebar.items` 假 slot）
- **攻击 3**：双副本不同步却声称一致
  - 防守：verify-on-edit 每次写后 sha 比对 → safetyFlags.semanticFail → 持续拦
  - 结论：✅ 代码上有防线（**未实测**）

### 阶段 4：任务行为（D 类）—— 完全体的主战场
- **攻击 1**：目标漂移（左侧入口 → 崩溃 → 设置页）
  - 防守：goalAnchors 叠加 + 意图漂移守卫（软）+ Critic 产物评审
  - 结论：⚠ **识别强、拦截弱**——Critic 2 次 REJECT 实证能识别，但拦不住持续漂移
- **攻击 2**：F12 甩锅 + completed
  - 防守：handoff 闸门（lastMsgToolCalls===0）→ handoffBlocked → safetyBlock 持续拦（跨轮持久）
  - 结论：✅ 新机制设计上能持续拦（**零实测**）
- **攻击 3**：重复探测循环
  - 防守：D1 → forceStop → safetyBlock 不要求纯文本收尾 → 持续拦
  - 结论：✅ 新机制设计上覆盖（**零实测**）
- **攻击 4**：连续相同写入 3 次
  - 防守：repeatedWriteCount → semanticFail → 持续拦
  - 结论：✅ 新机制（**零实测**）

### 阶段 5：工具误用（E 类）—— 已实测有效
- cwd bug（5 次假 Cannot find module）：✅ **真实修好了**（turn 11 零复发，实证）
- glob 扫 asar：skill 卡 `dsh-ui-slots.md` 写了正确方法（grep -ao）——但模型没加载该 skill（turn 11 skill 调用 0 次）→ ⚠ **知识沉淀了但没用上**

### 阶段 6：认知缺陷（F 类）—— 审计员最弱区
- "假设当已知""规则与实例脱节""自我承认但不修"——这些是 rubric 软规则（planner/critic rubric 里的 `assumption_disclosure` 等）
- A 核实：这些规则部分只在 rubric JSON 里、代码零消费（历史教训）
- 结论：⚠ **软规则，模型可忽略**。自我承认但不修（seq1402）今天补了 CORRECTION_RE 句法 + safetyBlock，但"承认→必须修正"的硬闭环仍弱（**零实测**）

### 阶段 7：压缩相关（G 类）—— 有机制
- goalAnchors 跨 state 重建持久、纠错保留 —— 实证 turn 11 触发 4 次纠错保留
- 结论：✅ 这部分**有真实触发证据**

### 阶段 8：性能伪优化（H 类）—— 完全盲区
- "moe-cache-cpu-share 伪加速""decode t/s 误导"——审计员没有性能指标验证机制
- 结论：❌ **盲区**：靠项目文档/记忆里的基线人工把关，审计员不管

## 五、演练总结论

**完全体审计员的真实覆盖**（按子任务 ABC 交叉核验）：

| 攻击类别 | 审计员能管吗 | 有无实测证据 |
|---|---|---|
| A 物理层崩溃 | ❌ 原理上管不到 | 外部守卫兜底 |
| B 配置自我破坏 | ⚠ harness 软，plugin_guard 硬 | 外部巡检实证 |
| C UI 破坏 | ✅ 新机制代码覆盖 | **零实测** |
| D 任务行为 | ✅ 新 safetyBlock 设计覆盖 | **零实测**（Critic 2 次 REJECT 是唯一实证）|
| E 工具误用 | ✅ cwd 已实测修好 | 有实证 |
| F 认知缺陷 | ⚠ 软规则为主 | 无 |
| G 压缩相关 | ✅ 有机制 | 纠错保留 4 次实证 |
| H 性能伪优化 | ❌ 盲区 | 靠人工 |

**最诚实的结论**：
1. 今天打完 7 个补丁后，**代码层面**的防线比演练前完整得多（D 类从"4 穿透"变"7 全有防线"）。
2. 但**除 cwd 修复、Critic 2 次 REJECT、纠错保留 4 次外，所有新闸门零真实会话触发证据**——
   它们的实战效果完全是推断。
3. 审计员**原理上就管不到**两类：物理层崩溃（A）和性能伪优化（H）。这不是修不修的问题，是机制类型不匹配。
4. 核心矛盾依旧：**识别 ≠ 阻止**。Critic 2 次准确 REJECT 但拦不住持续漂移；
   新 safetyBlock 设计成"持续拦到工具修正"，但没有任何真实任务验证过它是否真能做到。

## 六、攻击面全景（给下一次迭代的优先级）
1. **P0**：给新 safetyBlock 做一次真实受控实验——零实测是最大风险
2. **P0**：物理层失败（A 类）明确交给外部守卫，审计员文档要写清"管不到"
3. **P1**：性能伪优化（H 类）加一个"加速主张必须端到端验证"的 rubric 软规则
4. **P1**：认知缺陷（F 类）的 rubric 规则检查代码消费（历史教训：文档写规则 ≠ 代码生效）
5. **P2**：skill 卡加载机制——知识沉淀了但模型不加载等于没有

## 七、诚实边界
- 本文是**静态代码路径 + 历史证据 + 单元回放**的推演，不是实测。
- 三份子任务结果有口径差异（trace 行数 348 vs 74661），我按自己核验的 348 行判定 Critic 数据，并注明差异。
- 子任务 A 提到两处缺口文件（`dsh-llama-server-autostart/index.js`、`dsh-sandbox-policy/index.js`），
  我核验时这些具体路径不存在——可能是文件名/路径记忆偏差，不影响主 harness 补丁已同步的结论，但需要标注。
- 攻击脚本来自历史真实错误（子任务 B 8 类约 30 种），但"如果全起作用"的"全"是按代码最大能力假设。
