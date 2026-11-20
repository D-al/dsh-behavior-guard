"""分析读写决策-执行漏斗：从 trace 的真实事件序列判断"识字率"瓶颈在哪一层。"""
import json
from collections import defaultdict, Counter

TEST = {'s1', 'b', 'b7332eb6', 'budget-4', 'fb', 'r', 'outcome-', 'budget-1', 'budget-2', 'budget-3', 'inject-test'}
rows = []
for l in open(r'D:\Brain\workspace\bench\_trace.jsonl', encoding='utf-8', errors='replace'):
    try:
        r = json.loads(l)
    except Exception:
        continue
    if r.get('sid') in TEST or not r.get('ts', '').startswith('2026-11-20'):
        continue
    rows.append(r)

# 按 sid+step 排序，重建事件序列
rows.sort(key=lambda r: (r.get('sid', ''), r.get('ts', '')))
by_sid = defaultdict(list)
for r in rows:
    by_sid[r.get('sid')].append(r)

print('=== 读写决策-执行漏斗（今天真实 sid）===')
tot_read = tot_write = tot_edit = tot_fail = 0
read_then_write = 0
fail_then_retry = 0
fail_then_giveup = 0
long_read_runs = 0

for sid, evs in by_sid.items():
    seq = [r for r in evs if r.get('kind') in ('tool_call', 'tool_result')]
    calls = [r for r in seq if r.get('kind') == 'tool_call']
    results = [r for r in seq if r.get('kind') == 'tool_result']
    n_read = sum(1 for r in calls if r.get('name') == 'read')
    n_write = sum(1 for r in calls if r.get('name') in ('write', 'edit', 'apply_patch'))
    n_fail = sum(1 for r in results if r.get('status') != 'OK')
    tot_read += n_read
    tot_write += n_write
    tot_fail += n_fail
    # read 之后紧跟 write（同一 sid 内出现 read→write 顺序）
    seen_read = False
    for r in calls:
        if r.get('name') == 'read':
            seen_read = True
        elif seen_read and r.get('name') in ('write', 'edit'):
            read_then_write += 1
            seen_read = False
    # 连续 read 无 write 的最长串
    run = 0
    for r in calls:
        if r.get('name') in ('read', 'grep', 'glob'):
            run += 1
        elif r.get('name') in ('write', 'edit', 'apply_patch'):
            run = 0
        if run >= 5:
            long_read_runs += 1
            break

print(f'真实 sid 数: {len(by_sid)}')
print(f'read 调用: {tot_read}')
print(f'write/edit 调用: {tot_write}')
print(f'失败结果: {tot_fail}')
print(f'read→write 转化次数: {read_then_write}')
print(f'出现"连续读≥5无写"的会话数: {long_read_runs}')
print(f'整体 read→write 转化率: {read_then_write/tot_read*100 if tot_read else 0:.1f}%')

# 按 sid 看谁在反复读不写
print('\n=== 各 sid 的读/写/失败 ===')
for sid, evs in sorted(by_sid.items(), key=lambda x: -sum(1 for r in x[1] if r.get('kind') == 'tool_call'))[:8]:
    calls = [r for r in evs if r.get('kind') == 'tool_call']
    results = [r for r in evs if r.get('kind') == 'tool_result']
    nr = sum(1 for r in calls if r.get('name') == 'read')
    nw = sum(1 for r in calls if r.get('name') in ('write', 'edit', 'apply_patch'))
    nf = sum(1 for r in results if r.get('status') != 'OK')
    print(f'  {sid[:14]:14s} read={nr:3d} write={nw:3d} fail={nf:3d}')
