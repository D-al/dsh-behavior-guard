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
- id: S1
  title: Self-Harness P0-P2
  tier: 1
  deps:
  - ground
  - S1_data
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: gate_result
    script: tools/self_harness_gate.py
  what: Self-Harness P0-P2 纳入路线图 + 35B 真提案落候选
  why: 让 agent 自主读写能力阶梯，不用人工勾选
  benefit_to_self: 真正学会走路——没人盯着也能在低风险区持续成长
  caveats:
  - 只在白名单+预算内
  cost: 低
  category: short
  unlocks:
  - rebaseline
- id: S2
  title: 可控遗忘常态化
  tier: 1
  deps:
  - ground
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: python tools/test_controllable_forgetting.py
    min: 1
  what: 真实计数 + 月度 decay + 假记忆自检
  why: 旧经验不沉淀会占空间，新经验不筛选会污染判断
  benefit_to_self: 该留的留、该忘的忘，长任务不糊成一团
  caveats:
  - decay 周期按实际频率调
  cost: 低
  category: short
- id: S3
  title: 频次收尾（trace 带 turn/controlTotal）
  tier: 1
  deps:
  - ground
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_trace_context.mjs
    min: 1
  what: trace 带 turn/controlTotal 字段
  why: 没有频次信息就无法做衰减和过滤
  benefit_to_self: 知道哪些经验高频出现，值得优先保留
  caveats: []
  cost: 低
  category: short
- id: S4
  title: 自适应 A/B
  tier: 2
  deps:
  - M4_budget
  risk: med
  autonomous: false
  status: done
  verify:
  - kind: file_exists
    path: docs/AUTONOMY_AND_SELF_HARNESS_20261122.md
  what: adaptiveThinkEnabled 默认值验证
  why: token 消耗需要自适应机制
  benefit_to_self: 智能开关思考深度以省 token
  caveats:
  - DoD 要求'token 降且成功率不降'
  - 单次 FAIL→PASS 有噪声
  cost: 中
  verify_type: document
  category: short
- id: S5
  title: 角色失效修复
  tier: 2
  deps:
  - CritBank
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_role_fixes.mjs
    min: 1
  what: 静默失败 / Critic 0% / 验收员触发修复
  why: 角色静默失败导致验证链断裂
  benefit_to_self: 每个角色都有效运转，不漏掉任何一环
  caveats: []
  cost: 低
  category: short
- id: S6
  title: 注入检测
  tier: 2
  deps:
  - S6_rule
  risk: med
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_injection_scan.mjs
    min: 1
  what: 规则层已在线 + trace kind injection_hit>0
  why: 防止外部注入篡改 agent 行为
  benefit_to_self: 不被外部输入误导做出错误决策
  caveats:
  - 模型层 86M 未做
  cost: 中
  category: short
- id: S7
  title: CPU 小模型基准
  tier: 3
  deps:
  - M8
  risk: med
  autonomous: false
  status: done
  verify:
  - kind: file_exists
    path: docs/AUTONOMY_AND_SELF_HARNESS_20261122.md
  what: 0.6B CPU 分类 4-2s 基准
  why: 证伪实时外设可行性（边缘设备 392ms vs 本机 4.2s）
  benefit_to_self: 知道什么可行、什么不可行，避免浪费时间
  caveats:
  - 比文献慢 10×
  - thinking 吃光 content 需 max_tokens≥512
  cost: 中
  verify_type: document
  category: short
- id: S8
  title: 审计自校准落盘
  tier: 2
  deps:
  - M8
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_audit_feedback.mjs
    min: 1
  what: 审计结果可追溯 + 自动反馈到路线图
  why: 没有持久化审计就不知道 agent 是否按路线图走
  benefit_to_self: 知道自己做了什么、做得对不对
  caveats: []
  cost: 低
  category: short
- id: S9
  title: 有状态反馈
  tier: 2
  deps:
  - M8
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_review_loop.mjs
    min: 1
  what: review loop 有状态不丢上下文
  why: 无状态 review 每次都是新会话，无法积累改进
  benefit_to_self: 从历史 review 中学习，越评越好
  caveats: []
  cost: 低
  category: short
- id: M4
  title: 注入预算 token 化
  tier: 1
  deps:
  - ground
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_injection_budget.mjs
    min: 1
  what: token 级预算控制安全注入
  why: 注入检测不能无限消耗资源
  benefit_to_self: 在安全和效率之间找到平衡点
  caveats:
  - 含安全注入双闸门豁免 P0 修复
  cost: 低
  category: mind
  unlocks:
  - rebaseline
- id: M6
  title: 安全规则不可覆盖
  tier: 1
  deps:
  - ground
  risk: high
  autonomous: false
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_security_boundary.mjs
    min: 1
  what: 声明 + 测试：安全规则不可被 skill/prompt/用户指令覆盖
  why: 防止任何方式绕过安全底线
  benefit_to_self: 保证系统行为始终符合设计意图
  caveats:
  - 需人工确认最终方案
  cost: 高
  category: mind
- id: GWT_FEP_done
  title: GWT 共享状态总线 + FEP 预期闭环
  tier: 1
  deps:
  - S1_data
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_gwt_fep.mjs
    min: 1
  what: 胼胝体（GWT）+ 小脑（FEP）共享状态闭环
  why: 多器官需要统一通信机制
  benefit_to_self: 各组件协同工作不冲突
  caveats: []
  cost: 低
  category: infra
- id: archive_dedup
  title: 压缩存档去重
  tier: 2
  deps:
  - CritBank
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_archive_dedup.mjs
    min: 1
  what: 角色失效诊断 + 过程折叠
  why: 重复存档浪费空间且干扰判断
  benefit_to_self: 存储更高效，检索更精准
  caveats: []
  cost: 低
  category: infra
- id: regression_106
  title: 回归审计 106 PASS / 0 FAIL
  tier: 1
  deps:
  - M4_budget
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: python tools/regression_check.py
    min: 1
  what: 深度维护审计（8 P0 + 9 P1 修复）
  why: 确保所有修复经得起测试验证
  benefit_to_self: 每次改动都经过自动化验证
  caveats: []
  cost: 低
  category: infra
- id: gpu_guard
  title: GPU 引擎守护
  tier: 1
  deps:
  - ground
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/gpu_engine_guard.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_gpu_guard.py
    min: 1
  what: GPU 自检通过 + 同族对标
  why: GPU 是推理基础设施，必须持续可用
  benefit_to_self: 不因硬件/驱动问题导致推理中断
  caveats: []
  cost: 低
  category: infra
