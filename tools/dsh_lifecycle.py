#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dsh 按需生命周期：start / stop / status / auto-stop

用户决策（2026-11-22 15:30）："dsh 不用长期跑着，只需要在要测试的时候拉起它，
测试完一段时间后就把它先关了。"

与既有机制的关系（已核实）：
- freeze_watch.py 拿不到 slot 就直接 sleep，不会把主动关停误判为冻死 → 安全
- RestartDsh 计划任务 State=Ready（不会自动拉起）→ 只有 start 才拉起
- bridge descriptor 在 dsh 关掉后**不会自动清理**——status 必须核对真实进程，
  不能只看 bridge health（曾误报 pid=28444 而 dsh 进程已不存在）

用法:
  python tools/dsh_lifecycle.py status
  python tools/dsh_lifecycle.py start
  python tools/dsh_lifecycle.py stop [--force]
  python tools/dsh_lifecycle.py auto-stop --idle-minutes 10 [--once]
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DESC = Path('D:/Brain/dsh-data/session-bridge.json')
LOG = Path('D:/Brain/workspace/bench/_dsh_lifecycle.jsonl')
PS = 'powershell.exe'


def log(action, detail=''):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {'at': datetime.now(timezone.utc).isoformat(), 'action': action, 'detail': detail}
    with LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def ps(cmd):
    return subprocess.run([PS, '-NoProfile', '-Command', cmd],
                          capture_output=True, text=True, timeout=60)


def real_dsh_pids():
    """真实 dsh 进程（不看 descriptor——它会陈旧）。"""
    # 只数真正活着的：HasExited=False 且有 Path。
    # Windows 进程表会短暂残留已退出进程(无Path/HasExited=True)——数进去会误报 RUNNING。
    r = ps('Get-Process -Name "DeepSeek Harness" -ErrorAction SilentlyContinue | '
           'Where-Object {$_.HasExited -eq $false -and $_.Path} | '
           'Select-Object -ExpandProperty Id')
    return [int(x) for x in r.stdout.split() if x.strip().isdigit()]


def running_sessions():
    """从 dsh 会话 API 读 running=true 的会话（需要桥活着）。"""
    try:
        import urllib.request
        d = json.loads(DESC.read_text(encoding='utf-8'))
        url = f"http://{d['address']}:{d['port']}/v1/sessions"
        req = urllib.request.Request(url, headers={'Authorization': f"Bearer {d['token']}"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        items = data.get('items', data if isinstance(data, list) else [])
        return [x.get('sessionId') or x.get('id') for x in items
                if (x.get('running') or {}).get('value') is True
                or x.get('running') is True]
    except Exception:
        return None  # 桥不可达


def last_activity_ms():
    """最后活动时刻（所有会话 updatedAt 最大值）——真实空闲判据。"""
    try:
        import urllib.request
        d = json.loads(DESC.read_text(encoding='utf-8'))
        req = urllib.request.Request(
            f"http://{d['address']}:{d['port']}/v1/sessions",
            headers={'Authorization': f"Bearer {d['token']}"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode())
        items = data.get('items', data if isinstance(data, list) else [])
        vals = [x.get('updatedAt', 0) for x in items]
        return max(vals) if vals else None
    except Exception:
        return None


def descriptor_pid():
    try:
        return json.loads(DESC.read_text(encoding='utf-8')).get('pid')
    except Exception:
        return None


def status(args):
    pids = real_dsh_pids()
    dp = descriptor_pid()
    sess = running_sessions()
    stale = bool(dp and not pids)
    print(f'dsh 真实进程: {pids or "无"}')
    print(f'descriptor pid: {dp} {("← 陈旧(dsh已关)" if stale else "")}')
    print(f'活跃会话: {sess if sess is not None else "桥不可达"}')
    verdict = 'RUNNING' if pids else 'STOPPED'
    print(f'状态: {verdict}' + (' [descriptor陈旧,不可用bridge health判活]' if stale else ''))
    return 0 if pids else 1


def start(args):
    pids = real_dsh_pids()
    if pids:
        print(f'ALREADY_RUNNING: {pids}')
        return 0
    # 复用已验证的 RestartDsh 计划任务（interactive session，全速）
    r = ps('Start-ScheduledTask -TaskName RestartDsh')
    if r.returncode != 0:
        print(f'FAIL 启动计划任务: {r.stderr.strip()[:150]}')
        return 2
    log('start', 'via RestartDsh')
    print('STARTED: RestartDsh 已触发；等 10~70s 后 status 确认')
    return 0


def stop(args):
    pids = real_dsh_pids()
    if not pids:
        print('ALREADY_STOPPED')
        return 0
    # 先优雅 cancel 活跃会话（不碰用户真实会话——只 cancel running 的）
    sess = running_sessions() or []
    if sess and not args.force:
        bridge = Path('D:/Brain/workspace/bench/dsh-session-bridge/bridge.mjs')
        for sid in sess:
            subprocess.run(['node', str(bridge), 'cancel', sid],
                           capture_output=True, timeout=30)
            print(f'  cancel 会话 {sid[:24]}')
    # 再停进程（dsh 停后 llama-server 由它自己/router 管理）
    r = ps('Get-Process -Name "DeepSeek Harness" -ErrorAction SilentlyContinue | '
           'Stop-Process -Force -ErrorAction SilentlyContinue')
    log('stop', f'pids={pids} cancelled={len(sess)} force={args.force}')
    print(f'STOPPED: 原 pids={pids}, 已 cancel {len(sess)} 个活跃会话')
    print('注: descriptor 会陈旧——用 status 核对真实进程，不要用 bridge health 判活')
    return 0


def auto_stop(args):
    """空闲 N 分钟后自动关。once=只检查一次（给计划任务/轮询用）。"""
    pids = real_dsh_pids()
    if not pids:
        if not args.once:
            print('dsh 未运行，退出')
        return 0
    sess = running_sessions()
    if sess:
        print(f'有 {len(sess)} 个活跃会话，不关')
        return 0
    # 无活跃会话：看 llama slot 最后活动 / 或简单按上次 start 时间
    idle = args.idle_minutes
    if args.once:
        # 真实空闲判据：所有会话 updatedAt 的最大值（descriptor mtime 只在启动时写，不可靠）
        last_ms = last_activity_ms()
        if last_ms is None:
            age_min = 99999  # 无会话数据 → 视为长期空闲，允许关
        else:
            age_min = (time.time() * 1000 - last_ms) / 60000
        if age_min < idle:
            print(f'真实空闲 {age_min:.1f}min < {idle}min，不关')
            return 0
        return stop(args)
    # 前台模式：每 30s 查，连续 idle 分钟无会话则关
    quiet = 0
    while True:
        s = running_sessions()
        if s:
            quiet = 0
        else:
            quiet += 0.5
            if quiet >= idle:
                return stop(args)
        time.sleep(30)


def main():
    ap = argparse.ArgumentParser(description='dsh 按需生命周期（用户决策 2026-11-22）')
    ap.add_argument('cmd', choices=['status', 'start', 'stop', 'auto-stop'])
    ap.add_argument('--force', action='store_true', help='stop: 跳过优雅 cancel 直接杀')
    ap.add_argument('--idle-minutes', type=float, default=10)
    ap.add_argument('--once', action='store_true', help='auto-stop: 只检查一次')
    args = ap.parse_args()
    return {'status': status, 'start': start, 'stop': stop, 'auto-stop': auto_stop}[args.cmd](args)


if __name__ == '__main__':
    sys.exit(main())
