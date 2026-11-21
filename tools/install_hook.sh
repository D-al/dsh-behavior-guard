#!/bin/bash
# 安装 pre-commit hook：提交时自动重渲染路线图 + 科技树
# 用法: bash tools/install_hook.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOKS="$ROOT/.git/hooks"
mkdir -p "$HOOKS"
cp "$ROOT/tools/pre-commit" "$HOOKS/pre-commit"
chmod +x "$HOOKS/pre-commit"
chmod +x "$ROOT/tools/pre-commit"
echo "INSTALLED: $HOOKS/pre-commit"
echo "以后每次 git commit 会自动跑 roadmap_check --refresh（含科技树重生成），并把产物纳入该次提交。"
