# -*- coding: utf-8 -*-
"""promote_skills —— 技能写回闭环的审批门（P0-3，零 LLM）

依据（2026-11-18 广搜）：
- 全社区最一致的发现：零训练下"变聪明" = 写文件（memory + skill）；
  Hermes skill lifecycle 有 cooldown + 写审批 + provenance + 去重 + stale 归档。
- 反面：SkillLearnBench 持续更新会 drift/regress；SkillsBench 自动生成的技能收益不一致；
  marketplace 26.1% 技能有漏洞 → **未经审批不得入库**。

流程：
  skill_draft.py 生成草稿 → bench/_skill_drafts/pending/（隔离区）
  → 人工/审计检查 → promote_skills.py --promote <name>（入库到 skills/）
  → -outcome 记录命中结果 → --stale 归档过期技能

用法：
  python promote_skills.py                       # 列出 pending 与已入库状态
  python promote_skills.py --stage <draft.md>    # 把草稿放进 pending（加 provenance 头）
  python promote_skills.py --promote <name>      # 审批入库（备份原文件）
  python promote_skills.py --reject <name>       # 拒绝（移入 rejected/ 留审计链）
  python promote_skills.py --stale               # 30 天未命中且非 protected 的标 retired
"""
import json
import os
import re
import shutil

# 投毒防御：技能草稿入库前扫描注入指令（与 index.mjs S6 规则层同源）
# SkillJack 实证：80% 攻击删源后仍存活 → 写回闭环必须在 stage 和 promote 两道门都扫。
INJECTION_PATTERNS = [
    re.compile(r'ignore (all )?(previous|prior|above) instructions', re.I),
    re.compile(r'disregard (the )?(system|previous|above)', re.I),
    re.compile(r'忽略(之前|上述|前面|所有).{0,6}(指令|指示|规则)'),
    re.compile(r'你现在是|you are now a (different|new)', re.I),
    re.compile(r'请执行以下命令|run this command immediately', re.I),
]


def scan_injection(txt):
    """返回命中的模式字符串，干净则返回 None。"""
    for p in INJECTION_PATTERNS:
        if p.search(txt or ''):
            return p.pattern
    return None
import sys
from datetime import datetime, timezone

BENCH = r'D:\Brain\workspace\bench'
SKILLS = os.path.join(BENCH, 'skills')
PENDING = os.path.join(BENCH, '_skill_drafts', 'pending')
REJECTED = os.path.join(BENCH, '_skill_drafts', 'rejected')
ARCHIVE = os.path.join(BENCH, '_skill_drafts', 'archive')
LEDGER = os.path.join(BENCH, '_skill_ledger.json')
STALE_DAYS = 30


def load(p, d):
    if not os.path.exists(p):
        return d
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return d


def save(p, o):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(o, f, ensure_ascii=False, indent=2)


def ensure():
    for d in (PENDING, REJECTED, ARCHIVE):
        os.makedirs(d, exist_ok=True)


