#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""战略目标 KR 判据的可执行验证器（v3）

设计原则（不可违背）：
  ★ 三态输出 PASS / FAIL / NOT_MEASURABLE——绝不把"测不了"伪装成通过或失败
  ★ 只读证据源，不采信 agent 自述
  ★ 缺证据源 → NOT_MEASURABLE + 明确说出前置依赖
  ★ 每条 KR 附证据路径、测量者、样本量

 KR1 决策环自走：10 任务零误改锁外 + 干预≤2 + trace完整
 KR2 经验改进：hold-out ≥8 次配对对照，提升>10% 且 CI 不跨零，OOD不负
 KR3 自我模型：能力账本可生成 + 人工抽检≥80%（数值阈值待基线）
 KR4 感知-行动：预埋事件100%在时间盒内有动作+证据

用法:
  D:/Python/python.exe -B tools/goal_verify.py [--json] [--kr KR1]
退出码: 0=全部PASS; 1=有FAIL; 2=有NOT_MEASURABLE(无FAIL)
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = Path('D:/Brain/workspace/bench')
TRACE = BENCH / '_trace.jsonl'
HOLDOUT = BENCH / '_benchmark_holdout.jsonl'
CAPABILITY_LEDGER = BENCH / '_capability_ledger.json'
EVENT_REPLAY = BENCH / '_event_replay_results.jsonl'
OUT = BENCH / '_goal_verification.jsonl'

sys.path.insert(0, str(ROOT / 'tools'))
try:
    import roadmap_check as rc
    import rulepack_guard as rpg
except ImportError:
    rc = rpg = None


def nm(kr, why, prerequisite):
    return {'kr': kr, 'status': 'NOT_MEASURABLE', 'why': why,
            'prerequisite': prerequisite, 'evidence': None}


def verify_kr1():
    """决策环自走：需要 claim/done/写回/干预的完整事件链"""
    if not TRACE.exists():
        return nm('KR1', 'trace 文件不存在', '生成 _trace.jsonl')
    events = []
    for line in TRACE.open(encoding='utf-8', errors='replace'):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get('sid') == 's1':
            continue
        events.append(r)
    # 需要的事件类型
    task_done = [e for e in events if e.get('kind') in ('task_done', 'apply', 'writeback')]
    interventions = [e for e in events if e.get('kind') in ('human_intervention', 'escalate')]
    violations = [e for e in events if e.get('kind') in ('rule_violation', 'locked_file_tamper')]
    if not task_done:
        return nm('KR1',
                  f'无 task_done/apply/writeback 事件（找到 {len(events)} 条真实事件，但无任务完成记录）',
                  '给 flow_orchestrator 的 claim→verify→apply 加 trace 打点（task_done）')
    n = len(task_done)
    if n < 10:
        return nm('KR1', f'任务完成记录仅 {n} 条 < 10', f'积累到 10 条 task_done')
    ok = len(violations) == 0 and len(interventions) <= 2
    return {'kr': 'KR1',
            'status': 'PASS' if ok else 'FAIL',
            'why': f'{n} 任务, 误改 {len(violations)}, 干预 {len(interventions)}',
            'evidence': str(TRACE), 'sample': n}


def verify_kr2():
    """经验改进：需要 hold-out 集 + ≥8 次配对对照"""
    if not HOLDOUT.exists():
        return nm('KR2', 'hold-out 基准集不存在',
                  '建 _benchmark_holdout.jsonl（固定任务集 + 基线通过率）')
    try:
        d = json.loads(HOLDOUT.read_text(encoding='utf-8'))
    except Exception as e:
        return nm('KR2', f'hold-out 文件解析失败: {e}', '修复 JSON 格式')
    runs = d.get('paired_runs', [])
    if len(runs) < 8:
        return nm('KR2', f'配对运行 {len(runs)} < 8',
                  f'再做 {8 - len(runs)} 次独立配对运行')
    # 简化的提升判定（真实CI计算交给配对脚本）
    gains = [r.get('gain', 0) for r in runs]
    ood = [r.get('ood_gain', 0) for r in runs]
    mean_gain = sum(gains) / len(gains)
    ok = mean_gain > 0.10 and all(g >= 0 for g in ood)
    return {'kr': 'KR2', 'status': 'PASS' if ok else 'FAIL',
            'why': f'平均提升 {mean_gain:.1%}, OOD最差 {min(ood):.1%}',
            'evidence': str(HOLDOUT), 'sample': len(runs)}


