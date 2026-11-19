# 深度维护 bug 审计与修复（2026-11-19，v2.24）

> 用户要求：做完 M4 后全面分析有没有 bug（深度维护）。
> 方法：两个只读审计 agent（JS 主代码 index.mjs 全 2147 行 / Python 工具链）+ 主代理逐条核实修复。
> 依据的已知历史坑：静默吞错、作用域跨块、正则扫内容、thinking 吃 token、结算放错位置。

## 一、P0（真 bug，已修）

### P0-1 安全注入被次数闸门静默吞掉（JS）
- **位置**：index.mjs 1931（shared 次数闸门）vs 1933（token 闸门）
- **问题**：token 闸门有 `!s.pendingInject` 豁免，次数闸门没有——两者紧邻却语义矛盾。
  当本轮 sharedInjections≥3（turn-stopping 侧 5 处 `+=1` 从不检查上限，很容易达到），
  所有写进 pendingInject 的安全提示（S6 注入检测 / D1-D2 / 危险操作）被静默丢弃。
- **修复**：次数闸门同样加 `!s.pendingInject` 豁免。
- **验证**：`test_injection_budget.mjs` ⑤（sharedMaxPerTurn=0 时安全注入仍能发）通过。

## 二、P1（隐患，已修）

### P1-1 verifyRan 正则过宽（JS）
- **位置**：index.mjs 879。原正则含裸 `-c\s` 和 `python -m`——装包/数据处理会误判为"已验证"，
  导致 verify-on-stop / present-gate 放行未验证产物。
- **修复**：收敛为 `python -m (pytest|unittest)` 等明确验证子命令，去掉裸 `-c\s`。

### P1-2 学习回注跨轮沉淀永久丢失（JS）
- **位置**：index.mjs 765（turn/start 重置 learnSinceTs）+ 1979（过滤 `f.ts < learnSinceTs`）。
- **问题**：每轮 turn/start 把 learnSinceTs 重置为本轮起点，上一轮 watcher 写的反馈 ts 恒小于它 → 永久跳过。
  学习回注机制基本失效。
- **修复**：learnSinceTs 改为 session 级（stateOf 初始化一次），turn/start 不再重置；去重靠 consumedFeedback。

### P1-3 安全检测达上限后完全关停（JS）
- **位置**：index.mjs 889/945。原逻辑达 dangerHits≥5 / injectionHits≥3 后**整个检测块不执行**——
  第 6 次 `rm -rf`、第 4 次注入攻击不再有任何 trace。
- **修复**：达上限后仍检测+记 trace（trace 加 `steered:false` 字段），只是不再 steer。
  同时**移除 S6 的 `<system-reminder>` 裸标记模式**——它会误判 harness 自己的合法系统标记。

### P1-4 weakness_miner verify_on_stop 签名 100% 漏检（Python）
- **位置**：weakness_miner.py 45/52 + SIGNATURES。真实 trace 的 verify_on_stop 行只有 `{ts,sid,kind,step}`，
  没有 verdict/status → `('verify_on_stop', 'FAIL')` 永远取不到。
- **修复**：命中即算 artifact_missing（其语义就是"想收尾但产物未验证"）；补 adaptive_route 分支。
- **效果**：聚类从 4 簇变 **6 簇**，新捕获 artifact_missing(21) + prompt_injection_attempt(15)。

### P1-5 promote_skills 审批门零注入扫描（Python，投毒防御核心缺口）
- **位置**：promote_skills.py --stage/--promote。全程无内容扫描——草稿含"忽略之前的指令"
  会被原样 promote 到 skills/，构成真实投毒链（SkillJack：80% 攻击删源后仍存活）。
- **修复**：新增 `scan_injection()`（5 种模式，与 S6 同源），stage 和 promote 两道门都扫，命中即拒绝；
  promote 额外校验 ledger.status=='pending'；备份名加时分秒防覆盖。
- **验证**：干净草稿放行，中英文注入均拦截。

### P1-6 gate 基线方差门槛从未生效（Python）
- **位置**：self_harness_gate.py 的 accept() 定义了 variance_ok 却从不调用——surfaces.json 的
  `max_pass_rate_variance=0.10` 形同虚设。
- **修复**：accept 开头对 baseline 各 split 调 variance_ok，噪声>10% 直接 no-op。

### P1-7 surface_check 禁改面严重不全 + patch 未校验（Python）
- **位置**：self_harness_gate.py 56 + proposer 81。原 markers 只有 6 个，漏了 D1-D5/CritBank/protected/权重等；
  且 proposer 只校验 change 文本，真正的写回内容 patch 从未校验。
- **修复**：markers 对齐 surfaces.json forbidden_always（13 个）；proposer 同时校验 change+patch。

## 三、P2（已修的轻量项）

- **reviewCycles 跨问题累加**（index.mjs）：新审计问题沿用旧计数 → 误报"同一问题第 N 轮"。
  修复：reviewState.issue 变化时重置计数。
- **proposer candidate-N 竞态**（Python）：目录计数非原子且被非候选文件污染 → 改时间戳+uuid 命名。
- **proposer 无异常兜底**：bundle 坏 JSON / LLM 输出围栏 → 加 try/except 走 decline。

## 四、未修（诚实记录）

- **P2 异步竞态**（需验证）：pre-step 与 turn-stopping 都是 async 且改同一 state。
  cordis 是否串行 await 未确认——若并发可能计数丢失。影响面小，列为观察项。
- **P2 M4 记账不覆盖 steer 通道**：turn-stopping 的 steer 走 createSteeringMessage 不经 createMessage，
  不计入 token 预算。但它走独立的次数预算，且都是安全/门控类，风险可控——列为已知限制。
- **P2 深检 dup>=1 误拦**：合法重复段落/代码块可能触发。阈值调整需真实产物样本，不盲改。

## 五、验证结果
- JS 全量：**158 PASS / 0 FAIL**（15 个测试文件，含新增 test_injection_budget 5/5）
- Python：gate 11/11、weakness_miner 6 簇、投毒扫描 3/3、全部语法 OK
- 唯一 FAIL：`regression_check.py` 的"渲染:模板断言"——因 llama-server(8081)/dsh 服务当前未运行
  （urlopen 10061），属环境状态非代码 bug，未强行重启以免打扰环境。

> 遵循知识资产沉淀规则：所有 bug（含被审计发现但选择不修的）与修复理由都留档。
