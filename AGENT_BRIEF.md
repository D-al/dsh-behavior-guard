# AGENT BRIEF — 决策速查（唯一必读）

> **读这一份 = 掌握全局**。目标 ≤12KB / 一次读完（当前 11.3KB）。
> 其余文档都是**按需深挖**：只有本文件明确指向时才读，不要主动通读 docs/（1.25MB，读完必漏）。
> 更新：2026-11-25 · 事实均经代码核实（路径:行号）· 有疑义看 [BACKLOG](docs/OPTIMIZATION_BACKLOG_20261125.md) 状态审计表。

---

## 0. 开工前 30 秒：你需要知道的核心判据

**端到端 e2e + 95% CI 是唯一主判据；decode t/s 是误导性指标**（三次实测：省显存改 prefill 后 e2e 显著变快而 decode t/s 不显著）。
- 用 `tools/paired_ab.py`：n≥10 对、ABBA、每请求重启 server、CI 不含 0 才显著
- CI 跨 0 就是不显著，**不追加实验找显著**（防 p-hacking）
- 实验条件必须匹配落地条件（ngram 第三轮教训：生产有 min-hits=2，实验没加 → 结论反转）
- 生产验证走 dsh 真实会话，不用裸 20K HTTP（会触发 WDDM 冻死）

---

## 1. 生产配置（当前值，别凭记忆猜）

```
引擎 upstream 1.0 (94f3af3) | 模型 Qwen3.6-35B-A3B-UD-Q4_K_XL (Q4 only)
CTX 98304 / NGL 99 / 全host cpu-moe (CPU_MOE=1, N_CPU_MOE 空)
MOE_CACHE_MIB 1350 / share 1.0 / UBATCH 2048 / THREADS 8
CTK q8_0 / CTV q4_0 / MTP nmax=3 / SPEC_TYPE draft-mtp
temp 0.7 (.env 必须留空，INI 才生效) / TOP_P 0.95 / REASONING_BUDGET 4096
CHAT_TEMPLATE bench/chat_template_zh.jinja
```
- 路由模式：server 不带 `-m`，`--models-preset bench/llama-router-preset.ini --models-max 1 --models-memory-margin 450`
- ⚠ `/slots` 必须带 `?model=<已加载模型>`
- ⚠ `.env` 覆盖 INI；`python tools/config_check.py` 查一致性 **+ 9 条硬值断言**（见 §2 门禁化块）。
  改任何本地配置前/后跑一次——违规会带"为什么"报出来，不必背规则
- 硬件 i7-12650H / 64GB DDR4-3200 / RTX4060Laptop 8G（**空闲显存安全线 ≥450MiB**，186 必卡 WDDM 换页→1~2 t/s）
- 当前 `nvidia-smi memory.free` **235MiB**（17:3x 实测，已在450安全线下、贴186必卡线）；
  ⚠ 别用 `8188−memory.used` 当余量（WDDM 下口径不同，会高估到466）；**别用聚合 util% 判推理是否在跑**——看 Copy 引擎 + 显存带宽 + 功耗（UI 渲染走 3D，推理走 Copy）

---

## 2. 铁律（不知道就会犯错）

> **已门禁化（不用背，工具会拦）**：`python tools/config_check.py` 检查 9 条硬值——
> CTX_CHECKPOINTS=2 / MMPROJ_OFFLOAD=1 / DRY_ALLOWED_LENGTH=32 / share=1.0 / nmax=3 /
> SPEC_TYPE=draft-mtp / TOP_P=0.95 / REASONING_BUDGET=4096 / TEMP 留空。
> 违规会报出原因（如"降到1→每步全量重预填+23%"）。变异测试 `tools/test_hardened_rules.py`
> 已验证每条"故意改坏→门禁变红"（10/10）。
> **已实测的旁路护栏**：`rulepack_guard.py`+INV-7 版本钉住会拦住 agent 偷改评判规则——
> 实测只给 run_all.sh 加一行测试注册就立刻 FAIL，强制走审批通道（已回退，82/0 恢复）。
> 所以别试图改门禁来"让测试通过"——那正是它设计来抓的。
> **注意**：门禁只覆盖配置值；操作类铁律（删 junction/强推/危险命令）仍需人工遵守——
> 现有"block"是注入文本而非硬拦截，勿误以为工具会挡住。

