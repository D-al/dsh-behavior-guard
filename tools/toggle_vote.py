# -*- coding: utf-8 -*-
"""切换 voteOnCritic 开关（杠杆4 A/B 用）。可逆。

用法：python toggle_vote.py on|off|status
"""
import sys, hashlib, shutil
from pathlib import Path

AUTH = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
RUN = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')


def patch_one(p, target):
    raw = p.read_bytes(); crlf = b'\r\n' in raw
    s = raw.decode('utf-8').replace('\r\n', '\n')
    old_on = "  voteOnCritic: false,"
    old_off = "  voteOnCritic: true,"
    if target == 'on':
        if s.count(old_on) == 1: s = s.replace(old_on, "  voteOnCritic: true,", 1)
        elif s.count(old_off) == 1: pass  # 已是 on
        else: raise SystemExit(f'{p.name}: 未找到开关')
    else:
        if s.count(old_off) == 1: s = s.replace(old_off, "  voteOnCritic: false,", 1)
        elif s.count(old_on) == 1: pass
        else: raise SystemExit(f'{p.name}: 未找到开关')
    p.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'status':
        for p in [AUTH, RUN]:
            s = p.read_text(encoding='utf-8')
            print(f'{p.parent.name}: voteOnCritic={"true" if "voteOnCritic: true" in s else "false"} sha={hashlib.sha256(p.read_bytes()).hexdigest()[:12]}')
        return
    for p in [AUTH, RUN]:
        patch_one(p, cmd)
    print(f'voteOnCritic 已设为 {cmd}，两副本同步')
    for p in [AUTH, RUN]:
        print(f'  sha={hashlib.sha256(p.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__': main()
