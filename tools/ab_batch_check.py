# -*- coding: utf-8 -*-
"""同批次实验的完整性检查：验证动态开关是否真生效 + 混杂是否消除"""
import json, collections, sys

p = sys.argv[1] if len(sys.argv)>1 else r'D:/Brain/workspace/bench/_ab_reflection_result.json'
rows = json.load(open(p, encoding='utf-8'))
batch = [r for r in rows if r.get('batch') == 'v2']
print(f'v2 同批次记录: {len(batch)}')

by = collections.defaultdict(list)
for r in batch: by[r.get('group')].append(r)
for g, rs in sorted(by.items()):
    print(f'\n[{g}] n={len(rs)}')
    for k in ('tool_calls','failures','hard_stop','mined','live_injected'):
        v = [x.get(k,0) for x in rs]
        print(f'  {k:14s} sum={sum(v):3d} mean={sum(v)/len(v):.2f} values={v}')

print('\n=== 动态开关有效性（关键）===')
for g in ('off','on','inject-on'):
    rs = by.get(g, [])
    if not rs: continue
    mined = sum(x.get('mined',0) for x in rs)
    inj = sum(x.get('live_injected',0) for x in rs)
    expect = (g != 'off', g == 'inject-on')
    ok_mine = (mined > 0) == expect[0]
    ok_inj = (inj > 0) == expect[1] if g == 'inject-on' else (inj == 0)
    print(f'  {g:10s} mined={mined} (期望{">0" if expect[0] else "=0"}, {"OK" if ok_mine else "FAIL"}) '
          f'live_injected={inj} (期望{">0" if expect[1] else "=0"}, {"OK" if ok_inj else "FAIL"})')