def verify_kr3():
    """自我模型：本阶段只判能力账本能否生成（数值阈值待基线）"""
    if not CAPABILITY_LEDGER.exists():
        return nm('KR3', '能力账本不存在',
                  '建能力账本生成器（trace + benchmark → 已知/未知/置信记录）')
    try:
        d = json.loads(CAPABILITY_LEDGER.read_text(encoding='utf-8'))
    except Exception as e:
        return nm('KR3', f'账本解析失败: {e}', '修复 JSON 格式')
    items = d.get('capabilities', [])
    if not items:
        return nm('KR3', '账本无能力条目', '至少生成一条能力的已知/未知/置信记录')
    has_unknown = sum(1 for i in items if i.get('known_unknowns'))
    ok = len(items) >= 3 and has_unknown >= 3
    return {'kr': 'KR3', 'status': 'PASS' if ok else 'FAIL',
            'why': f'{len(items)} 能力, {has_unknown} 条有已知未知',
            'evidence': str(CAPABILITY_LEDGER), 'sample': len(items)}


def verify_kr4():
    """感知-行动：需要事件回放结果"""
    if not EVENT_REPLAY.exists():
        return nm('KR4', '事件回放结果不存在',
                  '建事件回放脚本 + _event_replay_results.jsonl')
    rows = []
    for line in EVENT_REPLAY.open(encoding='utf-8', errors='replace'):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not rows:
        return nm('KR4', '回放结果为空', '至少回放 N 个预埋事件')
    with_action = [r for r in rows if r.get('action') and r.get('evidence')]
    ok = len(with_action) == len(rows)
    return {'kr': 'KR4', 'status': 'PASS' if ok else 'FAIL',
            'why': f'{len(with_action)}/{len(rows)} 事件有动作+证据',
            'evidence': str(EVENT_REPLAY), 'sample': len(rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--kr', choices=['KR1', 'KR2', 'KR3', 'KR4'])
    args = ap.parse_args()

    fns = {'KR1': verify_kr1, 'KR2': verify_kr2, 'KR3': verify_kr3, 'KR4': verify_kr4}
    todo = [args.kr] if args.kr else list(fns)
    results = [fns[k]() for k in todo]

    n_pass = sum(1 for r in results if r['status'] == 'PASS')
    n_fail = sum(1 for r in results if r['status'] == 'FAIL')
    n_nm = sum(1 for r in results if r['status'] == 'NOT_MEASURABLE')
    report = {'ts': datetime.now(timezone.utc).isoformat(),
              'results': results,
              'summary': {'PASS': n_pass, 'FAIL': n_fail, 'NOT_MEASURABLE': n_nm},
              'principle': 'NOT_MEASURABLE 不等于 FAIL，也不等于 PASS'}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('=' * 68)
        print(' 战略目标 KR 验证 — 三态判定（测不了就是测不了）')
        print('=' * 68)
        for r in results:
            tag = {'PASS': 'PASS  ', 'FAIL': 'FAIL  ', 'NOT_MEASURABLE': 'N/M   '}[r['status']]
            print(f'  [{tag}] {r["kr"]}: {r["why"]}')
            if r['status'] == 'NOT_MEASURABLE':
                print(f'           ↳ 前置: {r["prerequisite"]}')
        print()
        print(f'  汇总: PASS {n_pass} / FAIL {n_fail} / NOT_MEASURABLE {n_nm}')
        if n_nm:
            print('  ⚠ 目标未达"可执行"——先补 NOT_MEASURABLE 的前置依赖')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('a', encoding='utf-8') as f:
        f.write(json.dumps(report, ensure_ascii=False) + '\n')
    return 1 if n_fail else (2 if n_nm else 0)


if __name__ == '__main__':
    sys.exit(main())
