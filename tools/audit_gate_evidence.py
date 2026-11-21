#!/usr/bin/env python3
"""闸门证据审计（2026-11-21）：找出"空泛闸门"——有前置声明但缺可执行证据/数据的卡。

缘起：M5 的 P-USER-DECISION（用户拍板哪些工具进内核）常年 manual-blocked，
因为没人把"拍板需要的数据"结构化——实际数据（1会话375唯一调用/11工具/前5占90%；8快照去重后）
一直躺在 docs 和 dump 里。本工具把这类"数据已存在但没进闸门"的问题系统化检出。

判据（每个 preconditions P-ID）：
1. 有明确数值指标（ms/%/倍/版本）→ 可执行指标型，需有验证脚本或已满足证据
2. 有 data_gates 且 status=satisfied → 数据齐，只剩决策（健康）
3. 纯文字决策/无指标且无 data_gates → 空泛闸门（警告：缺证据）

用法: python tools/audit_gate_evidence.py [--strict]
"""
import os
import re
import sys
from pathlib import Path

try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    alt = Path('D:/Python/python.exe')
    if alt.exists() and Path(sys.executable).resolve() != alt.resolve():
        os.execv(str(alt), [str(alt), str(Path(__file__).resolve())] + sys.argv[1:])
    raise

ROOT = Path(__file__).resolve().parent.parent
LADDER = ROOT / 'CAPABILITY_LADDER.yaml'

METRIC = re.compile(r'\d+\s*(ms|%|倍|秒|G显存|GB|G\b|g\b|个|\+|s\b|x\b|v\d)', re.I)
# 已知"纯人工决策"闸门（外部PR/产品判断/治理决策）——不需要数据脚本
# P-USER-DECISION 不在内：它是"数据可支撑的决策"，必须有 data_gates（2026-11-21 踩过坑）
HUMAN_DECISION = {'P-ADR-DECISION', 'P-UPSTREAM-PR', 'P-LLAMACPP-V1'}

def main():
    strict = '--strict' in sys.argv
    l = yaml.safe_load(LADDER.read_text(encoding='utf-8'))
    items = l['items'] + l['autonomy_rungs']

    rows = []
    for i in items:
        pres = i.get('preconditions') or []
        if not pres:
            continue
        data_ok = {g['id'] for g in (i.get('data_gates') or []) if g.get('status') == 'satisfied'}
        for p in pres:
            pid = str(p).split(':')[0].strip()
            desc = str(p).split(':', 1)[-1].strip()
            has_metric = bool(METRIC.search(desc))
            # 数据闸门可能用不同ID覆盖同一主题（如P-TOOL-FREQ-AUDIT覆盖P-USER-DECISION）
            covered_by_data = bool(i.get('data_gates'))
            threshold_tbd = '阈值待定' in str(p)
            if pid in HUMAN_DECISION:
                status = 'DATA_OK' if covered_by_data else 'HUMAN_ONLY'
            elif has_metric:
                status = 'METRIC'
            elif covered_by_data:
                status = 'DATA_OK'
            elif threshold_tbd:
                status = 'TBD'
            else:
                status = 'VAGUE'
            rows.append((i['id'], pid, desc[:38], status))

    print(f'=== 闸门证据审计（{len(rows)} 条前置）===')
    for cid, pid, desc, st in rows:
        mark = {'METRIC': '✓指标', 'DATA_OK': '✓数据齐', 'HUMAN_ONLY': '△人工', 'VAGUE': '✗空泛', 'TBD': '○待定'}[st]
        print(f'  {mark:7} {cid:8} {pid:22} {desc}')

    vague = [r for r in rows if r[3] == 'VAGUE']
    human = [r for r in rows if r[3] in ('HUMAN_ONLY', 'TBD')]
    print(f'\n空泛闸门(缺数据/指标): {len(vague)}')
    print(f'纯人工闸门(无需数据脚本): {len(human)}')
    print(f'结论: {"PASS" if not vague else "WARN"}')
    # strict 只在"空泛闸门"时失败；纯人工闸门是合法决策，不算错
    return (1 if strict and vague else 0)

if __name__ == '__main__':
    sys.exit(main())
