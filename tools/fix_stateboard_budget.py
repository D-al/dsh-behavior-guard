# -*- coding: utf-8 -*-
"""修复状态板被注入预算挤占：状态板走控制回合 parts.push（prompt 内），
与 M1 episodicSearch 同性质，不占 sharedInjections 运行时注入预算。"""
import hashlib, shutil
from pathlib import Path
p = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
raw = p.read_bytes(); crlf = b'\r\n' in raw
s = raw.decode('utf-8').replace('\r\n', '\n')
old = """            (s.step % Math.max(1, Number(cfg.stateBoardEverySteps) || 4)) === 0 &&
            state.sharedInjections < cfg.sharedMaxPerTurn
          ) {
            const sb = buildStateBoard(s, cfg)
            if (sb.text) {
              state.sharedInjections += 1
              s.stateBoardCount = (s.stateBoardCount || 0) + 1"""
new = """            (s.step % Math.max(1, Number(cfg.stateBoardEverySteps) || 4)) === 0
          ) {
            const sb = buildStateBoard(s, cfg)
            if (sb.text) {
              // 走控制回合 parts.push（prompt 内），与 M1 检索同性质，不占 sharedInjections
              s.stateBoardCount = (s.stateBoardCount || 0) + 1"""
assert s.count(old) == 1, f'锚点 {s.count(old)}'
s = s.replace(old, new, 1)
p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
shutil.copy2(p, 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
print('修复后两副本sha:', hashlib.sha256(p.read_bytes()).hexdigest()[:16])
