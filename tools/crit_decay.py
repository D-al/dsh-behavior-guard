# -*- coding: utf-8 -*-
"""crit_decay —— CritBank 可控遗忘与写入门控（P0-2，零 LLM）

依据（2026-11-18 广搜）：
- append-only 的 CritBank 会让过时经验自我强化；记忆增长致漂移（无攻击下 0.455→0.05，假记忆 6.8%）。
- ExpeL：helpful/harmful 计数，降到 0 即删除；Zep/Graphiti：新事实使旧事实失效而非删除，保留时间切片。
- SSGM：决定/承诺/偏好/身份类设写保护，不允许低置信更新覆盖。

设计：**状态侧表**，不改 critbank.json 本身（向后兼容）。
  {id: {helpful, harmful, last_hit, status(active|superseded|retired), supersedes, protected}}

用法（只读为主，--apply 才写状态表）：
  python crit_decay.py                      # 报告各条目健康度
  python crit_decay.py --hit C-001 --ok     # 记录一次成功命中（helpful +1）
  python crit_decay.py --hit C-001 --bad    # 记录一次失败命中（harmful +1）
  python crit_decay.py --apply              # 应用衰减：harmful>helpful+2 或 30 天未命中 → retired
  python crit_decay.py --supersede OLD NEW  # 新教训取代旧教训（保留指针）
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
BANK = str(Path(BENCH_DIR) / 'critbank.json')
STATE = str(Path(BENCH_DIR) / '_critbank_state.json')
RETIRE_DAYS = 30
HARMFUL_MARGIN = 2


def load_json(p, default):
    if not os.path.exists(p):
        return default
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return default


def save(p, obj):
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def state_for(bank, state):
    """确保每条 crit 都有状态，且不覆盖已有状态"""
    for c in bank:
        cid = c.get('id')
        if cid and cid not in state:
            state[cid] = {'helpful': 0, 'harmful': 0, 'last_hit': None,
                          'status': 'active', 'supersedes': None, 'protected': False,
                          'created': datetime.now(timezone.utc).isoformat()[:10]}
    return state


def report(bank, state):
    print(f'CritBank {len(bank)} 条 | 状态表 {len(state)} 条\n')
    print(f'{"ID":<8} {"状态":<12} {"help":>5} {"harm":>5} {"最后命中":<12} 教训（截取）')
    print('-' * 84)
    for c in bank:
        cid = c.get('id', '?')
        st = state.get(cid, {})
        print(f'{cid:<8} {st.get("status","active"):<12} {st.get("helpful",0):>5} {st.get("harmful",0):>5} '
              f'{str(st.get("last_hit") or "-"):<12} {str(c.get("lesson",""))[:34]}')
    active = sum(1 for c in bank if state.get(c.get('id'), {}).get('status') == 'active')
    retired = sum(1 for c in bank if state.get(c.get('id'), {}).get('status') == 'retired')
    print(f'\n活跃 {active} / 退役 {retired}')
    if retired:
        print('提示：retired 条目仍保留在 critbank.json（审计链完整），仅不再作为首选注入。')


def main():
    args = sys.argv[1:]
    bank = load_json(BANK, [])
    state = state_for(bank, load_json(STATE, {}))

    if '--hit' in args:
        cid = args[args.index('--hit') + 1]
        key = 'helpful' if '--ok' in args else 'harmful'
        if cid not in state:
            print(f'未知 Crit id: {cid}')
            return
        state[cid][key] = state[cid].get(key, 0) + 1
        state[cid]['last_hit'] = datetime.now(timezone.utc).isoformat()[:10]
        save(STATE, state)
        print(f'{cid} {key} → {state[cid][key]}')
        return

    if '--supersede' in args:
        old = args[args.index('--supersede') + 1]
        new = args[args.index('--supersede') + 2]
        if old in state and new in state:
            state[old]['status'] = 'superseded'
            state[old]['superseded_by'] = new
            state[new]['supersedes'] = old
            save(STATE, state)
            print(f'{old} → superseded by {new}（保留旧条目作为审计链）')
        else:
            print('两个 id 都必须已存在')
        return

    if '--apply' in args:
        today = datetime.now(timezone.utc).date()
        changed = 0
        for cid, st in state.items():
            if st.get('status') != 'active' or st.get('protected'):
                continue
            harmful = st.get('harmful', 0)
            helpful = st.get('helpful', 0)
            last = st.get('last_hit')
            stale = False
            if last:
                try:
                    stale = (today - datetime.fromisoformat(last).date()).days > RETIRE_DAYS
                except Exception:
                    pass
            if harmful > helpful + HARMFUL_MARGIN or (stale and helpful < 2):
                st['status'] = 'retired'
                st['retired_at'] = today.isoformat()
                changed += 1
                print(f'{cid} → retired (harmful={harmful}, helpful={helpful}, stale={stale})')
        save(STATE, state)
        print(f'退役 {changed} 条')
        return

    report(bank, state)


if __name__ == '__main__':
    main()
