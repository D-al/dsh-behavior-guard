# 审计：有没有"官方参数就够、我们造轮子反而更慢"

> 日期：2026-11-22 · 触发：用户问"已做的里面有没有官方几个参数就支持但我们重复造轮子，导致结果反而没官方快的情况"
> 方法：两条独立调查（引擎层 / harness 层）+ 主代理一手核实。`llama-server --help` 实测 + asar 官方文档提取。

## 结论（先说答案）

**没有找到"官方参数够用 + 自研更慢"的确凿案例。**
最像轮子的两个，反而**反向印证了官方能力**：
- `CTX_CHECKPOINTS` 就是官方 `--ctx-checkpoints`（PR #15293），关掉才慢 23%
- `moe-cache` 的"慢"是**官方全局参数误用**（share=1.0 端到端慢 2.4×），我们的补丁填的是上游真实缺口（分批 share）

但找到**三类值得注意的情况**，见下。

## 一、用的就是官方能力，只调参（不是轮子）

| 候选 | 真相 | 一手证据 |
|---|---|---|
| CTX_CHECKPOINTS | 官方参数 `--ctx-checkpoints`（默认32，我们设2）| `llama-server --help`：`-ctxcp, --ctx-checkpoints, --swa-checkpoints N ... PR #15293` |
| 投机解码 | 官方 `--spec-type draft-mtp`（我们用的就是官方类型）| --help：`--spec-type none,draft-simple,draft-eagle3,draft-mtp,...,ngram-*` |
| ngram 证伪 | 不是"官方 ngram 烂"，是"相对 MTP 无收益" | 项目实测 nmax 7：26.73 < 27.31 |
| moe-cache-cpu-share | 官方参数踩坑 → 端到端慢 2.4× | DECISIONS.md#5：decode +37% 但 P5 慢 2.4× |
| 压缩存档 | **100% 官方 `dsh-compaction-basic`**，只调 thresholdRatio 0.6→0.55 | profile.patch.yml 注释"逐条目比对，除新增config外完全一致" |
| todo / plan / approval / skills 工具 | 全是 dsh 官方原生，项目已启用 | asar `docs/subsystems/*.zh.md` + cordis.patch.yml |

**官方 `--cache-prompt` 试过但不适配**：90K 上下文下卡 40-100s，不是"没用官方参数"。

## 二、填官方真实缺口（合理自研）

| 自研 | 补的什么缺口 | 证据 |
|---|---|---|
| moe-cache 分批补丁 | 官方只有**单一全局** share；补丁让解码批 share=1.0 / 提示批 share=0 | P1/P2 从 199s→78s；.env 注释"★引擎补丁" |
| autoparser 2 行 | 上游未修的空白 bug，#29307 是大重构不会吸收小修 | docs/BRAIN_AUDIT_20261118.md:135-136 |
| 守卫 L0-L3 / D1-D5 / verify-on-edit / 控制回合 / present 深检 | dsh 官方文档无等价物（official auto-review 是**工具安全评审**，不是产物质量评审）| scaffold +15.6pp / 30-30 门禁 |
| 压缩后存档回注 | 官方 compaction 只做摘要替换，不注入自定义任务存档 | index.mjs:1942-1990 |
| todo 闹钟 / P1.5 回灌 | 官方 `dsh-tool-todo` README 明确"没有提醒机制/没有部分更新/没有回读" | 原生工具 + 自研闹钟是配合，不重复 |
| frame_limiter | Windows 无"按引擎限帧"官方 API | 单 GPU 无核显，实测真凶 WorkBuddy+dwm 的 3D 抢 Copy |

## 三、重复且更弱（真候选，值得重评）

### 3.1 skills 双轨（最像轮子）
- **官方**：`dsh-skill-filesystem` + `dsh-tool-skill` 已启用（`cordis.patch.yml:419/425`），支持分层注册表、`whenToUse`、模型主动加载（渐进披露）
- **自研**：`index.mjs:283 loadSkills()` + `:2023` 关键词命中注入，无分层、关键词脆弱，每会话最多 2 张卡
- **官方路径已在用**：`config/AGENTS.md:237-238,262` 明确教模型用 `skill` 工具
- **保留意见**：对 35B 弱模型，"关键词自动提醒"可能比"模型主动调用"可靠——但**没有实测数据**证明自动注入更好或更快

### 3.2 多角色裸 fetch（架构性重复）
- **官方**：`subagent.zh.md` 提供独立 preset / 模型覆盖 / outputSchema / Team 共享任务 / 生命周期；`workflow.zh.md` 脚本编排——但项目把 `delegation` 整组禁用了
- **自研**：`index.mjs:1367-1422` 用 fetch 直连 8081，单条 user message、无会话历史，靠 temperature 做伪"去同源"
- **合理降级理由**：8G 显存单 35B 跑不起第二个模型；"小模型做审计"已列明确不做
- **重要纠正**：诊断文档的"Critic 0% / 验收员从未触发"是**历史状态**，且部分是单测伪造数据误报；v2.16 已修

### 3.3 frame_limiter（过度工程嫌疑）
- 项目自己文档列了零成本方案（NVIDIA 面板限帧 / 全局帧率限制）
- 核心"给 dsh 降帧治卡死"的诊断后来被证伪（真凶是 WorkBuddy+dwm）
- 但现行全局 EcoQoS 方案实测有效，且 Windows 确实没有按引擎限帧 API——判"过度但未证伪"

## 四、诚实标注的局限

1. **没做受控 A/B**：说"真重复且更弱"是**架构能力对比**，不是"关掉自研版本后端到端跑一次"——因为 dsh 关着（按需），且切换会动生产配置。要下定论需要受控实验。
2. **ngram 的裁定窗口偏短**：项目记忆记"6 分钟固定窗口判 ngram 无收益"——短窗口可能低估 ngram 在长上下文的优势，这是个证据薄弱点。
3. **官方文档可能领先本机版本**：如 ADR-0029 所示（ctx.tools 热替换），实施前必须在本机 dsh 0.2.2-rc.3 做 smoke test。

## 五、可操作建议（未执行，待用户拍板）

1. **skills 双轨**：做一次受控实验（全注入 vs 仅官方 skill 工具），用 P1-P5 端到端成功率判定，不用 decode t/s
2. **多角色裸 fetch**：保持现状（硬件约束下合理降级），待有多卡再评估官方 subagent
3. **frame_limiter**：保持现状（已实测有效），不因"有零成本方案"就拆

## 铁律沉淀
**"官方有参数"≠"我们该用"，"我们自研了"≠"重复造轮子"。**
判据只有两条：① 官方能力是否真覆盖同一构念（不是名字像）② 端到端实测谁更快/更可靠（不是 decode t/s）。
