# 时间线（可扫读里程碑）

> 完整逐日日志见 `D:/Brain/workspace/memory/`。这里只列**改变了方向的节点**。

## Ⅰ 环境搭建（10-13～10-19）
- **10-13** dsh 接入本地 Ollama；发现 `/v1` 接口的 `think:false` 无效（→ 给 maxTokens 留余量）
- **10-14** 4B 反而比 8B 慢（256K 原生上下文 KV 开销）→ [ADR-0010](../../decisions/0010-4b-not-lightweight.md)
- **10-16** 本地 SearXNG 替换内置搜索 → [ADR-0009](../../decisions/0009-local-searxng-provider.md)
- **10-19** 选定 llama-server 主线 → [ADR-0001](../../decisions/0001-adopt-llama-server.md)

## Ⅱ 引擎调优（10-20～11-06）
- **10-20** CUDA 12.5 平移 D 盘；dsh session-trash-bin 重写
- **10-27** n-cpu-moe 40/2736 翻案（用户坚持复测）→ [ADR-0003](../../decisions/0003-ncpu-moe-40-cache-2736.md)；整层挪 GPU 证伪 → [ADR-0004](../../decisions/0004-reject-whole-layer-gpu.md)
- **11-03** "输出一半就完成"定位，确认提前 EOS 与显存无关
- **11-05** autoparser 补丁确认有效；升级 0.9.0
- **11-06** 预填充"卡死"真因=视觉编码器在 CPU → [ADR-0005](../../decisions/0005-mmproj-offload.md)

## Ⅲ 行为定位（11-07～11-16）
- **11-07** 「只输出好」= 上下文自强化回路；中文锚点必须自述句 → [ADR-0006](../../decisions/0006-chinese-anchor-self-narration.md)
- **11-10** 温度 U 形 → [ADR-0008](../../decisions/0008-temperature-07.md)
- **11-15** 模板移植 + 投机参数自调优；发现 ik 的 DRY 慢 2.6 倍（弃用 ik）
- **11-16** 中文思维链锚点定稿

## Ⅳ 架构成形（11-17）
- **08:20** 海马体（task-state）、前额叶（task-plan）外置
- **16:30** 插件合并：4 插件 → 3 插件（behavior-guard + continuity + llama-autostart）
- **18:40** `D:/Brain` 独立域——脑与 WorkBuddy 解耦，重装免疫
- 确立核心方法论："**守卫是免疫细胞，脑区是外置器官**"

## Ⅴ 工程化与心智（11-18）
- **00:52** 两插件再合并为单包 v2.0
- **01:35** 控制回合（v2.1）；**02:25** Trace/Skills/危险分级（v2.2）
- **09:30** G1-G7 自进化机制落地（v2.3）
- **10:45** 库成唯一真源（v2.4）；**11:40** 可移植性（v2.5）；**11:45** 全栈一致性（v2.5.1）
- **12:35** dsh rc.3 升级；**12:42** `{{cwd}}` 破坏性变更修复（v2.5.3）
- **13:10** README 总分式重构（v2.6）；**13:20** 定位提炼为"合成心智"（v2.6.1）
- **13:50** 心智状态快照接入（v2.7）；**14:12** 调研反面证据撤销强制二选一（v2.7.2）
- **14:30** 心智拼图 P0-P2 全部落地（v2.8）

> 决策详情见 [decisions/](../../decisions/README.md)，调优细节见 [tuning/](tuning/README.md)。
