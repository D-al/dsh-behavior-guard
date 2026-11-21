# 人读版路线图下线（2026-11-21）

> 用户决定："后面更新机器读的路线图和科技树就可以了，原来那个人读的路线图没用的话就删了。"
> 本文记录删除前的依赖排查与迁移，确保没有留下断链。

---

## 一、删除前的真实依赖（都已迁移）

| 依赖方 | 原来怎么用 ROADMAP.md | 迁移到 |
|---|---|---|
| `tools/tech_tree.py:load_rejected()` | 解析 §4 "明确不做"表格 → 12 张红卡 | **`CAPABILITY_LADDER.yaml` 的 `rejected` 字段**（12 条完整迁入）|
| `tools/roadmap_check.py:refresh_human_view()` | 重渲染 §1-§3 自动块并写文件 | 变成只返回未来卡数的 no-op（保留签名）|
| `tools/roadmap_check.py:save_authoritative()` | 读 ROADMAP + 调 refresh | 删掉，只写 GRAPH + LADDER |
| `tools/roadmap_check.py --refresh` | 读 ROADMAP + 重渲染 | 删掉，只重生成科技树 |
| `tools/pre-commit` | `git add ROADMAP.md TECH_TREE.html` | 只 add TECH_TREE.html |
| `tools/citation_guard.py` | ROADMAP §4 当"决策性质文档" | 删白名单；"不做"决策现在在 LADDER.rejected |
| `config/GUARD_MANIFEST.yaml` | ROADMAP.md 列受保护文件 | 移除 |
| README / docs/README / AGENTS.md | 入口链接指向 ROADMAP | 改指 TECH_TREE.html + ROADMAP_GRAPH.md |

**历史文档（docs/history、CHANGELOG、旧 docs/）保留 ROADMAP.md 字样**——那是历史记录，不改。

---

## 二、现在的权威结构（两文件一视图）

| 文件 | 角色 | 谁写 |
|---|---|---|
| `ROADMAP_GRAPH.md` | **机器权威**：状态/deps/preconditions/category | `roadmap_check.py`（apply/claim）|
| `CAPABILITY_LADDER.yaml` | **语义镜像 + 决策数据**：what/why/判据/ROI/rejected/data_gates | `roadmap_check.py`（同步）|
| `TECH_TREE.html` | **唯一人读视图**：交互科技树 | `tech_tree.py`（--refresh / pre-commit 自动生成）|

**不再有第三份人读文档**——消除"三副本一致性"问题（历史踩过权威源/运行版/旧 clone 不同步）。

---

## 三、验证

- `git rm ROADMAP.md` 后门禁 **43/43**
- 科技树 89 节点，其中 **12 张"明确不做"红卡**（数据来自 LADDER.rejected，非旧 ROADMAP）
- citation_guard：0 FAIL；config_check：全栈一致
- `--refresh` 输出改为："REFRESHED: 未来卡 27 张 + 科技树；卡片状态未改动（权威=GRAPH，视图=科技树）"

---

## 四、给未来的纪律

- **不要重建人读版路线图**——任何"状态一览"需求都通过科技树视图满足
- 新增"明确不做"条目 → 写 `CAPABILITY_LADDER.yaml` 的 `rejected` 数组（科技树自动显示）
- 想看某卡详情 → `python tools/roadmap_check.py --card <ID>` 或点科技树节点
- 提交时 pre-commit hook 自动重生成科技树，不用手改任何视图
