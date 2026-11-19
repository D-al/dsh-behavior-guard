# dsh 默认工作区路径：源码核查与方案（2026-11-20）

> 用户问题：把 dsh 默认工作区也放进 D:\Brain。并指出"dsh 代码里应该有规定它认哪个路径作为会话呈现，正常应该是改个类似设置的东西"。
> 结论先行：**用户判断正确**——dsh 有正规配置 `documentsDirectory`（WorkspaceController 的 cordis config），可把首次工作区根从 C 盘 Documents 改到任意目录。我先前只用 junction 镜像是绕路。

---

## 1. 权威源码证据（dsh v0.2.2-rc.3 / commit 38a6a5c）

### 1.1 工作区目录名是固定常量，但父目录可配置

`@deepseek-ai/dsh-api-workspace-controller/src/default-workspace.ts`：

```ts
export const DEFAULT_WORKSPACE_DIRECTORY = 'default-workspace'
```

README 原文：

> `initializeDefault()` ... The Host places the directory under its account's `<Documents>/deepseek-harness` ...
> **Configuration** `documentsDirectory` | System Documents directory | **Fully qualified Host directory override**
> `documentsLookupTimeoutMs` | `10000` | Positive maximum duration of OS directory lookup

asar 生产代码（生产版与源码一致）：

```js
static Config = z.object({
  documentsDirectory: z.string(),
  documentsLookupTimeoutMs: z.natural().min(1).default(1e4)
});
```

**所以正规设置项 = `documentsDirectory`**，设为 `D:\Brain\workspace` 后，首次工作区会落在 `D:\Brain\workspace\default-workspace`——正好是我们已备好的完整镜像目录。

### 1.2 存量 workspace 的 path 不会被重写

README 原文：

> An existing default Workspace is returned without another Documents lookup and is **never renamed or relocated**.

所以改配置**不动存量**——这正是"配置 + 新建 D 盘工作区"方案零破坏的根据。

### 1.3 会话归属机制（纠正我之前的错误理解）

`@deepseek-ai/dsh-workspace` README 原文：

> A session joins the project of the directory it runs in ... A new session must have a recorded directory that resolves to the project's directory. **Already-accounted sessions keep their project and order when their fully qualified recorded path is missing, including a dangling symlink** ...

本机实测数据：

- `workspace.json`：只有 **1 个 workspace**，path = `C:\Users\Ad\Documents\deepseek-harness\default-workspace`，`sessionIds` 只有 **6 个**
- 26 个会话文件的 `identity.cwd` 分布：**9 个** default-workspace、**16 个** `C:\Users\Ad\.dsh\profiles\desktop`、**1 个** `D:\Brain\dsh-data\profiles\desktop`

**我之前"26 个会话 cwd 都是 default-workspace、改 path 会让全部脱离分组"的说法是错的**——那是基于不完整采样的推断。真实归属不靠 workspace.json 的 sessionIds 一一对应。

关于 2026-11-17 的历史"脱离分组"：README 提到工作区创建时会 `canonicalizes the path`，且 `titled after the requested directory's final segment rather than the canonical one, so a symlink at that path does not retitle the Workspace`——这提示 **junction/symlink 被 realpath 解析后，canonical path 变化可能导致新旧会话分到不同 workspace**。这是推断，未做受控实验证实（诚实标注）。

---

## 2. 本机现状（已完成的低风险部分）

- **C 盘真身** `C:\Users\Ad\Documents\deepseek-harness\default-workspace` 保留为 dsh 身份锚点（不迁根）。
- **D 盘镜像** `D:\Brain\workspace\default-workspace` 已补全为完整一致副本：
  - 补齐 `find-pnpm.ps1`、`hardware-monitor-plugin`（55 文件）、2 个空目录
  - 修正 `p` 子联接：原为 bash 风格 symlink（Windows 解析不了），已改为正规 Junction → `D:\Brain\workspace`
  - 7 个子联接全部正规 Junction 且可访问
  - 全量 hash 校验：**C/D 各 16 真实项、70 文件、0 差异**
- **同步脚本** `setup/sync-default-workspace.ps1`（权威仓库）：单向 C→D、跳过所有 junction、SHA256 比对、支持 `-DryRun`、ASCII-only、parse 0 错误。Dry-run 实测：70 identical / 7 skipped links / 0 writes。
- **REBUILD.md** 已补充"双位置设计"说明（C 根 = 身份锚点，D 镜像 = 资产归档）。

