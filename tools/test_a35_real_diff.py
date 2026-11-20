#!/usr/bin/env python3
"""
test_a35_real_diff.py — 旁观者对 real_diff_check 的独立验收测试（非 agent 自证）

关键：测试样本用"真实场景"——改动行只含 surface target 的一个 token，
而不是恰好包含完整 'CONTROL_PROMPT / parts.push 文案' 字符串。
这能抓出 re.escape(整串) 导致的假阴性（合法改动被拒）。

用法: D:/Python/python.exe -B tools/test_a35_real_diff.py
退出: 0=全通过; 1=有失败
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import self_harness_gate as g

results = []


def expect(name, got, want):
    ok = got == want
    results.append((name, ok, got, want))
    print(f'{"PASS" if ok else "FAIL"}  {name}: got={got} want={want}')


# 正例 1：只改 CONTROL_PROMPT 那行（白名单内），改动行不含完整 target_region 字符串
base = 'const CONTROL_PROMPT = "old"\nconst OTHER = "keep"\n'
cand = 'const CONTROL_PROMPT = "new"\nconst OTHER = "keep"\n'
r = g.real_diff_check('SURF-PROMPT-CONTROL', {'index.mjs': {'base': base, 'candidate': cand}})
expect('whitelisted CONTROL_PROMPT change allowed', r.get('allowed'), True)

# 正例 2：CRITIC_PROMPT 同理
base2 = 'const CRITIC_PROMPT = "old"\nconst KEEP = 1\n'
cand2 = 'const CRITIC_PROMPT = "new"\nconst KEEP = 1\n'
r2 = g.real_diff_check('SURF-PROMPT-CRITIC', {'index.mjs': {'base': base2, 'candidate': cand2}})
expect('whitelisted CRITIC_PROMPT change allowed', r2.get('allowed'), True)

# 反例：改白名单外的 OTHER 行
cand3 = 'const CONTROL_PROMPT = "old"\nconst OTHER = "changed"\n'
r3 = g.real_diff_check('SURF-PROMPT-CONTROL', {'index.mjs': {'base': base, 'candidate': cand3}})
expect('non-whitelisted OTHER change rejected', r3.get('allowed'), False)

# 无变化：应允许
r4 = g.real_diff_check('SURF-PROMPT-CONTROL', {'index.mjs': {'base': base, 'candidate': base}})
expect('no-change allowed', r4.get('allowed'), True)

failed = [r for r in results if not r[1]]
print(f'\n==== {len(results) - len(failed)}/{len(results)} PASS ====')
sys.exit(1 if failed else 0)
