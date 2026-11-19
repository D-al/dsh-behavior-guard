# -*- coding: utf-8 -*-
"""session_tree —— 事件溯源会话树（P2-8，离线，零 LLM）

依据（2026-11-18 广搜）：
- OpenHands/Pi/OpenCode：历史是树不是列表，每事件指向 parent，fork/rewind/replay 是一等公民；
  "遗忘"也记为事件（标记"忘掉这些，这是摘要"），而非删除历史。
- 我们的压缩存档是线性覆盖，纠错无法回滚、无法分支对比。

本脚本把线性 trace 转成带 parent 指针的事件树，提供：
  --build    从 _trace.jsonl 建树 → _session_tree.json
  --query    查看某会话的事件链（可过滤 kind）
  --forget   记录一个"遗忘/压缩"事件（不改原 trace，只在树里加标记）
  --rewind   从某步回看（列出该步之后的事件，供回滚决策）

用法（只读 trace；写仅到 _session_tree.json）：
  python session_tree.py --build
  python session_tree.py --query --kind control_turn
  python session_tree.py --forget <step> "压缩摘要：..."
  python session_tree.py --rewind 40
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
TRACE = str(Path(BENCH_DIR) / '_trace.jsonl')
TREE = str(Path(BENCH_DIR) / '_session_tree.json')


def load_tree():
    if not os.path.exists(TREE):
        return {'nodes': [], 'meta': {'built_at': None, 'forget_events': []}}
    try:
        return json.load(open(TREE, encoding='utf-8'))
    except Exception:
        return {'nodes': [], 'meta': {'built_at': None, 'forget_events': []}}


def save_tree(t):
    with open(TREE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(t, f, ensure_ascii=False, indent=2)


def build():
    rows = [json.loads(l) for l in open(TRACE, encoding='utf-8') if l.strip()]
    nodes = []
    parent = None
    counters = {}
    for i, r in enumerate(rows):
        sid = r.get('sid', '?')
        counters[sid] = counters.get(sid, -1) + 1
        node = {'id': f'{sid}:{i}', 'parent': parent, 'seq': i, 'sid': sid,
                'local_seq': counters[sid], 'kind': r.get('kind'),
                'name': r.get('name'), 'step': r.get('step'), 'ts': r.get('ts'),
                'event': 'action'}
        # frame 五元组（若有）
        if 'frame' in r:
            node['frame'] = r['frame']
        nodes.append(node)
        parent = node['id']
    t = {'nodes': nodes, 'meta': {'built_at': datetime.now(timezone.utc).isoformat(),
                                  'source': TRACE, 'node_count': len(nodes), 'forget_events': []}}
    save_tree(t)
    print(f'会话树已建：{len(nodes)} 节点（parent 指针链）→ {TREE}')
    print('注：这是单链树（每节点 parent 为前一节点）；fork 需在 --forget 时创建分支。')


def main():
    args = sys.argv[1:]
    t = load_tree()
    if '--build' in args:
        build()
        return
    nodes = t.get('nodes', [])
    if not nodes:
        print('树为空，先跑 --build')
        return

    if '--forget' in args:
        step = int(args[args.index('--forget') + 1])
        note = args[args.index('--forget') + 2] if len(args) > args.index('--forget') + 2 else ''
        ev = {'at_step': step, 'note': note, 'ts': datetime.now(timezone.utc).isoformat(),
              'type': 'forget_marker'}
        t['meta'].setdefault('forget_events', []).append(ev)
        save_tree(t)
        print(f'遗忘事件已记录（step {step}）：{note}')
        print(f'语义：step <= {step} 的历史可视为"已摘要"，但节点保留，可随时 rewind 查阅。')
        return

    if '--rewind' in args:
        step = int(args[args.index('--rewind') + 1])
        tail = [n for n in nodes if n.get('seq', -1) >= step][:20]
        print(f'seq >= {step} 的事件（{len(tail)} 条）：（seq 为全局事件序号，保证可定位）')
        for n in tail:
            print(f'  [{n["seq"]:>4}] {n["kind"]:<14} {n.get("name") or ""} (step {n.get("step")})')
        return

    # --query 默认
    kind = args[args.index('--kind') + 1] if '--kind' in args else None
    filt = [n for n in nodes if not kind or n.get('kind') == kind]
    print(f'节点 {len(filt)}/{len(nodes)}' + (f' (kind={kind})' if kind else ''))
    for n in filt[-15:]:
        fr = n.get('frame', {})
        extra = f' | role={fr.get("role")} trust={fr.get("trust")}' if fr else ''
        print(f'  [{n["seq"]:>4}] {n["kind"]:<14} {n.get("name") or "":<16} parent={n.get("parent")}{extra}')
    if t['meta'].get('forget_events'):
        print(f'\n遗忘标记 {len(t["meta"]["forget_events"])} 个（历史保留，可 rewind）')


if __name__ == '__main__':
    main()
