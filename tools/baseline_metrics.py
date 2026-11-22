#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""STRATEGY 六项能力指标的科学基线测量（GQM + 构念效度框架）

依据：docs/SCIENTIFIC_MEASUREMENT_20261122.md
  - GQM（Basili 1984）：每个指标必须可向上追溯到 STRATEGY 目标
  - 构念效度（Cronbach & Meehl 1955）：代理指标不等于构念本身
  - Wilson 置信区间（小样本比例，优于 Wald）
  - 样本量 n ≥ 2(zσ/δ)²；RCI = 1.96·SEM·√2
  - Simpson 悖论防范：按会话类型分层报告（probe/task/synthetic）

核心诚实原则（不可违背）：
  ★ 不把"测不了"伪装成"测出来很低"
  ★ 不把"代理指标"伪装成"目标构念本身"
  ★ 单点数值必须带置信区间和样本量警告
  ★ 每个指标标注 MEASURABLE / PROXY_ONLY / NOT_INSTRUMENTED

用法:
  D:/Python/python.exe -B tools/baseline_metrics.py [--json] [--full]
输出: 控制台报告 + D:/Brain/workspace/bench/_baseline_metrics.jsonl
"""
import argparse
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACE = Path('D:/Brain/workspace/bench/_trace.jsonl')
LEDGER = Path('D:/Brain/workspace/bench/_compaction_ledger.jsonl')
OUT = Path('D:/Brain/workspace/bench/_baseline_metrics.jsonl')
STRATEGY = ROOT / 'STRATEGY.md'

# 会话分层（Simpson 悖论防范）
SYNTHETIC_SIDS = {'s1'}                    # 单测假数据
PROBE_PREFIXES = ('budget-', 'probe-')      # 推卡/预算探针
TASK_SIDS = None                           # 其余为真实任务会话（动态判定）

# 构念→操作化定义（GQM 的 Question→Metric 层）
METRICS = {
    'G1 同一性连续性': {
        'target': '跨会话目标/决策/约束可追溯率 ≥95%',
        'construct': '跨会话可追溯性（声称 vs 行为需区分）',
        'operational': 'task 会话中 evidence_cited 事件数 / (task会话数 × 每会话期望引用数)',
        'status': 'PROXY_ONLY',
        'validity': '代理指标：evidence_cited 只是"引用了证据"的信号，'
                    '不等于"目标/决策/约束可追溯"。构念效度未验证（需人工抽样对齐）',
        'anti_gaming': '需隐藏集 + 与奖惩脱钩；不能让 agent 知道被计数的具体事件',
    },
    'G2 连续性执行': {
        'target': '长任务不因上下文丢失重做率下降',
        'construct': '上下文丢失后的重复探测率',
        'operational': 'compaction 后的重复 tool_call 数 / compaction 总数',
        'status': 'NOT_INSTRUMENTED',
        'validity': 'trace 中 compaction 事件 = 0，无法计算；'
                    '不是"指标为0"，是"没有埋点"',
        'anti_gaming': '需固定任务集 + 随机顺序 + ≥8 次独立运行',
    },
    'G3 目标自生成': {
        'target': '未定义区域能提出候选目标，经35B裁决采纳后推进 ≥20%',
        'construct': '自主目标生成与采纳率（排除复述）',
        'operational': 'accepted goal_proposal 数 / 无指令 episode 数',
        'status': 'NOT_INSTRUMENTED',
        'validity': 'trace 中 goal_proposal = 0；当前全外部输入，无埋点',
        'anti_gaming': '必须排除复述用户指令；需盲审区分"自主提出"与"复述"',
    },
    'G4 价值校准': {
        'target': 'CritBank 注入后相似任务重复失败率下降 ≥30%',
        'construct': '价值校准带来的失败率改善（因果）',
        'operational': '(对照失败率 - 注入失败率) / 对照失败率',
        'status': 'PROXY_ONLY',
        'validity': 'crit_hit 只是"命中了 CritBank"，不等于"失败率下降"；'
                    '需有 hold-out 对照实验才能测因果',
        'anti_gaming': '双盲 + 配对对照 + 隐藏 hold-out 集',
    },
    'G5 经验进化': {
        'target': 'critique 编译成 delta 规则，回归测试通过率 100%',
        'construct': '经验→规则→回归通过的完整链条',
        'operational': '通过的 delta 规则回归数 / 生成的 delta 规则数',
        'status': 'NOT_INSTRUMENTED',
        'validity': 'trace 中 delta_rule = 0；无产物、无埋点',
        'anti_gaming': '隐藏分布外集 pass@k / pass^k，不用自报通过率',
    },
    'G6 开放环境适应': {
        'target': '遇到新失败模式时能生成新门控/规则并验证',
        'construct': '对新失败模式的适应与验证能力',
        'operational': '验证通过的新门控数 / 生成的新门控数',
        'status': 'PROXY_ONLY',
        'validity': 'git log 有"加门控"记录，但无法区分"应对新失败"还是"预防性添加"；'
                    '需绑定触发事故 ID',
        'anti_gaming': '每个新门控必须绑定一个已观测事故 ID（否则是剧场）',
    },
}


def wilson_ci(k, n, z=1.96):
    """小样本比例的 Wilson 置信区间（优于 Wald，k=0 时仍有效）"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return (max(0.0, center-half), min(1.0, center+half))