---

## 3. 配置注入尝试与崩溃（诚实记录）

尝试在 `cordis.patch.yml` 追加：

```yaml
- id: workspace-controller
  name: '@deepseek-ai/dsh-api-workspace-controller'
  config:
    documentsDirectory: D:/Brain/workspace
    documentsLookupTimeoutMs: 10000
```

结果：**dsh 启动后崩溃**（进程消失、8081 down）；回滚后恢复正常（pid 7636、8081 OK、bridge OK，30 秒稳定）。

这是纯字符串配置（无 `!!js`），崩溃原因待查。最可能：patch 对该 row 是**整段替换 config**，抹掉了原 row 的必需字段；或 row name/id 与本机的实际注册名不完全匹配。子任务正在从 asar 提取 `WorkspaceController` 完整实现定位根因。

**当前状态：配置已回滚，系统健康；documentsDirectory 尚未生效。**

### 补充：第二次实测（带 YAML 语法验证）——确认是本机硬失败

子任务从 asar 确认了 row id/name 正确、Config schema 正确，并给出"用单引号包路径"的写法。第二次重试：

1. 用 Python yaml（含 `!!js` 自定义 constructor）验证 patch：**parse OK，15 顶层条目唯一，config = `{documentsDirectory: 'D:/Brain/workspace', documentsLookupTimeoutMs: 10000}`** —— 语法完全正确。
2. 标准流程重启（先 Stop-ScheduledTask 回 Ready、杀残留进程、再 Start）。
3. 结果：**dsh 进程消失、8081 down、无 host crash 日志**；回滚后立即恢复（pid 20892 稳定 15s，bridge OK pid 24216）。

**结论（本机实证优先于源码推断）**：

- `documentsDirectory` 配置在源码层存在且 schema 正确，但在**本机 profile patch 注入即崩**——两次实测（无引号 + 有引号）都如此，与 YAML 写法无关。
- 最可能原因：patch 对该 row 是**整段替换 config**，覆盖了 base bundle 中该插件挂载必需的其他字段；或本机 dsh 构建对该 config 的校验路径有额外要求。未继续深挖（收益低、风险高）。
- **决策：放弃"配置注入"路线，保留已完成的 D 盘镜像 + 同步脚本作为低风险交付**。若将来真要改默认工作区根，正路是全新安装时设配置 / 用 UI directory picker 新建工作区，而不是在运行中的 profile patch 上注入。
- 教训再验证一次：**"源码说可以" ≠ "本机实际能跑"**——这是本项目反复出现的主题（参见 `!!js [...]`、pnpm 覆盖、Force kill finally）。

---

## 4. 方案对比（用户已选"配置 + 新建 D 盘工作区"）

| 方案 | 做法 | 存量影响 | 状态 |
|---|---|---|---|
| A 只改新会话 | 配置 documentsDirectory=D:\Brain\workspace，新工作区落 D 盘 | 零影响 | 配置注入崩溃，待修 |
| B 存量也迁 | 改 workspace.json 的 path 到 D 盘 | **官方不支持**（path 创建后不可重写），有归属风险 | 用户曾选，因源码证据改判 |
| C 配置 + 新建 | 配置 documentsDirectory + 用 UI/registry 新建 D 盘工作区 | 零影响（存量 workspace 不动） | **用户最终选择**，待配置注入修好 |
| D 只镜像 | 保持现状（C 真身 + D 镜像 + 同步脚本） | 零影响 | 已完成的兜底 |

**下一步**：待子任务定位崩溃根因 → 修正 patch 写法 → 重启验证 documentsDirectory 生效 → 新建 D 盘工作区 → 端到端验证新会话落在 D 盘、存量会话分组不变。

---

## 5. 教训

1. **用户"应该有类似设置的东西"的直觉是对的**——开源项目优先扒源码找正规配置入口，不要用 junction 技巧绕过。
2. **不要基于不完整采样下结论**——我先后两次错判（"26 会话都在 default-workspace"、"改 path 会让全部脱离分组"），都是采样不足就推断。
3. **patch 注入要先小步验证**——即使是纯字符串配置也要重启实测，dsh 对 config 是 fail-loud 的（起不来）。
