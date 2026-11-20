# 文件读写能力：路线图优先级调整与新卡提案（2026-11-20）

> 用户："它的弱点在于读写文件，当务之急是赋予它高水平的读写能力，防止浪费大量时间写垃圾。
> 这个目标有哪些卡靠得比较近、优先级前提；有哪些可以做成新卡，调研并放进路线图。"

## 0. 证据基准（先摆事实，避免凭印象开卡）

### 0.1 真实 trace 工具失败率（过滤测试 sid，今天 2026-11-20）

| 工具 | OK | FAIL | 失败率 |
|---|---|---|---|
| **write** | 24 | 0 | **0%** |
| read | 169 | 7 | 4.0% |
| edit | 15 | 2 | 11.8% |
| grep | 21 | 3 | 12.5% |
| glob | 23 | 4 | 14.8% |
| **pwsh** | 102 | 20 | **16.4%** |

**关键结论**：`write` 工具本身 100% 成功——"读写能力弱"**不是写工具坏了**。
真正的浪费来自：①pwsh 跑 python/node 的 ENOENT/ParserError（16.4% 失败）
②edit old_string 匹配失败（11.8%）③写了 24 次却大多写到临时补丁脚本而非有效产物。

**垃圾率实证**：A1_6 一张卡留下 5 个临时补丁脚本（`_apply_fix.py`/`_apply_future_claim.py`/
`_fix_index.py`/`_patch_future_claim.py`/`fix_index.js`）全部"写了没应用"，最终归档到
`docs/archive/a16-patch-scripts/`。有效产物只有 index.mjs 一处改动。
**写 24 次 ≈ 5 个垃圾 + 1 个有效**——这是"浪费时间写垃圾"的直接量化。

**所以正确目标不是"让 write 更可靠"，而是"让 agent 少绕路、少写垃圾、写完必落盘"。**

### 0.2 harness 的控制边界（重要）

工具（write/edit/read/pwsh...）是 **dsh 原生**的，harness 只是旁观+注入（index.mjs 无工具注册，
只有 trail/trace 记录）。我们**改不了工具本身**，能控制的杠杆只有：
守卫（guardDecide L0-L3 + 将来时承诺）、CritBank 教训注入、派活 prompt、trace/审计。
→ 所以新卡都走"行为治理"路线，不开"改造 write 工具"这种无效卡。

### 0.3 今天的事故模式

1. **edit old_string 截断**：中文残片漏进 index.mjs（C-010）
2. **补丁脚本不应用**：反复写修复脚本却从没成功落地（A1_6，read 循环 + pwsh 死循环）
3. **pwsh 绕路**：agent 用 pwsh 跑 python/node，ENOENT/ParserError 反复失败
4. **"我将..."将来时承诺不落盘**：A1_6 守卫已治

## 1. 现有卡盘点与优先级调整（已落地）

| 卡 | 原状态 | 与读写能力的关系 | 调整 |
|---|---|---|---|
| **A3_5** 安全地基（真实diff+回滚）| done | 读写正确性地基：逐行 diff + sha256 前后校验 | cost 中→低（经验复用）|
| **M7** 格式修复器 | manual-blocked | edit 截断/格式错配的直接解药 | cost→低、benefit→高，值得评估解锁 |
| **S3** 频次 trace | done | 工具失败率画像的基础设施（本次分析就靠它）| cost→低 |
| A1 会记路（机器判据）| done | 判据可信是"写完验收"的前提 | 保持 |
| A1_5 判据元验证 | done | 防判据假绿 | 保持 |
| A1_6 将来时承诺守卫 | done | 防"说要写"不落盘 | 保持 |
| M4 工具面收敛 | manual-blocked | 减工具面→少 pwsh 绕路（治本但涉产品决策）| 保持 blocked，待用户拍板 |

**排序机制的坑**：`rank` 数字字段**根本没被代码读取**（grep 全库无引用）——
真正排序只看 `rank_hint` 分桶 + `benefit/cost` 分数（`sort_cards_by_roi()`）。
所以"优先级前提"的正确做法是改 `benefit/cost`/`rank_hint`，不是改 rank。已按此调整。

## 2. 新卡（已开，均 ready / deps=A1）

| id | 卡 | what | 为什么现在开 | 判据 |
|---|---|---|---|---|
| **S13** | verifyRan 收紧（read≠验证）| 把 `index.mjs:913` 的"read/cat 即 verifyRan"收紧为真实验证证据 | **假绿源头**：A1_6 连续 6 次 read 同段无 write 却一路绿灯 | test_verify_ran.py + file_grep |
| **S11** | 写后校验覆盖全部写工具 | verify-on-edit 从只认 write/edit 扩到 8 种写工具 | `DEFAULT_WRITE_TOOLS` 列了 8 种，`:1042` 只捕获 write/edit，其余 6 种零校验 | test_write_verify_all.py |
| **S12** | 补丁应用闭环（禁写脚本不落地）| 补丁脚本写入后必须有 apply 证据（目标 mtime+语法）| 一张卡 5 个补丁脚本全没应用——"写了脚本≠应用了脚本" | test_patch_applied.py |

三卡形成闭环：**S13 让"验证过"可信 → S11 让"所有写入都校验" → S12 让"写脚本必须落地"**。

## 3. 明确不做（避免重复证伪方向）

- ❌ **改造 write 工具本身**：trace 实证 write 0% 失败，工具没坏——造这种卡是浪费
- ❌ 无差别提高自动化频次（§8 已证伪）
- ❌ apply_patch 替代 edit（§8 已证伪：无稳定收益）
- ❌ 小模型做审计/纠正（§8：一致率 45-60% 近抛硬币）
- ❌ 堆更多 judge（§8：9 judge≈2 票）

## 4. 落地动作（已完成）

1. ✅ 优先级调整：A3_5/M7/S3 的 benefit/cost（真正生效的字段）
2. ✅ 开 3 张新卡 S11/S12/S13 进 ROADMAP_GRAPH + LADDER
3. ✅ `--refresh` 重排视图（24 张卡）
4. ⏳ 下一步：从 S13 开始推卡（假绿源头优先）

## 5. 调研来源

- Explore-1：现有卡盘点 + CritBank + rank 机制（发现 rank 数字是装饰品）
- Explore-2：harness 读写机制深挖（发现 8 写工具仅 2 个被校验、`:913` read 即验证）
- 主代理：trace 工具失败率硬证据 + A1_6 垃圾率量化 + 控制边界确认
