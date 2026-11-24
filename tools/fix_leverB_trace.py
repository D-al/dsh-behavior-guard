# -*- coding: utf-8 -*-
"""修复杠杆B：errorPlaybook 顶层函数访问不到 apply 内的 trace 闭包，
导致 trace 调用抛 ReferenceError 被 catch 吞掉（动作生效但无 L4 证据）。
把 trace 移到挂点（apply 作用域内）。
"""
import hashlib, shutil
from pathlib import Path
AUTH = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
raw = AUTH.read_bytes(); crlf = b'\r\n' in raw
s = raw.decode('utf-8').replace('\r\n', '\n')

# 1) 删掉顶层函数里的 trace 块
old1 = """  try {
    trace({ ts: new Date().toISOString(), sid: st.sid || '', kind: 'error_playbook',
      tool: name, errorType: type, step: st.step || 0, injected: !st.pendingInject })
  } catch { /* trace 失败不影响注入 */ }
  return { type, text: action }"""
new1 = """  return { type, text: action }"""
assert s.count(old1) == 1, f'old1 {s.count(old1)}'
s = s.replace(old1, new1, 1)

# 2) 在挂点处打 trace（apply 作用域内，trace 可用）
old2 = """          if (!s.pendingInject) {
            const ep = errorPlaybook(s, cfg, c, status)
            if (ep) s.pendingInject = ep.text
          }"""
new2 = """          if (!s.pendingInject) {
            const ep = errorPlaybook(s, cfg, c, status)
            if (ep) {
              s.pendingInject = ep.text
              trace({ ts: new Date().toISOString(), sid: s.sid || '', kind: 'error_playbook',
                tool: String(c?.name || ''), errorType: ep.type, step: s.step || 0, injected: true })
            }
          }"""
assert s.count(old2) == 1, f'old2 {s.count(old2)}'
s = s.replace(old2, new2, 1)

AUTH.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
shutil.copy2(AUTH, 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
print('修复后 sha:', hashlib.sha256(AUTH.read_bytes()).hexdigest()[:12])
