# 证据生产工具（Evidence Tools）

> 2026-11-20 从 `D:/Brain/_cleanup_20261118/`（一个名字像"清理垃圾"的目录）收编。
> **工具的位置决定它的命运**——放在 cleanup 目录的证据工具，随时会被当垃圾删掉。

这四个工具是"合成心智"认识论免疫系统的**生产端**——
`citation_guard` 是"检验端"（决策引用幻觉就 FAIL），这四个是"造证据端"。

## 1. verify_arxiv_api.py — 权威源直连核实

```bash
# 默认：从 data/evidence/all_citations_20261120.txt 读编号，写 arxiv_verified_20261120.json
python tools/evidence/verify_arxiv_api.py
# 自定义输入输出
python tools/evidence/verify_arxiv_api.py <输入清单> <输出json>
```
- 用 arXiv 官方批量 API（`export.arxiv.org/api/query?id_list=`）一次拿真实标题+摘要
- **比逐篇 WebFetch 更可靠**——绕过任何中间转述（这正是 86 篇审计用的方法）
- 原始产出已存 `data/evidence/arxiv_verified_20261120.json`（86 篇，140KB）

## 2. extract_citations.py — 全量引用提取

- 扫描项目所有 .md/.json/.py/.mjs/.yaml，提取 arXiv 编号、GitHub issue、URL
- 输出按类型分组的清单（审计第一步：先建清单再核实）

## 3. rw_funnel.py — 读写漏斗诊断

- 从真实 `_trace.jsonl` 重建事件序列，过滤测试 sid
- 输出：read→write 转化率、连续读循环会话数、各 sid 读写失败分布
- 这是"识字率"类比的量化工具（当前基线：18.2%、6/8 会话读循环）

## 4. scan_citation_patterns.py — 可疑引用扫描

- 扫"百分比 + 模型名/基准名"组合模式，找可能编造的数字
- 与 `verify_arxiv_api.py` 配合：先扫可疑项，再权威源核实

## 与现有机制的关系

| 环节 | 工具 | 状态 |
|---|---|---|
| 造证据 | 本目录 4 个工具 | ✅ 已收编 |
| 存证据 | `config/citation_ledger.json`（104 条）+ `data/evidence/`（原始数据）| ✅ |
| 验证据 | `tools/citation_guard.py`（已接 run_all）| ✅ |
| 用证据 | `lineage/`（家谱）+ ADR Evidence 段 | ✅ |

**缺的一环**：这 4 个工具还没接入 run_all（它们是按需调用，不是每次跑）。
如需例行复核，可加 smoke test 验证脚本可导入/路径正确。
