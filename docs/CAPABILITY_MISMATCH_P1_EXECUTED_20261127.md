# 能力错配 P1/P2 执行结果与验证（2026-11-27 15:15）

> 用户："全做"（含之前标注需拍板的工具面裁剪）
> 结论：P1 三项已做并验证；**P2 工具面裁剪核查后决定不执行**——有决定性证据表明不能安全做。

## 一、P1 三项（已做 + 验证）

| 项 | 改动 | 验证证据 |
|---|---|---|
| **P1-1 教训注入绝对路径** | `critbank.json` 两副本（运行时 `bench/` + 仓库 `config/`）的 `verify_agent.py` 改为 `D:/Brain/publish/dsh-behavior-guard/tools/verify_agent.py` | 运行时副本含绝对路径=True、裸文件名残留=0；修复会话 `269ec283` 的"没看到脚本"错配 |
| **P1-2 compaction 必留未闭环纠错** | ① `HESITATION_RE` 纳入 legacy 的"可能是个问题/是个错误"（原 miner 反而漏了 seq481 那句）；② 存档注入新增"【未闭环的自我纠错（具体值，压缩必留）】"，只保留含具体路径/值 + 有"恢复/改回/搞错/有问题"语义的 raw，最多 2 条；③ 新增 trace `unclosed_correction_preserved` | 真实 seq481 原句：`@local` 捕获=True、cands 含具体值=True、2/2 保留；真实会话 `1fdf8537` 的纯计划句 0/6 保留（过滤精度正确）；`reflection_mined` 真实触发 3 条 |
| **P1-3 注入去重** | 发现并修复**我自己引入的回归**：`reflectionCandidates.length` 进了 archiveSig 会让"相同存档"签名每步变化、破坏 82 次重复的去重；同时让"未闭环纠错具体值"在去重分支里穿透（否则重复 compaction 仍会抹掉） | 签名行不含 reflectionCandidates=True；`_preserve = parts.filter` 存在=True |

**意外发现的能力错配**：我上一轮新写的 HVR miner 反而漏了 `captureOpenCorrection` 当初专门为 seq481 事故设计的窄正则模式（"可能是个问题"）。这印证了一条纪律——**替换旧机制时必须把旧机制的事故样本作为回归用例**，否则会重新踩同一个坑。已用 seq481 原句做验证。

## 二、P2 工具面裁剪：核查后决定不执行（重要）

用户授权"全做"，但核查发现**不能安全裁剪**，按纪律不做：

### 决定性证据

1. **schema 不在 harness 可控范围**：工具定义/ schema 在 dsh 客户端 `app.asar` 内；harness 全文件 `registerTool`/`addTool` 为 0 处，只是 `session/event` observer。
2. **`disabled` 配置无强制力**（两个反例）：
   - `web_fetch` 同时被 `DISABLED_TOOLS` 和 `cordis.patch.yml:413 fetch:false` 双重"禁用"，仍在 11-19~11-25 被调用 **1948 次**（单日最高 276）
   - `spawn_teammate` 所在 delegation 组 11-18 前已 `disabled: true`，仍在 11-18~11-25 被调用 **719 次**（单日最高 207）
3. **三条裁剪路径都不可靠**：
   - A 扩展 `DISABLED_TOOLS`：注释明写"不改行为只提示"（index.mjs:450），每工具只警告一次，占用注入预算
   - B 改 `cordis.patch.yml`：名义禁用实证不可靠，且低频必需工具（spawn_teammate/read_image/skill）误裁风险大，还会连带 web 服务故障
   - C prompt 告知子集：schema 仍在上下文，**不省 token**（已在 AGENTS.md:146-151 + skill tool-boundaries 做了）
4. **历史已拍板放弃**：`EVENTS.md:374`（2026-11-22）"科技树工具面重设计（放弃'砍到 N 个'）"。

### 实际工具使用分布（30708 条有效调用）

top-5：write 11085 / read 6251 / present 4939 / pwsh 3459 / web_fetch 1948(标禁用)。
**最近窗口 web_fetch = 0**——说明行为已在收敛，不需要强制裁剪。

长尾零使用工具（job_*/bash/exit_plan_mode/compact/subagent_fork 等）多数已在 `cordis.patch.yml` 静态 disabled。但**零调用 ≠ 可裁**——spawn_teammate 就是在"已 disabled"状态下仍被调用 719 次。

### 执行决定

- **不动** `cordis.patch.yml` 插件挂载、不动 `DISABLED_TOOLS`
- **保留**现有诊断指标：`tools/trace_report.py` 已有工具分布 top-10 报告
- 继续路径 C（AGENTS.md 语义边界表），零风险

## 三、全量回归

```
test_audit_allfix         25 PASS / 0 FAIL
test_wargame_fixes        ALL PASS
test_wargame_gaps         ALL PASS
test_all_remaining        ALL PASS
test_format_correction    全部通过
test_format_executor_result 全部通过
test_collect_corrector_input 19/19
test_reflection_miner     21/21
wargame_fixed_verify      24 PASS / 0 FAIL
模块 import + apply       OK
两版 sha256               一致
```

## 四、诚实边界

1. **P1-2 的 `unclosed_correction_preserved` 埋点未在真实 compaction 中触发**——短会话没有压缩。单测 + 过滤精度验证通过，但缺真实会话证据。
2. **critbank 两副本本来就内容不同**（config 2 处 vs 运行时 10 条），这次只同步了 verify_agent 路径，副本漂移是已知技术债，未根治。
3. **P1-1 只改数据没改代码**——如果未来 watcher 重新生成 critbank 且用裸文件名，会复发。根治需要改生成脚本（未做）。
4. 工具面"不裁剪"是**主动决策**，不是没做——有 1948 次/719 次两个反例支撑。
5. 本次没有证明"错误率下降"，只证明机制生效 + 误拦消失。

## 五、下一步（仍未做）

- 跨会话 A/B：开/关错题本与反思捕获，统计同类错误率
- 候选 0.85 相似度去重（本次观察到同句被多正则命中）
- verified 接真实验证器（当前 confidence>=0.85 兜底）
- 长会话触发 compaction，验证 `unclosed_correction_preserved > 0`
- critbank 两副本统一 + 生成脚本根治裸文件名
