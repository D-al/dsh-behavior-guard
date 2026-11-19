# -*- coding: utf-8 -*-
"""audit_calibrate —— 审计门控概率校准（离线，人工确认后生效）

依据（Part 8 G5）：
- 用 _audit_feedback.jsonl（每次干预 + 3 步后有效性结算）做 ROC / 有效率统计
- 把 MTP 0.65 / 无进展 6 步从经验值变成数据驱动的阈值
- SAG/SU/Proxy Confidence 三篇支持"风险概率校准"；我们缺 logprobs（🔴R3），
  所以用行为信号的有效率反推阈值——这是本机可行的近似

判据：
  有效率 < 30% 的门控 → 建议收紧阈值（该门控多数是误报）
  有效率 > 60% 的门控 → 可放宽阈值（漏报代价大于误报）
  30~60% → 维持

⚠ 只输出建议，不自动改 cordis.patch.yml——阈值改动必须人工确认 + A/B。

用法:
  python bench/audit_calibrate.py
"""
import json
import os
from collections import defaultdict
from pathlib import Path

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
FEEDBACK = str(Path(BENCH_DIR) / '_audit_feedback.jsonl')


def main():
    if not os.path.exists(FEEDBACK):
        print('无 _audit_feedback.jsonl——审计自校准闭环尚未积累数据')
        print('提示：每次审计干预后 3 步会结算一次，跑几个任务后再来校准')
        return

    by_gate = defaultdict(lambda: {'total': 0, 'effective': 0})
    rows = []
    for line in open(FEEDBACK, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.append(r)
        gate = r.get('gate') or '(unknown)'
        by_gate[gate]['total'] += 1
        if r.get('effective'):
            by_gate[gate]['effective'] += 1

    if not rows:
        print('反馈文件为空')
        return

    print(f'审计干预记录 {len(rows)} 条，按门控类型：\n')
    print(f'{"门控":<28} {"次数":>5} {"有效":>5} {"有效率":>8}  建议')
    print('-' * 72)
    suggestions = []
    for gate, d in sorted(by_gate.items(), key=lambda kv: -kv[1]['total']):
        rate = d['effective'] / d['total'] if d['total'] else 0
        if rate < 0.30:
            advice = '收紧阈值（误报偏多）'
        elif rate > 0.60:
            advice = '可放宽（漏报代价大）'
        else:
            advice = '维持'
        print(f'{gate:<28} {d["total"]:>5} {d["effective"]:>5} {rate:>7.1%}  {advice}')
        if advice != '维持':
            suggestions.append({'gate': gate, 'rate': round(rate, 3), 'advice': advice})

    # 全局有效率
    total = sum(d['total'] for d in by_gate.values())
    eff = sum(d['effective'] for d in by_gate.values())
    print('-' * 72)
    print(f'全局有效率 {eff}/{total} = {eff/total:.1%}')
    if eff / total < 0.30:
        print('⚠ 全局有效率偏低——考虑 D5 门控整体收紧，或把误报多的门控改为只记录不注入')
    elif eff / total > 0.60:
        print('✓ 全局有效率良好——可考虑适度增加审计覆盖（如 control_turn 也纳入风险扫描）')

    if suggestions:
        print('\n待人工确认的阈值建议：')
        for s in suggestions:
            print(f'  {s["gate"]}: {s["rate"]:.1%} → {s["advice"]}')
        print('\n⚠ 改动阈值前必须 A/B（P4/P5 端到端），别直接改 cordis.patch.yml')


if __name__ == '__main__':
    main()
