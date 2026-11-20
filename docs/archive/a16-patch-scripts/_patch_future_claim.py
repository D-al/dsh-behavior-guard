#!/usr/bin/env python3
"""Patch index.mjs: add FUTURE_CLAIM regexes and update claimedPaths."""
import pathlib

p = pathlib.Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
lines = p.read_text(encoding='utf-8').split('\n')

# Find line with "const WRITE_CLAIM ="
wl = None
for i, l in enumerate(lines):
    if 'const WRITE_CLAIM' in l:
        wl = i
        break
assert wl is not None, 'WRITE_CLAIM not found'
print(f'[+] Found WRITE_CLAIM at line {wl+1}')

# Insert new constants after WRITE_CLAIM
new_lines = [
    '',
    '// Future claim detection — catches "现在/接下来/下面 + 写/创建/实现 + X" patterns',
    "// These rely on PATH_RE for actual path extraction; they just trigger the L1 guard.",
    r'''const FUTURE_CLAIM = /(?:现在|接下来|下面|马上|立即)(?:要|了|就|正在)?[：:]?\s*(?:写|创建|生成|编写|实现|建立|产出|落盘|保存)[^\n]*(?:产|出|名|称)[:：]?\s*["`']?([A-Za-z]:[\\/][^\s"`']+)|(\.\.?\/[\w./\-]+\.(?:py|mjs|md)))/i''',
    r'''const ILL_CLAIM = /(?:我将|I'll)\s+(?:要\s+)?(?:写|创建|生成|编写|实现)[^\n]{0,80}?(?:产|出)["\u201c\u2018]?([A-Za-z]:[\\/][^\s"`']+)|(\.\.?\/[\w./\-]+\.(?:py|mjs|md))/i''',
    r'''const WILL_CLAIM = /\bwill\s+(?:write|create|generate|build|implement|place|save)\s+[`"']?([A-Za-z]:[\\/][^\s"`']+)|(\.\.?\/[\w./\-]+\.(?:py|mjs|md))/i''',
]

for offset, nl in enumerate(new_lines):
    lines.insert(wl + 1 + offset, nl)

p.write_text('\n'.join(lines), encoding='utf-8')
print(f'[+] Wrote {len(lines)} lines to index.mjs')
