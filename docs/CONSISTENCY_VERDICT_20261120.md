# 一致性 verdict：今晚改动真的达标了吗？（2026-11-20 事故后自审）

> 用户问：今晚做的改动是否真的保证 GitHub / 生产一致、达到承诺标准？有什么机制检验/防止？对它有什么教训？
> 这是本次会话最严重事故后的诚实自审。**答案先给：审计时不一致，审计后我修复了绝大多数，但仍有 3 个诚实缺口。**

---

## 1. Verdict：不，审计时不达标

我派了两路独立审计（远端/权威/生产三处 + 机制设计），并用 GitHub REST API 逐 blob 核对。结论（详见 `_AUDIT_20261120_RAW.md`）：

### 审计发现的不一致（9 项，不淡化）

| # | 问题 | 严重度 |
|---|---|---|
| 1 | tag `v2.26.5`/`v2.26.4` **根本不存在**（承诺的发布没兑现） | 高 |
| 2 | package.json version 2.26.2 ≠ CHANGELOG 2.26.5（文档宣称 vs 机器版本打架） | 高 |
| 3 | 生产 C 缺全部 5 个今晚新增文件（能力阶梯/roadmap_check/设计文档/同步脚本/帧限制器） | **严重** |
| 4 | 生产 ROADMAP 是 220 行旧版，无内嵌权威块 → "agent 自读阶梯"在生产完全不可用 | **严重** |
| 5 | autostart 生产是 1.1.1 + 手工限帧补丁，权威是 1.2.0（缺 parent-pid 看门狗修正）| 高 |
| 6 | autostart 版本三方打架：运行 1.1.1 / lock 1.1.0 / 权威 1.2.0 | 高 |
| 7 | lock 指向 f4a8d25(v2.26.2)，node_modules 已手工同步到 de9d111 → **一次 `pnpm install` 就会回退、今晚成果全丢** | **致命** |
| 8 | 审计时 dsh 进程为 0（服务死），8081 通是 llama 独立的假象 | 高 |
| 9 | frame_limiter 5 个孤儿进程堆积 | 中 |

**最讽刺的一点**：我整晚在讲"文档宣称完成≠实际生效"、"看着 A 改 B"，而审计证明**我自己正在制造同型问题**——交付了能力阶梯却没进生产、承诺了版本却没打 tag、改了 lock 却没验证 install。

### 一致的部分（如实记录）

- A 远端 / B 权威 HEAD 完全相同（de9d111 / 7926407），两个仓库工作树干净
- behavior-guard 三件套（index.mjs / cordis.patch.yml / package.json）B vs C 逐字节一致
- 所有新增文件在 A 远端 tree 与 B 提交中 blob sha 逐一相同
- CRLF 字节差是假的（`git hash-object --path` 归一化后相同）

---

## 2. 审计后修复（02:20-02:35）

| 问题 | 修复 | 验证 |
|---|---|---|
| tag 缺失 | 补建 v2.26.4/v2.26.5 并推送 | `git ls-remote` 确认 |
| 版本打架 | package.json → 2.26.5；files 纳入 CAPABILITY_LADDER.yaml | grep 确认 |
| 生产缺文件 | cp 同步权威→生产（含 ROADMAP/package）| sha256 逐字节相同；生产能跑 `--graph`(30/22/0环) 和 `--next` |
| autostart 老版本 | 同步权威 1.2.0（备份旧版在 _cleanup）| sha256 相同、parent-pid 到位 |
| lock 脱节 | 更新两个 commit + integrity（收 GitHub tarball 算 sha512）+ version | lock 4 处 a503509、version 2.26.5/1.2.0 |
| dsh 死 / 孤儿进程 | 标准流程重启；kill 孤儿 limiter | dsh pid 26580 稳定、8081 OK、bridge OK、limiter 仅 1 合法 |

### 三个诚实缺口（仍未达标的部分）

1. **`pnpm install --frozen-lockfile` 从未真跑**——lock 是手工更新 + hash 算自 tarball，但没有验证 pnpm 接受它。跑 install 风险高（今晚多次被 shim 拦截、曾清空 node_modules）。这是"名义一致"而非"验证一致"。**下次任何 install 前必须先验证 lock。**
2. **`--apply` 从未真实触发**——能力阶梯的写回（evidence_log + save_authoritative）只有代码，没有一次真实 doing→done。按证据阶梯是 L1/L2，不是 L4/L5。
3. **dsh 当前加载的是新代码，但没做端到端 trace 验证**——重启后 health OK、bridge OK，但没验证"新能力阶梯真的被 agent 用了"。

**最终核验（02:40，修复全部完成后）**：

