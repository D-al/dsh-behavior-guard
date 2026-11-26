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
4. **预算上限防死循环**：每轮 3 次、每会话 8 次（`safetyBlockCount`/`safetySessionBlocks`），
   用完打 `safety_gate_exhausted` trace 后放行——避免无限循环卡死会话。
5. **标记清除条件**：
   - `handoffBlocked`：任意工具调用（模型在行动而非甩锅）
   - `forceStop`：写/命令类工具（真正推进）
   - `verifyFail`：跑含 verify/test/compile 关键词的验证命令
   - `criticRejected`：输出 >40 字且含"卡点/阶段性/已完成"等的状态报告
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
- `replay_attack.mjs`：用攻击脚本 7 个真实动作逐条回放，全部有对应防线
- 两版 `node --check` 通过、幂等 `--check` 通过
- dsh 已重启（17:37）

## 诚实边界
- 仍是**静态代码路径 + 单元级回放验证**，没有真实再跑一次受控实验——
  运行时标记清除的真实行为（尤其"状态报告清 criticRejected"的正则）需实测。
- slot 用途映射基于 slot 名前缀规律（sidebar.*=导航等），
  DSH 若增加新 slot 前缀可能误报/漏报——映射表可配置但需维护。
- 预算 3/8 是防死循环的妥协：用完仍会放行。若模型在预算内不改，最终仍能 completed——
  真正解决需要 dsh 侧 veto 接口。
- `safetyBlockCount` 每轮重置，`safetySessionBlocks` 会话级；跨会话不延续。