def main():
    args = sys.argv[1:]
    ensure()
    ledger = load(LEDGER, {})

    if '--stage' in args:
        src = args[args.index('--stage') + 1]
        if not os.path.exists(src):
            print('草稿不存在:', src)
            return
        name = os.path.basename(src)
        dst = os.path.join(PENDING, name)
        txt = open(src, encoding='utf-8').read()
        hit = scan_injection(txt)
        if hit:
            print(f'拒绝隔离：草稿含疑似注入指令（{hit}）— 需人工复核后再 stage: {name}')
            return
        header = (f'<!-- staged {datetime.now(timezone.utc).isoformat()} | '
                  f'provenance: auto-draft | status: PENDING APPROVAL | '
                  f'do NOT trust until promoted -->\n')
        open(dst, 'w', encoding='utf-8', newline='\n').write(header + txt)
        ledger[name] = {'status': 'pending', 'staged_at': datetime.now(timezone.utc).isoformat()[:10],
                        'source': 'skill_draft.py', 'hits': 0}
        save(LEDGER, ledger)
        print(f'已隔离到 pending: {name}（未经 --promote 不得生效）')
        return

    if '--promote' in args:
        name = args[args.index('--promote') + 1]
        if not name.endswith('.md'):
            name += '.md'
        src = os.path.join(PENDING, name)
        if not os.path.exists(src):
            print('pending 中无此技能:', name)
            return
        txt = open(src, encoding='utf-8').read()
        # 投毒防御：入库前再扫一次（防止 pending 区被绕过 stage 直接写入）
        hit = scan_injection(txt)
        if hit:
            print(f'拒绝入库：草稿含疑似注入指令（{hit}）— 需人工复核: {name}')
            return
        # 校验 ledger 状态：只有 pending 的才能 promote
        if ledger.get(name, {}).get('status') != 'pending':
            print(f'拒绝入库：{name} 不在 pending 状态（ledger 无记录或已处理）')
            return
        # 移除隔离头
        txt = re.sub(r'^<!-- staged .*?-->\n', '', txt, count=1, flags=re.S)
        # provenance 头（可追溯）
        txt = ('<!-- provenance: promoted ' + datetime.now(timezone.utc).isoformat()[:10] +
               ' | reviewed: yes -->\n') + txt
        dst = os.path.join(SKILLS, name)
        if os.path.exists(dst):
            shutil.copy(dst, os.path.join(ARCHIVE, name + '.bak-' + datetime.now().strftime('%Y%m%d-%H%M%S')))
        open(dst, 'w', encoding='utf-8', newline='\n').write(txt)
        ledger[name] = {'status': 'active', 'promoted_at': datetime.now(timezone.utc).isoformat()[:10],
                        'last_hit': None, 'hits': 0, 'protected': False}
        save(LEDGER, ledger)
        print(f'已审批入库: {name}（原版本备份到 archive/ 如有）')
        return

    if '--reject' in args:
        name = args[args.index('--reject') + 1]
        if not name.endswith('.md'):
            name += '.md'
        src = os.path.join(PENDING, name)
        if os.path.exists(src):
            shutil.move(src, os.path.join(REJECTED, name))
            ledger[name] = {'status': 'rejected', 'rejected_at': datetime.now(timezone.utc).isoformat()[:10]}
            save(LEDGER, ledger)
            print(f'已拒绝并留审计链: {name}')
        return

    if '--stale' in args:
        today = datetime.now(timezone.utc).date()
        n = 0
        for name, st in ledger.items():
            if st.get('status') != 'active' or st.get('protected'):
                continue
            last = st.get('last_hit')
            if not last:
                continue
            try:
                age = (today - datetime.fromisoformat(last).date()).days
            except Exception:
                continue
            if age > STALE_DAYS:
                src = os.path.join(SKILLS, name)
                if os.path.exists(src):
                    shutil.move(src, os.path.join(ARCHIVE, name))
                st['status'] = 'retired'
                st['retired_at'] = today.isoformat()
                n += 1
                print(f'{name} → archived (未命中 {age} 天)')
        save(LEDGER, ledger)
        print(f'归档 {n} 个技能')
        return

    # 默认：状态报告
    print('=== pending（未审批，不生效）===')
    pend = [f for f in os.listdir(PENDING) if f.endswith('.md')] if os.path.isdir(PENDING) else []
    print('\n'.join('  ' + f for f in pend) if pend else '  (空)')
    print('\n=== 已入库技能状态 ===')
    for f in sorted(os.listdir(SKILLS)):
        if not f.endswith('.md'):
            continue
        st = ledger.get(f, {})
        print(f'  {f:<28} {st.get("status","untracked"):<10} hits={st.get("hits",0)} last={st.get("last_hit") or "-"}')
    print(f'\n审批: --promote <name> | 拒绝: --reject <name> | 归档过期: --stale')


if __name__ == '__main__':
    main()
