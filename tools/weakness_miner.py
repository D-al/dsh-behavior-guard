# -*- coding: utf-8 -*-
"""S1-P1 弱点挖掘：从真实 trace 抽失败签名 (terminal_cause, criticality, agent_mechanism)，
精确匹配聚类，产出 evidence_bundle.json。含 recovered_friction 保护段。
零 LLM 调用（规则驱动）。用法: D:/Python/python.exe bench/weakness_miner.py
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
TRACE = str(Path(BENCH_DIR) / '_trace.jsonl')
OUT = str(Path(BENCH_DIR) / '_evidence_bundle.json')

# A0 — test SID blacklist (loaded lazily once)
_TEST_SIDS_CACHE = None


def _load_test_sids():
    """Load test_sids.json; return set() if missing/invalid."""
    global _TEST_SIDS_CACHE
    if _TEST_SIDS_CACHE is not None:
        return _TEST_SIDS_CACHE
    import json as _json
    _candidates = [
        str(Path(__file__).resolve().parent.parent / 'test_sids.json'),
        str(Path(__file__).resolve().parent / 'test_sids.json'),
        str(Path(BENCH_DIR) / 'test_sids.json'),
    ]
    for _p in _candidates:
        try:
            with open(_p, encoding='utf-8') as _f:
                data = _json.load(_f)
                sids = set(data.get('sids', []))
                _TEST_SIDS_CACHE = sids
                return sids
        except Exception:
            continue
    _TEST_SIDS_CACHE = set()
    return _TEST_SIDS_CACHE

# 失败签名映射：trace kind/tag → (terminal_cause, criticality, agent_mechanism)
SIGNATURES = {
    ('llm_failed', 'audit'): ('audit_unavailable', 'high', 'role-llm'),
    ('llm_failed', 'critic'): ('critic_unavailable', 'medium', 'role-llm'),
    ('llm_failed', 'corrector'): ('corrector_unavailable', 'high', 'role-llm'),
    ('llm_failed', 'planner'): ('planner_unavailable', 'medium', 'role-llm'),
    ('tool_result', 'FAIL'): ('tool_failure', 'medium', 'tool-execution'),
    # P0 修复：真实 verify_on_stop trace 只有 {ts,sid,kind,step}，没有 verdict/status 字段。
    # 它出现的语义就是"模型想结束但产物未验证"，故命中即算 artifact_missing 信号，不再依赖 verdict。
    ('verify_on_stop', None): ('artifact_missing', 'high', 'verify-gate'),
    ('injection_hit', None): ('prompt_injection_attempt', 'high', 'input-boundary'),
    ('adaptive_route', 'full-think'): ('no_degradation', 'low', 'adaptive-router'),
}


def load_rows():
    """Load trace rows, filtering out test SIDs (A0 blacklist)."""
    if not os.path.exists(TRACE):
        return []
    _blacklist = _load_test_sids()
    rows = []
    with open(TRACE, encoding='utf-8') as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            sid = r.get('sid', '')
            # Skip if sid starts with any blacklisted prefix or exact match
            if _blacklist and (sid in _blacklist or any(sid.startswith(prefix) for prefix in _blacklist)):
                continue
            rows.append(r)
    return rows


def mine(rows):
    clusters = defaultdict(lambda: {'count': 0, 'examples': [], 'sessions': set()})
    protected = []
    for r in rows:
        kind = r.get('kind')
        tag = r.get('tag') or r.get('status')
        sig = None
        if kind == 'llm' and not r.get('ok'):
            sig = SIGNATURES.get(('llm_failed', tag))
        elif kind == 'tool_result':
            sig = SIGNATURES.get(('tool_result', tag))
        elif kind == 'verify_on_stop':
            # 出现即信号（见上方注释），兼容未来若加了 verdict 字段则只在 FAIL 时计
            verdict = r.get('verdict')
            sig = SIGNATURES.get(('verify_on_stop', None)) if verdict is None else SIGNATURES.get(('verify_on_stop', verdict))
        elif kind == 'injection_hit':
            sig = SIGNATURES.get(('injection_hit', None))
        elif kind == 'adaptive_route':
            sig = SIGNATURES.get(('adaptive_route', r.get('route') or r.get('decision')))
        elif kind == 'crit_hit':
            # crit_hit = 教训命中 = harness 救回来的案例 → protected（不是要修的失败）
            protected.append({'kind': 'recovered_friction', 'id': r.get('id'),
                              'step': r.get('step'), 'ts': r.get('ts')})
        if sig:
            key = sig  # 精确匹配聚类（论文做法，不用 embedding）
            clusters[key]['count'] += 1
            clusters[key]['sessions'].add(r.get('sid', ''))
            if len(clusters[key]['examples']) < 3:
                clusters[key]['examples'].append({
                    'ts': r.get('ts'), 'step': r.get('step'), 'sid': r.get('sid'),
                    'error': r.get('error'), 'finish': r.get('finish'),
                })
    result = []
    for sig, v in sorted(clusters.items(), key=lambda x: -x[1]['count']):
        cause, crit, mech = sig
        # support × actionability 排序分：高频 + 机制可改 = 高优先
        actionable = mech in ('role-llm', 'tool-execution', 'input-boundary', 'adaptive-router')
        score = v['count'] * (2 if actionable else 1) * (2 if crit == 'high' else 1)
        result.append({
            'terminal_cause': cause, 'criticality': crit, 'agent_mechanism': mech,
            'support': v['count'], 'actionability': actionable, 'priority': score,
            'unique_sessions': len(v['sessions']), 'examples': v['examples'],
        })
    return result, protected


def main():
    rows = load_rows()
    sigs, protected = mine(rows)
    bundle = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'trace_rows': len(rows),
        'method': 'exact-match clustering (no embedding), per Self-Harness paper',
        'failure_signatures': sigs,
        'protected': {
            'description': 'recovered_friction: 上下文不堪但靠 harness 救回来的案例，必须保护而非修复',
            'count': len(protected),
            'examples': protected[:20],
        },
        'top_actionable': [s for s in sigs if s['actionability']][:5],
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    print(f'trace rows: {len(rows)}')
    print(f'failure clusters: {len(sigs)} | recovered_friction protected: {len(protected)}')
    for s in bundle['top_actionable']:
        print(f"  {s['terminal_cause']:28s} support={s['support']:4d} priority={s['priority']:5d} mech={s['agent_mechanism']}")
    print(f'written: {OUT}')


if __name__ == '__main__':
    main()
