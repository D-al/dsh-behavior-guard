# -*- coding: utf-8 -*-
"""auditor_metrics —— 审计员自校准指标（读 _audit_feedback.jsonl）

指标（Agnost AI 校准方法论的本地版）：
  - 干预数 / 有效数（注入后 3 步内无新失败）/ 有效率  —— 按门控类型分组
  - 有效率低 = 该门控误判多 → 收紧阈值或修 prompt
用法: python bench/auditor_metrics.py [jsonl路径]
"""
import json
import os
import sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Brain\workspace\bench\_audit_feedback.jsonl'
if not os.path.exists(path):
    print('尚无审计干预记录:', path)
    sys.exit(0)

rows = []
for line in open(path, encoding='utf-8'):
    line = line.strip()
    if line:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass

if not rows:
    print('记录为空')
    sys.exit(0)

by_gate = defaultdict(lambda: [0, 0])
for r in rows:
    g = r.get('gate', '?')
    by_gate[g][0] += 1
    if r.get('effective'):
        by_gate[g][1] += 1

print(f'审计干预记录 {len(rows)} 条')
print(f'{"门控":20s} {"干预":>4s} {"有效":>4s} {"有效率":>6s}')
for g, (n, ok) in sorted(by_gate.items(), key=lambda x: -x[1][0]):
    print(f'{g:20s} {n:4d} {ok:4d} {ok / n * 100:5.0f}%')

total = len(rows)
eff = sum(1 for r in rows if r.get('effective'))
print(f'\n总体有效率: {eff}/{total} = {eff / total * 100:.0f}%')
low = [(g, n, ok) for g, (n, ok) in by_gate.items() if n >= 3 and ok / n < 0.5]
if low:
    print('⚠ 有效率 <50% 的门控（建议收紧阈值）：')
    for g, n, ok in low:
        print(f'  - {g}: {ok}/{n}')