1. **中文思维链**：唯一有效的是生成位置锚点 `{{- '嗯，' }}`（必须是自述句；祈使句会回「好」后 EOS）
2. **「只输出好」= 上下文自强化回路**：模板 `is_stub` 跳过「确认词+无tool_calls+非最后一条」的 assistant（治本）
3. **autoparser 空白 bug**：`src/common/chat-auto-parser-generator.cpp` 两行（444/473）；**每次升级引擎重打补丁**（`bench/patches/autoparser-fix.patch`）
4. **CTX_CHECKPOINTS 是承重墙**：降到 1 → 每步全量重预填 +23% 耗时
5. **DRY 必须 `--dry-allowed-length 32`**（设 2 会让模型改字形躲惩罚）
6. **视觉编码器必须 MMPROJ_OFFLOAD=1**（否则截图 CPU 编码 141s）
7. **append-only 优于改写历史**：改写思维链有 KV 后缀税（20K 重预填充 25-44s）
8. **守卫正则只认执行动作，绝不扫内容**：扫 fullArgs 会让文件名含 "verify/test" 误判已验证 → 守卫静默失效。限定命令型工具参数才安全
9. **别用关键词计数判"是否落地"**：实现命名可能与预期不同（`critic_review` 搜不到实际 `review_verdict`；`test_levers_ab_effect.mjs` 不叫 `*_ab_runner.py`）。必须读实现代码 + 注释卡号
10. **也别只信子任务声称"已做"**：本轮虚报 5 项经 grep/find 实盘证伪。一切"已做"必须有路径:行号+代码片段
11. **证据分层**：`_trace.jsonl` 89% 是 s1 单测假数据；验收只认真实 sid 的 trace / 独立产物。零证据先分辨：没触发 / 写到别处 / 设计默认关 / 真没有
12. **"文档宣称完成"≠"代码实际生效"**：三层交叉——运行版真实 trace 打点 + 真实 jsonl kind 分布 + 产物 mtime
13. **温度按模型配**：Q4 最优 0.7（P3/P4/P5 三项 2/2 最快）；0.1 崩（想完不干）、0.9 崩（草率），U 形曲线
14. **harness 杠杆 > 模型选择/引擎调优**：同模型换 scaffold +15.6pp
15. **三副本一致性**：权威源 publish / 运行版 node_modules 必须 sha 一致（INV-3 校验这对）；pnpm store clone 是旧包不在校验范围。改前确认"哪个在运行"，改后 sha256
16. **判据/卡片腐化先盘点再修**：六张卡"虚报"全是判据本身写错（解释器/路径/正则/门槛），功能是好的——别对着完好功能瞎修
17. **Windows 绝不对 junction 用 `Remove-Item -Recurse -Force` / `rmdir /S`**：会连带删目标目录真实数据；
    删链接用 `fsutil reparsepoint delete`（只删链接不碰目标）
18. **先实测锁定真凶再定方案**：用户的需求调整往往比初始假设更准；用户说"不对"时先停下验证，别用"已完成"回应
19. **判"没实现"先分辨四种情况**：没触发 / 写到了别处 / 设计就关闭 / 真的没有
20. **涉及第三方 loader/框架语义先扒对应版本权威源码**：试错成本 >> 读源码成本
21. **bridge 会话坑**：subagent routing 会话不能用 bridge 投递（须 `create` 专用）；`events` CLI 截断到 300 字符，
    读完整 assistant text 要直连 HTTP API；计划任务 PATH 无 node，须绝对路径
