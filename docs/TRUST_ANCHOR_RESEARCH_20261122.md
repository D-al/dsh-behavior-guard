# 无限回归的终止点：信任锚调研（2026-11-22）

> 缘起：用户问"基于对审计者本身的信任有没有更天然的解法？区块链能否帮忙？"
> 两路并行调研（信任根基工程解法 / 区块链密码学批判评估）结论一致。

## 一、总答案

**理论终点不存在，实践可止损。** 这是明希豪森三难（Münchhausen trilemma）的工程版：
任何证成只能落在无限回溯、循环自证、武断中止三者之一。所有成熟方案本质都是
"选择在哪里停止追问"，并让停止点尽可能小、可独立复验（de Bruijn 准则）。

**区块链：在这个场景有害（用错工具）。** 详见 §三。

## 二、五条路径评估

| 路径 | 核心洞察 | 对我们 | 成熟度 |
|---|---|---|---|
| **TCB 最小化** | 回归不消失，被集中到可审计的窄接口。seL4 内核 1-1.6万行 C，但证明体 110万行/20人年；官网明示假设（340行汇编/启动代码/硬件/DMA/侧信道在证明外）| ❌ 单人不可行 | 生产级 |
| **形式化验证 / PCC** | de Bruijn 准则：证明生成可复杂不可信，**证明检查必须小而独立**——目前唯一数学意义上成立的终止点。Lean4 内核 5-6千行 C++，mathlib 50万行不可信只产证明 | ⚠️ 只做局部不变量可行 | 成熟但需专家 |
| **确定性小检查器** | "untrusted solver + trusted checker"：审计者做成确定、无外部依赖、纯函数后，"审计者的审计"从"再运行一个程序"**降级为代码审查**——成本最低的维度降级 | ✅ **最优** | 成熟+前沿 |
| **能力安全/类型系统** | 让腐化在编译期/硬件层**不可编码**（CHERI tag+bounds、Rust ownership、Idris 依赖类型）；但只覆盖可编码的不变量，语义正确性仍需外部锚 | ❌ 需换语言/硬件 | 部分成熟 |
| **透明日志/供应链** | 不证明代码正确，只证明**"运行的就是你审查过的那份"**——把"身份/来源"从"正确性"剥离独立解决。SLSA 1.2 / Sigstore Rekor / in-toto | ✅ 部分有用（见§四）| 大规模部署 |

## 三、区块链：为什么有害

1. **场景错配**：区块链核心是多方互不信任下的拜占庭共识（NIST IR 8202 / 以太坊白皮书）。
   本场景只有一个参与方，且该方（LLM）正是要防的攻击者——没有 n=3f+1、没有 Sybil 威胁，
   BFT 在解一道不存在的题。
2. **安全假设倒置**：唯一操作者即对手时，链只是把 LLM 说的任何话**永久固化**——
   "上链=不可篡改"制造致命的虚假安全感（garbage in, garbage out forever），
   还引入节点/密钥/gas/共识依赖与更多攻击面。
3. **学术印证**：Budish《The Economic Limits of Bitcoin and the Blockchain》指出企业本有
   更便宜的可信方数据安全形式；2025 Emerald 论文实证联盟链最终沦为可信第三方，变得多余
   （Hawlitschek "trust-free fallacy"）。

**zkVM 也不能救命**：ZK 证明"程序 P 在输入 X 输出 Y"——若 LLM 能改 P（门禁本身），
证明就是在为恶意程序背书；只是把回归搬到电路。且一次本机检查重跑远便宜于验签，
验签远便宜于证明（prove once verify forever 适合多方反复验证，不适合我们）。

**可信时间戳价值极低**：只证明"某哈希不晚于某时刻存在"，不证明内容为真/日志完整/
呈现者即盖章者。OTS 自述"若不知道入侵何时发生，时间戳帮不了你"——LLM 自修改恰不知漂移起点。

## 四、真正有用的部分（不用区块链）

**密码学不能消灭回归，只能把锚从代码挪到密钥/外部锚点**——信任必须终止于某个
你愿意不证明就相信的东西。优先级：**硬件隔离 > 第二设备/本人 > 外部透明日志**。

- **git 已是 Merkle DAG + 内容寻址**：`git rev-parse HEAD` 就是内容指纹，`git log` 是不可篡改的
  时间证明。我们现有的 sha256 权威源/运行版对比就是 git 思想的简化版。