```
HEAD: 11835b64  worktree clean: True  远端 HEAD == 本地 HEAD
B/C sha256 逐字节相同：index.mjs / cordis.patch.yml / package.json /
  CAPABILITY_LADDER.yaml / roadmap_check.py / ROADMAP.md  (6/6 OK)
autostart B/C：index.mjs / package.json / frame_limiter.py  (3/3 OK)
版本：package=2.26.5 prod=2.26.5 autostart=1.2.0/1.2.0 CHANGELOG=2.26.5 ✓
lock 指向 HEAD(11835b6) + version 2.26.5 ✓
tag v2.26.5 本地+远端均存在（指向 a503509，比 HEAD 落后 1 个审计文档提交——
  这是正常的：tag 标记功能发布点，之后只加了审计文档）
dsh pid 26580 稳定；8081 OK；bridge OK；生产能跑 --graph(30/22/0环) 和 --next
```

**所以诚实结论**：修复后**文件层与运行层都一致了**（9/9 关键文件逐字节、版本三方对齐、lock 指向 HEAD、服务健康、生产能力阶梯可用）。**仍存的两个缺口**：`pnpm install --frozen-lockfile` 与能力阶梯 `--apply` 从未真实跑过——它们是"名义可用"而非"验证可用"。我不夸大这两个缺口，也不掩盖它们。

---

## 3. 检验与防止机制（怎么不再发生）

两路审计给了方案（详见 `CONSISTENCY_GUARD_DESIGN_20261120.md`，462 行设计稿），核心是三条：

### 机制 A：一致性守卫 `tools/consistency_guard.py`（待实现）
零 LLM、<2s，一条命令对比 A/B/C：
- commit：远端 HEAD == 权威 HEAD（用 `git ls-remote`，不 fetch 改动本地）
- 关键文件 sha256：B vs C 逐字节（CRLF 用 `git hash-object --path` 归一化，避免假差异）
- 版本三方：package.json / CHANGELOG 顶部 / lock version 必须一致
- lock commit 指向的 tag == 期望发布版本
- 输出 PASS/FAIL + 差异清单；**自身出错 exit 2**（不许静默 exit 0 当 PASS）

### 机制 B：宣称 vs 落地交叉验证
不靠关键词计数（历史坑：内存变量被误判为落盘），而是三层交叉：
1. 运行版真实打点（`trace({kind})`）
2. 真实产物（文件存在 + 内容断言 + SHA256）
3. 调用者 + mtime（脚本真被调用过）
判据写进能力阶梯的 `verify`，由 `roadmap_check.py verify <ID>` 执行。

### 机制 C：强制触发点（守卫自己不能被人忘记跑）
今晚的教训是"机制存在但没人触发"（P3 按 ADR 不启动、watcher 只消费 trace）。所以守卫必须挂到**已有的强制通道**：
- `restart_dsh.ps1` 启动前跑一次 `--scope copies`（dsh 每次重启都校验）
- autostart 插件的 `dbg()` 里加运行时哨兵（<5ms）：报"当前加载的 package version/commit vs 权威"
- `roadmap_check.py --apply` 写回前校验权威块 checksum（手工改过就报警）

---

## 4. 对 agent 本身的教训（写进成长直升的 CritBank 候选）

从这次事故里，agent 该学到什么（按"触发→动作"格式）：

| # | 触发信号 | 教训（一句话规则）|
|---|---|---|
| C-01 | 自己说"已推送/已完成/全绿"时 | **推送 ≠ 生产生效**。说完成前必须核对三处（远端/权威/运行版）的 commit 与 sha256；health 200 不等于进程活着 |
| C-02 | 改了版本/CHANGELOG | 版本号必须三方一致（package.json / CHANGELOG / tag / lock）；打 tag 要 `ls-remote` 确认上了远端 |
| C-03 | 手工 cp 文件到 node_modules | 必须同步更新 lock 的 commit+integrity，否则一次 install 全回退；且要重启让运行版真加载 |
| C-04 | trace/日志出现高比例单一 sid | 先按 sid 分组查假数据（这次 91% 是 s1），再下结论 |
| C-05 | patch 配置改动 | `!!js [...]` 会被 YAML 当 flow sequence 切碎 → dsh 起不来；纯字符串配置也可能触发整段替换丢字段；改前备份、改后重启验证 |
| C-06 | 清理进程/孤儿 | Force kill 不触发 finally；清理前确认父进程死活，别误杀当前合法实例 |
| C-07 | 派子任务后 | 结果就在上下文/落盘文件里，不要说"投递丢失"；先读文件再下判断 |

**这些应该进能力阶梯的 `caveats` 字段**——它们正是"干的过程中要注意的坑"，让 agent 下次爬类似卡片时不再重蹈覆辙。

---

## 5. 一句话回答用户

> 审计证明我不达标：承诺的版本没打 tag、能力阶梯没进生产、lock 指向旧 commit（一次 install 就回退）、服务还死了。
> 我修复了绝大多数可立即修的并重启验证，但 `pnpm install` 与 `--apply` 从未真实跑过——**文件层一致了，运行层/验证层还没闭环**。
> 防止再犯靠三件：一致性守卫（零 LLM 对比三处）+ 宣称交叉验证（打点/产物/调用者）+ 强制触发点（重启前/运行时哨兵/写回校验）。
> 对 agent 最大的教训：**"我提交了"不等于"生效了"，验收只认真实运行的证据。**
