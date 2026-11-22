#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flow KPI —— 用吞吐/前置时间/失败率取代"门禁数/通过率"（TOC 目标重定义）

依据：docs/FIRST_PRINCIPLES_GOVERNANCE_20261122.md
- 旧目标"零缺陷通过率" → 检查环是目标本身，加固永远正确（局部优化陷阱）
- 新目标"单位时间正确自我改进的吞吐" → 暴露决策环是真约束

DORA 四指标映射：
  Lead Time（决策→完成）| 部署频率（commit 频率）| 变更失败率（回滚/修复 commit）| MTTR

用法:
  D:/Python/python.exe -B tools/flow_metrics.py [--days N] [--json]
输出: 控制台摘要 + 追加 D:/Brain/workspace/bench/_flow_metrics.jsonl
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path('D:/Brain/workspace/bench/_flow_metrics.jsonl')


def git(*args):
    r = subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=30)
    return r.stdout.strip() if r.returncode == 0 else ''


def parse_commits(days):
    """解析 git log：日期 | hash | subject"""
    since = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    raw = git('log', f'--since={since}', '--format=%aI|%h|%s')
    out = []
    for line in raw.splitlines():
        if '|' not in line:
            continue
        ts, h, subj = line.split('|', 2)
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            continue
        out.append({'dt': dt, 'hash': h, 'subject': subj})
    return out


def classify(subject):
    """按 commit message 分类（项目有严格的 commit 前缀纪律）"""
    s = subject.lower()
    if re.match(r'^(fix|revert|rollback)', s):
        return 'fix'
    if re.match(r'^(feat|roadmap|docs|chore|refactor|perf)', s):
        return 'change'
    if re.match(r'^gate', s):
        return 'gate'
    return 'other'


def extract_card_ids(subject):
    """从 commit message 提取卡片 ID（S13/A6/M5/S22 等）"""
    return set(re.findall(r'\b(?:[SMALG]\d+[A-Z]?_\d+|[SMALG]\d+|STRAT\d+|A\d_\d)\b', subject))


def compute(commits):
    by_id = {}
    for c in commits:
        ids = extract_card_ids(c['subject'])
        for cid in ids:
            by_id.setdefault(cid, []).append(c)

    lead_times = []
    for cid, cs in by_id.items():
        # 首次出现（claim/开工）→ 最后一次 done/完成类 commit
        ordered = sorted(cs, key=lambda x: x['dt'])
        start, end = ordered[0]['dt'], ordered[-1]['dt']
        hours = (end - start).total_seconds() / 3600
        lead_times.append({'card': cid, 'hours': round(hours, 2),
                           'commits': len(cs), 'first': start.isoformat(), 'last': end.isoformat()})

    kinds = Counter(classify(c['subject']) for c in commits)
    total = len(commits)
    failures = kinds['fix'] + kinds['gate']  # fix = 修复类；gate = 门禁类（含修复门禁）
    return {
        'commits_total': total,
        'by_kind': dict(kinds),
        'change_failure_rate': round(failures / total, 3) if total else 0,
        'lead_time_count': len(lead_times),
        'lead_time_median_hours': round(sorted(x['hours'] for x in lead_times)[len(lead_times) // 2], 2)
                                  if lead_times else 0,
        'lead_times': sorted(lead_times, key=lambda x: -x['hours'])[:10],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    commits = parse_commits(args.days)
    m = compute(commits)
    m['window_days'] = args.days
    m['measured_at'] = datetime.now(timezone.utc).isoformat()

    if args.json:
        print(json.dumps(m, ensure_ascii=False, indent=2))
    else:
        print('=' * 58)
        print(f' Flow KPI — 最近 {args.days} 天（TOC 新目标：吞吐，非门禁数）')
        print('=' * 58)
        print(f'  提交总数          : {m["commits_total"]}')
        print(f'  变更频率(commit/天): {m["commits_total"] / args.days:.1f}')
        print(f'  变更失败率        : {m["change_failure_rate"]:.1%}  (fix+gate / total)')
        print(f'  任务前置时间中位数: {m["lead_time_median_hours"]} 小时 ({m["lead_time_count"]} 张卡)')
        print(f'  最长前置时间 top3 : ' + ', '.join(
            f'{x["card"]}={x["hours"]}h' for x in m['lead_times'][:3]))
        print()
        print('  ⚠ 判据说明：Lead Time 从 commit message 的卡片 ID 推断，')
        print('     不是精确的 claim→done 时间戳；仅作趋势用，不作硬 KPI。')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('a', encoding='utf-8') as f:
        f.write(json.dumps(m, ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
