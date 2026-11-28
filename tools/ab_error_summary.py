# -*- coding: utf-8 -*-
"""错误类型实时摘要（实验运行中可随时执行）"""
import json, collections, os, sys

ERRLOG = r'D:/Brain/workspace/bench/_ab_error_log.jsonl'
NOVELLOG = r'D:/Brain/workspace/bench/_ab_novel_types.jsonl'
RESULT = r'D:/Brain/workspace/bench/_ab_reflection_result.json'

def read_jsonl(p):
    if not os.path.isfile(p): return []
    return [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]

logs = read_jsonl(ERRLOG)
novels = read_jsonl(NOVELLOG)
r = json.load(open(RESULT, encoding='utf-8'))
v2 = [x for x in r if x.get('batch')=='v2']

print(f'=== 实验进度: {len(v2)} 组 ' +
      str(dict(collections.Counter(x['group'] for x in v2))) + ' ===')
print(f'错误日志记录: {len(logs)}  新类型告警: {len(novels)}')

if logs:
    print('\n=== 错误类型分布（新实验段）===')
    c = collections.Counter()
    byg = collections.defaultdict(collections.Counter)
    for x in logs:
        for code in x.get('codes', []):
            c[code] += 1
            byg[x.get('group','?')][code] += 1
    for code, n in c.most_common():
        print(f'  {code:26s} {n:3d}  off={byg["off"][code]:2d} on={byg["on"][code]:2d} inject={byg["inject-on"][code]:2d}')

    empty = sum(1 for x in logs if not x.get('codes'))
    print(f'  无错误类型: {empty}/{len(logs)} ({100*empty/len(logs):.0f}%)')

if novels:
    print('\n=== ⚠ 新类型告警 ===')
    for x in novels[-15:]:
        print(f"  {x['ts'][11:19]} {x['sid'][:14]:14s} {x['group']:10s} "
              f"narrow={x.get('narrow')} broad={x.get('broad')}")
else:
    print('\n新类型告警: 0（暂无）')

print('\n提示: 基线0次类型 = FORCED_HELP/INTENT_DRIFT/RECALL_BLIND/REPEAT_WRITE_SPIN/VERIFY_NARRATION_LOOP')
