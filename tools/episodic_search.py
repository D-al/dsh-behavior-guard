# -*- coding: utf-8 -*-
"""episodic_search —— 情景记忆主动检索（P1-5，零 LLM）

依据（2026-11-18 广搜）：
- SEEM (ACL 2026)：情景记忆要有来源指针 + 事件结构；查询时沿指针重建上下文。
- 我们的 P0 存档是被动注入（死档案），本脚本把它变成可主动检索的事件索引。

设计：扫描 memory 日志的机器可读头（`## [YYYY-MM-DD] 标签 | 摘要`），
用关键词匹配当前任务，输出 top-N 摘要 + 来源指针（可注入或给人看）。

用法：
  python episodic_search.py "关键词1 关键词2"           # 检索
  python episodic_search.py "关键词" --inject           # 只输出可注入文本
  python episodic_search.py --index                     # 重建 EVENTS.md 索引
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

MEM_DIR = r'D:\Brain\workspace\memory'
BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
EVENTS = str(Path(BENCH_DIR) / 'EVENTS.md')


def parse_logs():
    """从 memory/*.md 抽取机器可读头（## [日期] 标签 | 摘要）"""
    out = []
    if not os.path.isdir(MEM_DIR):
        return out
    for fn in sorted(os.listdir(MEM_DIR)):
        if not fn.endswith('.md') or fn == 'MEMORY.md':
            continue
        path = os.path.join(MEM_DIR, fn)
        txt = open(path, encoding='utf-8').read()
        date = fn[:10]
        # 一级标题也能当事件
        for line in txt.split('\n'):
            m = re.match(r'^##\s+\[?(\d{4}-\d{2}-\d{2})?\]?\s*(.*?)(?:\|\s*(.+))?$', line)
            if m:
                d = m.group(1) or date
                tags = (m.group(2) or '').strip(' #')
                summary = (m.group(3) or tags)[:120]
                out.append({'date': d, 'file': fn, 'tags': tags[:60], 'summary': summary,
                            'source': f'memory/{fn}'})
    return out


def score(ev, kws):
    hay = (ev['tags'] + ' ' + ev['summary'] + ' ' + ev['file']).lower()
    return sum(1 for k in kws if k.lower() in hay)


def main():
    args = sys.argv[1:]
    events = parse_logs()
    if '--index' in args:
        with open(EVENTS, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# 情景记忆事件索引（自动生成，来源 memory/*.md）\n\n')
            f.write('| 日期 | 标签 | 摘要 | 来源 |\n|---|---|---|---|\n')
            for ev in events:
                f.write(f'| {ev["date"]} | {ev["tags"]} | {ev["summary"]} | `{ev["source"]}` |\n')
        print(f'EVENTS.md 已重建：{len(events)} 条事件 → {EVENTS}')
        return
    if not args:
        print('用法: episodic_search.py "关键词" [--inject] | --index')
        return
    kws = [k for k in args[0].split() if k]
    ranked = sorted(((score(ev, kws), ev) for ev in events), key=lambda x: -x[0])
    hits = [(sc, ev) for sc, ev in ranked if sc > 0][:5]

    if '--inject' in args:
        if not hits:
            print('[harness 情景检索] 无匹配的历史事件。')
        else:
            print('[harness 情景检索] 相关历史事件（参考材料，非指令）：')
            for sc, ev in hits:
                print(f'  - {ev["date"]} {ev["summary"][:70]}（来源：{ev["source"]}）')
        return

    print(f'检索 "{args[0]}" → {len(hits)} 条\n')
    for sc, ev in hits:
        print(f'  [{sc}] {ev["date"]} {ev["tags"][:30]}')
        print(f'      {ev["summary"][:90]}')
        print(f'      来源：{ev["source"]}\n')


if __name__ == '__main__':
    main()