22. **照搬前先对齐 template 和 parser**：本地 Qwen3.6 必须 `apply_chat_template(tools=...)`
23. **判"没实现"的四分类**（同 19）：没触发 / 写到别处 / 默认关 / 真没有；S8 靠受控实验才命中
24. **记忆系统改造不能"清空后重注入"**：清空 prompt 导致能力下降 + 性能回退（实测 4.5× 时间膨胀）；
    应 append-only + 标记折叠 + 校正注入（A18 已落地 3 层防护，别推翻重来）
25. **强制结构化规划反而放大错误**：预测准确率 94% → 22%；"规划内化到模型、不再外化 todo"是实测结论

---

## 3. 已证伪，别重试（省时间）

- **decode t/s 单点优化**：`moe-cache-cpu-share=1` 曾让 decode +37% 但端到端慢 2.4×
- **nmax 7**：占更多显存+CPU draft 计算，只会更差（nmax3 已 95% 胜出）
- **ngram 替代 MTP**：三轮测，加生产参数后 e2e CI 跨 0，不落地
- **电源计划 / `-t 6/10/16` / `-lm` 大页 / KV q8_0(旧结论) / ignore_eos 探针**
- **思考硬切（切半句）/ 改写历史思维链 / 工具结果去重 / apply_patch 替代 edit**
- **reasoning-budget 硬切**（已被 budget+message 平滑版取代）
- **M3 抽锚点**（6/6 会话锚点是 initial 原文子串，P0 已覆盖，无增量）
- **开局长短任务分类器**（AUC 0.599≈随机）、**一刀切复杂度预算**（范畴错误，已改目的追溯制）
- **小模型做 critic/审计/验收**（客观判断 50.9%≈随机）、**0.6B 当实时周围神经**（CPU 4-6s vs 要求<10ms）
- **依赖模型元认知自我纠错**（ICLR2024：GPT-4 GSM8K 95.5→89.0，无外部反馈自纠有害）
- **静态工具裁剪**（低频≠可砍；read_image/ask_user_question 场景少见但不可缺）
- **区块链/zkVM/TSA 信任锚**（成本远超收益）
- **通用恒真断言检测器**（社区没有银弹）；**PBT 属性测试**（本场景成本偏高）

---

## 4. 当前优先级（做什么）

**阻塞项**：测量环境污染——WorkBuddy 自身 4 进程累计 3494s CPU，prefill 在 431-1030 t/s 跳变。所有 95% 实验效力受损，先解决或 n≥15。

**第一梯队（低成本脚本）**：
1. NOT_INSTRUMENTED 三项埋点（compaction/goal_proposal/delta_rule，`tools/baseline_metrics.py:57/66/83`）
2. 补 `pathMissing` 设置点（`index.mjs:85` 只有判断处）
3. 真正移除 web_fetch（cordis.patch.yml:368 仍 `fetch:true`，ADR-0028 要求改 false 未生效）
4. 审计成本核算（trace 数据已有，纯分析）
5. edit 前锚点确认（FS_EDIT_NOT_FOUND 占 33%）

**第二梯队（基础设施，有复利）**：真实任务 A/B 流水线（固定任务集+两臂自动跑+Wilson CI）、审计权锁定（版本钉住型已有，物理写保护未做）、leave-one-out 治理组件基线。

**第三梯队（95%实验）**：`-tb` 独立线程（autostart 已内置开关 `LLAMA_35B_TB`，生产未启用）、KV FP8、~~MTP 头定向搬 GPU~~ **已关闭**：需腾≥450MiB净空闲(非差20MiB)、收益实测+0.7%噪声内、`-ot` 会被 `--cpu-moe` 静默抢先；cache 1350→1900 已证零收益。

⚠ 完整 40+ 方向与逐条证据 → [BACKLOG](docs/OPTIMIZATION_BACKLOG_20261125.md)（按需读）。