def load_events():
    sessions = defaultdict(lambda: defaultdict(int))
    if not TRACE.exists():
        return sessions
    for line in TRACE.open(encoding='utf-8', errors='replace'):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = str(r.get('sid', '?'))
        sessions[sid][r.get('kind', '?')] += 1
    return sessions


def classify_session(sid):
    if sid in SYNTHETIC_SIDS:
        return 'synthetic'
    if sid.startswith(PROBE_PREFIXES):
        return 'probe'
    return 'task'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--full', action='store_true')
    args = ap.parse_args()

    sessions = load_events()
    layers = defaultdict(lambda: defaultdict(int))
    for sid, kinds in sessions.items():
        layer = classify_session(sid)
        for k, v in kinds.items():
            if k in ('evidence_cited', 'compaction', 'crit_hit', 'control_turn',
                     'review_verdict', 'goal_proposal', 'delta_rule', 'gate_created',
                     'mind_state', 'tool_call'):
                layers[layer][k] += v
        layers[layer]['sessions'] += 1

    task_n = layers['task']['sessions']
    results = {}
    for name, m in METRICS.items():
        r = dict(m)
        r['layer'] = 'task'  # 只在 task 层算（Simpson 防范）
        # 操作化计数
        if name.startswith('G1'):
            k = layers['task']['evidence_cited']
            r['raw'] = {'count': k, 'sessions': task_n}
            lo, hi = wilson_ci(k, max(task_n, 1))
            r['ci95_per_session'] = [round(lo, 3), round(hi, 3)]
        elif name.startswith('G4'):
            k = layers['task']['crit_hit']
            r['raw'] = {'count': k, 'sessions': task_n}
            lo, hi = wilson_ci(k, max(task_n, 1))
            r['ci95_per_session'] = [round(lo, 3), round(hi, 3)]
        else:
            key = {'G2':'compaction','G3':'goal_proposal','G5':'delta_rule','G6':'gate_created'}[name[:2]]
            r['raw'] = {'count': layers['task'][key], 'sessions': task_n}
        # 样本量充足性（σ=10%, δ=10% → n≈16; 现 task_n）
        r['sample_sufficient_for_10pct_effect'] = task_n >= 16
        r['min_detectable_effect'] = round(1.96*0.10*math.sqrt(2/max(task_n,1))*100, 1)
        results[name] = r

    report = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'principle': '不把测不了伪装成测出来很低；不把代理指标伪装成目标构念',
        'layers': {k: dict(v) for k, v in layers.items()},
        'task_sessions': task_n,
        'metrics': results,
        'scientific_checklist': {
            'GQM追溯': True, '操作化定义': True, '分层报告': True,
            '置信区间': '部分(PROXY_ONLY)', '噪声估计': 'σ=10%沿用项目基线,未重测',
            '样本量充足': task_n >= 16, '构念效度': '未验证(PROXY_ONLY需人工对齐)',
            '对照组': False, '防gaming': '见各项anti_gaming(未实施)',
        },
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('=' * 70)
        print(' 能力指标科学基线 — GQM + 构念效度 + 分层报告')
        print('=' * 70)
        print(f'  会话分层: synthetic={layers["synthetic"]["sessions"]} '
              f'probe={layers["probe"]["sessions"]} task={task_n}')
        print(f'  ★ 能力指标只在 task 层计算（Simpson 悖论防范）')
        print(f'  样本量: {task_n} < 16 → 只能检测 >{report["metrics"]["G1 同一性连续性"]["min_detectable_effect"]}% 的相对变化')
        print()
        for name, r in results.items():
            tag = {'MEASURABLE':'可测','PROXY_ONLY':'代理','NOT_INSTRUMENTED':'未埋点'}[r['status']]
            print(f'  [{tag}] {name}')
            print(f'      目标: {r["target"][:56]}')
            print(f'      实测: {r["raw"]}')
            if 'ci95_per_session' in r:
                print(f'      95%CI(每会话): {r["ci95_per_session"]}')
            print(f'      效度: {r["validity"][:70]}...')
            if args.full:
                print(f'      反gaming: {r["anti_gaming"][:70]}')
            print()
        nm = sum(1 for r in results.values() if r['status']=='NOT_INSTRUMENTED')
        pm = sum(1 for r in results.values() if r['status']=='PROXY_ONLY')
        print(f'  结论: 可测0 / 代理{pm} / 未埋点{nm} — 当前不具备科学测基线条件')
        print('  ↳ 优先给 NOT_INSTRUMENTED 的指标埋点，而不是优化代理指标')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'ts': report['ts'], 'task_sessions': task_n,
                            'status': {k:v['status'] for k,v in results.items()}},
                           ensure_ascii=False) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
