---
name: git-workflow
summary: 本地 git 操作（沙箱无 git，需在 Git Bash 或本机提权执行）的标准流程与回滚
keywords: [git commit, git tag, git push, stash, 回滚提交, 撤销改动]
---
# git 工作流

## 环境约束
- **沙箱里没有 git**（`pwsh` 沙箱 PATH 无 git）→ 两种方式：
  1. 用**本机提权**的 `pwsh`（`dangerouslyDisableSandbox` 或本机模式）
  2. 让用户在自己的 Git Bash 里执行
- `gh` CLI **未安装**（无法创建 PR / 建远程仓库）

## 发布插件类的标准流程（我们实际用的）
```bash
cd D:/Brain/publish/<仓库>
git add -A
git commit -m "vX.Y.Z (日期 时间): 一句话变更"
git tag "vX.Y.Z-YYYYMMDD-HHMM"
git push origin main --tags
```

## 常用安全操作
| 需求 | 命令 | 风险 |
|---|---|---|
| 看改了什么 | `git status --short` / `git diff --stat` | 无 |
| 撤销未暂存改动（单文件）| `git checkout -- <file>` | **丢改动**（warn 级）|
| 暂存当前工作去切分支 | `git stash push -m "wip"` | 低（可 `stash pop` 回）|
| 撤销最近一次提交（保留改动）| `git reset --soft HEAD~1` | 低 |
| 撤销提交（丢改动）| `git reset --hard HEAD~1` | **block 级**，先备份 |
| 清理未跟踪文件 | `git clean -n` 先预览，再 `-f` | `-f` 是 block 级 |

## 必须避免
- `git push --force` 到主分支（block 级）
- `git reset --hard` 在有未提交改动时（先 `git stash`）
- 在 `D:/Brain/workspace`（junction 目标）里跑 `git clean -fdx`（会删 bench 脚本）

## 如果仓库 push 失败
1. `git remote -v` 看地址是否对
2. 凭据问题 → 在 Git Bash 里 `git push` 让用户交互登录
3. 网络问题 → 重试一次；仍失败就本地 commit + tag 保留，告诉用户稍后推
