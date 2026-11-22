#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KR4 预埋事件记录器：同步写 event_ts / action_ts，时间盒自动算，绝不事后填

依据（2026-11-22 构念修正）：KR4 测"预埋事件在时间盒内反应"，不是"工具有回执"。
判据 verify_kr4 要求每行 seeded=true + event_ts/action_ts + 延迟<=30s + 动作证据。

协议（时间戳必须当场同步写，不能事后补）：
  1) seed   --id E1 --desc "改config/x.json加一行"   → 写 {id, event_ts, seeded:true}（同步）
  2) respond --id E1 --action edit --evidence "diff..." → 追加 action_ts + action/evidence（同步）
  3) 延迟 = action_ts - event_ts 自动算；>30s 判 FAIL，不伪造
  4) --render → 生成 _event_replay_results.jsonl（只含完整三要素的行）

防造假：
  - seed/respond 必须显式 --id --desc/--action/--evidence，不默认值
  - 不存在的 id 不能 respond（防凭空造响应）
  - 重复 seed 同 id 拒绝（防覆盖）
  - probe 模式写临时路径，不碰正式证据

用法:
  python tools/kr4_seed_event.py seed --id E1 --desc "..." [--log PATH]
  python tools/kr4_seed_event.py respond --id E1 --action edit --evidence "..." [--log PATH]
  python tools/kr4_seed_event.py status [--log PATH]
  python tools/kr4_seed_event.py render [--log PATH] [--out PATH] [--probe]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path('D:/Brain/workspace/bench')
LOG = BENCH / '_kr4_seed_log.jsonl'
OUT = BENCH / '_event_replay_results.jsonl'
BOX_SECONDS = 30


def now():
    return datetime.now(timezone.utc).isoformat()


def append_sync(path, row):
    """同步写 + flush + fsync——时间戳当场落盘，防进程快速退出丢失。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
        f.flush()
        import os
        os.fsync(f.fileno())


def read_log(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.open(encoding='utf-8', errors='replace'):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def cmd_seed(args, log):
    rows = read_log(log)
    if any(r.get('id') == args.id and r.get('op') == 'seed' for r in rows):
        print(f'REJECT: id={args.id} 已 seed（防覆盖）')
        return 2
    append_sync(log, {'op': 'seed', 'id': args.id, 'desc': args.desc,
                      'event_ts': now(), 'seeded': True, 'by': args.by or 'human'})
    print(f'SEEDED: {args.id} @ {now()} — 请现在触发事件')
    return 0


def cmd_respond(args, log):
    rows = read_log(log)
    seeds = [r for r in rows if r.get('op') == 'seed' and r.get('id') == args.id]
    if not seeds:
        print(f'REJECT: id={args.id} 未 seed（防凭空造响应）')
        return 2
    if any(r.get('op') == 'respond' and r.get('id') == args.id for r in rows):
        print(f'REJECT: id={args.id} 已 respond（防重复）')
        return 2
    append_sync(log, {'op': 'respond', 'id': args.id, 'action': args.action,
                      'evidence': args.evidence, 'action_ts': now(),
                      'by': args.by or 'agent'})
    print(f'RESPONDED: {args.id} @ {now()}')
    return 0


def cmd_status(args, log):
    rows = read_log(log)
    seeds = [r for r in rows if r.get('op') == 'seed']
    resps = {r['id']: r for r in rows if r.get('op') == 'respond'}
    print(f'KR4 预埋事件: {len(seeds)} 个 seed / {len(resps)} 个 respond')
    for s in seeds:
        r = resps.get(s['id'])
        if not r:
            print(f'  [{s["id"]}] 待响应 (seed @ {s["event_ts"][:19]})')
            continue
        try:
            a = datetime.fromisoformat(s['event_ts'])
            b = datetime.fromisoformat(r['action_ts'])
            lat = (b - a).total_seconds()
            tag = 'OK' if 0 <= lat <= BOX_SECONDS else f'TIMEOUT>{BOX_SECONDS}s'
        except ValueError:
            lat, tag = -1, 'BAD_TS'
        print(f'  [{s["id"]}] {tag} 延迟={lat:.1f}s action={r["action"]}')
    return 0


def cmd_render(args, log, out):
    rows = read_log(log)
    seeds = [r for r in rows if r.get('op') == 'seed']
    resps = {r['id']: r for r in rows if r.get('op') == 'respond'}
    rendered = []
    for s in seeds:
        r = resps.get(s['id'])
        if not r:
            continue
        try:
            a = datetime.fromisoformat(s['event_ts'])
            b = datetime.fromisoformat(r['action_ts'])
            lat = (b - a).total_seconds()
        except ValueError:
            continue
        rendered.append({'action': r['action'], 'evidence': r['evidence'],
                         'seeded': True, 'source_type': 'seeded',
                         'event_ts': s['event_ts'], 'action_ts': r['action_ts'],
                         'latency_s': round(lat, 2),
                         'id': s['id'], 'desc': s['desc']})
    if not rendered:
        print('N/M: 无完整 seed+respond 配对，不写证据')
        return 2
    if args.probe:
        print(f'[PROBE] 将写 {len(rendered)} 行到 {out}（探针模式不落盘）')
        for r in rendered:
            print('  ' + json.dumps(r, ensure_ascii=False)[:160])
        return 0
    target = args.out or OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        for r in rendered:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    tmp.replace(target)
    print(f'RENDERED: {len(rendered)} 行 → {target}')
    return 0


def main():
    ap = argparse.ArgumentParser(description='KR4 预埋事件记录器（同步时间戳，防造假）')
    ap.add_argument('cmd', choices=['seed', 'respond', 'status', 'render'])
    ap.add_argument('--id', help='事件 ID')
    ap.add_argument('--desc', help='seed:事件描述')
    ap.add_argument('--action', help='respond:动作类型')
    ap.add_argument('--evidence', help='respond:动作证据')
    ap.add_argument('--by', help='记录者（seed 默认 human / respond 默认 agent）')
    ap.add_argument('--log', type=Path, default=LOG)
    ap.add_argument('--out', type=Path, help='render 输出路径')
    ap.add_argument('--probe', action='store_true')
    args = ap.parse_args()

    log = args.log
    if args.cmd == 'seed':
        if not args.id or not args.desc:
            ap.error('seed 需 --id 和 --desc（不填默认=造假）')
        return cmd_seed(args, log)
    if args.cmd == 'respond':
        if not args.id or not args.action or not args.evidence:
            ap.error('respond 需 --id --action --evidence（不填默认=造假）')
        return cmd_respond(args, log)
    if args.cmd == 'status':
        return cmd_status(args, log)
    return cmd_render(args, log, args.out)


if __name__ == '__main__':
    sys.exit(main())
