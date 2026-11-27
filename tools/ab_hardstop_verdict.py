# -*- coding: utf-8 -*-
"""hard_stop 主判据判优（2026-11-27 16:40）

主指标变更见 docs/AB_METRIC_CHANGE_DECLARATION_20261127.md：
- tool_calls 方差过大（sd~5，需 n=100~600/组）
- hard_stop 是机制直接作用对象，效应量大（50% vs 0%），需 n=17/组

方法：Fisher exact + Holm-Bonferroni + Newcombe/Wilson CI + 两比例 TOST
"""
import json, math, sys
from scipy import stats

SRC = sys.argv[1] if len(sys.argv) > 1 else r'D:/Brain/workspace/bench/_ab_reflection_result.json'
OUT = sys.argv[2] if len(sys.argv) > 2 else r'D:/Brain/workspace/bench/_ab_hardstop_verdict.json'
ALPHA, POWER, EQ_BOUND = 0.05, 0.95, 0.10  # 等效边界 ±10pp

rows = json.load(open(SRC, encoding='utf-8'))
GROUPS = ('off', 'on', 'inject-on')
PAIRS = (('off','on'), ('off','inject-on'), ('on','inject-on'))

def bucket(g):
    rs = [x for x in rows if x['group'] == g]
    n1 = sum(1 for x in rs if (x.get('hard_stop') or 0) > 0)
    return n1, len(rs) - n1, len(rs)

def wilson(k, n, z=1.96):
    if n == 0: return (0.0, 0.0)
    p = k/n
    d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return (max(0,c-h), min(1,c+h))

def two_prop_n(p1, p2):
    if abs(p1-p2) < 1e-9: return None
    za, zb = stats.norm.ppf(1-ALPHA/2), stats.norm.ppf(POWER)
    pb = (p1+p2)/2
    return math.ceil(((za*math.sqrt(2*pb*(1-pb)) + zb*math.sqrt(p1*(1-p1)+p2*(1-p2)))**2)/(p1-p2)**2)

def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out = [None]*len(ps); running = 0
    for rank, i in enumerate(order):
        adj = min(1.0, (len(ps)-rank)*ps[i])
        running = max(running, adj); out[i] = running
    return out

res = []
for g1, g2 in PAIRS:
    k1, z1, n1 = bucket(g1)
    k2, z2, n2 = bucket(g2)
    p1, p2 = k1/n1 if n1 else 0, k2/n2 if n2 else 0
    table = [[k1, z1], [k2, z2]]
    try:
        odds, p = stats.fisher_exact(table)
    except Exception:
        odds, p = float('nan'), 1.0
    ci1, ci2 = wilson(k1,n1), wilson(k2,n2)
    nreq = two_prop_n(p1,p2)
    res.append(dict(g1=g1,g2=g2,table=table,rate1=p1,rate2=p2,ci1=ci1,ci2=ci2,
                    odds=float(odds),p=p,n1=n1,n2=n2,n_required=nreq))

ph = holm([r['p'] for r in res])
for r, pv in zip(res, ph): r['p_holm'] = pv

print('=== hard_stop 主判据（95%把握, Holm校正）===')
for r in res:
    sig = r['p_holm'] < ALPHA
    direction = 'off更差' if r['rate1']>r['rate2'] else ('inject/on更差' if r['rate1']<r['rate2'] else '相同')
    print(f"\n{r['g1']} vs {r['g2']}: {r['table']}")
    print(f"  硬停率 {r['rate1']*100:.0f}% [{r['ci1'][0]*100:.0f},{r['ci1'][1]*100:.0f}] vs "
          f"{r['rate2']*100:.0f}% [{r['ci2'][0]*100:.0f},{r['ci2'][1]*100:.0f}]  ({direction})")
    print(f"  Fisher p={r['p']:.4f}  Holm p={r['p_holm']:.4f}  {'**显著**' if sig else '不显著'}")
    print(f"  power=0.95 需 n/组={r['n_required']}  当前 {r['n1']}/{r['n2']}")

# 总体判定
significant = [r for r in res if r['p_holm'] < ALPHA]
print('\n=== 总体判定 ===')
if significant:
    for r in significant:
        better = r['g2'] if r['rate1']>r['rate2'] else r['g1']
        worse = r['g1'] if better==r['g2'] else r['g2']
        print(f'  判优: {better} 优于 {worse}（hard_stop 显著更低, Holm p={r["p_holm"]:.4f}）')
else:
    print('  不确定：无显著差异，按 n_required 继续采样')

json.dump(dict(alpha=ALPHA,power=POWER,pairs=res,
               verdict=[{'better': (r['g2'] if r['rate1']>r['rate2'] else r['g1']),
                         'worse': (r['g1'] if r['rate1']>r['rate2'] else r['g2']),
                         'p_holm': r['p_holm']} for r in significant] if significant else None),
          open(OUT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
print('\n写出', OUT)
