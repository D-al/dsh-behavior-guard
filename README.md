# dsh-agent-harness

> **合成心智（Synthetic Mind）**：用一个 35B 本地模型 + 一套确定性脚手架，合成比模型本身可靠得多的心智——**模型权重一个字节没动，变的是它外面的脑区**。

本仓库是 **Single Source of Truth**：插件代码 + 生产配置 + 10 个技能 + 19 个工具 + 决策档案 + 一键安装。
当前 **v2.9.0**（2026-11-18）。仓库名沿用历史名 `dsh-behavior-guard`，npm 包名/插件 id 为 `dsh-agent-harness`。

---

## 快速入口

| 你是谁 | 从哪读起 |
|---|---|
| **只想用** | [一键开箱](#一键开箱) → [说明书](docs/MANUALS.md) |
| **想接手开发** | [文档地图](docs/README.md) → [路线图](ROADMAP.md) → [决策档案](decisions/README.md) |
| **想知道为什么这么做** | [8 条分支](docs/MANUALS.md#8-心智拼图操作手册p0-p2) → [调研汇总](docs/MIND_GAPS_RESEARCH.md) → [社区对比](docs/COMPETITIVE_ANALYSIS.md) |
| **想看历史** | [时间线](docs/history/TIMELINE.md) → [调优决策](docs/history/tuning/DECISIONS.md) |

---

## 五层涌现逻辑（历史的真实骨架）

> 时间线是表象，**依赖链才是本质**——每一层都是下一层的前提，跳过任何一层都建不成脑。
> 这段逻辑决定了我们文档的组织方式和未来工作的优先级。详见 [历史说明书](docs/history/README.md)。

| 层 | 名称 | 做了什么 | 时间 | 为什么是下一层的前提 |
|---|---|---|---|---|
| 1 | **物质基础** | 推理引擎 + 模型权重（llama.cpp / Q4 / CUDA / 8G 边界）| 10-13～10-19 | 没有引擎和权重，后面无从谈起 |
| 2 | **调优基础** | 让引擎稳定跑起来（显存账 / KV q8_0 / 温度 U 形 / 投机解码）| 10-20～11-06 | 不稳的地基上建不了脑；此层确立"端到端验证"铁律 |
| 3 | **构建脑** | 外置器官（L0-L3 / 海马体 task-state / 前额叶 task-plan / 免疫）| 11-07～11-17 | 有了稳定算力才发现行为缺陷，才需要器官 |
| 4 | **合成心智** | 器官整合为整体（三角色 / 控制回合 / D:/Brain 独立域）| 11-17～11-18 | 器官齐了才谈得上"合成"，权重零改动变外面 |
| 5 | **进一步探索** | 元认知 / 自进化 / 可复制（心智拼图 / 6 路调研 / 文档架构）| 11-18～ | 心智成形后才问"它会不会更新自己" |

**反向检验**：如果第 2 层没做（不懂显存墙、没证伪 decode 伪优化），第 3 层的外置器官会直接撞显存天花板；
如果第 3 层没做（没见过「只输出好」回路），第 4 层的三角色就没有要解决的问题。这就是依赖链的意义。

## 一句话定位与三个认知

**把"能由系统可靠完成的事"从模型肩上卸下来，让模型只专注决策。**

| 认知 | 来源 | 意义 |
|---|---|---|
| 模型不是瓶颈，harness 是 | 换 scaffold +15.6pp / +26pp（[2604.11465](https://arxiv.org/abs/2604.11465)）| 优先改 harness |
| decode t/s 是误导性指标 | 本项目证伪：+37% decode 却端到端慢 2.4× | 加速必须端到端验证 |
| 合成 > 调教 | 权重零改，能力来自外置器官的组合涌现 |  muscles→反射→器官→整合→合成 |

> 护城河是**整合与跨层复用**，不是任何单一技术原创——详见 [社区对比](docs/COMPETITIVE_ANALYSIS.md)。

---

## 路线图（三阶段）

> 完整、可验证的目标见 [ROADMAP.md](ROADMAP.md)。这里只列骨架。

| 阶段 | 时间 | 主题 | 核心目标（可验证） |
|---|---|---|---|
| 🟢 **短期** | 1-2 周 | **收口已知风险** | ① spec 阈值 0.65 用 P3/P4/P5 标定（误触发 <10%）② Critic 去同源（只看产物+证据，不看执行者推理）③ test-time 自适应原型（token 降而成功率不降）④ v2.9.0 新机制跑 3-5 个真实长任务回归 |
| 🟡 **中期** | 1-2 月 | **从能用到可靠** | ① 每轮结构化成功/失败判定，攒 20-50 条跑技能进化 ② CritBank 月度归档、假记忆自检 ③ 情景检索进主循环（历史经验被主动引用 >0 次）④ 工具面 28→18-20 ⑤ 会话树实时化 |
| 🔴 **长期** | 季度级 | **架构完整性** | ① GWT 广播总线（共享状态对象）② FEP 预测闭环（先断言→比对→偏差驱动）③ 用户意图 BDI 深化 ④ autoparser PR + v1.0.0 升级 ⑤ 迁到社区标准 benchmark |

**明确不做**：多模态/CUA、通用 agent 框架、向量检索代码、模型微调、堆更多 judge。理由见 [ROADMAP §不做](ROADMAP.md#明确不做)。

---

## 硬约束（不可突破）

- **硬件**：i7-12650H / 64G DDR4 / RTX 4060 Laptop **8G** / Qwen3.6-35B-A3B UD-Q4_K_XL（21.28 GiB）
- **显存安全线**：空闲 ≥450 MiB；低于 186 必卡（WDDM 换页 → 1~2 t/s）
- **引擎**：自编 b12244 + autoparser 两行补丁（上游 [未合并](https://github.com/ggml-org/llama.cpp/pull/29307)，每次升级重打）
- **配置铁律**：`.env` 覆盖 INI；`CTX_CHECKPOINTS=2` 承重墙；`MOE_CACHE_CPU_SHARE=0`；`.env` 的 `LLAMA_35B_TEMP` 必须留空

---

## 一键开箱

```
git clone https://github.com/D-al/dsh-behavior-guard.git && cd dsh-behavior-guard
.\setup\install.ps1 -DryRun
.\setup\install.ps1
.\setup\links.ps1 -DryRun
.\setup\links.ps1
# 重启 dsh 后验证：curl http://127.0.0.1:8081/health
#                python bench/config_check.py
#                python bench/regression_check.py   → 30/30
```
新机器仍需手工：dsh/llama.cpp 本体、b12244 二进制、计划任务。详见 [说明书 §1](docs/MANUALS.md#1-一键开箱与同步)。

---

## 文档地图（一句话职责）

| 文档 | 职责 |
|---|---|
| **README.md**（本文）| 薄入口：定位 + 路线骨架 + 导航 |
| [ROADMAP.md](ROADMAP.md) | **活文档**：短中长期目标，每条含验证方法 |
| [docs/README.md](docs/README.md) | 全部文档的索引与分工 |
| [docs/MANUALS.md](docs/MANUALS.md) | **说明书集合**：怎么装、怎么调、怎么查 |
| [docs/history/](docs/history/README.md) | **历史说明书**：时间线 + 调优决策 + 经验证据 |
| [decisions/](decisions/README.md) | **ADR 决策档案**：为什么这么决定（不可变） |
| [docs/MIND_GAPS_RESEARCH.md](docs/MIND_GAPS_RESEARCH.md) | 6 路调研：心智还缺什么拼图 |
| [docs/COMPETITIVE_ANALYSIS.md](docs/COMPETITIVE_ANALYSIS.md) | 社区对比：先进 / 落后 / 以为先进其实平凡 |
| [docs/MD_SYSTEM_PLAN.md](docs/MD_SYSTEM_PLAN.md) | 文档分层原则（三层体系） |

## 版本历史
完整版本历史 → [CHANGELOG.md](CHANGELOG.md)。当前 **v2.9.0**（心智拼图 P0-P2 + 学习闭环双向合流，全部在线）。

## License
MIT
