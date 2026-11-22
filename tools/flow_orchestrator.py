#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DBR 编排器：把决策环的零件串成有节拍的循环（TOC 第2-4步）

背景：A2(写回)/A3(选任务)的零件都已实现在 roadmap_check.py
（find_next / cmd_claim / cmd_apply），但没人串起来，也没有 WIP 限流——
这就是约束理论说的"WIP 堆在等决策"。

DBR 映射：
  Drum   = 决策节拍：一次只推一张卡，处理完才放下一张
  Buffer = 就绪队列（find_next 给出的候选），小而优先级化
  Rope   = WIP 上限：doing 中的卡数 >= 上限时，拒绝 claim 新卡

用法:
  D:/Python/python.exe -B tools/flow_orchestrator.py --status    # 看当前节拍/WIP
  D:/Python/python.exe -B tools/flow_orchestrator.py --next      # 选下一张（不领取）
  D:/Python/python.exe -B tools/flow_orchestrator.py --claim     # 领一张（受WIP限流）
  D:/Python/python.exe -B tools/flow_orchestrator.py --verify ID # 验一张
  D:/Python/python.exe -B tools/flow_orchestrator.py --apply     # 写回所有 doing 且全 PASS
  D:/Python/python.exe -B tools/flow_orchestrator.py --cycle     # 完整一拍：状态+建议

注意：本脚本**不执行任务本身**（那是 agent 的事），只管决策节拍与状态流转。
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / 'tools/roadmap_check.py'
PY = sys.executable
WIP_LIMIT = 1  # DBR Rope：同时 doing 的卡数上限（单人 agent = 1）


def rc(*args):
    r = subprocess.run([PY, '-B', str(CHECK), *args], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


def load_data():
    """通过 --dry-run 之外的方式读权威源：用 --card 不够，直接 import"""
    sys.path.insert(0, str(ROOT / 'tools'))
    import roadmap_check as rmod
    return rmod.load_ladder()


def trace_emit(kind, card='', phase='', verdict='', evidence_ref=''):
    """决策环打点（KR1 证据源）——失败不影响主流程"""
    try:
        from task_trace import emit
        return emit(kind, card=card, phase=phase, verdict=verdict,
                    evidence_ref=evidence_ref, mode='live')
    except Exception:
        return False


def doing_ids(data):
    return [i['id'] for g in ('items', 'rungs') for i in data[g] if i.get('status') == 'doing']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--next', action='store_true')
    ap.add_argument('--claim', action='store_true')
    ap.add_argument('--verify', metavar='ID')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--cycle', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    data = load_data()
    doing = doing_ids(data)
    wip_full = len(doing) >= WIP_LIMIT

    status = {'wip_limit': WIP_LIMIT, 'doing': doing, 'wip_full': wip_full,
              'decision_ready': not wip_full}

    if args.status or args.cycle:
        rc_next, out_next = rc('--next')
        try:
            _j = json.loads(out_next)
            status['next_card'] = _j.get('id', 'none')
        except Exception:
            status['next_card'] = out_next.splitlines()[0] if out_next else 'none'
        if wip_full:
            status['verdict'] = 'WAIT: WIP full — 先完成 doing 的卡再领新的（Rope 拦住）'
        else:
            status['verdict'] = 'READY: 决策环有空位，可领下一张'
        if args.json:
            print(json.dumps(status, ensure_ascii=False, indent=2))
        else:
            print('=' * 56)
            print(' DBR 决策节拍状态')
            print('=' * 56)
            print(f'  WIP: {len(doing)}/{WIP_LIMIT}  doing={doing or "[]"}')
            print(f'  下一张候选: {status["next_card"]}')
            print(f'  判定: {status["verdict"]}')
        if args.status:
            return 0

    if args.next:
        code, out = rc('--next')
        print(out)
        return code

    if args.claim:
        if wip_full:
            print(f'[ORCH] REFUSED: WIP 已满 ({len(doing)}/{WIP_LIMIT}) — {doing}')
            print('[ORCH] ↳ 先 --verify + --apply 完成当前卡，再领新的（DBR Rope）')
            return 1
        code, out = rc('--next')
        card = None
        for line in out.splitlines():
            m = __import__('re').search(r'\b([SMALG]\d+[A-Z]?_\d+|[SMALG]\d+|STRAT\d+)\b', line)
            if m:
                card = m.group(1)
                break
        if not card:
            print(f'[ORCH] 无候选任务: {out[:200]}')
            return 1
        print(f'[ORCH] Drum 拍板: {card}')
        code, out2 = rc('--claim', card)
        trace_emit('task_done', card=card, phase='claim',
                   verdict='ok' if code == 0 else 'fail', evidence_ref='roadmap_check --claim')
        print(out2)
        return code

    if args.verify:
        code, out = rc('--verify', args.verify)
        trace_emit('task_done', card=args.verify, phase='verify',
                   verdict='ok' if code == 0 else 'fail', evidence_ref='roadmap_check --verify')
        print(out)
        return code

    if args.apply:
        code, out = rc('--apply')
        trace_emit('task_done', card='apply', phase='apply',
                   verdict='ok' if code == 0 else 'fail', evidence_ref='roadmap_check --apply')
        print(out)
        return code

    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