- **git 的硬边界**：有 push 权限者可 rebase/force-push 重写全部历史，新 clone 哈希自洽无警告；
  只有拿**独立信任锚**对比才有效。SHA-1 已可碰撞，应迁 SHA-256。
- **最小可行**：git(SHA-256) + 签名提交/标签，**私钥放在被审机器之外**；
  drift 日志用 HMAC 哈希链；把 HEAD/树根**单向发布到第二设备/邮箱/公共日志**作外部锚。
  无外部锚则链与 git 都只是自证。
- **强制验签是灵魂**：无强制执行的签名只是装饰。

## 五、本项目现状与建议

### 实测的信任基规模（2026-11-22）
- `index.mjs` 2445 行 / 41 顶层函数——**太大，不可能"显然正确"**
- `foundation_guard.py` 180 行、`test_census.py` 106 行、`fingerprint.py` 113 行——小
- `check_verify.py` 389 行、`roadmap_check.py` 820 行——偏大
- **L4 依赖 L3/L2（guard 调 census/audit_verify/tech_tree），无循环依赖**——真分层
- ⚠️ **但 L4 和 L2 都调用同一批检查器**——"两次通过"不是两个独立证据，是同一检查跑两次

### 实证的 evaluator tampering 风险
- `foundation_guard.py` / `run_all.sh` / `AGENTS.md` **均无写保护标记**——agent 可改自己的评判者
- git 历史证实 agent 确实改过 `run_all.sh`（cba4600 等）
- 2026 自改进 harness 论文（arXiv:2611.22299 / 2509.26354）明确列出 evaluator tampering、
  权限自削弱、benchmark gaming，防御是：**agent 不得改写唯一评判测试、不得削弱权限层、
  harness 必须版本化并经人工评审**

### 建议（按性价比）
1. **冻结评判测试**：把 `run_all.sh` / `foundation_guard.py` / 关键 test_* 设为"仅人工可改"
   （流程约束：agent 改这些必须先问用户；技术上可用 git path 保护/hook 提示）
2. **缩小信任基**：把地基不变量抽成独立小模块（guard 已是静态扫描，不依赖 import，可行）
3. **外部锚**：把 HEAD/体检结果单向发到第二设备或邮箱（零成本外部验证点）
4. **不建议**：区块链、zkVM、TSA、全量形式化验证、换 CHERI 硬件

### 一句话
不需要第六层审计者。需要的是**把信任压缩到一个小而独立、可人工复验的核**，
并让"被审对象 = 运行对象"（内容摘要锁定）——加上一个**在机器之外的锚**。

## 六、出处
Hans Albert《批判理性论》1968 / Münchhausen trilemma；de Bruijn 准则；
sel4.systems FAQ；Necula PCC；Lean4Lean arXiv:2403.14064；compcert.org；
FORGE/PCAS arXiv:2602.16708（Datalog 策略，LLM 遵从率 48%→93%）；
CHERIoT 1.0 (2025-11)；SLSA v1.2 (2025-11)；Sigstore Rekor v2 (2025-10)；
NIST IR 8202；Budish 2018；Emerald SCM 30(2) 2025；gethasp.com；
OpenTimestamps 0.7.2；arXiv:2611.22299 / 2509.26354（自改进 harness 安全）。


---

## 七、追问：锚不必是人，只要不是执行者就行？（2026-11-22 10:25 调研）

### 答案：直觉对了一半。"人"不是定义属性，但"不是执行者"是必要远非充分。

**信任锚的形式定义**（NIST SP 800-57 / RFC 5280 / RFC 4949 / TCG）：
锚是"信任被假定、无上层可验证者、经带外注入"的权威实体——可以是公钥、CA、硬件 RoT，
**从来不需要是人**。human 只是 bootstrap 决策者（root program），是另一个层次。

### 精确判据：不是"它是谁"，而是"执行者是否持有任何能影响它或其送达通道的 capability"

设 E=执行者，A=候选锚，V=消费 A 输出的验证器。A 是真锚当且仅当同时满足：
1. **不可达**：E 不持有指向 A 的任何 capability（不能读写/删除其状态或判定逻辑）——
   不是"不同进程"，而是权限不可达；
