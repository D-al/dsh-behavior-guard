#!/usr/bin/env python3
"""citation_guard.py — 引用-决策对应守卫（零 LLM）

强制规则（用户 2026-11-20 架构级要求）：
  存量决策与引用必须对应；未来决策也必须与引用依据严格对应。

判定：
  1. 决策文档（decisions/0014-*、README §8 等）里出现的外部引用 ID
     必须在 config/citation_ledger.json 有条目
  2. 条目 status 决定判定：
     verified/n-a  → PASS
     partial       → WARN（必须注明"仅背景"）
     hallucinated/missing/pending → FAIL（禁止作为决策依据）
  3. 台账里 decision_uses 非空的条目，status 必须 verified 或 n-a

退出码：0=全通过（WARN 除非 --strict）；1=有 FAIL；2=守卫自身错误

用法：
  python tools/citation_guard.py
  python tools/citation_guard.py --strict
  python tools/citation_guard.py --json
  python tools/citation_guard.py --quiet
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / 'config' / 'citation_ledger.json'
ARXIV = re.compile(r'(\d{4}\.\d{4,5})')
BAD = {'hallucinated', 'missing', 'pending'}
OK = {'verified', 'n/a'}


def load_ledger():
    d = json.loads(LEDGER.read_text(encoding='utf-8'))
    return {e['id']: e for e in d.get('entries', [])}


def decision_files():
    out = []
    adr = ROOT / 'decisions'
    for f in adr.glob('*.md'):
        if not f.name.startswith('_'):
            out.append(f)
    # ROADMAP 的已证伪章节也是决策性质
    out.append(ROOT / 'ROADMAP.md')
    return out


def check():
    ledger = load_ledger()
    results = []
    # 反向：台账里 decision_uses 非空的条目必须是 verified/n-a
    for cid, e in ledger.items():
        if e.get('decision_uses') and e.get('status') not in OK:
            results.append(('FAIL', cid, f'decision_uses={e["decision_uses"]} but status={e["status"]}'))
    # 正向：决策文档里的 arxiv ID 必须在台账
    # 关键：更正声明（"这是幻觉/已作废"）里的编号不算"引用"，必须排除——
    # 否则 guard 会把"声明某引用有害"误判成"仍在引用它"，这是正则扫内容的经典坑
    RETRACT = re.compile(r'作废|幻觉|已清除|更正|hallucinated|retracted|编造|待核')
    for f in decision_files():
        lines = f.read_text(encoding='utf-8').split('\n')
        for i, line in enumerate(lines):
            if RETRACT.search(line):
                continue  # 整行是更正/作废声明 → 其中的 ID 不是有效引用
            for aid in sorted(set(ARXIV.findall(line))):
                key = f'arxiv:{aid}'
                e = ledger.get(key)
                if not e:
                    results.append(('FAIL', f'{f.name}:{i+1}:{aid}', '引用未登记台账'))
                    continue
                st = e['status']
                if st in BAD:
                    results.append(('FAIL', f'{f.name}:{i+1}:{aid}', f'禁止作为决策依据: {st}'))
                elif st == 'partial':
                    results.append(('WARN', f'{f.name}:{i+1}:{aid}', f'仅背景非唯一依据: {e.get("note", "")[:60]}'))
                elif st == 'listed':
                    # 2026-11-21 方法论自审修复：listed 只过了 L1-L2（存在+标题），
                    # 旧逻辑落进 else 被当 verified 放行 = "打勾文化"漏洞。
                    # 决策引用只核了标题的论文必须 WARN，不能拿绿灯。
                    results.append(('WARN', f'{f.name}:{i+1}:{aid}',
                                    '仅L1-L2核实(存在+标题)，未核结论/数字——不得作决策唯一依据'))
                else:
                    # 反自动化偏见（2026-11-21）：PASS 不能只说 "verified"——
                    # 连续绿灯会让人停止看原始证据，把 PASS 本身当成"已核实"的证据。
                    # 强制随 PASS 显示真实标题+核实日期，保持"看的动作"不消失。
                    real = str(e.get('real_title', ''))[:70]
                    when = e.get('verified_at', '?')
                    results.append(('PASS', f'{f.name}:{i+1}:{aid}',
                                    f'verified@{when} | 真实标题: {real}'))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    try:
        results = check()
    except Exception as e:
        print(f'citation_guard ERROR: {e}', file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps([{'status': s, 'ref': r, 'msg': m} for s, r, m in results],
                         ensure_ascii=False, indent=2))
    elif not a.quiet:
        for s, r, m in results:
            print(f'[{s:4s}] {r}: {m}')
    fails = [x for x in results if x[0] == 'FAIL']
    warns = [x for x in results if x[0] == 'WARN']
    if not a.quiet and not a.json:
        print(f'\nverdict={"FAIL" if fails else ("WARN" if warns else "PASS")} '
              f'PASS={sum(1 for x in results if x[0]=="PASS")} WARN={len(warns)} FAIL={len(fails)}')
    if fails:
        return 1
    if warns and a.strict:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
