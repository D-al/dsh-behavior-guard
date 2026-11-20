"""进程外可靠刹车（P0，2026-11-21）。

依据（一手调研）：
- Palisade (TMLR 2026)：o3 在 79/100 场景下破坏关停机制；同进程/同模型的"自愿停止"不可靠。
- Governor：max_tokens/max_iterations 类预算会砍掉健康运行却放过病理循环（非进展才是信号）。
- OnTrack：每步 <1ms 检测 loops/stalls；83% 被中断的轨迹确实走向失败。
- corrigibility no-go：单一奖励目标做不到"可纠正地停下"，必须外部机制。

设计：
- 进程外独立脚本，不依赖 dsh 插件配合、不依赖模型自愿。
- 检测 signal = 会话事件流的"状态指纹"（seq + 最后事件类型 + 内容 hash）。
  指纹连续 N 次不变 = 非进展（比 token 数更能抓"活跃但错误"的循环）。
- 分级响应：
  L1 告警（默认）
  L2 bridge cancel（尽力，非硬保证）
  L3 硬杀 dsh 进程（仅 --enable-hard-kill 且连续无进展超过硬阈值）
- fail-safe：默认只告警；硬杀需显式开启；每次动作写日志+审计 jsonl。

用法：
  python tools/kill_switch.py --once                    # 单次扫描
  python tools/kill_switch.py --watch 5                 # 每5秒监控（前台）
  python tools/kill_switch.py --watch 5 --enable-hard-kill --sid <id>  # 硬刹车
"""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

DESC = Path('D:/Brain/dsh-data/session-bridge.json')
BRIDGE = Path('D:/Brain/workspace/bench/dsh-session-bridge/bridge.mjs')
AUDIT = Path('D:/Brain/workspace/bench/_kill_switch.jsonl')


def api(path, timeout=8):
    d = json.loads(DESC.read_text(encoding='utf-8'))
    req = urllib.request.Request(f"http://127.0.0.1:{d['port']}{path}",
                                 headers={'Authorization': 'Bearer ' + str(d.get('token', ''))})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8'))


def log(action, sid, detail=''):
    rec = {'ts': datetime.now().isoformat(), 'action': action, 'sid': sid, 'detail': detail}
    try:
        with AUDIT.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    except Exception:
        pass
    print(f"[{action}] {sid} {detail}", flush=True)


def fingerprint(sid):
    """会话状态指纹：seq + 最近事件类型序列 + 最后事件内容 hash。
    比 token 数好——token 在动但内容循环时，指纹会停滞。"""
    try:
        e = api(f'/v1/sessions/{urllib.parse.quote(sid)}/events?limit=12')
        recs = e.get('records', [])
        if not recs:
            return None
        types = [r.get('event', {}).get('type', '') for r in recs]
        last = json.dumps(recs[-1].get('event', {}).get('data', {}), ensure_ascii=False, sort_keys=True)
        # ⚠️ 不能含 cursor！cursor 随每次事件递增，带它则指纹永远不同、检测永不触发
        # （2026-11-21 自测抓到：我第一版带了 cursor，测试却只比 hash 部分，差点假绿）
        h = hashlib.sha256((','.join(types) + '|' + last).encode('utf-8')).hexdigest()[:16]
        return h
    except Exception:
        return None


def running_sessions():
    try:
        return [x.get('sessionId') for x in api('/v1/sessions').get('items', []) if x.get('running')]
    except Exception:
        return []


def bridge_cancel(sid):
    try:
        subprocess.run(['node', str(BRIDGE), 'cancel', sid], capture_output=True,
                       text=True, timeout=15)
        return True
    except Exception:
        return False


def hard_kill_dsh():
    """Windows：Stop-Process；其它：pkill。只杀 DeepSeek Harness 进程。"""
    try:
        if os.name == 'nt':
            subprocess.run(['powershell', '-NoProfile', '-Command',
                            'Get-Process -Name "DeepSeek Harness" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue'],
                           capture_output=True, timeout=20)
        else:
            subprocess.run(['pkill', '-f', 'DeepSeek Harness'], capture_output=True, timeout=20)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--watch', type=int, default=0, help='轮询间隔秒')
    ap.add_argument('--sid', help='只监控指定会话')
    ap.add_argument('--stall-limit', type=int, default=6, help='指纹连续不变次数→L1告警')
    ap.add_argument('--cancel-limit', type=int, default=10, help='→L2 cancel')
    ap.add_argument('--kill-limit', type=int, default=16, help='→L3 硬杀（需 --enable-hard-kill）')
    ap.add_argument('--enable-hard-kill', action='store_true')
    a = ap.parse_args()

    state = {}  # sid -> {'fp':指纹, 'count':连续不变次数, 'level':已响应级别}
    log('start', '-', f'watch={a.watch} stall={a.stall_limit} cancel={a.cancel_limit} '
                      f'kill={a.kill_limit} hardKill={a.enable_hard_kill}')

    while True:
        sids = [a.sid] if a.sid else running_sessions()
        for sid in sids:
            fp = fingerprint(sid)
            if fp is None:
                continue
            st = state.setdefault(sid, {'fp': fp, 'count': 0, 'level': 0})
            if fp == st['fp']:
                st['count'] += 1
            else:
                st['fp'] = fp
                st['count'] = 0
                st['level'] = 0  # 有进展→重置响应级别
                continue
            n = st['count']
            if n >= a.stall_limit and st['level'] < 1:
                st['level'] = 1
                log('L1-STALL', sid, f'指纹连续 {n} 次不变')
            if n >= a.cancel_limit and st['level'] < 2:
                st['level'] = 2
                ok = bridge_cancel(sid)
                log('L2-CANCEL', sid, f'指纹停滞 {n} 次，cancel={ok}')
            if a.enable_hard_kill and n >= a.kill_limit and st['level'] < 3:
                st['level'] = 3
                ok = hard_kill_dsh()
                log('L3-HARD-KILL', sid, f'指纹停滞 {n} 次，kill={ok}')
        if a.once or a.watch <= 0:
            break
        time.sleep(a.watch)


if __name__ == '__main__':
    main()
