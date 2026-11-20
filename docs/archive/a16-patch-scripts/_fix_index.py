"""Fix index.mjs: remove duplicate/broken regex lines and keep only working version."""
import pathlib

p = pathlib.Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
lines = p.read_text(encoding='utf-8').split('\n')

# Find the problematic lines - we have two sets of future claim definitions
# Lines around 593-595 are broken; 596+ has PATH_RE and functions
# We need to keep WRITE_CLAIM at line 593 and add clean future claim defs after it

# Let's find exact positions
for i, l in enumerate(lines):
    if 'const FUTURE_CLAIM' in l:
        print(f'[FUTURE_CLAIM at {i+1}]: {l[:100]}...')
    if 'const WILL_CLAIM' in l:
        print(f'[WILL_CLAIM at {i+1}]: {l[:100]}...')
    if 'const ILL_CLAIM' in l:
        print(f'[ILL_CLAIM at {i+1}]: {l[:100]}...')
    if 'CLAIM_PATTERNS' in l:
        print(f'[CLAIM_PATTERNS at {i+1}]: {l}')

print(f'\nTotal lines: {len(lines)}')
