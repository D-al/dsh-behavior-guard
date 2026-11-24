# -*- coding: utf-8 -*-
"""修复杠杆4投票：单次超时 20s→60s（thinking 模型 20s 出不完 JSON，5次全 PARSE_FAIL）。
总预算同步 180s→360s。可逆。"""
import hashlib, shutil
from pathlib import Path
p = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
raw = p.read_bytes(); crlf = b'\r\n' in raw
s = raw.decode('utf-8').replace('\r\n', '\n')
repls = [
    ("out = await callLLMOnce(prompt, maxTokens, 20000, {",
     "out = await callLLMOnce(prompt, maxTokens, Math.min(60000, timeoutMs || 60000), {"),
    ("  voteMaxTotalMs: 180000,", "  voteMaxTotalMs: 360000,"),
]
for old, new in repls:
    assert s.count(old) == 1, f'{old[:40]} {s.count(old)}'
    s = s.replace(old, new, 1)
p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
shutil.copy2(p, 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
print('修复后两副本sha:', hashlib.sha256(p.read_bytes()).hexdigest()[:16])
