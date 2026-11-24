# -*- coding: utf-8 -*-
"""修复回读门误报：无结构化写目标时跳过（不拦截），交给其他机制。

根因：tool/call write 无 arguments 时 lastProduct/changedFiles 都没设，
deterministicStateReadback 返回 no-structured-write-target → 误 steer。
正解：提取不到目标 = 无法回读 = 不拦（fail-open for skip，由 verify-on-stop/D4 兜底）。
"""
import hashlib, shutil
from pathlib import Path
p = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
raw = p.read_bytes(); crlf = b'\r\n' in raw
s = raw.decode('utf-8').replace('\r\n', '\n')

# 1) 无目标时 skipped=true 而不是硬失败
old1 = """  if (!out.targets.length) {
    out.errors.push('no-structured-write-target')
    return out
  }"""
new1 = """  if (!out.targets.length) {
    // 无结构化写目标 → 无法回读 → 跳过本门（不误拦），由 verify-on-stop / D4 兜底
    out.skipped = true
    return out
  }"""
assert s.count(old1) == 1, f'old1 {s.count(old1)}'
s = s.replace(old1, new1, 1)

# 2) gate 里：skipped 时不 steer（但 trace 仍记，可观测）
old2 = """        const d5Reserve = Math.max(0, Number(cfg.deterministicReadbackReserveD5) || 0)
        if (!rb.ok && state.sharedInjections + 1 <= cfg.sharedMaxPerTurn - d5Reserve) {"""
new2 = """        const d5Reserve = Math.max(0, Number(cfg.deterministicReadbackReserveD5) || 0)
        if (!rb.skipped && !rb.ok && state.sharedInjections + 1 <= cfg.sharedMaxPerTurn - d5Reserve) {"""
assert s.count(old2) == 1, f'old2 {s.count(old2)}'
s = s.replace(old2, new2, 1)

# 3) trace 加 skipped 字段
old3 = """kind: 'verify_state_readback',
          step: state.step, ok: rb.ok, targets: (rb.targets || []).length,"""
new3 = """kind: 'verify_state_readback',
          step: state.step, ok: rb.ok, skipped: rb.skipped === true, targets: (rb.targets || []).length,"""
assert s.count(old3) == 1, f'old3 {s.count(old3)}'
s = s.replace(old3, new3, 1)

p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
shutil.copy2(p, 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
print('修复后两副本sha:', hashlib.sha256(p.read_bytes()).hexdigest()[:16])
