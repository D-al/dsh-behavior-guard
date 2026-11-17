# Changelog

所有迭代以本地时间记录（UTC+8）。格式参考 Keep a Changelog。

## [1.0.1] - 2026-11-17 21:45

### Added
- 详细 README：问题演进史（7 个实测失效现场）、途径、论文对照表、信号清单与实测结果、解决程度
- 版本戳与 tag（v1.0.1-20261117-2145）

### Fixed
- 首推 GitHub 时 `index.mjs` 缺失（构建产物复制被环境拦截未察觉）——从迁移备份补齐后重新推送（fcd3e6f）

### Security/Reliability
- 本仓库曾被 `pnpm update` 以旧版覆盖过一次（本地新版未先推送）——已确立纪律：**本地维护的插件必须先推 GitHub 再 pnpm update**

## [1.0.0] - 2026-11-17 19:58

### Added（首推 GitHub）
- 合并版首发布：dsh-turn-continuation-guard（L0-L3）+ dsh-audit-loop v3.3 合并为单插件
- 共享轨迹收集（call/todo/assistant 全入 trail）+ 统一注入预算（sharedMaxPerTurn=3）
- bundle 包形态（package.json `dsh.bundle.patch` + 包内 cordis.patch.yml）

### 内部迭代时间线（合并前的演进，均在 2026-11-17）
- 08:30-11:00 v1（turn-continuation-guard）：L1 文件声明校验（环境级 verified finish）+ L2 贴代码 + L3 确认词——26/26 单测
- 11:00-13:30 v2（audit-loop）：周期无历史审计（每 8 步）+ 修正器——漂移会话 step6 命中实测
- 13:30-14:30 v3.1：三档状态（FAIL/UNPRODUCTIVE/OK）+ 证据全文机制（审计看 2000 字证据而非 120 字摘要）——伪造验收 FAIL 精确判定
- 14:30-15:00 v3.2：只读代执行（纠正器确定正确参数后直接代跑）+ spawn 验收超时触发 verify_agent.py 代验收
- 15:00-16:00 v3.3：todo/write 观测 + D3 冗余 todo 检测（双向验证：真实推进不误伤/真冗余命中）
- 16:20-16:30 合并：turn-guard(339 行) + audit-loop(569 行) → behavior-guard(~750 行)，26/26 单测迁移全过

### 实验证伪记录（也是资产）
- v3.2 的"try 模式切换 + reasoning 预算硬切"实验：A/B 16 请求证明无效且有害，已回滚
- 审计员"todo 状态更新=浪费"误判：重放验证后加入判定纪律（防误伤）

[1.0.1]: https://github.com/D-al/dsh-behavior-guard/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/D-al/dsh-behavior-guard/releases/tag/v1.0.0
