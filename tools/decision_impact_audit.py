"""反仪式检查：这份决策记录上次改变了什么决定？

用户 2026-11-21 结论："方法论的判断标准只有一条——这份记录上一次改变了一个决定吗？"
本脚本把这句话变成可运行的检查，回答：
  1. ADR 的验证段是否写了可核对的条件（不是空话）
  2. 验证条件是否真的被后续证据触发过（决策是否产生过实际影响）
  3. 有没有"写了但从未改变任何事"的记录（=仪式化候选）

用法：
  python tools/decision_impact_audit.py            # 人读报告
  python tools/decision_impact_audit.py --json     # 机器可读
  python tools/decision_impact_audit.py --strict   # 仪式化条目 > 阈值则非零退出
"""
import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = ROOT / 'decisions'
LINEAGE = ROOT / 'lineage'

# 可核对的验证条件特征：有数字/阈值/命令/明确信号，而非"持续关注"这类空话
CONCRETE = re.compile(
    r'(\d+|A/B|run_all|citation_guard|trace|验证|测试|\bcmp\b|diff|PASS|FAIL|WARN|'
    r'推翻|撤销|降级|回滚|门控|则|when|if)', re.I)
VAGUE = re.compile(r'^(持续关注|后续再看|观察|视情况|待定|暂无|—|-)\s*$')


def collect_adrs():
    out = []
    for p in sorted(ADR_DIR.glob('*.md')):
        if p.name.startswith('_'):
            continue
        txt = p.read_text(encoding='utf-8')
        m = re.search(r'^#\s+(ADR-\d+[：:].+)$', txt, re.M)
        if not m:
            continue
        # 验证段：Consequences 里的"验证"行，或出现 verify/验收关键词的段落
        ver_lines = []
        for line in txt.split('\n'):
            if re.search(r'验证[：:]|verify[：:]|怎么知道|如何确认|判据[：:]', line, re.I):
                ver_lines.append(line.strip())
        # Evidence 段：新格式（2026-11-20 起）必须有勾选；老格式无此字段算历史欠账，不算当前仪式化
        has_evidence_section = '## Evidence' in txt
        ev_filled = has_evidence_section and len(re.findall(r'^- \[x\]', txt, re.M)) > 0
        ev_legacy = not has_evidence_section
        # 状态
        st = re.search(r'^-\s*状态[：:]\s*(.+)$', txt, re.M)
        status = st.group(1).strip() if st else 'unknown'
        out.append({
            'file': p.name,
            'title': m.group(1).strip(),
            'status': status,
            'verification_lines': ver_lines,
            'verification_concrete': any(CONCRETE.search(v) and not VAGUE.match(v) for v in ver_lines),
            'evidence_checked': ev_filled,
            'evidence_legacy': ev_legacy,
        })
    return out


def check_lineage_changes(adrs):
    """检查 lineage 里有没有记录某 ADR 被后续决策改变过（supersede/降级/修正）"""
    corpus = ''
    for p in LINEAGE.glob('*.md'):
        corpus += p.read_text(encoding='utf-8') + '\n'
    changed = {}
    for a in adrs:
        num = re.search(r'ADR-(\d+)', a['title'])
        if not num:
            continue
        n = num.group(1)
        # 在该 ADR 之外的文档里被提到 + 带改变类动词
        changed[a['file']] = bool(re.search(
            rf'ADR-0?{n}[^\n]{{0,120}}(降级|撤销|修正|更正|作废|supersed|推翻|改挂|替换)',
            corpus, re.I))
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--threshold', type=float, default=0.5,
                    help='仪式化比例阈值，超过则 strict 模式失败')
    a = ap.parse_args()

    adrs = collect_adrs()
    changed = check_lineage_changes(adrs)
    rows = []
    for x in adrs:
        flags = []
        if not x['verification_lines']:
            flags.append('无验证段')
        elif not x['verification_concrete']:
            flags.append('验证条件空泛')
        if x['evidence_legacy']:
            flags.append('Evidence段缺失(老格式历史欠账)')
        elif not x['evidence_checked']:
            flags.append('Evidence未勾选(新格式未填)')
        # "changed" 不是硬性要求（很多决策确实一直成立），只作提示
        impact = '改变过' if changed.get(x['file']) else '未见改变记录'
        rows.append({**x, 'flags': flags, 'impact': impact})

    ritual = [r for r in rows if r['flags']]
    rate = len(ritual) / max(1, len(rows))

    if a.json:
        print(json.dumps({'total': len(rows), 'ritual_candidates': ritual,
                          'ritual_rate': round(rate, 3)}, ensure_ascii=False, indent=2))
    else:
        print(f'决策影响审计：{len(rows)} 个 ADR，仪式化候选 {len(ritual)} 个（{rate:.0%}）')
        print('-' * 70)
        for r in ritual:
            print(f'  {r["file"]:42s} {", ".join(r["flags"])}  [{r["impact"]}]')
        print('-' * 70)
        print('注意：无验证段/空泛验证 = 无法判断决策是否生效，是仪式化信号；')
        print('      "未见改变记录" 不等于错——一直成立的决策不需要被改变。')

    if a.strict and rate > a.threshold:
        print(f'\n仪式化比例 {rate:.0%} 超过阈值 {a.threshold:.0%}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
