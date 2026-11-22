#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地基指纹：判断是否值得跑完整巡检（零空转的关键）

地基只可能因"变化"而漂移：仓库代码/测试/配置变化、权威源变化、运行版变化。
没有变化 → 直接跳过巡检（0 检查、0 扫盘）。

指纹组成：
- 仓库 git HEAD commit（已提交的变化）
- 关键文件 mtime_ns + size（未提交的工作区变化，防止只靠 HEAD 漏掉）
- 运行版 index.mjs 的 mtime/size（三副本同步状态）

用法:
  D:/Python/python.exe -B tools/foundation_fingerprint.py            # 打印当前指纹
  D:/Python/python.exe -B tools/foundation_fingerprint.py --changed # 有变化则 rc=0，无变化 rc=1
  D:/Python/python.exe -B tools/foundation_fingerprint.py --commit  # 提交当前指纹为基线
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = Path('D:/Brain/workspace/bench/_foundation_fingerprint.json')

# 关键文件：覆盖地基六条不变量所依赖的输入
# 目录用 glob 展开到每个文件的 mtime/size，这样新增/删除测试也能检出
WATCH = [
    ROOT / 'index.mjs',
    ROOT / 'ROADMAP_GRAPH.md',
    ROOT / 'CAPABILITY_LADDER.yaml',
    ROOT / 'TECH_TREE.html',
    ROOT / 'tools/run_all.sh',
    ROOT / 'tools/check_verify.py',
    ROOT / 'tools/test_census.py',
    ROOT / 'tools/test_new_guards.mjs',
    ROOT / 'tools/foundation_guard.py',
    Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs'),
]
GLOBS = [
    (ROOT / 'tools', 'test_*.mjs'),
    (ROOT / 'tools', 'test_*.py'),
]


def compute():
    parts = []
    # git HEAD
    try:
        r = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True,
                           text=True, timeout=10)
        parts.append('HEAD=' + (r.stdout.strip() if r.returncode == 0 else 'none'))
    except Exception:
        parts.append('HEAD=err')
    # 工作区状态（未提交改动也要检出）
    try:
        r = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True,
                           text=True, timeout=10)
        parts.append('DIRTY=' + hashlib.sha256(r.stdout.encode()).hexdigest()[:12])
    except Exception:
        parts.append('DIRTY=err')
    # 关键文件内容 hash（不用 mtime——touch 或改回原内容不该触发巡检）
    for p in WATCH:
        try:
            parts.append(f'{p}={hashlib.sha256(p.read_bytes()).hexdigest()[:16]}')
        except OSError:
            parts.append(f'{p}=missing')
    # 测试文件集合（新增/删除/内容改动都检出）
    for d, pat in GLOBS:
        for p in sorted(d.glob(pat)):
            parts.append(f'{p.name}={hashlib.sha256(p.read_bytes()).hexdigest()[:16]}')
    raw = '|'.join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def load():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding='utf-8')).get('fingerprint')
        except Exception:
            return None
    return None


def commit(fp):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({'fingerprint': fp, 'updated': __import__('datetime').datetime.now().isoformat()},
                                indent=2), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--changed', action='store_true', help='有变化 rc=0; 无变化 rc=1')
    ap.add_argument('--commit', action='store_true', help='提交当前指纹为基线')
    args = ap.parse_args()
    fp = compute()
    old = load()
    changed = (fp != old)
    if args.commit:
        commit(fp)
        print(f'[FP] committed {fp[:16]}')
        return 0
    if args.changed:
        print(f'[FP] changed={changed} current={fp[:16]} baseline={str(old)[:16]}')
        return 0 if changed else 1
    print(fp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
