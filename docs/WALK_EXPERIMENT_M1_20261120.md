# 「学会自己走路」第三张卡 M1 实验报告（2026-11-20 14:35–15:05）

> 用户离开前指令："尽量引导它一直更新下去；重大决策弹选项；每隔一段时间深度维护防止走偏。"
> 本卡全程按此执行：2 次 AskUserQuestion（是否爬 M1 / 白名单冲突怎么处理），9 轮深度维护。

## 1. 用户决策点（弹选项）

| # | 问题 | 用户选择 |
|---|---|---|
| 1 | `--next` 选出 M1（首张改 index.mjs 主循环的器官卡），爬不爬？ | **让它爬 M1** |
| 2 | 深度维护发现 M1 要求改主循环逻辑，但白名单只允许"文案措辞" | **开新 surface 让 agent 爬** |

据决策 2 新增 `SURF-EPISODIC-INJECT`（surfaces.json 第 7 项）：allows 控制回合 episodic 检索 + evidence_cited 埋点；forbids D1-D5/GWT/FEP/注入频率/测试 sid。

## 2. M1 成果（观察者接管实现）

agent claim 后陷入长会话退化（反复 `read index.mjs limit=4/6`），按预设接管阈值由观察者实现：
- `index.mjs` 控制回合（1891 行）接入 `tools/episodic_search.py` 的 top-3 + `trace({kind:'evidence_cited'})`
- 复用已有 `episodicSearchEnabled` 开关（此前是死开关）
- 只进控制回合 prompt，不占运行时注入通道（ADR-0017）
- `docs/reflection-M1.md`（含两条 CritBank 教训）

**真实证据**：`_trace.jsonl` 中 `kind:evidence_cited, sid:8554ffde, step:8, cited:3`（真实会话、过滤测试 sid 后 count=1）。

## 3. 九轮深度维护中修复的真 bug

| # | bug | 修复 |
|---|-----|------|
| 1 | 人类进度表只列 A 系列，漏 M1（用户最早指出的问题残余）| `save_authoritative` 遍历 rungs+items |
| 2 | `GUARD_MANIFEST.yaml` 漏 surfaces.json | 补入 key_files |
| 3 | `file_diff` 逐行比对 → 纯插入使后续行偏移假报修改 | 改 difflib.SequenceMatcher LCS |
| 4 | `real_diff_check` 只取第一个 token → 多 token target 后半永不匹配 | 匹配全部 token |
| 5 | 逐行判定 → 整段功能代码的通用行(try/{/const q)被误拒 | 改连续块级判定 |
| 6 | 我改权威 index.mjs 后没同步生产就重启 → trace 不产生新 kind | 同步生产→重启→多步会话触发（我自己也踩了"权威≠生产"）|

**关键教训**：白名单 diff 校验从"改一行文案"升级到"插入整段功能"必须做块级判定 + LCS——这是 A3_5 设计的固有局限，M1 首次暴露。

## 4. agent 提交尝试（诚实记录）

按用户"让它向 GitHub 提交"的要求，3 次 steer 让它 commit/push：
- 前两次（A0/A3_5 之后）：**成功**——它自己执行了 commit + push（6a08e97），我 clone 远端实测人类进度表确实在 GitHub 上
- M1 这次：3 次 steer 均被退化循环吞掉（反复 read 同一区域），**观察者接管提交**（ed3e83f）

不是能力问题——是长会话退化（同一会话累计 ~100 步、多次压缩）。下次该换新会话而不是继续 steer。

## 5. 最终验收（全绿）

```
verify M1: 3/3 (含 real-sid evidence_cited=1)
self_test: 14/14 | a35_real_diff: 4/4 | run_all: 17/17
node --check index.mjs: OK
push: ed3e83f (本地=远端) | lock 收敛 | guard: 37 PASS + 1 UNKNOWN(真实) exit 0
权威 vs 生产: 8 文件同步
能力阶梯: A0 ✅ → A3_5 ✅ → M1 ✅，--next 现为 M8
```

## 6. 对"一直更新"的建议（给下一轮）

- 下一卡 M8（轨迹 FSM）需要新建 eval_fsm.py + held-out AUROC≥0.85——**是真正的新代码卡**，比 M1 更重
- **必须换新会话**：当前会话已严重退化，继续 steer 无效
- 每卡都要做"权威→生产同步 + 重启 + 真实会话触发"才能验 trace 类判据
- 保持 9 轮深度维护的节奏：每 ~5 分钟跑一次 guard + 全套回归
