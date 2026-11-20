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
    script: self_harness_gate.py
  what: Self-Harness P0-P2 纳入路线图 + 35B 真提案落候选
  why: 让 agent 自主读写能力阶梯，不用人工勾选
  benefit_to_self: 真正学会走路——没人盯着也能在低风险区持续成长
  caveats:
  - 只在白名单+预算内
  cost: 低
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
  what: adaptiveThinkEnabled 默认值验证
  why: token 消耗需要自适应机制
  benefit_to_self: 智能开关思考深度以省 token
  caveats:
  - DoD 要求'token 降且成功率不降'
  - 单次 FAIL→PASS 有噪声
  cost: 中
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
  what: 0.6B CPU 分类 4-2s 基准
  why: 证伪实时外设可行性（边缘设备 392ms vs 本机 4.2s）
  benefit_to_self: 知道什么可行、什么不可行，避免浪费时间
  caveats:
  - 比文献慢 10×
  - thinking 吃光 content 需 max_tokens≥512
  cost: 中
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
  - kind: gate_result
    script: gpu_engine_guard.py
  what: GPU 自检通过 + 同族对标
  why: GPU 是推理基础设施，必须持续可用
  benefit_to_self: 不因硬件/驱动问题导致推理中断
  caveats: []
  cost: 低
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
    regex: freq|FREQUENCY|heartbeat
    min: 1
  what: 频次三层改造：语法 OK；心跳 [deep] 每 10 分钟
  why: 监控频率需要分层管理不同场景
  benefit_to_self: 按需调整监控粒度，不浪费资源
  caveats: []
  cost: 低
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
  what: 短期全完成、M4/M1 升首档、M7/L5 降级、L7 新增
  why: v2.23 短期全部完成需重新评估优先级
  benefit_to_self: 路线图反映真实进展而非历史遗留
  caveats:
  - 需人工确认新优先级
  cost: 低
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
  cost: 中低
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
  title: 用户意图 BDI 三槽
  what: 把 s.bdi 单槽升级成 belief/desire/intention 三槽，承载用户意图跨压缩不丢
  why: 单槽装不下"用户要什么/信什么/打算怎么做"，压缩后约束丢失，意图漂移检测无状态可依
  benefit_to_self: 长任务压缩后仍记得用户最初要什么，不会因为 context 缩短而跑偏
  caveats:
  - 改 index.mjs 的 bdi 状态结构，不在白名单细粒度 target 内 → 人工确认
  - 复用现有 mind_state kind 埋点，别新造 kind
  - 用户意图多轮冲突时以最新指令为准（ADR-0014 不质疑式干预）
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection:
  - 三槽里哪一槽最常在压缩后丢失？
  - 有没有把用户临时指令误当长期意图的情况？
  abort_if: bdi 结构改动导致现有 control_turn/FEP 断言回归
  instrumentation_needed:
  - tools/test_bdi_slots.mjs（新建）；复用 mind_state kind
  unlocks:
  - M9
  - L1
  cost: 中
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
  title: 意图分类器
  what: 用意图分类器填 BDI 意图槽，高置信直接用、低置信交三角色
  why: 规则判意图太脆，但本机 8G 挂 embedding 编码器不可行
  benefit_to_self: 意图识别从"靠关键词猜"变成有置信度的判断，低置信时会主动求助而非乱做
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
  - 'P-ZH-VALIDATION: 中文表现验证'
  - 'P-86M-EMBEDDING: 8G 显存可行性'
  instrumentation_needed:
  - tools/test_intent_classifier.mjs（新建）
  unlocks:
  - L1
  cost: 中
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
- id: M5
  tier: 3
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 用户拍板'哪些进内核'——价值判断，agent 不得自主
  title: 工具面结构改造
  what: 把 28 个工具收敛到最小内核，低频能力进 skill 卡
  why: 工具面过宽会退化:Anthropic官方"10+ tools就该考虑"(Tool Use Examples 72→90%)、弱模型拐点12-15(社区实测)、Prosodica
    10工具78%→100工具<40%。旧"上限约40"已被推翻——它是模型/描述相关拐点非硬上限。哪些进内核仍是产品判断
  benefit_to_self: 每次决策要在更少的工具里选，减少选择噪声
  caveats:
  - ⛔ 用户拍板项，agent 不得自主决定
  - 不动则保持现状，别为了改而改
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（人工决策项，不自主执行）
  preconditions:
  - 'P-USER-DECISION: 用户拍板哪些工具进内核'
  unlocks: []
  cost: 高
