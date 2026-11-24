# -*- coding: utf-8 -*-
"""修复回读门 steer 文案：加 verify-on-stop 判据关键词，兼容现有测试。"""
import hashlib, shutil
from pathlib import Path
p = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
raw = p.read_bytes(); crlf = b'\r\n' in raw
s = raw.decode('utf-8').replace('\r\n', '\n')
old = """            '。现在立刻用 write 工具把内容真正写到目标路径（或用 pwsh 确认文件已落盘），' +
            '不要只在正文里声称已写入；看到工具成功结果后再 present。',"""
new = """            '。现在立刻用 write 工具把内容真正写到目标路径，' +
            '然后用 pwsh 运行真实验证命令确认产物（如 python -m py_compile / node --check / pytest），' +
            '或 read 一个路径含 [VERIFY] 的验收文件。不要只在正文里声称已写入。',"""
assert s.count(old) == 1, f'锚点 {s.count(old)} 次'
s = s.replace(old, new, 1)
p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
shutil.copy2(p, 'D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
print('修复后两副本sha:', hashlib.sha256(p.read_bytes()).hexdigest()[:16])
