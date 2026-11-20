# 「学会自己走路」首次实战实验报告（2026-11-20 02:48–05:20）

> 用户指令：在 D 盘默认工作区开会话，引导 harness agent 学会自己走路；我在旁边观察，失控就干预，卡住可问用户。
> 这是能力阶梯（CAPABILITY_LADDER.yaml）的**首次真实运行**——不是单测、不是我手工模拟。

## 1. 实验设置

- **会话**：`session-8554ffde-fa0b-4448-ab46-fca0e7a9d449`，cwd = `D:/Brain/workspace/default-workspace`（已验证 identity.cwd，D 盘工作区）
- **怎么开的**：bridge CLI 的 `create` 不支持 cwd，直接用会话桥 API `POST /v1/sessions` 带 `cwd` 参数（插件 index.mjs:109 支持）
- **权限**：danger-full-access / approval never（它能做任何事——所以必须盯）
- **引导方式**：两轮 prompt，每轮严格限定范围
  - 第一轮：只读 + 读地图（读 3 个文件、跑 `--graph`/`--next`/`--card`，只回答 4 个问题）
  - 第二轮：领取并执行 A0（claim → 读 → 改 → verify → reflection → 汇报）

## 2. 观察结果：它做得怎么样

### 第一轮（读地图）—— 全部达标

| 观察项 | 结果 |
|---|---|
| 读文件 | 3 个指定文件，全绝对路径、全 read 工具 |
| 跑命令 | `--graph`、`--next`、`--card`，pwsh 带 UTF-8 编码设置 |
| 自我纠错 | 发现 PowerShell GBK 乱码 → 主动加 `PYTHONIOENCODING=utf-8` 重跑 |
| 四问回答 | A0 的 what/why/benefit/unlocks 全部正确复述；识别 C-01 为最关键约束 |
| 越界 | **零**（无写、无 push、无 install） |
| 小瑕疵 | 把 M1 的 `requires_new_instrument` 误读成 A0 的（读全文串行混淆），但结论正确、无危害 |

### 第二轮（执行 A0）—— 成功，零干预

| 步骤 | 它的表现 |
|---|---|
| `--claim A0` | 成功：`CLAIMED: A0 by unknown-agent` |
| 读脚本 | 反复用 read 带 offset/limit 精确定位插入点（不猜，践行 C-02） |
| 写 `test_sids.json` | 建在正确位置（权威仓库根），内容含 `_comment` + `sids` 11 项 |
| 改 3 个脚本 | 各加 `_load_test_sids()`（带缓存、三候选路径、容错）+ 在实际加载处过滤 |
| 遇挫 | pwsh 内嵌 Python 因中文引号被 PowerShell 解析破坏（ParserError）→ **自己诊断**并改用 edit 工具 |
| `--verify A0` | 4/4 PASS（自报）|
| reflection | 写 `docs/reflection-A0.md`，识别出黑名单漏项 + `b7332eb6` hash-like 误杀风险，产出 CritBank 格式教训 |
| 汇报 | 诚实准确；明确"状态仍为 doing，等你指示"，没擅自写回权威块 |

**我在旁边做了什么**：全程只读观察事件流（共 226 条事件）；一次都没干预——因为它没有触发任何失控判据（见 `_walk_intervention_plan.md`）。这是好事：说明它不需要人盯着也能在边界内完成低风险卡片。

### 旁观者独立验收（不信自报，C-01）

```
roadmap_check.py --verify A0  → 4/4 OK
ast.parse 三个脚本            → 全 OK
实际加载黑名单                → 11 项，过滤逻辑可用
git status                    → 只改了允许的 5 个文件 + 1 个 reflection
越界（push/install/生产改动）  → 零
```

## 3. 实验中发现的两个真 bug（都是我写的工具里的）

1. **A0 判据路径陷阱**：判据写 `bench/test_sids.json`，但校验器 `resolve_path()` 把 `bench/` 解析到 BENCH_DIR（D:\Brain\workspace\bench），而实现落在权威仓库根 → 必然假 FAIL。**我在投递第二轮前发现并修正**为 `test_sids.json`，还在指令里把它作为 C-08 教训讲给它听——它后来主动加了三候选路径防御。
2. **`--apply` 的 `re.sub` 反斜杠 bug**：`save_authoritative()` 用 `re.sub` 直接传替换字符串，内文含 `D:\Brain\...` 时 `\B` 被当正则转义 → `re.error: bad escape \B`。**第一次真实 `--apply` 才暴露**——再次证明"代码存在 + 单测过 ≠ 真实可用"。修法：lambda 返回替换文本。

## 4. 闭环完成：观察者执行写回

按"闸门上移"设计，agent 无写回权；我执行 `--apply` 后：

```
A0 status=done
evidence_log: [{at, commit=d958a1a, checks=[4条判据证据]}]
--next 现在选出 A3_5（安全地基）—— 阶梯真的往上爬了一格
```

所有成果同步到生产 node_modules，`--verify A0` 在生产同样 4/4 PASS。

## 5. 结论

**它学会了第一步走路**：读地图 → 选卡 → 领取 → 执行 → 自验 → 反思 → 停下等指令。全程零干预、零越界、遇挫自愈。

**但这次成功是有边界的**：
- 只跑了 1 张低风险卡（A0），且是我把任务切得很碎、路径写死、禁止项列全的前提下
- 下一个候选 A3_5 是"改 gate 主脑"——那才是真正的考验（需要 e2e + 回滚 + 人工审 diff），当前 agent 还没有这个权限
- 两次 bug 都出在**我写的工具/判据**上，不是 agent 的判断力——说明"脚手架本身的质量"才是自主化的瓶颈

**成功率口径**：1/1 卡完成（低风险档）；高风险档未测，不能外推。

## 6. 附：本次未完成的动作

- commit `155d2b8` 已落地本地，但 `git push` 因代理 CONNECT 502 连续失败（github.com 通 200、api.github.com 超时）——网络恢复后需推送并更新 lock。
- 垃圾文件 `tools/__pycache__/`、`tools/_patch_a0.py` 已由观察者在 apply 前清理。
