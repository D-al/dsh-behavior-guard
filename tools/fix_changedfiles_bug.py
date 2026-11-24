# -*- coding: utf-8 -*-
"""修复杠杆2真bug：changedFiles 累积里 callFull 未定义（实际变量是 fullArgs）。
导致 ReferenceError 被 catch 吞掉，changedFiles 永远为空，状态板 changed=none。
"""
import hashlib, shutil
from pathlib import Path
p = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
raw = p.read_bytes(); crlf = b'\r\n' in raw
s = raw.decode('utf-8').replace('\r\n', '\n')
old = "              const aa = JSON.parse(callFull || '{}') || {}"
new = "              const aa = JSON.parse(fullArgs || '{}') || {}"
assert s.count(old) == 1, f'锚点 {s.count(old)}'
s = s.replace(old, new, 1)
p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
shutil.copy2(p, 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
print('修复后两副本sha:', hashlib.sha256(p.read_bytes()).hexdigest()[:16])