- id: watcher_freq3
  title: learn_watcher 频次三层改造
  tier: 1
  deps:
  - S1_data
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_grep
    path: tools/learn_watcher.py
    regex: INTERVAL|CONSOLIDATE_EVERY
    min: 1
  - kind: file_grep
    path: tools/learn_watcher.py
    regex: def digest\(|def digest_deep_only\(|def one_round\(
    min: 3
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_freq_three_tiers.py
    min: 1
  what: 频次三层改造：语法 OK；心跳 [deep] 每 10 分钟
  why: 监控频率需要分层管理不同场景
  benefit_to_self: 按需调整监控粒度，不浪费资源
  caveats: []
  cost: 低
  verify_type: structural
  category: infra
- id: rebaseline
  title: 路线图重定基线
  tier: 2
  deps:
  - S1
  - M4
  risk: low
  autonomous: false
  status: done
  verify:
  - kind: file_exists
    path: docs/ROADMAP_EVOLUTION_20261120.md
  what: 短期全完成、M4/M1 升首档、M7/L5 降级、L7 新增
  why: v2.23 短期全部完成需重新评估优先级
  benefit_to_self: 路线图反映真实进展而非历史遗留
  caveats:
  - 需人工确认新优先级
  cost: 低
  verify_type: document
  category: infra
- id: outcome_all
  title: 结果反馈捕获 / 确定性门控 / 三角色 / P0-P2 心智拼图
  tier: 1
  deps:
  - ground
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: node tools/test_outcome.mjs
    min: 1
  - kind: test_pass
    cmd: node tools/test_turn_guard.mjs
    min: 1
  - kind: test_pass
    cmd: node tools/test_mind_state.mjs
    min: 1
  - kind: test_pass
    cmd: node tools/test_new_guards.mjs
    min: 1
  what: v2.0~v2.9 核心机制集
  why: 地基级机制确保 agent 基本行为正确
  benefit_to_self: 基础稳固后上层功能才能可靠运行
  caveats:
  - 见 CHANGELOG 全文
  cost: 低
  category: infra
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
  title: 情景检索进主循环
  what: 把离线 es.exe 检索接进控制回合，长任务里自动注入 top-3 历史经验
  why: 历史经验现在躺在 trace/日志里靠人肉搬运；长任务反复踩同样的坑，缺"想起来"这一环
  benefit_to_self: 以后遇到"这错误我见过"能真的想起来，少走 D1 重复探测的弯路
  caveats:
  - evidence_cited 埋点必须由本任务一起做，否则判据永远 FAIL（鸡生蛋）
  - 检索只进控制回合，不占运行时注入通道（ADR-0017：FEP 曾挤掉 D5 额度）
  - 过滤测试 sid，否则检索到 s1 假经验
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 注入的 3 条里有几条真被后续动作引用？没被引用的为什么没用？
  - 有没有"想起来的经验是错的/过时的"？怎么进可控遗忘？
  abort_if: D5 审计额度被挤占，或长任务 token 增幅>10% 且无质量提升
  instrumentation_needed:
  - trace kind evidence_cited（本任务埋点）
  unlocks:
  - L1
  cost: 中
  category: mind
- id: M8
  tier: 1
  deps:
  - S1_data
  risk: low
  autonomous: true
  status: done
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
  title: 轨迹 FSM 监控器
  what: 把 8147 行 trace 压成 FSM，做局部失败预测（重复探测/路径解析/工具报错）
  why: 长轨迹因果归因交主模型只有 0.56≈随机；但局部可观察信号（FSM）实测 AUROC 0.94，是可靠的前置预警
  benefit_to_self: 能在卡住的早期就知道"这个模式会导致失败"，提前换路，不用烧完 10 步才发现
  caveats:
  - 只做局部信号，别碰长轨迹因果归因（Jev 实测≈随机）
  - 判据产物 eval_fsm.py/_fsm_eval.json 由本任务自己生成
  - AUROC<0.85 不算完成，别降标准
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - FSM 预警的误报是什么模式？误报比漏报更伤吗？
  - 哪些失败签名是 FSM 抓不到、必须交主模型的？
  abort_if: held-out AUROC<0.85 反复达不到，或预警侵入运行时注入通道
  instrumentation_needed:
  - tools/eval_fsm.py（新建）+ _fsm_eval.json
  claimed_at: '2026-11-20T09:17:57.235651+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T09:17:57.571459+00:00'
  evidence_log:
  - at: '2026-11-20T09:17:57.571459+00:00'
    commit: ea05cb9
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\eval_fsm.py
    - heldout_auc=0.8927 >= 0.85
    - 3 hits in index.mjs
  unlocks:
  - L6
  - S7
  - S8
  - S9
  cost: 中低
  category: mind
- id: M3
  tier: 2
  deps:
  - GWT_FEP
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_s6_pattern_guard.mjs
    min: 6
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_pattern_lock_wire.mjs
    min: 4
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_intent_drift_trace.mjs
    min: 5
  - kind: trace_count
    source: _trace.jsonl
    kind_name: pattern_lock
    sid_filter: exclude_tests
    min: 1
    note: 观察线已落地(只写trace)；原test_bdi_slots不存在+mind_state假绿判据已移除
  title: 反模式匹配目标锚定（M3 重定位；观察线已落地）
  what: 反模式匹配目标锚定(重定位)：①观察线已落地——工具分布固化>=0.6且距目标重述>=6步，只写trace不steer，依据Goal Drift论文state complexity消融证伪"状态存更多"；②LLM抽锚点(RGE式)已证伪——15-16s/次且6/6锚点是P0 initial子串、零增量，不做；③⑤漂移trace加时机字段(StepShield:时机随机=没用)。
  why: 原假设被论文否定(Goal Drift state complexity消融：状态复杂度非漂移主因)；LLM抽锚点实测15-16s且6/6锚点是P0 initial原文子串=零增量；真正有证据的杠杆=反模式匹配观察线(已落地)+强目标重述(P0已在做)+动作层gate。
  benefit_to_self: 反模式匹配观察线在漂移早期给出可观测信号，避免长任务无声跑偏
  caveats:
  - 改 index.mjs 的 bdi 状态结构，不在白名单细粒度 target 内 → 人工确认
  - 观察线用独立pattern_lock kind；⑤漂移trace加时机字段；不再复用mind_state(假绿判据已移除)
  - 用户意图多轮冲突时以最新指令为准（ADR-0014 不质疑式干预）
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 三槽里哪一槽最常在压缩后丢失？
  - 有没有把用户临时指令误当长期意图的情况？
  abort_if: bdi 结构改动导致现有 control_turn/FEP 断言回归
  instrumentation_needed:
  - tools/test_s6_pattern_guard.mjs + test_pattern_lock_wire.mjs + test_intent_drift_trace.mjs(均已落地)
  unlocks:
  - L1
  cost: 中
  category: mind
  review: docs/PIPELINE_AND_INFRA_BRIDGE_20261120.md + docs/CLASSIFIER_BENCH_SERIES_20261121.md + docs/PIPELINE_AND_INFRA_BRIDGE_20261120.md + docs/PIPELINE_AND_INFRA_BRIDGE_20261120.md
- id: M9
  tier: 2
  deps: []
  risk: high
  autonomous: false
  status: rejected
  verify:
  - kind: manual
    reason: 已毙——原定位证伪+替代定位学术否定+本地规则基线够用；见 what
  title: 意图分类器（已毙 2026-11-22）
  what: 【已毙】原"意图分类器填BDI槽"零增量已证伪；"开局判长短分类器"学术强否定且本地零成本规则94.3%够用；不实现
  why: BDI槽被P0存档覆盖(零增量)；开局长短prompt-only近随机(AUC0.599/R²0.025)且同任务30×波动；本地关键词规则已94.3%
  benefit_to_self: 已无——价值被P0存档+⑤漂移检测+本地零成本规则覆盖
  caveats:
  - 8G 显存硬约束：先验证 86M CPU 分类器，别直接上 embedding
  - GLiClass 英文为主，中文表现未验证
  - 共享一个编码器，不为每意图训独立模型
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 中文意图分类的置信度分布如何？低置信阈值定多少合适？
  - 分类器错了有没有被三角色拦住？
  abort_if: 86M CPU 延迟>500ms 或中文准确率不达 92%
  preconditions:
  - 'P-ZH-VALIDATION: 中文准确率>=92%（M9.abort_if）'
  - 'P-86M-EMBEDDING: 86M分类器<=8G显存可运行（M9.caveat硬约束）'
  instrumentation_needed:
  - tools/test_intent_classifier.mjs（新建）
  unlocks: []
  cost: 中
  category: mind
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
  title: 会话树实时化
  what: 让 session_tree.py 从事后分析变实时写 parent 指针，支持从任一节点 fork
  why: 现在只能事后重建会话树，无法在长任务中实时知道"我现在是哪条支线"
  benefit_to_self: 能真正 rewind 到任意节点重试，而不用重读整段历史
  caveats:
  - append-only 历史语义，fork 不能改写既有记录（ADR-0013）
  - 不付 KV 后缀税——靠追加不靠改写
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - fork 后旧节点的经验有没有被正确继承？
  - 有没有因为 parent 指针错而 rewind 到错误节点？
  abort_if: parent 指针写入导致历史 trace 被改写或 KV 后缀税回升
  instrumentation_needed:
  - tools/test_session_tree.mjs（新建）
  unlocks: []
  cost: 中高
  category: mind
- id: M5
  tier: 3
  deps: []
  risk: high
  autonomous: false
  status: done
  verify:
  - kind: manual
    reason: 用户已拍板(2026-11-22 07:30)采纳三层治理原则:核心常驻/低频关键按需加载/已禁用入口移除
  title: 工具面结构改造（三层治理原则）
  what: 三层治理:核心7工具常驻(95.7%)/低频关键按需加载/已禁用入口(job_*/web_fetch)移除。放弃按频次砍到N个
  why: 全量37会话1959调用证明低频≠可砍;真正问题是已禁用入口污染选择空间(11次违规)+描述碰撞,不是工具数量
  benefit_to_self: 每次决策要在更少的工具里选，减少选择噪声
  unlocks:
  - S22
  caveats:
  - ⛔ 用户拍板治理原则
  - 不看单纯频次-低频但关键必须保留
  - 证据:docs/PIPELINE_AND_INFRA_BRIDGE_20261120.md
  reflection: []
  abort_if: 无（人工决策项，不自主执行）
  preconditions:
  - 'P-USER-DECISION: 用户拍板哪些工具进内核'
  cost: 高
  category: mind
- id: M7
  tier: 3
  deps: []
  risk: high
  autonomous: false
  status: rejected
  verify:
  - kind: manual
    reason: 需先验证 86M 分类器 + A/B 端到端提速
  title: 格式修复器（降级）
  what: 格式修复器：只做格式重写、不判断对错，35B 首轮兜底
  why: 0.6B生成式已证伪(4-6s);verify-on-edit零LLM已覆盖格式错误;原前置"86M分类器"方向已放弃
  benefit_to_self: 格式问题不用走到 35B 全量推理就能修，省 11s/次
  caveats:
  - 降级项：0.6B 已证伪（4-6s 比文献慢 10×）
  - 必须 86M CPU 延迟<500ms + A/B 端到端提速才上
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（前置未满足，manual-blocked）
  preconditions:
  - 'P-CLASSIFIER-LATENCY: 已实测Horizon 102ms<500ms(原P-86M-LATENCY的86M方向已放弃)'
  - 'P-AB-SPEEDUP: A/B端到端提速>=10%（仍需实测）'
  unlocks: []
  cost: 低
  category: mind
- id: S6_model
  tier: 3
  deps:
  - S6_rule
  risk: high
  autonomous: true
  status: done
  verify:
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_classifier_decision_wire.mjs
    min: 1
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_s6_signal_gate.mjs
    min: 18
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_classifier_fragment_filter.py
    min: 8
  - kind: manual
    reason: 大样本93.3%/2.3%FPR+真实会话三轮验证+生态调研确认定位；门禁77/77
  title: S6 模型层升级（守门+片段筛选已启用）
  what: S6 规则层+ONNX分类器Tier-2+高信号守门+片段级筛选+pre-step同步门控决策线
  why: 规则层2/4→分类器语义级28/30；守门降送检率+片段筛选堵白名单绕过+同步门控提示早于生成8s
  benefit_to_self: 注入检测从关键词匹配升级到语义级，减少漏报
  caveats:
  - 时机修复：fire-and-forget改pre-step同步门控，提示早于模型生成8.2s(session-639df0d6)
  - 实测@0.9=93.3%召回/2.3%FPR/80%Precision;真机离线776条FPR3.09%，前置过滤错误/乱码后有效0.64%
  - 延迟税：短文本0.268s(+2.4%)/长文本长跑3.85s(+35%)；高信号守门只送指令性文本
  - 生态调研：分类器只做纵深一层，OWASP/PromptGuard主张信任边界放动作层；当前只写trace+中性提示不拦截
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 86M gated不可得且基准表现差(默认阈值1%),已放弃该方向;改用Horizon
  unlocks: []
  cost: 中
  category: short
- id: L2
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 迁移 SWE-bench Verified 子集，外部基准
  title: 标准化 eval
  what: 把自建 P3/P4/P5 评测迁移到 SWE-bench Verified 子集
  why: 自建 bench 无法与社区同基准可比，外部效度存疑
  benefit_to_self: 知道自己在社区真实水平的位置，不再自我感觉良好
  caveats:
  - 高成本：迁移+跑基准
  - 长期优先，不插队
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（长期人工排期）
  preconditions:
  - 'P-SWEBENCH: 迁移SWE-bench Verified子集（阈值待定：长期人工排期，跑通子集即算达标）'
  unlocks:
  - L1
  cost: 高
  category: longterm
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
  title: 专属误差预测器
  what: 用 trace + 35B 标注训 0.5B 二分类误差预测器
  why: 由 M8 的 FSM 局部信号解锁，不再空中楼阁
  benefit_to_self: 能预测"这一步会不会错"，提前触发审计而非事后补救
  caveats:
  - 只做单次蒸馏 n=1（递归自噬第 9 代会退化成野兔清单）
  - 保留 UNCERTAIN 样本
  - 长轨迹因果归因仍交主模型
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（依赖 M8 完成后人工评估）
  unlocks: []
  cost: 高
  category: longterm
- id: L1
  tier: 4
  deps:
  - M1
  - M3
  risk: high
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 产物内容满足 what 的断言精度/召回可测
  title: FEP 深化 → 世界模型
  what: FEP 从"产物是否存在"升级为"产物内容满足 what"的世界模型断言
  why: 存在性判据太浅，产物写错内容也能过
  benefit_to_self: 能真正判断"做对了没"，不只是"做了没"
  caveats:
  - 需 M1+M3 先完成（M9已毙）
  - 误报不能侵占注入通道（ADR-0017）
  - 断言精度/召回必须可测
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（长期，依赖M1+M3两个前置）
  instrumentation_needed:
  - tools/test_world_model.mjs（新建）
  unlocks: []
  cost: 极高
  category: longterm
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
  title: 多标签心智编码器
  what: 一个前向同时输出意图+风险+难度，写进 GWT 共享状态
  why: 现在三个判断分散，128 标签仅掉 7-20% 吞吐可行
  benefit_to_self: 一次推理拿到三维心智状态，比三次判断省时
  caveats:
  - GLiClass 英文为主，中文表现必须先验证
  - 8G 可行性待证
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（探索项）
  preconditions:
  - 'P-ZH-VALIDATION: GLiClass中文表现（阈值待定：需先定中文测试集与准确率的达标线）'
  unlocks: []
  cost: 高
  category: longterm
- id: L5
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: rejected
  verify:
  - kind: manual
    reason: 须换 86M 且召回 A/B ≥80%；0.6B 已证伪
  title: 小模型 Critic 预警（降级）
  what: 小模型 Critic 做轻量预警（0.6B已证伪；分类器可作信号源但价值待证）
  why: 0.6B证伪;Critic门控可行性验证=无产物文本/无标签+分类器对产物质量零区分度(占位符@0.9检出0/8)
  benefit_to_self: 能在主模型提交前快速扫一眼风险
  caveats:
  - 降级：0.6B 已证伪，须换 86M 且召回 A/B≥80%
  - 未命中只记 trace 不拦截
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（降级观望）
  preconditions:
  - 'P-CLASSIFIER-RECALL: Horizon@0.9召回93.3%>=80%(原P-86M方向已放弃)'
  - 'P-RECALL-AB: 召回 A/B>=80%（端到端A/B仍需实测）'
  unlocks: []
  cost: 高
  category: longterm
- id: L3
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 调研完成，待决定是否落 ADR
  title: 脑功能分区空白区
  what: 补眶额价值/脑干稳态的脑功能空白
  why: BRAIN_PARITY 盘点的空白区
  benefit_to_self: 多目标冲突时有价值排序
  caveats:
  - 调研完成，待决定是否落 ADR
  - 观望
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（观望）
  preconditions:
  - 'P-ADR-DECISION: 是否落 ADR'
  unlocks: []
  cost: 高
  category: longterm
- id: L4
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 'autoparser 上游 PR #29307 未合并，本地补丁还在'
  title: 独立轨道（上游 PR）
  what: 上游 autoparser PR 合并后撤本地补丁，升级引擎
  why: 跟上游减少维护负担
  benefit_to_self: 不用每次升级重打补丁
  caveats:
  - '#29307 未合并，本地 2 行补丁还在'
  - 不插队
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（等上游）
  preconditions:
  - 'P-UPSTREAM-PR: autoparser #29307 合并'
  - 'P-LLAMACPP-V1: v1.0.0 升级'
  unlocks: []
  cost: 高
  category: longterm
- id: L7
  tier: 4
  deps: []
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: S4 发现 ⑦，先小规模对照，不占正式坑
  title: FAKEOK 抑制（探索）
  what: 验证"防提前假装完成"的轻量机制
  why: S4 发现提示让 FAKEOK→PASS（token 未降）
  benefit_to_self: 减少"看着完成了其实没做"的自欺
  caveats:
  - 先小规模对照，不占正式坑位
  - 与 D4 交付闸门同源
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（探索）
  instrumentation_needed:
  - tools/test_fakeok.mjs（新建）
  unlocks: []
  cost: 低
  category: longterm
- id: M10
  title: 会话生命周期治理（刹车）
  status: done
  tier: 2
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_exists
    path: docs/AUTONOMY_AND_SELF_HARNESS_20261122.md
  - kind: file_exists
    path: docs/COMPACTION_CONTEXT_CADENCE_20261120.md
  - kind: test_pass
    cmd: node tools/test_kill_switch.mjs
    min: 3
  - kind: file_grep
    path: index.mjs
    regex: killSwitch|kill_switch
    min: 1
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_session_brake.py
    min: 3
  what: 进程外可靠刹车(kill_switch.py:事件指纹检测非进展→L1告警/L2cancel/L3硬杀) + 任务级上下文(taskProfile根治4假阳性)
    + loop_breaker告警 + 开新会话前硬件三层检查
  why: 2026-11-20 僵尸会话复活改坏 index.mjs；我误判"dsh 无终止 API"（只查 REST 404，实际走 cordis sessionController.cancel）；双会话并行险些
    again
  benefit_to_self: 有硬刹车（不靠模型自愿 STOP）+ 不再双会话并行 + 并行时有组织地分盯
  cost: 中
  caveats:
  - 不能误杀正常推理中的会话（必须有明确的无进展判据）
  - 停止必须是幂等的、可复查的
  abort_if: 停止机制误杀正常会话，或 dsh 侧根本没有可用的会话控制通道
  unlocks: []
  category: mind
  claimed_at: '2026-11-22T07:51:32.788086+00:00'
  claimer: unknown-agent
  done_at: '2026-11-22T07:51:44.627358+00:00'
  evidence_log:
  - at: '2026-11-22T07:51:44.627358+00:00'
    commit: 43840dd
    checks:
    - D:\Brain\publish\dsh-behavior-guard\docs\AUTONOMY_AND_SELF_HARNESS_20261122.md
    - D:\Brain\publish\dsh-behavior-guard\docs\COMPACTION_CONTEXT_CADENCE_20261120.md
    - rc=0 PASS=4
    - 1 hits in index.mjs
    - rc=0 PASS=3
- id: S10
  title: 推理活性判据纠偏（取消单帧采样）
  status: manual-blocked
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: tools/frame_limiter.py
    regex: effect_check|回读|no_effect|WARN_THROTTLE
    min: 1
  - kind: file_exists
    path: docs/PLATFORM_REPAIR_20261120.md
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_frame_limiter_effect.py
    min: 1
  what: 废除"单帧硬件快照判推理活性"，改用 token 计数连续采样(n_decoded/n_prompt_tokens 5-10秒增长)作为唯一判据
  why: 我用单帧100%/1%/25W误判为spin-wait并开卡，用户实证两窗口全开推理正常；相位间隙的瞬态被当成稳态
  benefit_to_self: 限帧从"调用了就算"升级为"有效才算"——避免静默无效 6 小时
  cost: 中
  caveats:
  - token计数要在同task内比较，跨task会跳变
  - 别再回到聚合util%判据
  abort_if: 无法可靠回读单进程3D占用，或升级手段影响系统稳定性
  human_note: 2026-11-20 21:12 用户实证推翻前提：两窗口全开推理正常(n_decoded 1211→1356/5s，带宽22-29%功耗36-41W)。原"3D抢占致spin-wait"是单帧采样撞相位间隙的误判。S10原目标(降帧效果回读)前提不成立，阻塞待重定义。
  tier: 1
  category: infra
- id: S11
  title: 写后校验覆盖全部写工具
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: index.mjs
    regex: cfg\.writeTools\.includes\(c\.name\)|DEFAULT_WRITE_TOOLS
    min: 1
  - kind: file_grep
    path: index.mjs
    regex: checkSyntax\(s\.lastProduct\)|verifyOnEditEnabled
    min: 1
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_edit_protocol.py
    min: 1
  what: 把 verify-on-edit 从只覆盖 write/edit 扩展到 DEFAULT_WRITE_TOOLS 全部8种（apply_patch/multi_edit/create_file/str_replace/write_file/notebook_edit），每种按扩展名跑对应语法校验
  why: 真实trace显示write 0%失败但edit 11.8%失败；verify-on-edit(index.mjs:1042)只认write/edit，其余6种写工具零校验——假绿温床
  benefit_to_self: 所有写入路径都有语法护栏，不再有"换了写工具就绕过校验"
  cost: 中
  caveats:
  - 别让校验失败阻断正常写入（拦=纠错消息而非硬失败）
  - 扩展名映射要覆盖.mjs/.js/.py/.json/.yaml
  abort_if: 无法在不改dsh原生工具的前提下拿到写后内容
  claimed_at: '2026-11-20T16:57:05.100377+00:00'
  claimer: unknown-agent
  tier: 1
  category: infra
- id: S12
  title: 补丁应用闭环（禁写脚本不落地）
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: index.mjs
    regex: patch.*applied|补丁.*应用|applyEvidence
    min: 1
    flags: IGNORECASE
  - kind: file_exists
    path: tools/test_patch_applied.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_patch_applied.py
    min: 1
  what: 检测"写了修复脚本但没真正应用"的模式：补丁脚本(_apply_*.py/_fix_*.py)写入后必须有对应的apply证据（目标文件mtime变化+语法通过），否则守卫提示"脚本已写但未应用"
  why: A1_6一张卡留下5个补丁脚本全没应用，浪费几十分钟——"写了脚本"≠"应用了脚本"是新变体的说要做不做
  benefit_to_self: 堵住"用写脚本代替改文件"的绕路，把时间花在真正落盘
  cost: 中
  caveats:
  - 别误伤合法的临时分析脚本
  - apply证据要用环境事实（目标mtime+内容），不认模型声明
  abort_if: 无法可靠关联补丁脚本与目标文件
  tier: 1
  unlocks: []
  claimed_at: '2026-11-21T08:27:50.078173+00:00'
  claimer: unknown-agent
  done_at: '2026-11-21T08:28:04.165663+00:00'
  evidence_log:
  - at: '2026-11-21T08:28:04.165663+00:00'
    commit: 26bda1a
    checks:
    - 5 hits in index.mjs
    - D:\Brain\publish\dsh-behavior-guard\tools\test_patch_applied.py
    - rc=0 PASS=2
  category: infra
- id: S13
  title: verifyRan收紧（read≠验证）
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: index.mjs
    regex: verifyEvidence|真实.*验证|s\.verifyRan = true[^\n]*syntax
    min: 1
  - kind: file_exists
    path: tools/test_verify_ran.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_verify_ran.py
    min: 1
  what: 把 index.mjs:913 的"read/cat 即 verifyRan"收紧为真实验证证据（语法检查/测试命令/verify_agent），解决A1_6反复read却被认为验证过的假绿
  why: :913规则当年为修25/26回归误判加的宽松判断，现在成了"读循环被当成验证"的源头——A1_6连续6次read同段无write却一路绿灯
  benefit_to_self: verify信号可信——"验证过"必须真跑了检查，不是读了文件
  cost: 中
  caveats:
  - 收紧后可能重现25/26回归误判，要用更精确的文件名匹配替代宽松规则
  - 保留对真实语法检查命令的识别
  abort_if: 收紧导致正常验证流程被大面积误拦
  tier: 1
  unlocks: []
  category: infra
- id: S14
  title: 编辑协议升级（降低复现负担）
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: config/AGENTS.md
    regex: 紧邻重读|最短唯一锚点|引用而非重述|near.?read|minimal.?anchor
    min: 1
  - kind: file_grep
    path: config/AGENTS.md
    regex: 压缩.*重读|compaction.*reread
    min: 1
  - kind: file_exists
    path: tools/test_edit_protocol.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_edit_protocol.py
    min: 1
  what: 把 AGENTS.md:105 的裸 read→edit 升级为"短文件(<400行)整块输出、长文件紧邻重读+最短唯一锚点、压缩后强制重读"；失败时回灌精确差异(edit-doctor模式)。不押注结构化diff格式——Diff-XYZ证明小模型换格式收益很小
  why: '学术证据:RoPE 1D归纳偏置致精确复制失败(arXiv:2607.16072);Diff-XYZ(NeurIPS25w,arXiv:2510.12487)明确"smaller
    open models benefit little from any formatting choice";Aider 26→59%是GPT-4大模型数据不可套用到35B;Claude
    Code #26996 tab→空格致6连败;edit-doctor旁路诊断第二次即成功。C-010正是压缩后凭记忆重建1300字符old_string截断'
  benefit_to_self: 减少要精确复现的字符量——35B在Diff-XYZ属"换格式收益小"区间，降负担才是杠杆
  cost: 中低
  caveats:
  - 别照搬Aider大模型结论到35B——Diff-XYZ明确小模型换格式收益小
  - 锚点要唯一且从第一个非空白字符起，绕开tab/CRLF/不可见字符
  - 失败回灌要给可复制文本而非裸重试
  - 35B属于"格式收益小"区间，重心是降低要复现的字符量
  abort_if: 无法在dsh原生edit工具约束下实现可验证的锚点协议
  claimed_at: '2026-11-20T14:18:32.327124+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T14:31:21.313624+00:00'
  evidence_log:
  - at: '2026-11-20T14:31:21.313624+00:00'
    commit: 172dfcc
    checks:
    - 4 hits in config/AGENTS.md
    - 1 hits in config/AGENTS.md
    - D:\Brain\publish\dsh-behavior-guard\tools\test_edit_protocol.py
    - rc=0 PASS=6
  tier: 1
  category: infra
  unlocks:
  - S24
- id: STRAT1
  title: 战略陈述（模型只读顶层约束）
  tier: 0
  deps: []
  risk: low
  autonomous: false
  status: done
  verify:
  - kind: file_exists
    path: STRATEGY.md
  - kind: file_grep
    path: tools/consistency_guard.py
    regex: STRATEGY
    min: 1
  what: 新建 STRATEGY.md：一句话终极目标 + 可观测成功标准 + 明确非目标 + 战略假设；由人类设定，模型只读；consistency_guard
    校验其哈希未被改动。
  why: 77轮战略会话[109]诊断"路线图围绕技术打转因无战略顶层约束"；RRSI/Harness² 证明自改进者会 objective hacking，判据外置才有治理。
  unlocks:
  - S18
  - S19
  - S20
  - S21
  benefit_to_self: 选卡不再靠 tier 字段缺失的机械排序；"下一张该做什么"有顶层判据可对照。
  cost: 低
  caveats:
  - 不能把 STRATEGY.md 放进 35B 可写路径
  - '"谁在锁外"必须显式：治理权归属写进文件'
  abort_if: 无法保证模型只读则不做（自我授权比没有战略更糟）
  verify_type: document
  category: governance
  done_at: '2026-11-22T06:32:06.790138+00:00'
  evidence_log:
  - at: '2026-11-22T06:32:06.790138+00:00'
    commit: b84638e
    checks:
    - ADR-0021 用户显式批准关闭陈旧卡
    - STRATEGY.md存在
    - consistency_guard STRATEGY校验3hits
    note: autonomous=false治理卡——人工按ADR写回,未经自动claim/apply
- id: S18
  title: 自改进正则化（RRSI 纪律）
  tier: 1
  deps:
  - A1
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/holdout_split.py
  - kind: file_grep
    path: tools/roadmap_check.py
    regex: noise_floor|NOISE_FLOOR|holdout
    min: 1
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/holdout_split.py --probe
    min: 1
  what: 给 agentlab/projectlab 切 30% hold-out 任务永不用于选卡；一次只改一个可归因机制；先测基线方差设噪声地板（±10%内不算提升）；新增机制须证
    token/时间收益；定期剪枝无收益守卫。
  why: RRSI(arXiv2609.24972)：无正则自改进 OOD 跌破初始基线；增益归因研究 54% 过拟合+14% test-time scaling；我们明知±10%却没当判据。
  unlocks:
  - S19
  - S20
  - S21
  benefit_to_self: 让"加了机制→门禁全绿→宣称完成"不再等于自欺；所有改进可被证伪。
  cost: 中
  caveats:
  - hold-out 集必须真隔离，不能被 agent 看到
  - 剪枝要区分补偿性/永久性规则
  abort_if: 若无法隔离 hold-out 则退化为只做噪声地板
  verify_type: structural
  category: governance
  claimed_at: '2026-11-22T05:58:33.080981+00:00'
  claimer: unknown-agent
  done_at: '2026-11-22T05:58:40.244229+00:00'
  evidence_log:
  - at: '2026-11-22T05:58:40.244229+00:00'
    commit: 54a3324
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\holdout_split.py
    - 7 hits in tools/roadmap_check.py
- id: S19
  title: CritBank 校准门禁（CEB 路线）
  tier: 1
  deps:
  - A1
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/critbank_calibration.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_critbank_calibration.py
    min: 5
  what: CritBank 条目加 hindsight 伪标签 ŷ（V=5 投票）与当初一致性标志 χ；按 B+/B- 正负对照检索；冻结 critic 执行前给
    confidence，低置信转人工/重规划。
  why: CEB(arXiv2607.12397)复合键(task,state,action)与我们逐字同构；3bench×3backbone 9/9 组合 ECE/Brier/AUC
    全胜、ECE 最多-54%；记忆放 critic 侧非 actor 侧。
  unlocks:
  - S20
  benefit_to_self: 把"检索注入"从可能帮倒忙的提示变成可校准、可门禁的信号。
  cost: 中
  caveats:
  - 原始失败轨迹有害(ReasoningBank 44.4→42.2)，只存蒸馏规则
  - EvoMemBench：没有单一记忆形式全胜，需匹配任务结构
  abort_if: 若 hindsight 投票不可靠则不入 ŷ 字段
  category: governance
  claimed_at: '2026-11-22T06:31:52.066356+00:00'
  claimer: unknown-agent
  done_at: '2026-11-22T06:32:26.550212+00:00'
  evidence_log:
  - at: '2026-11-22T06:32:26.550212+00:00'
    commit: b84638e
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\critbank_calibration.py
    - rc=0 PASS=5
- id: S20
  title: Critique 编译为结构化 delta（ACE 路线）
  tier: 2
  deps:
  - S19
  risk: med
  autonomous: true
  status: backlog
  verify:
  - kind: file_exists
    path: tools/delta_curator.py
  - kind: file_grep
    path: tools/delta_curator.py
    regex: helpful|harmful
    min: 1
  what: 引入 Generator/Reflector/Curator 三角色分离：Curator 把 critique 转成带 helpful/harmful
    计数器的结构化 delta，做确定性 dedup/merge/prune，增量更新而非全文重写。
  why: ACE(ICLR2026 arXiv2510.04618)相对 GEPA 延迟-82.3%/rollout-75.1%/token-80.8%，agent+10.6%；增量
    delta 避免 context collapse。
  unlocks: []
  benefit_to_self: 把"从经验编译分类器"降级为"编译成可审计规则"，符合权重零改+可回滚。
  cost: 中高
  caveats:
  - Curator 不做自由文本摘要
  - 计数器读数字不读段落
  - 每轮全对抗性更新会跌破基线
  abort_if: 若 delta 无法被回归测试则不做
  verify_type: structural
  category: governance
- id: S21
  title: 验证层去自审（质量压倒多样性）
  tier: 1
  deps:
  - A1
  risk: med
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/verifier_layer.py
  - kind: file_grep
    path: tools/verifier_layer.py
    regex: def build_report|def run_probe|def load_rubrics
    min: 2
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_verifier_layer.py
    min: 3
  what: Critic/Planner 不再 35B 自审：proposer 用最强模型多次采样(Self-MoA式)；能断言的判断下沉到 Python 规则/测试/哈希；必须
    LLM judge 时成对交换顺序+独立 rubric+人工抽检。弱模型只做门控/校验/快速路径，不做最终语义裁决。
  why: Self-MoA(2502.00674)最强采样比混合+6.6分；JudgeBench(2410.12784)GPT-4o客观判断50.9%=抛硬币；会话Q13/Q19协调者悖论。
  unlocks: []
  benefit_to_self: 判断权下沉到确定性层，唯一语义裁决瓶颈留给 35B。
  cost: 中
  caveats:
  - 0.8B多角色critic已被双证伪，别重做
  - judge 的 rubric 选择本身是分数漂移主因
  abort_if: 无
  verify_type: structural
  category: governance
  claimed_at: '2026-11-22T06:32:40.127169+00:00'
  claimer: unknown-agent
  done_at: '2026-11-22T06:32:42.576162+00:00'
  evidence_log:
  - at: '2026-11-22T06:32:42.576162+00:00'
    commit: b84638e
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\verifier_layer.py
    - 4 hits in tools/verifier_layer.py
    - rc=0 PASS=5
- id: S22
  title: 工具面治理工程（清理+描述碰撞）
  tier: 1
  deps:
  - M5
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/tool_surface_audit.py
  - kind: file_grep
    path: config/AGENTS.md
    regex: input_examples
    min: 1
  - kind: test_pass
    cmd: node tools/test_disabled_tools.mjs
    min: 1
  what: harness能落地的工程:对已禁用入口(job_*/web_fetch)做调用拦截提示+描述触发条件审计+描述碰撞自检+保留低频关键能力;不做dsh
    runtime工具面裁剪(做不到)
  why: 全量37会话1959调用证明低频≠可砍;可行性校正:dsh无工具面裁剪hook,harness的writeTools只是内部计数——移除入口做不到,改为拦截提示
  unlocks: []
  benefit_to_self: 减少参数错误导致的重复失败(D1/D2)，不占主模型注意力。
  cost: 中
  caveats:
  - 不按频次砍关键工具
  - dsh runtime工具面动不了,只做harness层拦截
  - 改完回归43/43
  - M5已拍板
  abort_if: 无
  verify_type: structural
  category: infra
- id: S23
  title: 前缀 KV 稳定性守护
  tier: 1
  deps: []
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/prefix_stability_probe.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_prefix_stability.py
    min: 1
  what: 把 harness 改动纳入"是否使 prompt 前缀失效"的评估：工具定义/指令放前缀后部；不因小改使整个 cache 失效；改动前后测 prefill
    差异。
  why: 9000 token 前缀 KV cold 1.77s vs hot 0.03s(60×)；印证我们"CTX_CHECKPOINTS 承重墙(降到1→+23%)"实测；频繁小改可能比少改但改对更慢。
  unlocks: []
  benefit_to_self: harness 改动成本可量化，避免"改对了但变慢了"。
  cost: 低
  caveats:
  - 前缀稳定性与功能正确性冲突时优先正确性
  - 别为了 cache 稳定而拒绝必要修复
  abort_if: 无
  claimed_at: '2026-11-21T08:27:32.771058+00:00'
  claimer: unknown-agent
  done_at: '2026-11-21T08:28:04.410777+00:00'
  evidence_log:
  - at: '2026-11-21T08:28:04.410777+00:00'
    commit: 26bda1a
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\prefix_stability_probe.py
    - rc=0 PASS=3
  category: infra
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
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_sid_blacklist.py
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
  title: 数据可信（sid 黑名单）
  what: 抽 test_sids.json 黑名单，让 4 个消费脚本统一过滤测试 sid
  why: trace 91%、pendingLearn 95.7% 是 s1 假数据；不清洗，后面所有自动判断都建立在沙子上
  benefit_to_self: 我看的每一条经验都是真的，不会被单测假数据骗（之前差点把假 audit fail 当生产故障）
  caveats:
  - 黑名单要覆盖 s1/outcome-/budget-*/b7332eb6 等
  - 只过滤不删数据本体（可逆）
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  - '[C-08] 判据路径必须和文件实际落点一致：bench/ 前缀会被解析到 BENCH_DIR，不是权威仓库根'
  reflection:
  - 过滤后真实数据占比多少？还有哪种假数据没被黑名单抓到？
  - 有没有真实 sid 被误过滤？
  abort_if: 过滤后真实样本<100 行，不足以支撑后续判断
  cost: 低
  tier: 0
  category: autonomy
  unlocks:
  - A1
- id: A1
  deps:
  - A0
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/roadmap_check.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/backtest_archive.py
    min: 11
    note: 独立归档回测11项全过(10个唯一测试脚本+graph可加载;标签=脚本名，零递归)
  title: 会记路（机器判据 + dry-run 核验）
  what: 给路线图补机器判据 + roadmap_check.py dry-run 核验
  why: 路线图已可机器写回(--apply)，但人工勾选仍占多数，autonomous 地基待补
  benefit_to_self: 我不用等人告诉我"这条做完了没"，跑一次脚本就知道
  caveats:
  - 对 §7 归档 16 项回测必须 100% PASS、对未完成项 0 误报才准开 --apply
  - 主观 DoD（M5/M7）标 manual-only
  - 判据指向真实产物，过滤测试 sid
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 回测里有没有"判据 PASS 但其实没做"的假阳性？
  - 哪些判据太松/太紧，需要调阈值？
  abort_if: 回测出现假阳性且无法用判据修正
  claimed_at: '2026-11-20T09:22:36.317587+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T10:27:57.921689+00:00'
  evidence_log:
  - at: '2026-11-20T10:27:57.921689+00:00'
    commit: 370c93f
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\roadmap_check.py
    - rc=0 PASS=13
  cost: 中
  tier: 0
  category: autonomy
  unlocks:
  - A1_5
  - A1_6
  - A1_7
  - A2
  - A5
  - M10
  - S10
  - S11
  - S12
  - S13
  - S14
  - S15
  - S18
  - S19
  - S21
- id: A2
  deps:
  - A1
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: 写回需审 git diff，闸门上移但未取消
  title: 会指路（自动勾选，只写权威源）
  what: roadmap_check.py 自动勾选确定性条目，只写权威源
  why: 把人从"每次勾选"解放到"审 git diff"，闸门上移但不取消
  benefit_to_self: 我改完就能自己记进度，人只需看一眼 diff
  caveats:
  - 必须写权威源 CAPABILITY_LADDER.yaml，不写 p/bench 副本
  - 写回前 git diff --check
  - 主观项不勾选
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 自动勾选有没有和人的判断冲突过？
  - diff 审阅里人最常改哪类勾选？
  abort_if: 出现一次假完成勾选 → 退回人工勾选
  cost: 中
  tier: 1
  category: autonomy
  unlocks:
  - A3
  - A5
- id: A3
  deps:
  - A2
  risk: med
  autonomous: false
  status: backlog
  verify:
  - kind: manual
    reason: watcher 常驻 + 队列准入，需稳定性验证
  title: 会迈步（预批低风险队列取任务）
  what: watcher 从人工预批的低风险队列取任务，执行→gate→写回
  why: 没人按"开始走"按钮，自进化 P3 一直没启动
  benefit_to_self: 我没任务时不用等着人派活，能从已批准队列里自己找活干
  caveats:
  - 只执行队列内任务，绝不碰队列外
  - 限单次预算（35B 每步 11s）
  - 白名单含 index.mjs 细粒度项需 A3.5 先完成
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 队列里的任务我完成率多少？失败的是哪类？
  - 有没有越界执行过队列外任务？
  abort_if: 越界执行 1 次或连续 2 次任务失败
  cost: 中
  tier: 1
  category: autonomy
  unlocks:
  - A5
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
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_future_claim_guard.py
    min: 1
  claimed_at: '2026-11-20T05:28:05.737234+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T05:54:28.652577+00:00'
  evidence_log:
  - at: '2026-11-20T05:54:28.652577+00:00'
    commit: 83151cb
    checks:
    - 31 hits in tools/self_harness_gate.py
    - D:\Brain\publish\dsh-behavior-guard\tools\run_all.sh
  title: 安全地基（真实 diff + e2e + 回滚）
  what: gate 升级真实 diff 校验 + deploy_with_rollback + 廉价 e2e
  why: 现在 surface_check 只做字符串匹配、无 e2e、无回滚——让 agent 改自己的大脑却没人验证
  benefit_to_self: 我改完东西能自己验证"没把自己改傻"，改坏了能自动恢复
  caveats:
  - 廉价 e2e = node --check + 全量 test_*.mjs + config_check.py
  - 排除 verify_agent.py（35B 600s）
  - 快照落权威源外的 archive/
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - diff 校验拦住过哪种绕过？
  - 回滚触发过几次，都是什么原因？
  abort_if: e2e 假阴性（把好改动判坏）反复出现
  cost: 中
  tier: 0
  category: autonomy
  unlocks:
  - A4
  - A5
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
  title: 会转弯（旁路 meta_decision）
  what: 把 D1 重复探测等信号从 prompt 软提示升级为旁路 meta_decision 决策器
  why: 控制回合只是 prompt 反思，代码无 abandon/skip 路径
  benefit_to_self: 我卡住时能真的"换条路"，而不是在 prompt 里被提醒了还继续重复
  caveats:
  - 做旁路决策器，不改 D1-D5 判定本体（禁改面）
  - 先只做 D1（最明确）
  - 命中写结构化 trace
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - meta_decision 跳过后再没重复探测的比例多少？
  - 有没有误跳过本该继续的动作？
  abort_if: 误跳过率>10%
  instrumentation_needed:
  - trace kind meta_decision（旁路决策器写）
  cost: 中
  tier: 2
  category: autonomy
  unlocks:
  - A5
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
  title: 自己走（常驻闭环）
  what: 全链常驻闭环：读图→选任务→执行→验收→写回→反思→下一轮
  why: 把前面所有器官连成 24/7 自走系统
  benefit_to_self: 我真正"学会走路"——没人盯着也能在低风险区持续成长
  caveats:
  - 只在白名单+预算内
  - 保留人工验证基线，定期 diff 防语义漂移
  - L5 自我改写目标永不做
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 一周里我沉淀了几条可复用经验？爬后面的任务是否真的更快了？
  - 有没有"越爬越偏"的漂移迹象？
  abort_if: 7 天内出现 1 次越界或需人工救场 → 暂停闭环
  cost: 高
  tier: 2
  category: autonomy
- id: S24
  title: 执行层工具失败自愈（edit锚点/路径兜底）
  tier: 1
  deps:
  - S14
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/test_tool_failure_healer.mjs
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_tool_failure_healer.mjs
    min: 1
  - kind: test_pass
    cmd: D:/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin/node.exe tools/test_tool_failure_heal_integration.mjs
    min: 1
  what: 在 harness 的 session/event 监听里捕获 isError 工具失败，pre-step 自动注入修正提示（FS_STALE_VERSION/FS_EDIT_NOT_FOUND→重读+最短锚点；FS_NOT_FOUND→相近文件suggest）。与S14提示层协议分工，执行层兜底。
  why: 工具失败画像54次/2000+调用，文件系统类63%；关键反转=S14(11-20提示层协议)落地后edit锚点失败反从2涨到8/天→提示层已证无效，缺执行层兜底。
  unlocks: []
  benefit_to_self: 把"模型记不记得协议"变成"环境保证兜底"，不依赖模型元认知。
  cost: 中低
  caveats:
  - 只注入修正提示不改dsh工具本身
  - 每轮<=1次每会话<=4次避免提示风暴
  - 失败判据只认isError/data.error结构化字段，绝不扫结果文本（219误报教训）
  abort_if: session/event拿不到tool/result的isError字段（已确认可拿到）
  claimed_at: '2026-11-22T19:50:00+08:00'
  claimer: unknown-agent
  evidence_log:
  - at: '2026-11-22T19:50:00+08:00'
    checks:
    - 单测9/9 + 集成测试4/4（真实FS_STALE_VERSION事件结构→接线确定性验证）
- id: A6
  title: 验收可信度加固（测试收集普查 + 退出码真实）
  tier: 1
  deps:
  - A1_5
  risk: low
  autonomous: true
  status: done
  verify:
  - kind: file_exists
    path: tools/test_census.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_census.py
    min: 1
  - kind: file_grep
    path: tools/run_all.sh
    regex: tools/test_\*\.py
    min: 1
  - kind: test_pass
    cmd: node tools/test_disabled_tools.mjs
    min: 1
  what: 测试收集普查(census)+全py测试纳入门禁+恒真/退出码假绿修复+行为断言规范+独立核验SOP
  why: 实锤:12个py测试仅1个在门禁;test_new_guards有8 FAIL却rc永0;改坏脚本43/43全绿。社区collection census/变异测试/verifier-actor分离印证方向
  benefit_to_self: 验收从'看起来全绿'变成'真的全绿';新增测试自动纳入门禁;假绿/恒真/退出码丢失三类隐蔽问题有机制拦截
  caveats:
  - 6个历史失败SKIP是权宜需后续修
  - census基线需随测试增删更新
  - PYTHON解析已修重复块
  abort_if: census误报持续红
  unlocks: []
  cost: 中
  category: infra
  data_gates:
  - id: P-CENSUS-COVERAGE
    desc: test_census.py检出48测试全纳入门禁(此前12个py仅1个),missing_in_gate=0
    status: satisfied
    evidence: tools/test_census.py VERDICT PASS + 门禁57/57
    source: commit f607cf5
  - id: P-EXITCODE-HONEST
    desc: test_new_guards补exitCode判定,暴露6个历史失败并SKIP诚实标注(不再假绿)
    status: satisfied
    evidence: node tools/test_new_guards.mjs rc=0 with 6 SKIP printed
    source: commit f607cf5
- id: A1_5
  title: 判据元验证（防假绿）
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_exists
    path: tools/check_verify.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/check_verify.py
    min: 1
  - kind: file_grep
    path: tools/check_verify.py
    regex: recursive|递归|self.?ref
    min: 1
    flags: IGNORECASE
  what: 写 check_verify.py 检测判据自身的四类病：自引用递归、格式不匹配、恒真判据、测试sid污染
  why: A1 判据曾递归6分钟不停、^PASS格式不匹配假FAIL、管道吞rc假绿；A1只管卡状态核验，不管判据本身可信
  benefit_to_self: 自治信任建立在判据可信上——避免"全绿但没做"
  cost: 中
  caveats:
  - 元验证器自己不能递归（必须独立于 roadmap_check 的 evaluate）
  - 用构造的假判据样本验证必须全判FAIL
  abort_if: 无法构造稳定的假判据样本，或元验证器本身产生假绿
  claimed_at: '2026-11-20T12:06:01.711017+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T12:26:01.475219+00:00'
  evidence_log:
  - at: '2026-11-20T12:26:01.475219+00:00'
    commit: a423329
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\check_verify.py
    - rc=0 PASS=7
    - 7 hits in tools/check_verify.py
  tier: 0
  category: autonomy
  unlocks:
  - A6
- id: A1_6
  title: 守卫 L1 补将来时承诺检测
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: index.mjs
    regex: FUTURE_CLAIM|将来时|承诺式
    min: 1
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_future_claim_guard.py
    min: 1
  - kind: file_exists
    path: docs/FUTURE_CLAIM_AND_CONSISTENCY_20261120.md
  what: 把 guardDecide 的 L1 从只校验过去时声明（已写入X）扩展到将来时承诺（现在写X/接下来创建X），要求承诺的产物在本轮真实产生
  why: 2026-11-20 A1_5 会话输出"现在进入核心：编写 check_verify.py"后结束回合、文件不存在——WRITE_CLAIM 只匹配过去时，将来时承诺穿过
    L0-L3 全部防线，是"只输出好"的新变体
  benefit_to_self: 防止模型用"说要干"冒充"干了"——自治闭环的完成判定不能再被将来时承诺绕过
  cost: 中
  caveats:
  - 别把正常的进度汇报误判为承诺（如"下一步我会考虑..."）
  - 必须要求真实产物+mtime，不能只做文本匹配
  - L1 校验必须仍以环境事实为准，不能只信模型声明
  abort_if: 无法区分"将来时承诺"与"正常下一步说明"导致大量误拦截
  claimed_at: '2026-11-20T13:12:01.950856+00:00'
  claimer: unknown-agent
  done_at: '2026-11-20T13:49:00.488751+00:00'
  evidence_log:
  - at: '2026-11-20T13:49:00.488751+00:00'
    commit: 16497fe
    checks:
    - 2 hits in index.mjs
    - rc=0 PASS=8
    - D:\Brain\publish\dsh-behavior-guard\docs\FUTURE_CLAIM_AND_CONSISTENCY_20261120.md
  tier: 0
  category: autonomy
- id: A1_7
  title: 评审机制可观测性
  status: done
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: index.mjs
    regex: 'kind: ''review_verdict''|review_kind: ''critic''|review_kind: ''planner'''
    min: 1
  - kind: file_exists
    path: docs/COMPACTION_CONTEXT_CADENCE_20261120.md
  - kind: file_grep
    path: index.mjs
    regex: rubric_version|dimensions_checked
    min: 1
  - kind: trace_count
    source: D:/Brain/workspace/bench/_trace.jsonl
    sid_filter: exclude_tests
    kind_name: review_verdict
    min: 5
  what: 给 Critic/Planner 调用加专属 trace 打点（rubric_version/dimensions_checked/verdict），让每个评审机制有可审计的触发证据
  why: 2026-11-20 审计发现：新加的 Critic第6维/Planner假设披露确实进了 prompt，但 callLLM 只记 kind=llm，无法证明评审真的用了新维度——违反证据分层铁律
  benefit_to_self: 机制上线后能回答"它今天到底触发了吗、拦了什么"——不再靠"代码里写了"自我安慰
  cost: 中
  caveats:
  - 打点必须含 verdict 和具体维度，不能只记"调用过"造成另一种假绿
  - trace 写失败不能影响主评审流程
  abort_if: 无法在不改 callLLM 签名的前提下拿到 rubric 版本与维度判定
  claimed_at: '2026-11-20T16:45:21.583892+00:00'
  claimer: unknown-agent
  tier: 0
  category: autonomy
- id: S15
  title: 选择性验证深度（ Selective Verification）
  status: done
  tier: 2
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_exists
    path: tools/selective_verification.mjs
  - kind: test_pass
    cmd: node tools/test_selective_verification.mjs
    min: 1
  what: 把当前"每步无差别守卫 + present 前全量 Critic"改成门控式——低风险步骤跳过，只对高风险步骤做深度验证（多候选+独立评审）
  why: 2026-11-21 生产实证：无差别守卫把两步任务拖进 C-REJECT 死循环；SWE-Verifier 证明选择性验证以 <4% 验证率取得 +1.73pp
    且成本仅 1.09×，全步验证 2.03× 反不提升
  benefit_to_self: 守卫只在真需要时介入——减少假阳性与 token 税，也减少死循环触发面
  cost: 中
  caveats:
  - 必须保留确定性硬门（危险操作/引用幻觉）为全量，只对"软判断"（是否需todo/是否深度评审）做选择性
  - verifier 若用本地 4B 需实测延迟（Q8 约 2.5G 显存，本机 8G 可行但未验）
  - 门控阈值需在含漂移的留出集上验证单调性（Confidence Gate Theorem 警告）
  abort_if: 选择性门漏放危险操作，或端到端质量下降
  category: infra
- id: S16
  title: 工具描述瘦身与示例
  status: done
  tier: 1
  deps: []
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: config/AGENTS.md
    regex: input_examples
    min: 1
  what: 给高频工具的 schema 补 1-5 个 input_examples（最小/歧义/错误恢复各一），并测算工具定义总 token；作为 M5 工具面收敛的轻量替代
  why: Anthropic 内部测试 Tool Use Examples 把复杂参数准确率 72%→90%；本机工具面 28 个已在风险区，但砍工具需用户拍板，补示例零风险
  benefit_to_self: 减少参数错误导致的重复失败（D1/D2），不必动工具数量
  cost: 低
  caveats:
  - 示例要用真实数据，不用 placeholder（placeholder 教不会东西）
  - 收益在参数歧义大的工具上明显，简单单参数工具不必加
  - 不替代 M5 的结构改造——那需要用户拍板
  abort_if: 工具定义 token 增幅 >10% 且参数错误率未下降
  verify_type: document
  category: infra
  unlocks:
  - M5
- id: S17
  title: 函数外置模式推广（自修改地基）
  status: done
  tier: 2
  deps: []
  risk: low
  autonomous: true
  verify:
  - kind: file_exists
    path: tools/format_correction.mjs
  - kind: test_pass
    cmd: node tools/test_task_profile_integration.mjs
    min: 1
  what: 按 docs/MEMORY_AND_REFACTOR_20261120.md 的四段式模式，把剩余 13 个嵌套函数外置成"纯函数+单测+内联+集成测试"；先从
    3 个无依赖纯函数开始
  why: 合成心智需要 agent 能安全自修改；嵌套函数边界不清、无单测，agent 改自己时无法证明等价。taskProfile 已示范模式并验证可行
  benefit_to_self: 每次自修改都有机器可验的等价证据，不靠人肉小心（今晚手滑4次的根治）
  cost: 中
  caveats:
  - 默认 import 转发（index.mjs 顶部 import + 函数体 return _fn），tools/ 版是唯一真相；禁正则替换/整文件重建/手写Unicode转义（2026-11-21
    REFACTOR_PATTERN 实测，原"必须内联"已推翻）
  - 每个函数外置后跑 trace 基线对照（data/baseline/trace_pre_refactor_20261121.jsonl），不能只看单测
  - stateOf 需注入 4 依赖，最后做；callLLM/runAudit/runCritic 最难，压轴
  abort_if: trace kind 分布与基线不一致，或单测恒真（|| true / >=0）
  done_at: '2026-11-21T06:42:21.471911+00:00'
  evidence_log:
  - at: '2026-11-21T06:42:21.471911+00:00'
    commit: 4b676f6
    checks:
    - D:\Brain\publish\dsh-behavior-guard\tools\format_correction.mjs
    - rc=0 PASS=1
  category: infra
<!-- ROADMAP_GRAPH_END -->
