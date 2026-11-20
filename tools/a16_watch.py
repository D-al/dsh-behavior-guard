#!/usr/bin/env python3
"""A1_6 推卡实时看板数据采集器（只读，写 status JSON 供 HTML 轮询）。

判据铁律（2026-11-20 纠错后）：推理活性只看 token 连续采样，绝不用单帧 GPU util%。
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / '_a16_status.json'
SID = 'session-06be7982-f672-48f0-bacd-c99830e782c0'
SLOTS = 'http://127.0.0.1:8081/slots?model=Qwen3.6-35B-A3B-UD-Q4_K_XL'
BRIDGE = r'D:\Brain\workspace\bench\dsh-session-bridge'
NODE = r'C:\Users\Ad\.workbuddy\binaries\node\versions\22.22.2-6\node.exe'  # 计划任务环境 PATH 无 node，必须绝对路径


def slots():
    try:
        with urllib.request.urlopen(SLOTS, timeout=3) as r:
            d = json.loads(r.read().decode())
        s = d[0] if isinstance(d, list) and d else d
        nt = (s.get('next_token') or [{}])[0]
        return {
            'processing': bool(s.get('is_processing')),
            'decoded': nt.get('n_decoded', 0),
            'prompt_used': s.get('n_prompt_tokens_processed', 0),
            'task': s.get('id_task'),
        }
    except Exception as e:
        return {'error': str(e)[:60]}


def sessions():
    try:
        r = subprocess.run([NODE, 'bridge.mjs', 'sessions'], cwd=BRIDGE,
                           capture_output=True, text=True, timeout=8,
                           creationflags=0x08000000)
        lines = [l for l in r.stdout.splitlines() if 'running=true' in l]
        return {'running_count': len(lines), 'running_ids': [l.split('\t')[0] for l in lines]}
    except Exception as e:
        return {'error': str(e)[:60]}


def events():
    try:
        r = subprocess.run([NODE, 'bridge.mjs', 'events', SID], cwd=BRIDGE,
                           capture_output=True, text=True, timeout=8,
                           creationflags=0x08000000)
        return r.stdout.strip().splitlines()[-14:]
    except Exception:
        return []


def artifacts():
    a = {}
    for name, p in (
        ('test', ROOT / 'tools' / 'test_future_claim_guard.py'),
        ('doc', ROOT / 'docs' / 'FUTURE_CLAIM_GUARD_20261120.md'),
        ('reflection', ROOT / 'docs' / 'reflection-A1_6.md'),
    ):
        a[name] = p.exists()
    try:
        a['index_future_claim'] = 'FUTURE_CLAIM' in (ROOT / 'index.mjs').read_text(encoding='utf-8')
    except Exception:
        a['index_future_claim'] = False
    return a


def main():
    prev_decoded = None
    while True:
        s = slots()
        ss = sessions()
        ev = events()
        art = artifacts()
        # token 活性：与上一轮比较
        decoded = s.get('decoded')
        growing = (prev_decoded is not None and decoded is not None and decoded != prev_decoded)
        prev_decoded = decoded
        # 工具统计（近 12 条）
        tools = {}
        for line in ev[-12:]:
            for t in ('read', 'grep', 'edit', 'write', 'pwsh', 'glob', 'todo_write'):
                if t in line:
                    tools[t] = tools.get(t, 0) + 1
        status = {
            'ts': time.strftime('%H:%M:%S'),
            'slots': s,
            'token_growing': growing,
            'sessions': ss,
            'artifacts': art,
            'tool_counts': tools,
            'recent_events': ev[-8:],
        }
        OUT.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        time.sleep(5)


if __name__ == '__main__':
    main()
