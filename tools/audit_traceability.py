#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""目的追溯审计：每个机制必须能追溯到 STRATEGY.md 的某条战略条款

依据：docs/COMPLEXITY_BUDGET_GOAL_ALIGNED_20261122.md
  正确复杂度预算 = 目的追溯制，不是文件数/门禁数上限。
  "每个新增机制必须说明为何值得存在、团队能否长期承担"。

设计原则（避免"标注本身成为新负担"）：
  - **不手写 110 个标注**：核心机制（rulepack 受保护文件）显式标注在
    bench/rulepack/traceability.json；其余用 docstring 关键词启发式推断（标 inferred）。
  - **测试文件继承被测模块的追溯**：test_foo.py 不算独立 orphan。
  - **STRATEGY.md 是锁外文件**：本脚本只读它，绝不改。
  - orphan 不是"必须删"，是"需要人判断"——分类输出 essential 候选/accidental 候选。

用法:
  D:/Python/python.exe -B tools/audit_traceability.py [--json] [--full]
退出码: 0=无高置信 orphan; 1=有 orphan 需人工判断
输出: 控制台摘要 + D:/Brain/workspace/bench/_traceability_audit.jsonl
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / 'bench/rulepack/traceability.json'
OUT = Path('D:/Brain/workspace/bench/_traceability_audit.jsonl')

# 战略条款锚点（对应 STRATEGY.md §2.1/§2.2/§3/§5）
ANCHORS = {
    'G1 同一性连续性': ['continuity', '压缩存档', 'archive', 'checkpoint', 'session', '会话', 'trail', 'trailtext', 'corrector', '叙事', '纠正器'],
    'G2 连续性执行': ['compaction', 'context', '上下文', 'prefill', 'kv cache'],
    'G3 目标自生成': ['goal', '目标', 'propose', '提案', 'planner', 'strategy', 'find_next', 'roi', '选任务', '下一张'],
    'G4 价值校准': ['critbank', 'calibrat', '校准', 'crit'],
    'G5 经验进化': ['delta', 'critic', '规则', 'rule', 'skill', 'learn', '学习', 'fsm', 'agentlab', '压测', '可量化', '失败预测'],
    'G6 开放环境适应': ['guard', '门控', '守卫', 'drift', '漂移', 'adapt', '适应', 'tech_tree', '科技树', 'roadmap', '路线图', 'build_b12244', 'llama-server', '引擎'],
    'R1 自改进OOD': ['rsri', 'holdout', 'ood', 'variance', 'self_harness', '方差'],
    'R2 判据独立性': ['verify', '判据', 'census', 'tautology', '假绿', 'criteria', 'audit', 'test_pass'],
    'R3 CritBank预算': ['注入预算', 'token', 'inject'],
    'R4 工具面': ['tool_surface', 'tool_audit', '工具面'],
    'R5 前缀KV稳定': ['prefix', 'prefill', 'prefix kv'],
    'R6 安全对齐': ['safety', 'asr', 'alignment', '拒绝率'],
    'R7 元治理锁': ['rulepack', 'strategy', '锁外', 'immutable', 'pin', 'version', '版本钉住', 'freeze', 'watchdog', '看门狗', 'restart'],
    'N7 补偿性规则删除': ['退役', 'retire', '删除', 'deprecat', '减法'],
}


def load_explicit():
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding='utf-8')).get('mechanisms', {})
        except Exception:
            return {}
    return {}


def infer_refs(path):
    """从文件名+docstring启发式推断战略条款"""
    try:
        text = path.read_text(encoding='utf-8', errors='replace')[:800]
    except OSError:
        text = ''
    hay = (path.name + ' ' + text).lower()
    return [k for k, kws in ANCHORS.items() if any(w.lower() in hay for w in kws)]


def base_module(path):
    """test_foo.py / test_foo.mjs → foo（继承被测模块的追溯）"""
    m = re.match(r'test_(.+)\.(?:py|mjs)$', path.name)
    return m.group(1) if m else None


def audit():
    explicit = load_explicit()
    tools = sorted(list((ROOT / 'tools').glob('*.py')) + list((ROOT / 'tools').glob('*.mjs')))
    # 先算所有非测试文件的 refs，供测试文件继承
    refs_by_name = {}
    for p in tools:
        rel = p.relative_to(ROOT).as_posix()
        refs_by_name[p.stem] = explicit.get(rel, {}).get('strategy_ref') or infer_refs(p)

    rows, orphans = [], []
    for p in tools:
        rel = p.relative_to(ROOT).as_posix()
        exp = explicit.get(rel, {})
        refs = exp.get('strategy_ref') or []
        source = 'explicit'
        if not refs:
            base = base_module(p)
            if base and refs_by_name.get(base):
                refs = refs_by_name[base]
                source = 'inherited'
            else:
                refs = infer_refs(p)
                source = 'inferred'
        row = {'file': rel, 'refs': refs if isinstance(refs, list) else [refs], 'source': source}
        rows.append(row)
        if not row['refs']:
            orphans.append(row)
    return {'total': len(rows), 'explicit': sum(1 for r in rows if r['source'] == 'explicit'),
            'inherited': sum(1 for r in rows if r['source'] == 'inherited'),
            'inferred': sum(1 for r in rows if r['source'] == 'inferred'),
            'orphans': orphans, 'rows': rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--full', action='store_true')
    args = ap.parse_args()

    r = audit()
    r['ts'] = datetime.now(timezone.utc).isoformat()
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print('=' * 66)
        print(' 目的追溯审计 — 机制 → STRATEGY.md 条款')
        print('=' * 66)
        print(f'  机制总数 {r["total"]} | 显式 {r["explicit"]} | 继承 {r["inherited"]} | 推断 {r["inferred"]}')
        print(f'  ★ orphan（无追溯）: {len(r["orphans"])}')
        if r['orphans']:
            print('  【需人工判断：删 or 补标注】')
            for o in r['orphans']:
                print(f'    {o["file"]}')
            print('  ↳ 判据：删掉它，哪个战略目标无法达成？答不出=accidental候选删')
        else:
            print('  PASS  所有机制均可追溯到战略条款')
        if args.full:
            print('  【全部机制】')
            for row in r['rows']:
                print(f'    [{row["source"]:9}] {row["file"]:40} {",".join(row["refs"])[:50]}')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('a', encoding='utf-8') as f:
        f.write(json.dumps({'ts': r['ts'], 'total': r['total'], 'orphan_count': len(r['orphans']),
                            'orphans': [o['file'] for o in r['orphans']]}, ensure_ascii=False) + '\n')
    return 1 if r['orphans'] else 0


if __name__ == '__main__':
    sys.exit(main())
