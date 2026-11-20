# ROADMAP GRAPH — 机器权威块（agent 读写，人勿手改）

> 本文件是路线图状态的**唯一真相源**：`tools/roadmap_check.py` 从这里读卡片、写回状态。
> 人类可读视图在 [ROADMAP.md](ROADMAP.md) §1-§8 + 自动进度表。
> 语义字段（what/why/caveats/reflection）在 [CAPABILITY_LADDER.yaml](CAPABILITY_LADDER.yaml)。
> 三个文件靠 `ROADMAP_GRAPH_BEGIN/END` 标记与执行器解耦；移动/重命名需同步执行器常量。

<!-- ROADMAP_GRAPH_BEGIN v1 -->
schema_version: 1
authoritative: true
note: agent 读此块选卡；完整成长卡片(what/why/benefit/caveats/reflection)在 CAPABILITY_LADDER.yaml
status_enum:
- backlog
- ready
- doing
- done
- manual-blocked
anchors:
  ground:
    status: done
    note: 地基 v2.8-v2.12：outcome/GWT/安全规则
  S1_data:
    status: done
    artifact: _evidence_bundle.json
    note: 8147 行 trace 聚类
  GWT_FEP:
    status: done
    verify: test_gwt_fep.mjs 9/9 + trace kind fep_cycle>0
  M4_budget:
    status: done
    verify: test_injection_budget.mjs 5/5
  S1_p0p2:
    status: done
    verify: self_harness_gate.py 10/10 + candidate-1.json
  CritBank:
    status: done
    verify: _critbank_state.json 真实计数
  S6_rule:
    status: done
    verify: test_injection_scan.mjs 6/6 + trace kind injection_hit>0
    note: 规则层已在线，模型层 86M 未做
edges:
- - M1
  - ground
- - M1
  - S1_data
- - M1
  - GWT_FEP
- - M8
  - S1_data
- - M3
  - GWT_FEP
- - M9
  - M3
- - M2
  - GWT_FEP
- - S6_model
  - S6_rule
- - L6
  - M8
- - L1
  - M1
- - L1
  - M3
- - L1
  - M9
- - L8
  - GWT_FEP
- - A1
  - A0
- - A2
  - A1
- - A3
  - A2
- - A4
  - A3_5
- - A5
  - A1
- - A5
  - A2
- - A5
  - A3
- - A5
  - A3_5
- - A5
  - A4
items:
- id: M1
  tier: 1
  deps:
  - ground
  - S1_data
  - GWT_FEP
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_grep
    path: index.mjs
    regex: es\.exe.*top-3|ES_EXE.*top3
    min: 1
  - kind: file_grep
    path: index.mjs
    regex: 'kind: ''evidence_cited'''
    min: 1
    note: 埋点存在性
  - kind: trace_count
    source: _trace.jsonl
    kind_name: evidence_cited
    sid_filter: exclude_tests
    min: 1
    note: 埋点后真实会话跑一次
  claimed_at: '2026-11-20T06:38:36.373402+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T06:59:04.502943+00:00'
  evidence_log:
  - at: '2026-11-20T06:59:04.502943+00:00'
    commit: 6a08e97
    checks:
    - 1 hits in index.mjs
    - 1 hits in index.mjs
    - evidence_cited=1 (real sid)
- id: M8
  tier: 1
  deps:
  - S1_data
  risk: low
  autonomous: true
  status: ready
  verify:
  - kind: file_exists
    path: tools/eval_fsm.py
  - kind: json_field
    path: _fsm_eval.json
    field: heldout_auc
    op: '>='
    value: 0.85
  - kind: file_grep
    path: index.mjs
    regex: fsm.*signal|FSM_SIGNAL
    min: 1
- id: M3
  tier: 2
  deps:
  - GWT_FEP
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: file_exists
    path: tools/test_bdi_slots.mjs
  - kind: test_pass
    cmd: node tools/test_bdi_slots.mjs
    min: 5
  - kind: trace_count
    source: _trace.jsonl
    kind_name: mind_state
    sid_filter: exclude_tests
    min: 1
    note: BDI 三槽写进现有 mind_state kind，不新造 kind
