#!/usr/bin/env python3
"""test_next_roi.py — 锁定 find_next 的排序契约（risk/tier 硬约束 + ROI 平局打破）。

改 find_next 加入 ROI 权重前后的行为契约：
  1. risk 仍是第一硬约束：low 优先于 high，即使 high 的 ROI 极高
  2. tier 仍是第二硬约束
  3. 同 risk+tier 内：ROI 高的先被推（这是本次改动的核心）
  4. deps 未满足的不入选
  5. 非 autonomous / 非 ready 的不入选
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_check as rc


def make_data(cards):
    """构造最小 data：items + anchors（A1 作为 done 依赖）。"""
    return {
        'items': cards,
        'rungs': [],
        'anchors': {'A1': {'status': 'done'}},
    }


def pick(cards):
    return rc.find_next(make_data(cards))['id']


def base(cid, **kw):
    d = {'id': cid, 'status': 'ready', 'autonomous': True, 'risk': 'low',
         'deps': ['A1'], 'benefit': '中', 'cost': '中'}
    d.update(kw)
    return d


CASES = []

# 1. risk 硬约束：low/低ROI 必须赢 high/极高ROI
CASES.append((
    'risk_first',
    [base('Z_high_roi', risk='high', benefit='极高', cost='低'),
     base('A_low_roi', risk='low', benefit='低', cost='高')],
    'A_low_roi',
))

# 2. tier 硬约束：tier0 赢 tier1（即使 tier1 ROI 高）
CASES.append((
    'tier_first',
    [base('Z_t1_highroi', tier=1, benefit='极高', cost='低'),
     base('A_t0_lowroi', tier=0, benefit='低', cost='高')],
    'A_t0_lowroi',
))

# 3. 同 risk+tier：ROI 高的赢（本次核心改动）——用字母序反压，确保不是靠 id 偶然命中
CASES.append((
    'roi_breaks_tie',
    [base('A_lowroi', benefit='中', cost='高'),       # ROI 0.667
     base('Z_highroi', benefit='极高', cost='中低')],  # ROI 2.5
    'Z_highroi',
))

# 4. deps 未满足的不入选
CASES.append((
    'deps_gate',
    [base('A_bad_dept', deps=['NOT_DONE']),
     base('Z_ok', benefit='极高', cost='低')],
    'Z_ok',
))

# 5. 非 autonomous 不入选
CASES.append((
    'autonomous_gate',
    [base('A_manual', autonomous=False, benefit='极高', cost='低'),
     base('Z_auto', benefit='中', cost='中')],
    'Z_auto',
))


def main():
    passed = failed = 0
    for name, cards, expected in CASES:
        try:
            got = pick(cards)
        except Exception as e:
            got = f'EXCEPTION: {e}'
        ok = got == expected
        print(f'{"PASS" if ok else "FAIL"}  {name}: got={got} expected={expected}')
        if ok:
            passed += 1
        else:
            failed += 1
    print(f'\nRESULT: {passed} PASS / {failed} FAIL')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
