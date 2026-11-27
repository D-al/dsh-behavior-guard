# -*- coding: utf-8 -*-
"""读 _ab_reflection_result.json 做组间对比（受控 A/B）"""
import json, statistics, sys

p = sys.argv[1] if len(sys.argv)>1 else r'D:/Brain/workspace/bench/_ab_reflection_result.json'
rows = json.load(open(p, encoding='utf-8'))
groups = {}
for r in rows:
    groups.setdefault(r.get('group','?'), []).append(r)

print('=== 受控 A/B 汇总 ===')
for g, rs in sorted(groups.items()):
    def avg(k):
        v = [r.get(k,0) for r in rs]
        return sum(v)/len(v) if v else 0
    print(f'[{g}] n={len(rs)}')
    print(f'  tool_calls/session: {avg("tool_calls"):.2f}')
    print(f'  failures/session:   {avg("failures"):.2f}')
    print(f'  hard_stop/session:  {avg("hard_stop"):.2f}')
    print(f'  mined/session:      {avg("mined"):.2f}')
    fs = [r.get('failures',0) for r in rs]
    hs = [r.get('hard_stop',0) for r in rs]
    print(f'  零失败会话: {sum(1 for x in fs if x==0)}/{len(rs)}  零硬停会话: {sum(1 for x in hs if x==0)}/{len(rs)}')

if len(groups) >= 2:
    print('\n=== 差异 ===')
    keys = list(sorted(groups))
    a, b = groups[keys[0]], groups[keys[1]]
    for k in ('tool_calls','failures','hard_stop','mined'):
        ma = sum(r.get(k,0) for r in a)/len(a)
        mb = sum(r.get(k,0) for r in b)/len(b)
        print(f'  {k}: {keys[0]}={ma:.2f} vs {keys[1]}={mb:.2f}  (差 {mb-ma:+.2f})')

print('\n⚠ 统计边界：n<20 时任何差异都可能是随机波动；35B 单次方差 ±10%，判优至少 2 次。')
