#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CritBank 状态消费闭环（2026-11-26 18:1x）

依据子任务2复核：断点不在"crit_revision 反馈没消费"，而在 matchCritbank()
只读 critbank.json 数组、完全不读 _critbank_state.json —— 所以 crit_decay.py
标记的 retired/superseded 状态对注入毫无影响。

修复：matchCritbank 读状态表（缓存 + mtime 失效），过滤 retired/superseded 条目。
零 LLM、进程内、幂等。

幂等标记：CRITBANK_STATE-PATCHED
"""
import argparse
import sys
from pathlib import Path

TARGETS = [
    Path(r'D:\Brain\publish\dsh-behavior-guard\index.mjs'),
    Path(r'D:\Brain\dsh-data\profiles\desktop\node_modules\dsh-agent-harness\index.mjs'),
]
MARK = 'CRITBANK_STATE-PATCHED'

OLD_MATCH = """function matchCritbank(s) {
  if (!Array.isArray(CRITBANK) || CRITBANK.length === 0) return []
  const trail = Array.isArray(s?.trail) ? s.trail.slice(-8) : []
  const hay = trail.map((x) => `${x?.name || ''} ${x?.result || ''} ${x?.status || ''}`).join(' ').toLowerCase()
  return CRITBANK
    .map((c) => ({ c, score: (c.tags || []).filter((t) => hay.includes(String(t).toLowerCase())).length }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 2)
    .map((x) => `【相关教训 ${x.c.id}】${x.c.lesson}`)
}"""

NEW_MATCH = """// CritBank 状态表（2026-11-26）：crit_decay.py 会把有害教训标 retired，
// 但 matchCritbank 此前只读数组不读状态 → retired 教训照样注入。
// 缓存 + mtime 失效，避免每条 trail 都读磁盘。
let _critbankStateCache = { mtime: 0, data: null }
function critbankState() {
  const p = 'D:/Brain/workspace/bench/_critbank_state.json'
  try {
    const st = statSync(p, { throwIfNoEntry: false })
    if (!st) return null
    const mt = st.mtimeMs
    if (_critbankStateCache.data && _critbankStateCache.mtime === mt) return _critbankStateCache.data
    const data = JSON.parse(readFileSync(p, 'utf8'))
    _critbankStateCache = { mtime: mt, data }
    return data
  } catch { return null }
}
function matchCritbank(s) {
  if (!Array.isArray(CRITBANK) || CRITBANK.length === 0) return []
  const trail = Array.isArray(s?.trail) ? s.trail.slice(-8) : []
  const hay = trail.map((x) => `${x?.name || ''} ${x?.result || ''} ${x?.status || ''}`).join(' ').toLowerCase()
  const cstate = critbankState()
  return CRITBANK
    .filter((c) => {
      const st = cstate?.[c.id]
      return !st || (st.status || 'active') === 'active'   // retired/superseded 不再注入
    })
    .map((c) => ({ c, score: (c.tags || []).filter((t) => hay.includes(String(t).toLowerCase())).length }))
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 2)
    .map((x) => `【相关教训 ${x.c.id}】${x.c.lesson}`)
}"""


def patch(path: Path, dry: bool, check: bool) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING {path}'
    t = path.read_text(encoding='utf-8')
    if check:
        return MARK in t, f'{"已打补丁" if MARK in t else "未打补丁"} {path}'
    if MARK in t:
        return True, f'已打补丁跳过 {path.name}'
    if OLD_MATCH not in t:
        return False, f'FAIL {path.name}: matchCritbank 锚点不存在'
    out = t.replace(OLD_MATCH, NEW_MATCH, 1)
    out = out.replace('function matchCritbank(s) {', f'// {MARK} (2026-11-26)\nfunction matchCritbank(s) {{', 1)
    if not dry:
        path.write_text(out, encoding='utf-8')
    return True, f'{"DRY " if dry else ""}OK {path.name}: matchCritbank 状态消费'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    if not a.check and not a.apply:
        ap.print_help(); return 2
    ok_all = True
    for p in TARGETS:
        ok, msg = patch(p, a.dry_run, a.check)
        print(msg); ok_all = ok_all and ok
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
