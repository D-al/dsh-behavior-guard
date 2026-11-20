#!/usr/bin/env python3
"""Patch index.mjs: remove broken FUTURE/WILL lines, add clean future claim detection."""
import pathlib

p = pathlib.Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
src = p.read_text(encoding='utf-8')
lines = src.split('\n')

# Find indices of problematic lines
f_idx = None
w_idx = None
for i, l in enumerate(lines):
    if 'const FUTURE_CLAIM' in l and 'PHRASES' not in l:
        f_idx = i
    if 'const WILL_CLAIM' in l and 'PHRASES' not in l:
        w_idx = i

if f_idx is None or w_idx is None:
    print(f'[!] Could not find broken lines. f={f_idx}, w={w_idx}')
    # Show nearby lines for debugging
    for i in range(max(0, f_idx-2) if f_idx else 0, min(len(lines), (w_idx+3) if w_idx else len(lines))):
        print(f'  {i}: {repr(lines[i][:80])}')
    exit(1)

print(f'[+] Found broken FUTURE at line {f_idx+1}, WILL at line {w_idx+1}')

# New definitions to insert after WRITE_CLAIM (line ~593)
new_defs = [
    '// Future claim detection — catches "现在/接下来/下面 + 写/创建/实现 + X" patterns.',
    '// These trigger L1 file-existence+mtime verification just like past-tense claims.',
    r'const FUTURE_PHRASES = /(?:现在|接下来|下面|马上|立即)(?:要|了|就|正在)?[：:]?\s*(?:写|创建|生成|编写|实现|建立|产出|落盘|保存)/i',
    r"const ILL_PHRASES = /(?:我将|I'll)\s+(?:要\s+)?(?:写|创建|生成|编写|实现)/i",
    r'const WILL_PHRASES = /\bwill\s+(?:write|create|generate|build|implement|place|save)/i',
    'function hasFutureClaim(line) {',
    '  return FUTURE_PHRASES.test(line) || ILL_PHRASES.test(line) || WILL_PHRASES.test(line)',
    '}',
]

# Construct: lines before WRITE_CLAIM + WRITE_CLAIM + new_defs + PATH_RE onwards
wc_idx = None
for i, l in enumerate(lines):
    if 'const WRITE_CLAIM' in l and 'FUTURE' not in l and 'WILL' not in l:
        wc_idx = i
        break

if wc_idx is None:
    print('[!] Could not find WRITE_CLAIM')
    exit(1)

path_re_line = None
for i in range(max(f_idx, w_idx), min(len(lines), max(f_idx, w_idx) + 10)):
    if 'const PATH_RE' in lines[i]:
        path_re_line = i
        break

if path_re_line is None:
    print('[!] Could not find PATH_RE')
    for i in range(wc_idx+1, min(len(lines), wc_idx+15)):
        print(f'  {i}: {repr(lines[i][:80])}')
    exit(1)

new_lines = (lines[:wc_idx+1] + new_defs + [''] + lines[path_re_line:])
p.write_text('\n'.join(new_lines), encoding='utf-8')
print(f'[+] Wrote {len(new_lines)} lines to index.mjs')
