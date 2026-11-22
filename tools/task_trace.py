#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""决策环 trace 打点（Python appender → 同一 _trace.jsonl）

背景：index.mjs 的 makeTracer 是 JS 进程内的，flow_orchestrator.py 是独立 Python 进程，
不能直接调用。本模块提供等价的 append-only 打点，schema 与 index.mjs 的 trace 兼容。

事件类型（供 goal_verify KR1 判定）：
  task_done          claim→verify→apply 一轮完成
  rule_violation     检测到越界/误改锁外文件
  human_intervention 人类介入
  escalate           升级到人类

schema: {ts, sid, kind, card, phase, verdict, evidence_ref, mode}
  - sid 必须真实（非 s1）——由 --sid 传入，默认 orch-<pid>
  - mode=probe 表示探针数据，不作正式验收（防造假）

用法（被 flow_orchestrator 调用）:
  from task_trace import emit
  emit('task_done', card='A2', phase='apply', verdict='ok', sid=...)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

TRACE = Path('D:/Brain/workspace/bench/_trace.jsonl')
VALID_KINDS = {'task_done', 'rule_violation', 'human_intervention', 'escalate'}


def emit(kind, card='', phase='', verdict='', evidence_ref='', sid=None, mode='live'):
    """append-only 打点，返回是否成功（失败不抛异常，避免打断主流程）"""
    if kind not in VALID_KINDS:
        return False
    sid = sid or os.environ.get('ORCH_SID') or f'orch-{os.getpid()}'
    if sid == 's1':
        return False  # 绝不写进被排除的假数据 sid
    rec = {'ts': datetime.now(timezone.utc).isoformat(),
           'sid': str(sid), 'kind': kind, 'card': card, 'phase': phase,
           'verdict': verdict, 'evidence_ref': evidence_ref, 'mode': mode}
    try:
        TRACE.parent.mkdir(parents=True, exist_ok=True)
        with TRACE.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        return True
    except OSError:
        return False


if __name__ == '__main__':
    # 自测：显式 probe 模式，绝不混入 live
    ok = emit('task_done', card='SELFTEST', phase='apply', verdict='ok', mode='probe')
    print(f'SELFTEST emit={"OK" if ok else "FAIL"} (mode=probe, 不作验收)')
    sys.exit(0 if ok else 1)
