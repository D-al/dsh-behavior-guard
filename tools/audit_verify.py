#!/usr/bin/env python3
"""判据合理性审计（2026-11-21）。

不跑判据看结果，而是分析判据**本身**能否证伪"卡没做"：
- 强判据：test_pass / gate_result / trace_count / trace_absent / json_field
  —— 验的是行为、事件、状态；实现被删 → 判据会 FAIL
- 弱判据：file_exists / file_grep
  —— 验的是"文件在/文本有"；常见于"写了文档就算完成"的假绿
- 无判据：manual 或空 —— 需人工，不算绿

输出：每张卡的判据强度画像 + 假绿风险卡列表。
用法: python tools/audit_verify.py [--strict]
"""
import os
import re
import sys
from pathlib import Path

# run_all.sh 优先用 PATH 的 python3（本环境无 PyYAML）；自检并 re-exec 到带 yaml 的解释器。
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    alt = Path('D:/Python/python.exe')
    if alt.exists() and Path(sys.executable).resolve() != alt.resolve():
        os.execv(str(alt), [str(alt), str(Path(__file__).resolve())] + sys.argv[1:])
    raise

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / 'ROADMAP_GRAPH.md'

STRONG = {'test_pass', 'gate_result', 'trace_count', 'trace_absent', 'json_field'}
WEAK = {'file_exists', 'file_grep'}

def load():
    m = re.search(r'<!-- ROADMAP_GRAPH_BEGIN v1 -->\s*(.*?)\s*<!-- ROADMAP_GRAPH_END -->',
                  GRAPH.read_text(encoding='utf-8'), re.S)
    return yaml.safe_load(m.group(1))

def main():
    strict = '--strict' in sys.argv
    data = load()
    weak_only = []
    rows = []
    for i in data['items'] + data['rungs']:
        vs = i.get('verify') or []
        kinds = [v.get('kind') for v in vs]
        strong = [v for v in kinds if v in STRONG]
        weak = [v for v in kinds if v in WEAK]
        manual = [v for v in kinds if v == 'manual']
        # verify_type=document：交付物就是文档/决策记录，file_exists 是合理判据（非假绿）
        doc_type = i.get('verify_type') == 'document'
        if not vs:
            grade = 'NONE'
        elif strong:
            grade = 'OK' if not weak else 'MIXED'
        elif weak:
            # structural：判据虽是 grep，但查的是具体函数定义/具体字段（非泛关键词），
            # 且卡尚未完成（待办卡的判据是"完成时的标准"）——不算已完成卡的假绿。
            structural = i.get('verify_type') == 'structural' and i.get('status') != 'done'
            grade = 'DOCUMENT' if doc_type else ('STRUCTURAL' if structural else 'WEAK_ONLY')
        else:
            grade = 'MANUAL'
        if grade == 'WEAK_ONLY':
            weak_only.append(i['id'])
        rows.append((i['id'], i.get('status', '?'), grade, len(strong), len(weak), len(manual)))

    print(f'{"卡":14} {"状态":16} {"等级":10} 强 弱 人工')
    for cid, st, grade, s, w, m in rows:
        flag = '⚠️' if grade == 'WEAK_ONLY' else '  '
        print(f'{flag} {cid:12} {st:15} {grade:10} {s}  {w}  {m}')

    print(f'\n=== 汇总 ===')
    from collections import Counter
    c = Counter(r[2] for r in rows)
    print('等级分布:', dict(c))
    print('纯弱判据(假绿高风险) %d 张: %s' % (len(weak_only), ', '.join(weak_only)))

    # strict: 有"非manual且WEAK_ONLY"就非零退出（done卡的假绿最危险）
    done_weak = [r[0] for r in rows if r[2] == 'WEAK_ONLY' and r[1] == 'done']
    print('已完成但判据纯弱(最高风险):', ', '.join(done_weak) or '无')
    if strict and (weak_only or done_weak):
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