- id: M9
  tier: 2
  deps:
  - M3
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 需验证中文表现 + embedding 编码器（8G 显存硬约束）
- id: M2
  tier: 2
  deps:
  - GWT_FEP
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: file_grep
    path: index.mjs
    regex: parentId
    min: 1
  - kind: test_pass
    cmd: node tools/test_trace_context.mjs
    min: 5
- id: M5
  tier: 3
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 用户拍板'哪些进内核'——价值判断，agent 不得自主
- id: M7
  tier: 3
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 需先验证 86M 分类器 + A/B 端到端提速
- id: S6_model
  tier: 3
  deps:
  - S6_rule
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 86M Prompt-Guard + 阈值重标定；FPR 98% 教训
- id: L2
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 迁移 SWE-bench Verified 子集，外部基准
- id: L6
  tier: 4
  deps:
  - M8
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 单次蒸馏 n=1 + 保留 UNCERTAIN；需 35B 标注
- id: L1
  tier: 4
  deps:
  - M1
  - M3
  - M9
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 产物内容满足 what 的断言精度/召回可测
- id: L8
  tier: 4
  deps:
  - GWT_FEP
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: GLiClass 中文表现验证；128 标签仅掉 7-20% 吞吐
- id: L5
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 须换 86M 且召回 A/B ≥80%；0.6B 已证伪
- id: L3
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 调研完成，待决定是否落 ADR
- id: L4
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 'autoparser 上游 PR #29307 未合并，本地补丁还在'
- id: L7
  tier: 4
  deps: []
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: S4 发现 ⑦，先小规模对照，不占正式坑
rungs:
- id: A0
  deps: []
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: test_sids.json
  - kind: file_grep
    path: tools/learn_watcher.py
    regex: test_sids|TEST_SIDS
    min: 1
  - kind: file_grep
    path: tools/weakness_miner.py
    regex: test_sids|TEST_SIDS
    min: 1
  - kind: file_grep
    path: tools/trace_report.py
    regex: test_sids|TEST_SIDS
    min: 1
  claimed_at: '2026-11-20T04:56:06.145832+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T05:14:02.333493+00:00'
  evidence_log:
  - at: '2026-11-20T05:14:02.333493+00:00'
    commit: d958a1a
    checks:
    - D:\Brain\publish\dsh-behavior-guard\test_sids.json
    - 13 hits in tools/learn_watcher.py
    - 13 hits in tools/weakness_miner.py
    - 13 hits in tools/trace_report.py
- id: A1
  deps:
  - A0
  risk: low
  autonomous: true
  status: backlog
  verify:
  - kind: file_exists
    path: tools/roadmap_check.py
  - kind: test_pass
    cmd: python tools/roadmap_check.py --dry-run
    min: 16
    note: §7 归档 16 项回测 100% PASS
- id: A2
  deps:
  - A1
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 写回需审 git diff，闸门上移但未取消
- id: A3
  deps:
  - A2
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: watcher 常驻 + 队列准入，需稳定性验证
- id: A3_5
  deps: []
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_grep
    path: tools/self_harness_gate.py
    regex: diff|snapshot|rollback
    min: 1
  - kind: file_exists
    path: tools/run_all.sh
  claimed_at: '2026-11-20T05:28:05.737234+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T05:54:28.652577+00:00'
  evidence_log:
  - at: '2026-11-20T05:54:28.652577+00:00'
    commit: 83151cb
    checks:
    - 31 hits in tools/self_harness_gate.py
    - D:\Brain\publish\dsh-behavior-guard\tools\run_all.sh
- id: A4
  deps:
  - A3_5
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: trace_count
    source: _trace.jsonl
    kind_name: meta_decision
    sid_filter: exclude_tests
    min: 1
- id: A5
  deps:
  - A1
  - A2
  - A3
  - A3_5
  - A4
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 7 天无人干预稳定性 + 零越界审计
<!-- ROADMAP_GRAPH_END -->
