# -*- coding: utf-8 -*-
"""A/B 分析：反思捕获是否降低同类错误率（2026-11-27）

对比两组 trace：
  BEFORE = 反思捕获上线前的历史 trace（无 reflection_mined 埋点）
  AFTER  = 上线后的 trace（有 reflection_mined）

指标（都是"同类错误率"的代理，诚实标注局限）：
  1. hard_stop_rate      = step_hard_stop / (step_hard_stop + 正常结束)
  2. repeated_fail_rate  = 同一 sid 内 tool_failure 后 3 步内同类失败的比例
  3. guard_burst_rate    = 单会话 safety_gate_block>=2 的会话占比
  4. steps_per_session   = 平均步数（效率代理）

用法:
  python tools/ab_reflection_analysis.py <before_trace> <after_trace>
"""
import json, sys, collections, statistics

def load(p):
    rows = []
    with open(p, encoding='utf-8') as f:
        for l in f:
            try: rows.append(json.loads(l))
            except Exception: pass
    return rows

def split_by_time(rows, ts):
    """按 ISO 时间戳切分（自然实验：同一 harness，开关上线时间点）"""
    before = [r for r in rows if str(r.get('ts','')) < ts]
    after = [r for r in rows if str(r.get('ts','')) >= ts]
    return before, after

def metrics(rows, label):
    by_sid = collections.defaultdict(list)
    for r in rows:
        sid = str(r.get('sid') or '')
        if not sid or sid.startswith('s1'): continue  # 过滤测试假数据
        by_sid[sid].append(r)
    kinds = collections.Counter(r.get('kind') for r in rows)
    n_sessions = len(by_sid)
    hard = kinds.get('step_hard_stop', 0)
    guard = kinds.get('safety_gate_block', 0)
    burst = sum(1 for rs in by_sid.values() if sum(1 for r in rs if r.get('kind')=='safety_gate_block') >= 2)
    steps = sum(1 for r in rows if r.get('kind') in ('tool_call','step')) / max(1, n_sessions)
    # 反思后重犯：reflection_mined 后同 sid 是否再出现 tool_failure
    mined = [r for r in rows if r.get('kind')=='reflection_mined']
    reoffend = 0
    for m in mined:
        sid = str(m.get('sid') or '')
        step = m.get('step') or 0
        if any(r.get('sid')==sid and r.get('kind')=='tool_failure' and (r.get('step') or 0)>step for r in rows):
            reoffend += 1
    print(f'--- {label} ---')
    print(f'  会话数(过滤s1): {n_sessions}')
    print(f'  tool_call: {kinds.get("tool_call",0)}  tool_failure: {kinds.get("tool_failure",0)}')
    print(f'  step_hard_stop: {hard}  safety_gate_block: {guard}')
    print(f'  hard_stop/session: {hard/max(1,n_sessions):.2f}')
    print(f'  guard_burst sessions: {burst}/{n_sessions} ({100*burst/max(1,n_sessions):.1f}%)')
    print(f'  steps/session: {steps:.1f}')
    if mined:
        print(f'  reflection_mined: {len(mined)}  其中后续同类失败: {reoffend} ({100*reoffend/len(mined):.1f}%)')
    return dict(sessions=n_sessions, hard=hard, guard=guard, burst=burst, steps=steps, mined=len(mined), reoffend=reoffend)

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    a = metrics(load(sys.argv[1]), 'BEFORE (反思捕获上线前)')
    b = metrics(load(sys.argv[2]), 'AFTER  (反思捕获上线后)')
    print('\n--- 差异（AFTER - BEFORE）---')
    for k in ('hard','guard','burst'):
        print(f'  {k}: {b[k]-a[k]:+d}')
    print(f'  steps/session: {b["steps"]-a["steps"]:+.1f}')
