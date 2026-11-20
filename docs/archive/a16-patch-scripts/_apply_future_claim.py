"""Patch index.mjs: add FUTURE_CLAIM regex + update claimedPaths L1 check."""
import re as _re, sys
from pathlib import Path

src = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs').read_text(encoding='utf-8')

# 1) Add FUTURE_CLAIM constant after WRITE_CLAIM line (line 593)
old_line_593 = src.split('\n')[592]   # 0-based
print(f'Line 593: {repr(old_line_593[:80])}...')

future_claim_def = r'''const FUTURE_CLAIM = /(?:现在|接下来|下面|马上|立即|随后)(?:要|了|就|正在)?\s*(?:写|创建|生成|编写|实现|建立|新建|产出|落盘|保存)[^\n]*?(?:一[个位]?[的])?\s*[`\u201c\u2018\u3010“‘]?([A-Za-z]:[\\/][^\s`"'））,，。；;、]{4,}|[./][^\s`"'））,，。；;、]+\.py|[./][^\s`"'））,，。；;、]+\.mjs|[./][^\s`"'））,，。；;、]+\.md)/i
const ILL_CLAIM = /(?:我将|I'll)\s+(?:要\s+)?(?:写|创建|生成|编写|实现)[^\n]{0,60}?[`"']?([A-Za-z]:[\\/][^\s`"'））,，。；;、]{4,}|[./][^\s`"'））,，。；;、]+\.py|[./][^\s`"'））,，。；;、]+\.mjs|[./][^\s`"'））,，。；;、]+\.md)/i
const WILL_CLAIM = /\bwill\s+(?:write|create|generate|build|implement|place|save)\s+[`"']?([A-Za-z]:[\\/][^\s`"'））,，。；;、]{4,}|[./][^\s`"'））,，。；;、]+\.py|[./][^\s`"'））,，。；;、]+\.mjs|[./][^\s`"'））,，。；;、]+\.md)/i'''

lines = src.split('\n')
lines.insert(593, future_claim_def)   # insert AFTER line 593 (index 593 → becomes line 594)

# Write intermediate file to verify syntax
Path('D:/Brain/publish/dsh-behavior-guard/index.mjs').write_text('\n'.join(lines), encoding='utf-8')
print(f'Wrote index.mjs with {len(lines)} lines, added FUTURE_CLAIM constants.')
