#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工具面审计：统计会话 dump 里「暴露多少工具 / 各自调用多少次 / schema 占多少 token」。

2026-11-21 修复：原默认路径 bench/_cur8.jsonl 已失效（历史遗留），且原逻辑
要求 request/header 含 tools schema，否则报"无法审计"——但真实 dump 只有
tool/call 事件。现在兼容两种格式，无 schema 时仍产出调用频次报告。

用法:
  python tools/tool_audit.py                          # 默认：跨 archive/session-dumps 全部 dump
  python tools/tool_audit.py <file.jsonl>             # 单个 dump
  python tools/tool_audit.py --json                   # 机器可读（供判据/闸门使用）
"""
import collections
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 会话 dump 是运行数据（在 workspace），不进仓库；可用 TOOL_AUDIT_DUMPS 覆盖
DUMP_DIR = os.environ.get('TOOL_AUDIT_DUMPS',
                          os.path.join('D:/Brain/workspace/bench', 'archive', 'session-dumps'))
DEFAULT_GLOB = os.path.join(DUMP_DIR, '_cur*.jsonl')


def load_rows(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def audit(paths):
    total = collections.Counter()
    per_sess = {}
    schema_tools = None
    seen_calls = set()   # 2026-11-21: dump 是同一会话的累积快照，必须按 callId 去重
    dup_count = 0
    for p in paths:
        rows = load_rows(p)
        c = collections.Counter()
        for r in rows:
            if r.get('type') == 'tool/call':
                d = r.get('data') or {}
                cid = d.get('callId')
                if cid:
                    if cid in seen_calls:
                        dup_count += 1
                        continue
                    seen_calls.add(cid)
                c[d.get('name') or '<unnamed>'] += 1
            # 兼容 request/header 里带 tools schema 的格式
            if r.get('type') == 'request/header' and schema_tools is None:
                schema_tools = (r.get('data') or {}).get('tools')
        per_sess[os.path.basename(p)] = c
        total.update(c)
    return total, per_sess, schema_tools, dup_count


def report(paths):
    total, per_sess, schema, dup_count = audit(paths)
    n = sum(total.values())
    if not n:
        print('没有 tool/call 事件，无法审计')
        return 1
    print(f'会话 dump: {len(paths)} 个（按 callId 去重后）| 唯一调用 {n} | 重复快照 {dup_count} | 不同工具 {len(total)}')
    print(f'{"工具":30} {"调用":>6} {"占比":>6} {"会话数":>6}')
    print('-' * 56)
    for k, v in total.most_common():
        print(f'{k:30} {v:6} {v*100//n:5}% {sum(1 for c in per_sess.values() if c.get(k)):6}')
    print('-' * 56)
    for top in (3, 5, 8):
        r = sum(v for _, v in total.most_common(top))
        print(f'前 {top} 种工具占调用 {r*100//n}%')
    if schema:
        zero = [t.get('name') for t in schema if not total.get(t.get('name'))]
        print(f'schema 定义 {len(schema)} 个工具，零调用 {len(zero)} 个: {zero}')
    else:
        print('注：dump 无 tools schema，仅有调用频次（足够判断零使用/低频工具）')
    return 0


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    args = [a for a in args if not a.startswith('--')]
    paths = args or sorted(glob.glob(DEFAULT_GLOB))
    if not paths:
        print('未找到会话 dump: ' + DEFAULT_GLOB)
        return 1
    if as_json:
        total, per_sess, schema, dup_count = audit(paths)
        print(json.dumps({
            'files': len(paths),
            'unique_calls': sum(total.values()),
            'duplicate_snapshot_calls': dup_count,
            'total_calls': sum(total.values()),
            'distinct_tools': len(total),
            'by_tool': dict(total.most_common()),
            'schema_tools': len(schema) if schema else None,
        }, ensure_ascii=False, indent=2))
        return 0
    return report(paths)


if __name__ == '__main__':
    sys.exit(main())
