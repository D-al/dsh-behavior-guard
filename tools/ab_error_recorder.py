# -*- coding: utf-8 -*-
"""A/B 实验的错误类型记录器（2026-11-28）

在 runner 每会话结束后调用，把错误类型 + 新类型标记写到独立 JSONL，
不污染 result.json 的统计字段。

用法（Python 内）:
    from ab_error_recorder import record_session
    record_session(sid, group, mode)
"""
import json, os, sys, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import error_taxonomy as et

ERRLOG = r'D:/Brain/workspace/bench/_ab_error_log.jsonl'
NOVELLOG = r'D:/Brain/workspace/bench/_ab_novel_types.jsonl'
_baseline = None

def _bl():
    global _baseline
    if _baseline is None:
        _baseline = et.load_baseline()
    return _baseline

def record_session(sid, group, mode=None):
    """记录单会话错误类型；返回 (types, novel) 供打印。"""
    try:
        by_sid = et.load_trace()  # dict: short_sid -> [trace rows]
        key = et._short(sid)
        rows = by_sid.get(key, [])
        text = et.session_text_for(sid) or ''
        types = et.classify_session(sid, rows, text)
    except Exception as e:
        types = []
        err = f'classify failed: {e}'
    else:
        err = None

    codes = [t['code'] for t in types]
    novel_narrow = et.detect_novel(codes, _bl(), mode='narrow')
    novel_broad = et.detect_novel(codes, _bl(), mode='broad')
    rec = dict(ts=datetime.datetime.now().isoformat(), sid=sid, group=group,
               mode=mode, codes=codes, types=types,
               novel_narrow=novel_narrow, novel_broad=novel_broad,
               error=err)
    with open(ERRLOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    # 新类型单独告警文件
    if novel_narrow or novel_broad:
        alert = dict(ts=rec['ts'], sid=sid, group=group,
                     narrow=novel_narrow, broad=novel_broad,
                     types=types)
        with open(NOVELLOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(alert, ensure_ascii=False) + '\n')
    return codes, novel_narrow, novel_broad

if __name__ == '__main__':
    sid = sys.argv[1] if len(sys.argv)>1 else ''
    g = sys.argv[2] if len(sys.argv)>2 else '?'
    print(record_session(sid, g))
