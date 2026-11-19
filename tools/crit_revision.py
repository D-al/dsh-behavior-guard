# -*- coding: utf-8 -*-
"""crit_revision —— CritBank 反向修订通道（离线结算，人工确认后生效）

依据（Part 8 G2）：ReHarness (arXiv 2610.12668)——forward-only 记忆是结构性缺陷：
"记错了不认账"，过时/过度泛化的经验会在后续检索中反复被激活，错误自我强化。
本脚本从 _trace.jsonl 的 crit_hit 记录出发，检查"教训命中后是否仍重复同类失败"，
生成**降级/修订建议**到 bench/_crit_revisions.json（人工确认后才改 critbank.json）。

⚠ 设计纪律（与 G1 成对）：
- 只生成建议，**绝不自动改 critbank.json**——自动降级可能把正确教训误降级
- 一笔教训的"命中后失败"需达到 min_harms 次才建议修订
- G1（生成新技能）+ G2（修订旧技能）必须成对，否则错误经验加速积累

用法:
  python bench/crit_revision.py                 # 默认窗口 3 步、阈值 2 次
  python bench/crit_revision.py --window 5 --min-harms 3
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
TRACE = str(Path(BENCH_DIR) / '_trace.jsonl')
CRITBANK = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'critbank.json')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_crit_revisions.json')


def main():
    args = sys.argv[1:]
    window = 3
    min_harms = 2
    if '--window' in args:
        window = int(args[args.index('--window') + 1])
    if '--min-harms' in args:
        min_harms = int(args[args.index('--min-harms') + 1])

    rows = []
    if os.path.exists(TRACE):
        for line in open(TRACE, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # 按会话分组，按时间排序
    by_sid = defaultdict(list)
    for r in rows:
        by_sid[r.get('sid', '?')].append(r)
    for sid in by_sid:
        by_sid[sid].sort(key=lambda x: x.get('ts', ''))

    harms = defaultdict(list)   # lesson_id -> [(sid, hit_step, fail_step)]
    for sid, seq in by_sid.items():
        hits = [i for i, r in enumerate(seq) if r.get('kind') == 'crit_hit']
        for hi in hits:
            hit = seq[hi]
            lid = hit.get('id')
            if not lid:
                continue
            hstep = hit.get('step', 0)
            # 窗口内是否又出现同类失败（tool_result 非 OK，或 D1/D2 重复探测注入）
            for j in range(hi + 1, min(hi + 1 + window * 4, len(seq))):
                r = seq[j]
                step = r.get('step', 0)
                if step > hstep + window:
                    break
                if r.get('kind') == 'tool_result' and r.get('status') not in ('OK', None):
                    harms[lid].append({'sid': sid, 'hit_step': hstep, 'fail_step': step,
                                       'tool': r.get('name')})
                    break

    bank = []
    if os.path.exists(CRITBANK):
        try:
            bank = json.load(open(CRITBANK, encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            pass
    known = {c.get('id'): c for c in bank}

    suggestions = []
    for lid, cases in sorted(harms.items()):
        if len(cases) < min_harms:
            continue
        c = known.get(lid, {})
        suggestions.append({
            'id': lid,
            'lesson': c.get('lesson', '(not in critbank)'),
            'harm_count': len(cases),
            'samples': cases[:5],
            'suggestion': '降级或修订：该教训命中后仍重复失败 ≥%d 次。检查是否过度泛化/过时；'
                          '改写为更窄的触发条件，或标记 deprecated。' % min_harms,
            'status': 'PENDING_REVIEW',
        })

    out = {
        'generated_from': TRACE,
        'criteria': {'window_steps': window, 'min_harms': min_harms},
        'suggestions': suggestions,
        'note': '人工核验后决定是否改 critbank.json。自动生效被禁止（避免误降级正确教训）。',
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'crit_hit 记录: {sum(1 for r in rows if r.get("kind") == "crit_hit")}')
    print(f'降级建议: {len(suggestions)} → {OUT}')
    for s in suggestions[:5]:
        print(f'  {s["id"]}: 命中后失败 {s["harm_count"]} 次 — {s["lesson"][:50]}')


if __name__ == '__main__':
    main()
