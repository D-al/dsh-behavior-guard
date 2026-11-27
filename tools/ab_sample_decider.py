# -*- coding: utf-8 -*-
"""样本量决策：基于同批次实测方差，算达到 95% 把握还需多少样本"""
import json, statistics, math, sys
from scipy import stats

P = r'D:/Brain/workspace/bench/_ab_reflection_result.json'
rows = [x for x in json.load(open(P, encoding='utf-8')) if x.get('batch') == 'v2']
ALPHA, POWER = 0.05, 0.95

def vals(g, k):
    return [x.get(k, 0) for x in rows if x['group'] == g]

def pooled_sd(a, b):
    if len(a) < 2 or len(b) < 2: return None
    return math.sqrt(((len(a)-1)*statistics.variance(a) + (len(b)-1)*statistics.variance(b)) / (len(a)+len(b)-2))

def n_for(delta, sd, alpha=ALPHA, power=POWER):
    if not sd or delta == 0: return None
    za, zb = stats.norm.ppf(1-alpha/2), stats.norm.ppf(power)
    return math.ceil(2 * (sd * (za+zb) / abs(delta)) ** 2)

print(f'同批次样本: ' + ', '.join(f'{g}={len(vals(g,"tool_calls"))}' for g in ('off','on','inject-on')))
print(f'目标: alpha={ALPHA} (95%置信) power={POWER} (95%把握)\n')

# 关键比较：on vs inject-on（唯一有因果链的干预）
for g1, g2 in [('off','on'), ('on','inject-on'), ('off','inject-on')]:
    a, b = vals(g1,'tool_calls'), vals(g2,'tool_calls')
    if len(a)<2 or len(b)<2:
        print(f'{g1} vs {g2}: 样本不足，跳过'); continue
    d = statistics.mean(a)-statistics.mean(b)
    sd = pooled_sd(a,b)
    n = n_for(d, sd) if d else None
    have = min(len(a),len(b))
    print(f'{g1:10s} vs {g2:10s}  diff={d:+.2f}  pooled_sd={sd:.2f}  '
          f'需 n/组={n}  已有={have}  还差={max(0,(n or 0)-have)}')

print('\n判定建议：')
print('  - 若 on vs inject-on 的 diff 接近0 → 判"回注无增益"，需等效性检验(TOST)确认')
print('  - 若 diff 明显 → 继续跑到目标 n，用 Mann-Whitney + Bootstrap CI 判优')
print('  - 同批次随机化已消除时序混杂，剩余方差是真实模型方差')