- id: M7
  tier: 3
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 需先验证 86M 分类器 + A/B 端到端提速
  title: 格式修复器（降级）
  what: 格式修复器：只做格式重写、不判断对错，35B 首轮兜底
  why: 模型输出格式错误浪费后续步骤，但前置 86M 分类器还没验证
  benefit_to_self: 格式问题不用走到 35B 全量推理就能修，省 11s/次
  caveats:
  - 降级项：0.6B 已证伪（4-6s 比文献慢 10×）
  - 必须 86M CPU 延迟<500ms + A/B 端到端提速才上
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（前置未满足，manual-blocked）
  preconditions:
  - 'P-86M-LATENCY: 86M CPU 延迟<500ms'
  - 'P-AB-SPEEDUP: A/B 端到端提速'
  unlocks: []
  cost: 低
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
  title: S6 模型层升级
  what: S6 从规则层升级到 86M Prompt-Guard 模型层
  why: 规则层够用；模型层是误报率兜底，但 FPR 98% 的教训在前
  benefit_to_self: 注入检测从关键词匹配升级到语义级，减少漏报
  caveats:
  - 必须先阈值重标定，FPR 98% 的坑不能再踩
  - 规则层已在线，实测误报率>2% 才做模型层
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（manual-blocked）
  unlocks: []
  cost: 中
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
  - 'P-SWEBENCH: 迁移 SWE-bench Verified 子集'
  unlocks:
  - L1
  cost: 高
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
  title: FEP 深化 → 世界模型
  what: FEP 从"产物是否存在"升级为"产物内容满足 what"的世界模型断言
  why: 存在性判据太浅，产物写错内容也能过
  benefit_to_self: 能真正判断"做对了没"，不只是"做了没"
  caveats:
  - 需 M1+M3+M9 先完成
  - 误报不能侵占注入通道（ADR-0017）
  - 断言精度/召回必须可测
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（长期，依赖三个前置）
  instrumentation_needed:
  - tools/test_world_model.mjs（新建）
  unlocks: []
  cost: 极高
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
  - 'P-ZH-VALIDATION: GLiClass 中文表现'
  unlocks: []
  cost: 高