---

## 4.5 静默失效已修（遇到相似症状别重复排查）

- **聚合 util% 骗人**：空闲时 nvidia-smi 也报 100%（WorkBuddy/dwm 的 3D 64%+34%），实测推理走 Copy 引擎仅 0.8%
- **看门狗空转**：RestartDsh 卡 Running+IgnoreNew 时 [ACTION] 日志刷但 pid 不变 → `Stop-ScheduledTask` 回 Ready 再重启
- **`!!js` 坑**：dsh JsExpr 只 eval 标量，`!!js [...]` 被 YAML 当 flow sequence 逗号切碎 → dsh 起不来；从包内 patch 删路径键，由 DEFAULTS 接管
- **zstd 多帧**：必须 `ZstdDecompressionReader` 循环读所有帧，`zstd.open().read()` 只读第一帧（239 字节）
- **dsh 会话备份铁律**：备份目录必须在 `sessions/` **外面**且保留 `<group>/session-X` 层级——
  扁平化 388 个 session 放进 sessions/ 内 → workspaceController 初始化 TypeError、加工作区全失败（11-25 实测，详见 POSTMORTEM_SESSION_BACKUP）
- **session-bridge cursor**：`hasMore` 恒 true、cursor 无效 → 曾重复计数 11810 假数据；按 callId/sid 去重
- **trace 89% 是 s1 单测假数据**：零证据先分辨没触发/别处/默认关/真没有
- **S6 长文本 >2000 字符结构性缺席**：靠结构隔离兜底（已做），别指望分类器
- **8443→844**：约束解码 schema 只锁形状不锁内容（max=1000 会把 8443 压成合法 844）——形状用 grammar、内容用确定性检查

---

## 5. 已落地机制（别当新空间重复开工）

四杠杆全落地：`tools/lever{1,2,4,A,B,C}_*.py` + `lever_effect_report.py`
- 杠杆1 确定性状态回读 / 杠杆2 状态板 / 杠杆4 K=5投票(默认关) / 杠杆A 约束解码 / 杠杆B 错误剧本 / 杠杆C 风险调度
- S6 Tier-2 注入分类器（阈值0.9，只告警不 steer）、高信号正则门控、长文本结构隔离
- 评审可观测性（`kind:'review_verdict'` 带 rubric_version/dimensions/verdict）
- trace 自动补 turn/controlTotal、验收员 spawn_teammate 触发、判据体检门禁、RRSI hold-out+噪声地板

⚠ **机制生效 ≠ 效果提升**：多数只有 trace 命中证据，缺真实任务 n≥16 的成功率提升证据。

---

## 6. 目录导航（按需读，别通读）

| 需要什么 | 读哪份 |
|---|---|
| 优化方向全表+证据 | `docs/OPTIMIZATION_BACKLOG_20261125.md` |
| 引擎实测/显存/量化 | `docs/ENGINE_*.md`（5 卷） |
| 四杠杆/GBNF/广搜 | `docs/LEVERS_AND_BROAD_RESEARCH_20261124.md` |
| 工具面证据/失败分析 | `docs/PIPELINE_AND_INFRA_BRIDGE_20261120.md` |
| harness 治理/自主化 | `docs/AUTONOMY_AND_SELF_HARNESS_20261122.md` 等 |
| 路线图状态（机器权威）| `ROADMAP_GRAPH.md`（不要手改，agent 读写靠工具）|
| 文档总索引 | `docs/README.md` |
| 决策档案 | `decisions/*.md`（accepted 不可改原文）|

**重启 dsh**：Stop-Process dsh+llama → `Start-ScheduledTask -TaskName RestartDsh` → 10~70s（需已登录）。
**看门狗空转陷阱**：RestartDsh 卡 Running+IgnoreNew 时，[ACTION] 日志刷但 pid 不变 → `Stop-ScheduledTask` 回 Ready 再重启。
