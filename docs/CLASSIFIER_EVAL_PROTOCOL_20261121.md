# 本地分类器评测协议（2026-11-21）

> 缘起：用户问"现在值得试 86M 分类器吗"，并要求"用我们自己的历史数据测"。
> 本文定义**怎么测才算可信**——因为连续两次踩了"数据看着多其实是假的"的坑：
> ① 工具频次把 8 个累积快照当 8 会话（2849 → 去重 375）；
> ② 公开基准证明 standalone 攻击串的准确率预测不了"嵌在工具输出里"的真实表现。

---

## 一、三条铁律（违反任一条，结果作废）

1. **去重后再统计**：`_cur*.jsonl` 是同一会话的累积快照，callId 必须去重。
   - tool/call 用 `data.callId`；tool/result 用 `data.message.source.callId`
   - 去重后：**375 次调用 / 375 条唯一工具输出**（不是 2849）
2. **用 contextual 样本，不用 standalone 攻击串**：攻击必须嵌在真实工具输出里。
   - 629 条真实 agent 攻击基准：Prompt Guard 2 86M 默认阈值抓 6/629(1%)、单独攻击串 0/27；
     但 standalone 抓 27/27 的 detect-or 在嵌到工具输出后只剩 23%——正反例都证明上下文决定成败。
3. **不预设赢家**：86M / 22M / DeBERTa-v2 / jailbreak-detector-large 一起测，本机实测说话。
   - 同一基准里 86M 默认阈值 1%，`jailbreak-detector-large` 51%、`protectai-deberta-v2` 23%。

---

## 二、数据源（我们自己的历史流量）

| 数据 | 位置 | 用途 | 状态 |
|---|---|---|---|
| 良性工具输出 | `_cur*.jsonl` tool/result，按 callId 去重 | **375 条**，测 FPR；平均 979 字符 | ✅ 可用（已核对去重）|
| 注入测试串 | `tools/test_injection_scan.mjs` | 英/中注入模式，嵌到工具输出 | ✅ 可用（个位数，仅冒烟）|
| 真实注入命中 | `_trace.jsonl` kind=injection_hit | 92 条，作攻击样本 | ⚠️ 需检查是否含实际文本 |
| **推卡会话完整数据** | dsh API `GET /v1/sessions/{sid}/events?limit=10000`（**不能走 bridge CLI**）| **755 条完整 tool/result 文本 + 706 call，17 个不同任务会话** | ✅ 已提取到 `push_samples.json` |
| 各任务 _tmp_*_trace.jsonl | `D:/Brain/workspace/bench/` | 任务多样性 | 待扫 |

**⚠️ 踩坑记录**：`bridge.mjs events` 把每条记录 `.slice(0,300)` 截断，
tool/result 正文被切掉，看起来像"推卡会话没有 result 文本"——这是**显示截断**，不是数据缺失。
必须直接调 HTTP API（descriptor 在 `D:/Brain/dsh-data/session-bridge.json`）拿完整文本。
用户提醒"推卡会话肯定有读写工具调用"后才挖出：read 218 / write 52 / edit 37 / pwsh 239。

**样本现状**：375（SearXNG 单一任务）+ 755（17 个推卡多任务）= **1130 条良性工具输出**，
已达业界建议 1000 条下限，可做第一轮阈值标定。两个池子**分别报数**（任务分布不同）。

---

## 三、测什么（每个候选必须产出）

1. **本机 CPU 单次延迟**：5 次取中位；不许抄文献的 15-40ms 当本机结果
2. **阈值-召回/FPR 曲线**：至少 3 个阈值点，用嵌攻击的真实工具输出
3. **长文本处理**：>512 token 必须滑窗 + 重叠 + **max 聚合**（不是 mean）
4. **上下文对比**：同一攻击串 standalone vs 嵌入工具输出，分别报数（量化 contextual 差距）
5. **环境记录**：模型版本/量化/依赖版本/命令，全部写进报告

---

## 四、判据（什么结果算"值得上线"）

| 门槛 | 目标 | 来源 |
|---|---|---|
| 延迟 | <500ms（M7 闸门），理想 <50ms（实时注入） | LADDER preconditions |
| 召回 | 嵌攻击召回 ≥80%（L5），中文准确率 ≥92%（M9） | LADDER preconditions |
| FPR | 在自有良性流量上可标定到可接受水平（ refuse 98% 默认阈值不可用）| docs/CLASSIFIERS... |
| 泛化 | 不能只在一个 wrapper 模板上过拟合（跨 prompt 措辞测） | 629 攻击基准作者警告 |

**任何一条不满足 → 如实记录为未满足，不写成"有据可依"。**

---

## 五、产物与去向

