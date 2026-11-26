# 部署：攻防演练暴露问题的统一修复（2026-11-26 17:3x）

> 依据 `WARGAME_FULL_AUDITOR_20261126.md`：识别 ≠ 阻止。
> 这次不再堆散补丁——做**统一安全闸门层**重构，一次修掉 8 个结构缺陷。

## 核心重构：safetyBlock 统一闸门

**旧设计的问题**：闸门散落在 turn-stopping 各处，各有各的一次性开关，
且 `continuations>=1`（:2237）会把**所有**闸门短路掉——这是最大漏洞。

**新设计**：
1. **位置**：`safetyBlock` 放在 `continuations` 短路**之前**（:2327 vs 短路 :2359）——
   无论 guardDecide 是否拦过，安全检查都会执行。
2. **统一标记**：`s.safetyFlags` 对象，五个标记源：
   - `forceStop`（D1 重复探测）
   - `criticRejected`（Critic C-REJECT）
   - `handoffBlocked`（F12 甩锅）
   - `semanticFail`（语义/用途/sha/重复写入检查）
   - `verifyFail`（verify_on_stop 溢出）
3. **持续拦截**：不再"拦一次就作废"。任一标记存在 → 每次 turn-stopping 都拦，
   直到标记被真实动作清除。
4. **跨轮持久**（gap 补修）：`safetyFlags` 存模块级 `safetyFlagsMap`（仿 goalAnchors），
   state 引用同一对象，turn/start **只清本轮计数、不清标记**。原设计每轮清零是漏洞，
   模型只要拖到下一轮就能绕过拦截。
5. **预算只升级措辞、不停止拦截**（gap 补修）：原设计每轮 3 次 / 每会话 8 次用完就放行，
   第 4 次甩锅穿透。改为**持续拦截**——预算只用来升级提示措辞（1-2 次温和、3-5 次强硬、
   6+ 次最后通牒），会话硬上限 20 是极端兜底（模型死活不调工具时避免永久卡死）。
6. **标记清除条件**（gap 补修后）：
   - `handoffBlocked`：任意工具调用（模型在行动而非甩锅）
   - `forceStop`：写/命令类工具（真正推进）
   - `verifyFail`：跑含 verify/test/compile 关键词的验证命令
   - `criticRejected`：**只由写/命令类工具清除**——原来"输出 >40 字含卡点/阶段性的报告就清"
     被 seq1649 的"阶段性卡点报告"命中，等于换说法即绕过，已删除
   - `semanticFail`：下一次写后语义检查通过自动清除

## 8 项修复逐条

| # | 演练暴露的缺陷 | 修复 |
|---|---|---|
| 1 | `continuations>=1` 短路让所有闸门失效 | safetyBlock 移到短路之前 |
| 2 | 硬闸门一次性（`hardGateInjected`），换说法就过 | 持续拦截预算 3/8 |
| 3 | 标记每轮重置，跨轮不延续 | safetyFlags 每轮重置（防污染），但 safetySessionBlocks 会话级累计 |
| 4 | 语义检查软 + 只查 slot 存在性 | 升级为 safetyFlags.semanticFail 硬标记 + slot 用途映射表 |
| 5 | 双副本 sha 与 [VERIFY] 抢 deepChecked 一次性名额 | 移到 verify-on-edit 每次写后（`checkDualCopy`），删除深检旧块 |
| 6 | forceStop 在探测循环中不触发（要求纯文本） | safetyBlock 不检查 lastMsgTC，循环中持续拦 |
| 7 | Critic REJECT 只 steer 一次 | criticRejected 硬标记 + 持续拦 + 状态报告才清 |
| 8 | verify_on_stop 溢出完全放行 | 置 verifyFail 标记交 safetyBlock，验证命令才清 |

## 新增能力
- **slot 用途映射**（`SLOT_USAGE`）：用户目标含"左侧/侧边栏/入口/sidebar"时，
  注入 `settings.*` / `conversation.composer.*` / `conversation.input.*` → 判错位。
  实测：要左侧+settings.section → 检出；要左侧+sidebar.pane.tab → 不误报；
  改崩溃+settings.section → 不误报。
- **连续相同写入检测**：`repeatedWriteCount`，第 2 次相同内容即置 semanticFail。
- **每次写后 sha 比对**：workspace 源 vs node_modules 安装副本。

## 验证
- `test_wargame_fixes.mjs`：8 项修复 + 两版一致性，全部 PASS
- `test_wargame_gaps.mjs`：4 个 gap 补修，全部 PASS
- `replay_attack.mjs`：用攻击脚本 7 个真实动作逐条回放，7/7 全有对应防线
- 两版 `node --check` 通过、7 个补丁幂等 `--check` 全通过
- dsh 已重启（17:41）

## 诚实边界
- 仍是**静态代码路径 + 单元级回放验证**，没有真实再跑一次受控实验——
  运行时标记清除的真实行为需实测。
- slot 用途映射基于 slot 名前缀规律（sidebar.*=导航等），已加存在性白名单
  （`settings.section` 在 asar 中不存在，只有 `settings.section.icon`）——
  DSH 若增加新 slot 前缀仍需维护映射表。
- 会话硬上限 20 是防死循环兜底：极端情况（模型 20 次都不调工具）仍会放行。
  真正解决需要 dsh 侧 veto 接口。
- `safetyFlags` 跨轮持久但跨会话不延续；`safetyBlockCount` 每轮重置用于措辞升级，
  `safetySessionBlocks` 会话级累计。
