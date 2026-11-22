#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""落地就绪度检查：战略目标提案能否写进权威源（STRATEGY.md）

依据：docs/GOAL_LANDING_PLAN_20261122.md
五条落地判据（全部满足才可落地）：
  L1 可判定：至少 KR1 从 N/M 变成可判（goal_verify 实测）
  L2 可迁移：STRATEGY §2 六指标→KR 映射已写入 ADR
  L3 可保护：判定者与证据源在不可写区或 ADR 登记 sha
  L4 可授权：人类显式批准 + ADR 编号 + sha 锁更新
  L5 可回滚：落地前快照存在

三态：READY / BLOCKED / NOT_READY。不把"没批准"伪装成"技术不行"。

用法:
  D:/Python/python.exe -B tools/landing_readiness.py [--json]
退出码: 0=READY; 1=BLOCKED(需人类决策); 2=NOT_READY(需建工具)
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / 'decisions'
STRATEGY = ROOT / 'STRATEGY.md'
SNAPSHOT_DIR = ROOT / 'snapshots'
BENCH = Path('D:/Brain/workspace/bench')


def check_l1():
    """可判定：跑 goal_verify，看 KR1 是否可判"""
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/goal_verify.py'), '--json'],
                       cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=120)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {'gate': 'L1 可判定', 'status': 'NOT_READY', 'why': 'goal_verify 输出无法解析'}
    kr1 = next((x for x in d['results'] if x['kr'] == 'KR1'), None)
    if not kr1:
        return {'gate': 'L1 可判定', 'status': 'NOT_READY', 'why': 'KR1 结果缺失'}
    ok = kr1['status'] in ('PASS', 'FAIL')
    return {'gate': 'L1 可判定', 'status': 'READY' if ok else 'NOT_READY',
            'why': f'KR1={kr1["status"]}: {kr1["why"][:80]}',
            'prerequisite': kr1.get('prerequisite')}


def check_l2():
    """可迁移：ADR 里有 KR 映射"""
    if not DECISIONS.exists():
        return {'gate': 'L2 可迁移', 'status': 'NOT_READY', 'why': 'decisions/ 不存在'}
    hits = []
    for f in DECISIONS.glob('*.md'):
        t = f.read_text(encoding='utf-8', errors='replace')
        if 'KR1' in t and ('STRATEGY' in t or '迁移' in t):
            hits.append(f.name)
    ok = bool(hits)
    return {'gate': 'L2 可迁移', 'status': 'READY' if ok else 'NOT_READY',
            'why': f'含KR映射的ADR: {hits or "无"}'}


def check_l3():
    """可保护：验证器在 manifest，证据源有 ADR 登记"""
    manifest = json.loads((ROOT / 'bench/rulepack/manifest.json').read_text(encoding='utf-8'))
    verifier_ok = 'tools/goal_verify.py' in manifest.get('protected', {})
    # 证据源：检查 ADR 是否登记 sha（不是检查文件存在——文件还没建）
    registered = []
    for f in DECISIONS.glob('*.md'):
        t = f.read_text(encoding='utf-8', errors='replace')
        if '_benchmark_holdout' in t or '证据源' in t:
            registered.append(f.name)
    ok = verifier_ok and bool(registered)
    return {'gate': 'L3 可保护', 'status': 'READY' if ok else 'NOT_READY',
            'why': f'验证器受保护={verifier_ok}; 证据源ADR登记={registered or "无"}'}


def check_l4():
    """可授权：人类批准的 ADR（本工具不能自己满足——这是设计意图）"""
    approved = []
    for f in DECISIONS.glob('*.md'):
        t = f.read_text(encoding='utf-8', errors='replace')
        if '战略目标' in t and '状态：accepted' in t and '决策者：用户' in t:
            approved.append(f.name)
    ok = bool(approved)
    return {'gate': 'L4 可授权', 'status': 'READY' if ok else 'BLOCKED',
            'why': f'人类批准的战略ADR: {approved or "无——须用户显式批准（本工具不能代劳）"}'}


def check_l5():
    """可回滚：落地前快照"""
    ok = SNAPSHOT_DIR.exists() and any(SNAPSHOT_DIR.iterdir())
    return {'gate': 'L5 可回滚', 'status': 'READY' if ok else 'NOT_READY',
            'why': f'snapshots/ 存在={SNAPSHOT_DIR.exists()}, 有内容={ok}'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    checks = [check_l1(), check_l2(), check_l3(), check_l4(), check_l5()]
    n_ready = sum(1 for c in checks if c['status'] == 'READY')
    n_blocked = sum(1 for c in checks if c['status'] == 'BLOCKED')
    n_not = sum(1 for c in checks if c['status'] == 'NOT_READY')

    # BLOCKED（需人类决策）优先于 NOT_READY（需建工具）决定总体状态
    overall = 'READY' if n_ready == 5 else ('BLOCKED' if n_blocked else 'NOT_READY')
    report = {'ts': datetime.now(timezone.utc).isoformat(), 'overall': overall,
              'checks': checks,
              'summary': {'READY': n_ready, 'BLOCKED': n_blocked, 'NOT_READY': n_not}}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('=' * 68)
        print(f' 落地就绪度 — {overall}  ({n_ready}/5 READY)')
        print('=' * 68)
        for c in checks:
            tag = {'READY': 'READY ', 'BLOCKED': 'BLOCK ', 'NOT_READY': 'NOT-R '}[c['status']]
            print(f'  [{tag}] {c["gate"]}: {c["why"][:66]}')
            if c.get('prerequisite'):
                print(f'           ↳ {c["prerequisite"]}')
        print()
        if overall == 'BLOCKED':
            print('  ⚠ 技术条件可补，但"人类批准"本工具无法代劳——这是设计意图')
        elif overall == 'NOT_READY':
            print('  ⚠ 先补 NOT_READY 的前置工具/数据，再谈落地')
        else:
            print('  ✅ 五条判据全满足——可以落地')

    return {'READY': 0, 'BLOCKED': 1, 'NOT_READY': 2}[overall]


if __name__ == '__main__':
    sys.exit(main())