- id: L5
  tier: 4
  deps: []
  risk: high
  autonomous: false
  status: manual-blocked
  verify:
  - kind: manual
    reason: 须换 86M 且召回 A/B ≥80%；0.6B 已证伪
  title: 小模型 Critic 预警（降级）
  what: 86M 小模型 Critic 做轻量预警
  why: 0.6B 扫一次 5s 不实用；但小 judge 一致率仅 45-60%，需谨慎
  benefit_to_self: 能在主模型提交前快速扫一眼风险
  caveats:
  - 降级：0.6B 已证伪，须换 86M 且召回 A/B≥80%
  - 未命中只记 trace 不拦截
  - '[事故教训] 说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 不等于进程活着'
  reflection: []
  abort_if: 无（降级观望）
  preconditions:
  - 'P-86M: 换 86M 分类器'
  - 'P-RECALL-AB: 召回 A/B>=80%'
  unlocks: []
  cost: 高
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
- id: M10
  title: 会话生命周期治理（刹车）
  status: ready
  tier: 2
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_grep
    path: bench/dsh-session-bridge/bridge.mjs
    regex: case 'cancel'
    min: 1
  - kind: file_grep
    path: bench/dsh-session-bridge/index.mjs
    regex: sessionController.*cancel|ctrl.cancel
    min: 1
  - kind: file_exists
    path: docs/SESSION_BRAKE_20261120.md
  - kind: file_exists
    path: docs/MECHANISM_TRIGGER_AUDIT_20261120.md
  what: bridge cancel 命令（已做）+ 开新会话前硬件三层检查 + 并行时子任务分盯+汇总呈递协议；freeze_watch 加会话级无进展检测
  why: 2026-11-20 僵尸会话复活改坏 index.mjs；我误判"dsh 无终止 API"（只查 REST 404，实际走 cordis sessionController.cancel）；双会话并行险些
    again
  benefit_to_self: 有硬刹车（不靠模型自愿 STOP）+ 不再双会话并行 + 并行时有组织地分盯
  cost: 中
  caveats:
  - 不能误杀正常推理中的会话（必须有明确的无进展判据）
  - 停止必须是幂等的、可复查的
  abort_if: 停止机制误杀正常会话，或 dsh 侧根本没有可用的会话控制通道
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
    path: docs/FRAME_LIMITER_SLOTS_BUG_20261120.md
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
    regex: DEFAULT_WRITE_TOOLS.*verify|verifyOnWriteFor|writeTools.*check
    min: 1
  - kind: file_exists
    path: tools/test_write_verify_all.py
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_write_verify_all.py
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
- id: S12
  title: 补丁应用闭环（禁写脚本不落地）
  status: ready
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
- id: S13
  title: verifyRan收紧（read≠验证）
  status: ready
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
    path: docs/FUTURE_CLAIM_GUARD_20261120.md
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
    - D:\Brain\publish\dsh-behavior-guard\docs\FUTURE_CLAIM_GUARD_20261120.md
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
    regex: critic_review|planner_check
    min: 1
  - kind: file_exists
    path: docs/MECHANISM_TRIGGER_AUDIT_20261120.md
  - kind: test_pass
    cmd: D:/Python/python.exe -B tools/test_review_trace.py
    min: 1
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
- id: S15
  title: 选择性验证深度（Selective Verification）
  status: ready
  tier: 2
  deps:
  - A1
  risk: low
  autonomous: true
  verify:
  - kind: file_exists
    path: lineage/MUTATION_AUDIT.md
  - kind: test_pass
    cmd: node tools/test_task_profile.mjs
    min: 4
  what: 把无差别守卫改成门控式——只对高风险步骤做深度验证，低风险跳过
  why: 2026-11-21 实证无差别守卫拖入 C-REJECT 死循环；SWE-Verifier(arXiv:2610.30284) 验证<4%步骤得+1.73pp@1.09x成本
  benefit_to_self: 减少假阳性与token税，减少死循环触发面
  cost: 中
  caveats:
  - 确定性硬门（危险操作）保持全量，只对软判断做选择性
  - 门控阈值需在含漂移留出集验单调性
  abort_if: 漏放危险操作或端到端质量下降
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
  what: 给高频工具补 input_examples（最小/真实路径各一），M5工具面收敛的轻量替代
  why: Anthropic Tool Use Examples 复杂参数准确率72%→90%；dsh已完成并修正虚构路径(commit 1fe0659)
  benefit_to_self: 减少参数错误重复失败，不动工具数量
  cost: 低
  caveats:
  - 示例用真实数据不用 placeholder
  abort_if: 工具定义token增幅>10%且错误率未降
- id: S17
  title: 函数外置模式推广（自修改地基）
  status: doing
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
  what: 按四段式把剩余嵌套函数外置成纯函数+单测+内联+集成测试；formatCorrection已由dsh自主完成
  why: 合成心智需要agent能安全自修改；每次改动有机器可验的等价证据
  benefit_to_self: 不靠人肉小心（今晚手滑4次的根治）
  cost: 中
  caveats:
  - 必须内联；tools/版只作规范+测试载体
  - 每步跑trace基线对照，不能只看单测
  abort_if: trace分布与基线不一致或单测恒真
<!-- ROADMAP_GRAPH_END -->
