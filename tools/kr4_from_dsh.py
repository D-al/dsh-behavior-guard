#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KR4 感知-行动测量：从 dsh 会话的真实 event 流提取 event_ts→action_ts

构念（2026-11-22 修正）：KR4 测的是**被改造的 agent（dsh 里的 35B）**
对外部事件的感知-反应闭环，不是开发 agent(WorkBuddy) 的响应速度。
所以数据源必须是 dsh session events（有毫秒级 time），不是手填 seed 日志。

提取规则：
  - event_ts = user/message 事件（用户输入/桥注入）的 time
  - action_ts = 该 turn 内首个 tool_call 类事件的 time
  - 延迟 = action_ts - event_ts（毫秒），<=30s 为有效
  - 每条输出 seeded=true（来自真实外部事件）、event_ts/action_ts（ISO）、action/evidence

用法:
  python tools/kr4_from_dsh.py --session <sid> [--probe] [--out PATH]
"""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

BRIDGE = Path('D:/Brain/workspace/bench/dsh-session-bridge/bridge.mjs')
OUT = Path('D:/Brain/workspace/bench/_event_replay_results.jsonl')
BOX_MS = 30000
# tool_call 事件类型（dsh session events 里的实际 kind）
TOOL_KINDS = ('tool/call', 'tool_call', 'assistant/tool_call', 'tool/use')


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def fetch_events(sid, limit=200):
    """直连 bridge HTTP API——CLI 的 events 把每行截到300字符致 JSON 损坏，
    user/message 长文本无法解析。descriptor 从 DSH_HOME 读（每次重读，跟随重启）。"""
    import urllib.request
    desc = json.loads(Path('D:/Brain/dsh-data/session-bridge.json').read_text(encoding='utf-8'))
    url = f"http://{desc['address']}:{desc['port']}/v1/sessions/{sid}/events?limit={limit}"
    req = urllib.request.Request(url, headers={'Authorization': f"Bearer {desc['token']}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode('utf-8'))
    return [x['event'] for x in data.get('records', []) if isinstance(x, dict) and 'event' in x]


def extract(sid, events):
    """按 turn 分组：每个 user/message → 同 turn 首个 tool_call。"""
    # 找真实用户输入（source.kind=user，排除 system-reminder）
    def is_external(e):
        if e.get('type') != 'user/message':
            return False
        d = e.get('data', {})
        # 只认桥/用户注入的真实外部事件：source.kind=user 且非系统内部反馈环
        src = d.get('source', {})
        if str(src.get('kind', '')) != 'user':
            return False
        text = ''
        for c in d.get('content', []):
            if c.get('type') == 'text':
                text = c.get('text', '')
                break
        if not text or text.startswith('<system') or text.startswith('[harness '):
            return False
        return True
    users = [e for e in events if is_external(e)]
    tool_calls = [e for e in events if e.get('type') in TOOL_KINDS]
    results = []
    for u in users:
        ets = u.get('time')
        turn = u.get('data', {}).get('turn')
        text = ''
        for c in u.get('data', {}).get('content', []):
            if c.get('type') == 'text':
                text = c.get('text', '')
                break
        if ets is None or not text:
            continue
        # 同 turn（或之后最近）的 tool_call
        cand = [t for t in tool_calls if t.get('time', 0) >= ets
                and (turn is None or t.get('data', {}).get('turn', turn) == turn)]
        if not cand:
            continue
        t = min(cand, key=lambda x: x['time'])
        lat = t['time'] - ets
        d = t.get('data', {})
        action = str(d.get('name') or d.get('tool') or d.get('kind') or 'tool_call')
        evidence = f'dsh event seq={t.get("seq")} turn={d.get("turn")} type={t.get("type")}'
        results.append({'action': action, 'evidence': evidence,
                        'seeded': True, 'source_type': 'seeded_dsh',
                        'event_ts': iso(ets), 'action_ts': iso(t['time']),
                        'latency_ms': lat, 'id': f'dsh-{u.get("seq")}',
                        'prompt': text[:60], 'session': sid,
                        'cold': (u is users[0])})
    return results


def main():
    ap = argparse.ArgumentParser(description='KR4 从 dsh 真实事件提取感知-行动延迟')
    ap.add_argument('--session', required=True, help='dsh sessionId')
    ap.add_argument('--out', type=Path, default=OUT)
    ap.add_argument('--probe', action='store_true', help='只打印不落盘')
    ap.add_argument('--limit', type=int, default=200)
    args = ap.parse_args()

    events = fetch_events(args.session, args.limit)
    rows = extract(args.session, events)
    print(f'事件 {len(events)} 条 → 提取 {len(rows)} 对 user→tool_call')
    for r in rows:
        tag = 'COLD' if r.get('cold') else ('OK' if 0 <= r['latency_ms'] <= BOX_MS else 'TIMEOUT')
        print(f'  [{tag}] {r["id"]} 延迟={r["latency_ms"]/1000:.1f}s action={r["action"]} prompt={r["prompt"][:30]}')

    if not rows:
        print('N/M: 无 user→tool_call 配对')
        return 2
    if args.probe:
        print('[PROBE] 不落盘')
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.out.with_suffix(args.out.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        for r in rows:
            if r.get('cold'):
                continue  # ADR-0022:冷启动含prefill,不计入KR4
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    tmp.replace(args.out)
    print(f'RENDERED {len(rows)} 行 → {args.out}')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
