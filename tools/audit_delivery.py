#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付真实性交叉审计：账面 done vs 真实判据（存在性 + 完整性认定）

依据：docs/FIRST_PRINCIPLES_GOVERNANCE_20261122.md
  - VOI：盘点改变资源分配 → 正价值
  - 审计存在性认定：防"压根没造却声称完成"
  - 审计完整性认定：防"已造但不知道→重复造"

复用已有工具（不重复造轮子）：
  - roadmap_check.check_one/evaluate：真跑判据
  - audit_verify 的强/弱/无分级逻辑
  - check_verify 的判据四类病
本脚本只做**交叉编排 + 账面 vs 实物对账**。

用法:
  D:/Python/python.exe -B tools/audit_delivery.py [--json] [--full]
输出: 控制台摘要 + D:/Brain/workspace/bench/_delivery_audit.jsonl
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import roadmap_check as rc

OUT = Path('D:/Brain/workspace/bench/_delivery_audit.jsonl')
STRONG = {'test_pass', 'gate_result', 'trace_count', 'trace_absent', 'json_field'}
WEAK = {'file_exists', 'file_grep'}


def audit_card(data, card):
    """真跑判据 + 判据强度 + 证据来源交叉"""
    results, auto_ok = rc.evaluate(data, card)
    kinds = [v.get('kind') for v in card.get('verify', [])]
    strong = sum(1 for k in kinds if k in STRONG)
    weak = sum(1 for k in kinds if k in WEAK)

    failing = []
    for i, (ok, ev) in enumerate(results):
        if not ok:
            failing.append({'index': i, 'kind': kinds[i] if i < len(kinds) else '?',
                            'evidence': ev[:120]})

    return {'id': card['id'], 'status': rc.status_map_of(data).get(card['id']),
            'auto_verifiable': auto_ok, 'verify_count': len(results),
            'strong': strong, 'weak': weak,
            'pass': sum(1 for ok, _ in results if ok),
            'all_pass': bool(auto_ok and all(ok for ok, _ in results)),
            'failing': failing,
            'has_evidence_log': bool(card.get('evidence_log'))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--full', action='store_true', help='列出所有卡，不只异常卡')
    args = ap.parse_args()

    data = rc.load_ladder()
    cards = data['items'] + data['rungs']
    done = [c for c in cards if rc.status_map_of(data).get(c['id']) == 'done']

    audits = [audit_card(data, c) for c in done]
    broken = [a for a in audits if not a['all_pass']]
    no_verify = [a for a in audits if a['verify_count'] == 0]
    weak_only = [a for a in audits if a['weak'] > 0 and a['strong'] == 0]
    no_evidence_log = [a for a in audits if not a['has_evidence_log']]

    summary = {'ts': datetime.now(timezone.utc).isoformat(),
               'done_total': len(done),
               'all_pass': len(audits) - len(broken),
               'broken': len(broken), 'no_verify': len(no_verify),
               'weak_only': len(weak_only), 'no_evidence_log': len(no_evidence_log),
               'audits': audits}

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print('=' * 66)
        print(' 交付真实性交叉审计 — 账面 done vs 真跑判据')
        print('=' * 66)
        print(f'  done 卡总数      : {summary["done_total"]}')
        print(f'  判据全过         : {summary["all_pass"]}')
        print(f'  ★判据不过(虚报)  : {summary["broken"]}')
        print(f'  无判据           : {summary["no_verify"]}')
        print(f'  纯弱判据         : {summary["weak_only"]}')
        print(f'  无evidence_log   : {summary["no_evidence_log"]}')
        print()
        if broken:
            print(' 【判据不过的 done 卡】')
            for a in broken:
                print(f'  {a["id"]:10} {a["pass"]}/{a["verify_count"]} pass '
                      f'strong={a["strong"]} weak={a["weak"]}')
                for f in a['failing'][:2]:
                    print(f'      ✗ [{f["kind"]}] {f["evidence"]}')
            print()
        if args.full:
            print(' 【全部 done 卡】')
            for a in audits:
                flag = 'OK  ' if a['all_pass'] else 'FAIL'
                print(f'  {flag} {a["id"]:12} {a["pass"]}/{a["verify_count"]}')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('a', encoding='utf-8') as f:
        f.write(json.dumps(summary, ensure_ascii=False) + '\n')
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
