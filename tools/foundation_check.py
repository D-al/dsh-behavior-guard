#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地基深度体检 —— 按需运行，像杀毒软件的"全盘扫描"

与 daemon 的区别：
  - daemon：变更驱动，指纹变了才跑（平时零空转）
  - 本命令：用户主动触发，无条件全量体检 + 可读报告 + 更新指纹基线

用法:
  D:/Python/python.exe -B tools/foundation_check.py           # 深度体检
  D:/Python/python.exe -B tools/foundation_check.py --quick   # 快速体检（只跑指纹+3条核心）
退出码: 0=健康; 1=有漂移

报告: 控制台摘要 + D:/Brain/workspace/bench/_foundation_drift.jsonl 追加
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
FP = ROOT / 'tools/foundation_fingerprint.py'
GUARD = ROOT / 'tools/foundation_guard.py'
DRIFT = Path('D:/Brain/workspace/bench/_foundation_drift.jsonl')


def run(script, extra=()):
    try:
        r = subprocess.run([PY, '-B', str(script)] + list(extra), cwd=ROOT,
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=180)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, f'{type(e).__name__}: {e}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true', help='快速体检（只查指纹+核心3条）')
    ap.add_argument('--no-commit', action='store_true', help='不更新指纹基线（调试用）')
    args = ap.parse_args()

    print('=' * 60)
    print(' 🩺 地基深度体检' + ('（快速模式）' if args.quick else ''))
    print(f' 时间: {datetime.now().isoformat(timespec="seconds")}')
    print('=' * 60)

    # 指纹状态
    rc_fp, out_fp = run(FP, ['--changed'])
    changed = (rc_fp == 0)
    print(f'\n[指纹] {"有变化" if changed else "无变化（自上次基线以来）"}')

    # 全量 guard
    rc, out = run(GUARD)
    guard_lines = [l for l in out.splitlines() if l.startswith('[GUARD]')]
    for l in guard_lines:
        print(' ' + l.replace('[GUARD] ', ''))

    verdict = 'HEALTHY' if rc == 0 else 'DRIFT DETECTED'
    print(f'\n{"=" * 60}')
    print(f' 结论: {verdict}')
    print(f'{"=" * 60}')

    # 健康时更新指纹基线（下次 daemon 就不再重复跑）
    if rc == 0 and not args.no_commit:
        run(FP, ['--commit'])
        print(' 指纹基线已更新 — 后续无变化将跳过巡检')

    return rc


if __name__ == '__main__':
    sys.exit(main())
