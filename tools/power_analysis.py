# -*- coding: utf-8 -*-
"""功效分析：判优实验需要多少样本（95% 置信度）"""
import json, statistics, math
from scipy import stats

R = json.load(open(r'D:/Brain/workspace/bench/_ab_reflection_result.json', encoding='utf-8'))
ALPHA = 0.05
POWER = 0.95   # 用户要"95%把握"→ 取 power=0.95（比常规 0.80 更严）

def series(g, k):
    return [x.get(k, 0) for x in R if x['group'] == g]

def cohens_d(a, b):
    if len(a) < 2 or len(b) < 2: return None
    na, nb = len(a), len(b)
    sp = math.sqrt(((na-1)*statistics.variance(a) + (nb-1)*statistics.variance(b)) / (na+nb-2))
    if sp == 0: return None
    return (statistics.mean(a) - statistics.mean(b)) / sp

def required_n(d, alpha=ALPHA, power=POWER):
    """两独立样本 t 检验，每组所需 n（近似）"""
    if d is None or d == 0: return None
    za = stats.norm.ppf(1 - alpha/2)
    zb = stats.norm.ppf(power)
    return math.ceil(2 * ((za + zb) / abs(d)) ** 2)

print(f'参数: alpha={ALPHA} (95%置信), power={POWER} (95%把握)')
print('=' * 70)

pairs = [('off', 'inject-on'), ('on', 'inject-on'), ('off', 'on')]
for g1, g2 in pairs:
    print(f'\n### {g1} vs {g2}')
    for k in ('tool_calls', 'failures', 'hard_stop'):
        a, b = series(g1, k), series(g2, k)
        d = cohens_d(a, b)
        n = required_n(d)
        print(f'  {k:12s} mean {statistics.mean(a):5.2f} vs {statistics.mean(b):5.2f}  '
              f'd={(format(d, chr(43)+chr(46)+chr(50)+chr(102)) if d is not None else chr(78)+chr(65))}  n/group={n if n else chr(78)+chr(65)}')

# 主指标选择建议
print('\n' + '=' * 70)
print('主指标建议：tool_calls/session（连续、有方差、能反映效率）')
print('失败率 failures 在 on 组方差=0（全是1），不适合做 t 检验；')
print('hard_stop 在 off 全 1、inject-on 全 0——二项分布，用 Fisher exact。')

# Fisher exact 对 hard_stop
print('\n### Fisher exact (hard_stop 有/无)')
for g1, g2 in pairs:
    a = series(g1, 'hard_stop'); b = series(g2, 'hard_stop')
    t1 = [[sum(1 for x in a if x>0), sum(1 for x in a if x==0)],
          [sum(1 for x in b if x>0), sum(1 for x in b if x==0)]]
    try:
        odd, p = stats.fisher_exact(t1)
        print(f'  {g1} vs {g2}: table={t1} odds={odd:.2f} p={p:.3f}')
    except Exception as e:
        print(f'  {g1} vs {g2}: {e}')
