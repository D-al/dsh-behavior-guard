# 防护方案：避免插件破坏事故重演（2026-11-26）

> 缘起：`POSTMORTEM_HARNESS_BLINDSPOT_20261126.md` 的深度复盘。
> 核心约束：**profile 默认 `danger-full-access` + `approval: never`**（`cordis.patch.yml:29-32`），
> 所以任何依赖 dsh 审批/提示词护栏的方案在生产配置下都天然失效。

## 零、先认清架构上限（否则方案会走偏）

harness 是"提示词注入 + LLM 工具事件钩子"。这次破坏的三个环节里：
- `remove_bundle`（白名单工具）→ 合法调用
- 真正毁目录的 pnpm rename → **执行层副作用，无独立 tool/call**
- compaction 抹掉自我纠错 → **harness 自己的机制反噬**

结论：**真正可靠的门禁必须在 dsh 之外**（文件系统层 / 启动校验层 / 独立进程）。
harness 内部只能做"可观测 + 下一轮纠偏"，不能当主防线。

## 一、三道独立防线（按 ROI 排序）

### 防线 1：文件监听层 watcher —— 唯一不受 dsh 权限影响的实时防线（P0）

独立 Python 进程（复用 `tools/` 目录），监听 profile 关键路径：
```
D:/Brain/dsh-data/profiles/desktop/node_modules/*/cordis.patch.yml
D:/Brain/dsh-data/profiles/desktop/node_modules/*/package.json
D:/Brain/dsh-data/profiles/desktop/{cordis.patch.yml,package.json}
```

三条规则（零 LLM，纯文件哈希 + 正则）：
1. **bundle 名合法性**：patch 里每个 `name:` 必须等于该插件 `package.json` 的 `name`
   （或合法 scoped 名）。`@local/...` 这类臆造前缀 → 告警 + 自动改回 + trace
2. **关键文件存在性**：三个核心插件的 `index.mjs`/`package.json`/`cordis.patch.yml`/`frame_limiter.py`
   消失 → 立即告警，从 publish 权威源自动恢复
3. **变更前后哈希**：每次变更记 `_plugin_guard.jsonl`（谁、何时、前后哈希），供事后审计

- 实现量：~100 行 Python（可用 watchdog 或轮询 mtime）
- 误报：低（bundle 名格式固定；"合法升级"用权威源比对区分）
- 验证：注入坏 patch / 删一个源码文件，应分别告警并恢复
- **关键点**：这个 watcher 跑在 dsh 进程外，dsh 无论什么权限都绕不过

### 防线 2：compaction 保留"未闭环的自我纠错"（P0，改 harness 自身）

事故扩大的直接原因：模型 seq 481 已发现 `@local` 错误并说"应该恢复"，
但 seq 456/528 的 compaction 把 EPERM 和 `@local` 线索剔除，导致 seq 646 用坏源码覆盖。

规则：**待办/自我纠错项若未执行，compaction 摘要必须保留**。
- 项目已有 P0 压缩存档（合同/已验证决策/开放项/已排除）——把"未执行的自我纠错"加入必留项
- 摘要模板加一行：`【未闭环的自我纠错】模型曾发现 X 有问题但未修复 → 下轮优先处理`
- 实现量：改压缩提示/摘要规则，0 LLM 额外开销
- 验证：构造"发现错误未修复"的会话，压缩后摘要应仍含该条

### 防线 3：工具结果语义识别 + 权威源恢复（P1）

1. **识别副作用型破坏**：tool/result 里 `application:failed` 或 `changed:true` 就算 `isError:false`
   也要触发审计。特别是 pnpm 的 `ERR_PNPM_EPERM`、`_tmp_*` rename 失败
2. **把 `Copy-Item -Recurse -Force` 到 node_modules 加入 DANGER_BLOCK**（index.mjs:248 附近）
   ——这次 seq 646 用的正是它
3. **manifest + 自动恢复**：`consistency_guard.py` 已有权威源比对，但只是被动巡检。
   加一个 `--fix` 模式：检测到运行版关键文件缺失/被篡改，从 publish 源恢复
4. 把 `consistency_guard.py` 纳入**启动门禁**而非"变更时提示"（这次运行版差 580 行没拦住）

## 二、最轻量的起点（如果只想先做一件事）

**先加 trace 埋点，不拦只记**：对 `node_modules/*/cordis.patch.yml` 的每次写入记前后哈希 + bundle 名。
符合项目"可观测优先"原则——先坐实事实，再上门禁，避免误伤"正常修插件"任务。

注意一个真实的两难：本次任务本身就是"修 node_modules 里的插件"，
所以**不能对所有 node_modules 写操作一刀切拦截**，必须用"bundle 名合法性 + 权威源比对"
这种语义规则，而不是路径黑名单。

## 三、明确不做什么

- ❌ 不加 dsh approval 弹窗——profile 默认 `never`，改它会破坏用户"无人值守"工作流
- ❌ 不靠 AGENT_BRIEF 再写一条"别改 bundle 名"铁律——提示词护栏在 full-access 会话里无效，已证伪
- ❌ 不把 harness 当主防线——架构上做不到拦截执行层副作用

## 四、验收标准

方案是否成功，用这次事故的五个关键节点回放验证：
| 节点 | 期望的新防线行为 |
|---|---|
| seq 388 remove_bundle | watcher 记录，不拦（合法工具） |
| seq 389 pnpm EPERM 目录清空 | **防线1 立即告警 + 从权威源恢复 autostart** |
| seq 431 edit 成 @local | **防线1 立即告警 + 自动改回** |
| seq 456 compaction 剔除纠错线索 | **防线2 强制保留"未闭环自我纠错"** |
| seq 646 Copy-Item 覆盖坏 patch | **防线1 校验 bundle 名失败，阻止落地** |