2. **带外通道**：A→V 的传递不被 E 控制（不可伪造/重放/替换/丢弃）；
3. **终止性**：V 不用同一机制反证 A；再加一层软件验证只是把锚后移，递归不终止。
   TCG 原文："must be trusted because misbehavior is not detectable"；
4. **不可传递**：E 不能通过调用 A 间接获得 A 的权限（capability 不可代理/委托）。

### 光谱（从假锚到真锚）
| 形态 | E 能篡改? | 真锚? |
|---|---|---|
| 同进程另一个函数 | 能（共享内存）| ❌ |
| 同机同权限脚本 | 能（直接改）| ❌ |
| 另一个 LLM verifier | 不能直接改文件，但共享环境/注入面/偏见 | ❌ 伪锚 |
| 不同 OS 用户+ACL+只读代码 | 普通用户不能、管理员能 | ⚠️ 弱锚（条件成立时）|
| chattr +i（E 无 root）/ 只读挂载 | 不能 | ✅ 较强 |
| TPM sealed key / Secure Boot / VBS-HVCI | OS 层不能 | ✅ 强（证明平台状态，不证明业务正确）|
| 硬件密钥（YubiKey/TPM）| 私钥不可导出（可篡改"签什么"）| ✅ 强 |
| 第二设备 / 透明日志（Rekor/CT）| 本机改不了历史，可 DoS | ✅ 最强（可检测 > 阻断）|

⚠️ TEE 有硬件攻击面：2024-26 BadRAM/WireTap/TEE.fail/DDRop 可伪造远程证明。

### 另一个 LLM 当锚——最危险的伪锚
- 共享执行环境/工具权限/工作区 → 违反不可达（prompt、配置、输出可被改写）
- 共享 prompt injection 面——注入是语义的，换会话不消失（CaMeL 2503.18813 / Design Patterns 2506.08837）
- self-preference：arXiv 2508.21164 标签致最高 50 个百分点偏好翻转
- 它输出"看似合理"，制造**递归已终止的假象**——比没有锚更危险
- **例外**：仅当跑在不同 authority domain、只读输入快照、无工具、输出签名/不可变通道，
  且只作**证据**由确定性规则裁决时才有价值（Ouroboros 2608.08311 的真正锚是
  immutable ground truth + deterministic preflight + fingerprint 防 TOCTOU + review ledger；
  DGM 2505.22954 的锚是 agent 不能控制的外部 benchmark）

### 最小可行非人锚（Windows 本机、运行时无人）
**前置硬条件：agent 必须是标准用户且不可提权**；若同一账号是管理员，一切软件边界失效，只剩硬件/外部日志。
1. 一次带外初始化（锚不能自举，必须有人/外部做一次）：新建标准用户 `verifier`；
   建 `C://Anchor`，`icacls` 设 verifier=Full、agent=RX、禁止继承/取得所有权；
   放入只读 `verify.ps1`、`policy.json`、`baseline.sha256`
2. 用**以 verifier 身份运行的计划任务**（由文件/事件触发，不由 agent 调用、不接 agent 参数）
   读工作区、算 Merkle root、对照基线，输出签名 `evidence.json`；
   密钥用 **TPM CNG key**（可 bind PCR 到 Secure Boot+HVCI，不可导出）
3. agent 只能读证据；对 `C://Anchor` 的写被 ACL 拒绝并进安全审计日志；
   工作区任何写使旧证据失效（ledger）
4. 可选：evidence 哈希提交 **sigstore Rekor** 取 inclusion proof——本机全控也改不了历史

**边界声明**：这不能证明"代码正确"，只证明"验证在 agent 权限域外执行且结论不可篡改"。

### 本项目的现成候选：GitHub remote
`D-al/dsh-behavior-guard` 每次 commit 都 push，是"不是人、不在本机、有独立权限边界"的候选锚。
但需确认：①branch protection 是否开启（agent 有无 force push 能力）②本地 credential manager
是否存了 token（若有，权限边界不成立）。**必须先收窄 push 权限才能真正当锚。**

### 出处（本轮补充）
NIST SP 800-57 Pt1 r5（词汇表/8.1.5.1.1）；RFC 4949/5280 §6.1.1/6024/9925(2026)；
TCG TPM2 Part1 §9.4；arXiv 2503.18813/2506.08837/2508.21164/2608.08311/2505.22954；
RFC 6962/9162、RFC 9943；MS Learn CFA/VBS/Credential Guard；TEE 攻击综述 2024-26。