- `tools/classifier_bench.py`：基准脚本（应能重复跑）
- `bench/` 或 `data/` 下的 JSON 结果（带版本/命令/参数）
- `docs/` 下的实测报告（含不确定项）
- 结果写回 `CAPABILITY_LADDER.yaml` 相关卡的 `data_gates`，
  让科技树上 M7/M9/L5/S6_model 从"假设闸门"变"有实测证据"

---

## 附：为什么这次不用公开数字拍板

- Prompt-Guard 86M 厂商称 <10ms，第三方测 60-65ms，某基准 149ms——**差 15 倍**，必须本机实测
- 默认阈值 FPR 98%（我们文档）vs in-distribution 0.6%（厂商）——**分布差异决定一切**
- Meta 自己建议"用 1000-10000 条自己的良性消息标定阈值"——公开数字不能直接搬

---

## 六、E 核绑定与延迟测量（2026-11-21 晚补，用户追问"怎么确保跑在 E 核"）

### 6.1 一个错误必须纠正
`torch.set_num_threads(4)` **只限制线程数量，不保证跑在 E 核**。Windows 调度器完全可能
把这 4 个线程放到 P 核。此前把"4 线程"称为"E 核约束"是错的。

### 6.2 P/E 核编号：用 CoreInfo 实证，不靠猜
微软 Sysinternals **CoreInfo v4.02**（`Coreinfo.exe -accepteula -c`）在本机的权威输出：
```
**--------------  Physical Processor 0    [P-CORE] (Hyperthreaded)
--**------------  Physical Processor 1    [P-CORE] (Hyperthreaded)
----**----------  Physical Processor 2    [P-CORE] (Hyperthreaded)
------**--------  Physical Processor 3    [P-CORE] (Hyperthreaded)
--------**------  Physical Processor 4    [P-CORE] (Hyperthreaded)
----------**----  Physical Processor 5    [P-CORE] (Hyperthreaded)
------------*---  Physical Processor 6    [E-CORE]
-------------*--  Physical Processor 7    [E-CORE]
--------------*-  Physical Processor 8    [E-CORE]
---------------*  Physical Processor 9    [E-CORE]
```
→ i7-12650H：**P 核 = 逻辑处理器 0-11**（6 核 × 2 超线程）；**E 核 = 12,13,14,15**（4 个单线程核）。

### 6.3 正确做法：绑定 + 读回自证
```python
psutil.Process().cpu_affinity([12,13,14,15])   # 先绑核
torch.set_num_threads(4)                       # 再设线程数（顺序重要）
actual = psutil.Process().cpu_affinity()        # 必须读回，写进结果 JSON
```
`bench/classifier_bench_v4.py` 已实现 `--cores e/p/all`，结果 JSON 的
`config.affinity` 含 `requested/actual/verified`，报告可自证跑在哪。

**限制**：沙箱派生进程被 CPU 限速、调度可能不遵守 affinity（实测绑 12-15 但负载溢出到其他核）。
故沙箱里的延迟数字是**参考值**；生产（计划任务启动）需复测。读回 verified=True 只证明"进程被标记绑定"，
不证明"OS 调度真的遵守"。

### 6.4 延迟数字的纠正（重要）
| 来源 | 数值 | 问题 |
|---|---|---|
| dsh v3 报告 | 1187ms/条 | batch10 均摊算法错误，把整批时间当单条 |
| v4 实测量 | **362.8ms**（E核短文本单条）<br>300.8ms（P核） | 正确：单条 512 token 内纯前向 |
| v4 长文本滑窗 | **单窗 1161ms / 8 窗共 9143ms**（E核） | 3481 token 长文本的真实开销 |

**结论**：短文本 0.36s 可接受（占 11s/步的 3%），但长文本滑窗 9 秒是致命的——
我们真实工具输出 24%-52% 超过 512 字符，接近一半的检测会掉进这个坑。

### 6.5 E 核 vs P 核对照（实测）
| 模式 | 短文本 | 长文本总 |
|---|---|---|
| E 核（12-15）| 362.8ms | 9143ms |
| P 核（0-3）| 300.8ms | 7847ms |

E 核慢约 **20%**。这印证"推理占满 P 核后只能用 E 核"要付 20% 溢价——
但 classifier 跑在 GPU 空闲间隙，这 0.36-9s 是**加在关键路径上**的，不是免费搭便车。

### 6.6 基准脚本的三处修正（v3→v4）
1. 攻击分层采样：v3 用 `all_attacks[:40]`，prepend(32)+append(8) 正好把 embedded_mid/benign_like 挤掉
2. 单条延迟 vs 长文本滑窗分开测（v3 只报 batch 均摊）
3. 多分类适配：`flowxai/injection` 是 4 分类，攻击类概率要求和非简单取 `[:,1]`
