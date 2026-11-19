# -*- coding: utf-8 -*-
"""Self-Harness P0 acceptance gate + 基线方差检查（ADR-0018）。
纯统计判定，零 LLM 调用。用法:
  D:/Python/python.exe tools/self_harness_gate.py --self-test
"""
import argparse
import json
import statistics
import sys

SURFACES = 'D:/Brain/publish/dsh-behavior-guard/surfaces.json'


def load_surfaces():
    with open(SURFACES, encoding='utf-8') as f:
        return json.load(f)


def variance_ok(runs):
    """基线 pass-rate 方差 <10%（用极差近似，样本少时更保守）。"""
    if not runs or len(runs) < 2:
        return False, 0.0
    vals = [float(x) for x in runs]
    mean = statistics.mean(vals)
    if mean == 0:
        return True, 0.0
    spread = (max(vals) - min(vals)) / mean
    return spread < 0.10, round(spread, 4)


def accept(baseline, candidate):
    """论文规则：任一 split 不退化且至少一个 split 提升。
    baseline/candidate: {'held-in': [r1,r2,...], 'held-out': [...]}
    """
    acc = load_surfaces()['acceptance']
    if any(len(baseline.get(s, [])) < acc['min_repeats'] or len(candidate.get(s, [])) < acc['min_repeats']
           for s in acc['splits']):
        return {'decision': 'no-op', 'reason': 'insufficient repeats'}
    # P1：基线方差门槛必须生效——基线自身噪声 >10% 时，任何"提升"都不可信（论文 P0 前置）
    noisy = {s: variance_ok(baseline[s]) for s in acc['splits']}
    bad = [s for s, (ok, spread) in noisy.items() if not ok]
    if bad:
        return {'decision': 'no-op', 'reason': f'baseline variance >{acc["max_pass_rate_variance"]:.0%} on {bad} — 先降噪声', 'variance': {s: v[1] for s, v in noisy.items()}}
    b_means = {s: statistics.mean(baseline[s]) for s in acc['splits']}
    c_means = {s: statistics.mean(candidate[s]) for s in acc['splits']}
    degraded = [s for s in acc['splits'] if c_means[s] < b_means[s] - 1e-9]
    improved = [s for s in acc['splits'] if c_means[s] > b_means[s] + 1e-9]
    if degraded:
        return {'decision': 'reject', 'reason': f'degraded on {degraded}', 'baseline': b_means, 'candidate': c_means}
    if not improved:
        return {'decision': 'no-op', 'reason': 'no improvement', 'baseline': b_means, 'candidate': c_means}
    return {'decision': 'accept', 'reason': f'improved on {improved}', 'baseline': b_means, 'candidate': c_means}


def surface_check(surface_id, modified_paths):
    """校验候选只改白名单内的一个 surface，且没碰禁改面。"""
    s = load_surfaces()
    allowed = {x['id'] for x in s['editable']}
    if surface_id not in allowed:
        return {'allowed': False, 'reason': f'unknown surface {surface_id}'}
    # P1：与 surfaces.json 的 forbidden_always 对齐（原 6 个标记漏了 D1-D5/CritBank/权重等）
    forbidden_markers = ['approval-delegate', 'L0-L3', 'verifyRan', 'GWT', 'FEP', 'AGENTS.md',
                         'CritBank', 'protected', 'D1-D5', 'turn-guard', 'llama-server', '权重',
                         '权限预设', 'GWT/FEP']
    blob = ' '.join(str(p) for p in modified_paths)
    hits = [m for m in forbidden_markers if m.lower() in blob.lower()]
    if hits:
        return {'allowed': False, 'reason': f'forbidden surfaces touched: {hits}'}
    return {'allowed': True, 'reason': 'ok'}


def self_test():
    passed = total = 0
    def check(label, ok):
        nonlocal passed, total
        total += 1; passed += 1 if ok else 0
        print(('PASS' if ok else 'FAIL') + '  ' + label)

    base = {'held-in': [0.5, 0.52], 'held-out': [0.4, 0.42]}
    check('accept: 两个 split 都提升', accept(base, {'held-in': [0.6, 0.62], 'held-out': [0.5, 0.52]})['decision'] == 'accept')
    check('accept: 一个提升一个持平', accept(base, {'held-in': [0.6, 0.62], 'held-out': [0.4, 0.42]})['decision'] == 'accept')
    check('reject: 一个 split 退化', accept(base, {'held-in': [0.6, 0.62], 'held-out': [0.3, 0.3]})['decision'] == 'reject')
    check('no-op: 全部持平', accept(base, {'held-in': [0.5, 0.52], 'held-out': [0.4, 0.42]})['decision'] == 'no-op')
    check('no-op: repeats 不足', accept({'held-in': [0.5], 'held-out': [0.4]}, base)['decision'] == 'no-op')
    ok, spread = variance_ok([0.50, 0.52])
    check('variance_ok: 窄分布通过', ok and spread < 0.10)
    ok, spread = variance_ok([0.30, 0.55])
    check('variance_ok: 宽分布拒绝', not ok)
    check('variance_ok: 样本不足拒绝', not variance_ok([0.5])[0])
    check('surface_check: 白名单内的 surface', surface_check('SURF-PROMPT-CRITIC', ['index.mjs:CRITIC_PROMPT'])['allowed'])
    check('surface_check: 未知 surface', not surface_check('SURF-EVERYTHING', ['index.mjs'])['allowed'])
    check('surface_check: 触碰禁改面', not surface_check('SURF-PROMPT-CRITIC', ['config/AGENTS.md'])['allowed'])
    print(f'\n══════ {passed}/{total} 通过 ══════')
    return 0 if passed == total else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--baseline', help='JSON file with held-in/held-out arrays')
    ap.add_argument('--candidate', help='JSON file with held-in/held-out arrays')
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    if a.baseline and a.candidate:
        b = json.load(open(a.baseline, encoding='utf-8'))
        c = json.load(open(a.candidate, encoding='utf-8'))
        print(json.dumps(accept(b, c), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(load_surfaces(), ensure_ascii=False, indent=2))
