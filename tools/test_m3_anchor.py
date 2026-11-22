#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M3 原型回放验证：真实会话 383 calls / 33 users
验证三件事：① 锚点抽取非空 ② 状态机正确区分追加 vs 改口 ③ 反模式匹配能检出循环
"""
import json, sys, zstandard
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from m3_anchor import extract_anchor, AnchorState, pattern_match_drift

fp = next(Path('D:/Brain/dsh-data/sessions').rglob('session-70f4485a*/session.v4.jsonl.zstd'))
d = zstandard.ZstdDecompressor()
ev = [json.loads(l) for l in d.stream_reader(open(fp,'rb')).read().decode('utf-8',errors='replace').splitlines() if l.strip()]

users, tools = [], []
for e in ev:
    dd = e.get('data') or {}
    if e.get('type') == 'user/message' and (dd.get('source') or {}).get('kind') == 'user':
        t = ''.join(str(c.get('text','')) for c in (dd.get('content') or []) if isinstance(c,dict) and c.get('type')=='text').strip()
        if t and not t.startswith(('[harness','<system-reminder>')):
            users.append(t)
    if e.get('type') == 'tool/call':
        tools.append(str(dd.get('name') or '') + ' ' + str(dd.get('arguments') or '')[:80])

state = AnchorState(extract_anchor(users[0], step=0))
print('① 锚点:', state.snapshot())
assert state.anchor.goal, '锚点为空'

overrides = 0
for i, u in enumerate(users[1:], 1):
    if state.update(u, step=i):
        overrides += 1
print(f'② 33条指令回放: evidence={len(state.anchor.evidence)} 目标级改口={overrides} superseded={len(state.anchor.superseded)}')
assert len(state.anchor.evidence) > 20, '证据没累积'
# 前几条是需求追加，不该判成改口（overlap 不该全触发）
assert overrides < len(users) * 0.5, '过度改口：追加需求被误判为目标推翻'

print(f'③ 工具序列长度={len(tools)}')
r = pattern_match_drift(tools, state.anchor, window=12)
print('   反模式匹配:', r)
assert r['reason'] in ('too-short','no-prior','ok','pattern-loop-off-goal')

# 合成检验：连续12次同一工具且不含目标词 → 应检出
fake = ['read ZZZ_NOT_RELATED'] * 12
r2 = pattern_match_drift(fake + ['read ZZZ'] * 12, state.anchor, window=12)
print('   合成循环样本:', r2)
assert r2['detected'], '合成循环未检出'

# 阴性：多样工具不检出
r3 = pattern_match_drift(['glob a','read b','pwsh c','grep d'] * 6, state.anchor, window=12)
print('   多样工具样本:', r3)
assert not r3['detected'], '误报：正常多样工具被判循环'

print('\nPASS 原型回放通过')
