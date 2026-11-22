#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skills 双轨受控重复实验 runner（2026-11-22 第二版）

修正上一版三个缺陷：
1. 每个 run 新建会话（技能卡 per-session 只注入一次，同会话会假阴性）
2. 严格等自然结束：轮询会话文件 turn/end(reason.completed) + 文件大小连续稳定，不用会超时的 watch
3. 轻量任务：1-2 步直接回答，不写文件，避免 D1 守卫/反复修正污染工具计数

用法：
  python tools/skills_ab_runner.py run <mode> <scenario> <idx>
      mode: on|off   scenario: common|rare   idx: 1..N
  python tools/skills_ab_runner.py tally    # 汇总所有 run 结果
"""
import argparse, glob, json, os, subprocess, sys, time
from collections import Counter
from pathlib import Path

BRIDGE = Path('D:/Brain/workspace/bench/dsh-session-bridge/bridge.mjs')
SESS_ROOT = Path('D:/Brain/dsh-data/sessions')
RESULTS = Path('D:/Brain/_cleanup_20261118/skills_ab_runs.jsonl')
POLL_SEC = 12
STABLE_N = 3          # 连续3次文件大小不变 = 结束
MAX_SEC = 180         # 单run上限3分钟(轻量任务正常60s;超时记为未结束继续下一个)

# 轻量任务：只需1-2步工具调用 + 直接回答，绝不写文件
TASKS = {
    'common': ('只做一个动作：用 glob 列出 D:/Brain/publish/dsh-behavior-guard/tools 目录下 test_*.py 文件，'
               '然后直接告诉我文件数量。不要写任何文件，不要做其它事。'),
    'rare': ('只做一个动作：用 pwsh 查询当前是否有 llama-server 进程在运行，然后直接告诉我结果。'
             '这是排查 llama-server 卡死/显存不足的第一步。不要写任何文件，不要做其它事。'),
}


def bridge(*args, timeout=60):
    r = subprocess.run(['node', str(BRIDGE), *args], capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.returncode


def session_dir(sid):
    """找 sid 对应的落盘目录（workspace 前缀不固定）。"""
    hits = glob.glob(str(SESS_ROOT / '**' / sid / 'session.v4.jsonl.zstd'), recursive=True)
    return Path(hits[0]) if hits else None


def wait_natural_end(sid, zstd):
    """严格等自然结束：出现 turn/end(reason=completed)。
    修正(2026-11-22)：原判据额外要求'文件大小连续3次不变'，但 zstd 文件即使无新事件
    也会内部刷新改变大小 → 首run会话已 completed 却一直判不结束，白等480s。
    turn/end(completed) 本身就是权威自然结束信号，无需再叠加文件稳定判据。"""
    import zstandard
    d = zstandard.ZstdDecompressor()
    t0 = time.time()
    while time.time() - t0 < MAX_SEC:
        try:
            data = d.stream_reader(open(zstd, 'rb')).read().decode('utf-8', errors='replace')
            ev = [json.loads(l) for l in data.splitlines() if l.strip()]
            done = [e for e in ev if e.get('type') == 'turn/end'
                    and (e.get('data') or {}).get('reason', {}).get('kind') == 'completed']
            if done:
                return True, len(done), int(time.time() - t0)
        except Exception:
            pass
        time.sleep(POLL_SEC)
    return False, 0, int(time.time() - t0)


def collect(zstd):
    import zstandard
    d = zstandard.ZstdDecompressor()
    data = d.stream_reader(open(zstd, 'rb')).read().decode('utf-8', errors='replace')
    ev = [json.loads(l) for l in data.splitlines() if l.strip()]
    tools = Counter()
    inject = 0
    turns = 0
    for e in ev:
        t = e.get('type')
        if t == 'tool/call':
            tools[(e.get('data') or {}).get('name', '?')] += 1
        if t == 'user/message' and '[harness 技能可用]' in json.dumps(e, ensure_ascii=False):
            inject += 1
        if t == 'turn/end':
            turns += 1
    return {'tools': dict(tools), 'inject': inject, 'events': len(ev), 'turns': turns}


def do_run(mode, scenario, idx):
    sid_out, rc = bridge('create', f'AB2-{mode}-{scenario}-{idx}')
    try:
        sid = json.loads(sid_out)['sessionId']
    except Exception:
        print(f'CREATE_FAIL: {sid_out[:200]}'); return 1
    print(f'[{mode}/{scenario}#{idx}] sid={sid}', flush=True)
    send_out, rc = bridge('send', sid, TASKS[scenario])
    if '"accepted": true' not in send_out:
        print(f'  SEND_FAIL: {send_out[:160]}'); return 1

    zstd = None
    for _ in range(10):
        zstd = session_dir(sid)
        if zstd: break
        time.sleep(2)
    if not zstd:
        print('  NO_ZSTD'); return 1

    ok, turns, secs = wait_natural_end(sid, zstd)
    c = collect(zstd)
    row = {'mode': mode, 'scenario': scenario, 'idx': idx, 'sid': sid,
           'natural_end': ok, 'completed_turns': turns, 'wait_sec': secs, **c}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'  end={ok} turns={turns} wait={secs}s tools={c["tools"]} inject={c["inject"]}', flush=True)
    return 0 if ok else 2


def rebuild_tally():
    """从会话文件重建统计（权威证据源）——runner的wait有时漏记，会话文件不会。
    按模式切换时间点区分 ON/OFF（本次实验：ON 18:26-18:35 / OFF 18:39-18:44）。"""
    import zstandard
    from datetime import datetime
    zstd = zstandard.ZstdDecompressor()
    CUTOFF = datetime(2026, 11, 22, 18, 38).timestamp()  # OFF 切换时刻
    rows = []
    for f in glob.glob(str(SESS_ROOT / '**' / 'session.v4.jsonl.zstd'), recursive=True):
        if os.path.getmtime(f) < datetime(2026, 11, 22, 18, 20).timestamp():
            continue
        try:
            ev = [json.loads(l) for l in zstd.stream_reader(open(f, 'rb')).read()
                  .decode('utf-8', errors='replace').splitlines() if l.strip()]
        except Exception:
            continue
        first = ''
        for e in ev:
            if e.get('type') == 'user/message':
                txt = (e.get('data', {}).get('content') or [{}])[0].get('text', '')
                if '只做一个动作' in txt:
                    first = txt; break
        if not first:
            continue
        mode = 'off' if os.path.getmtime(f) > CUTOFF else 'on'
        scenario = 'common' if 'glob' in first else 'rare'
        tools = Counter((e.get('data') or {}).get('name', '?')
                        for e in ev if e.get('type') == 'tool/call')
        inj = sum(1 for e in ev if '[harness 技能可用]' in json.dumps(e, ensure_ascii=False))
        done = any(e.get('type') == 'turn/end'
                   and (e.get('data') or {}).get('reason', {}).get('kind') == 'completed'
                   for e in ev)
        rows.append({'mode': mode, 'scenario': scenario, 'sid': Path(f).parent.name,
                     'natural_end': done, 'inject': inj, 'tools': dict(tools)})
    # 写权威结果文件
    with RESULTS.open('w', encoding='utf-8') as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'从会话文件重建 {len(rows)} 条 run')
    return 0


def tally():
    rows = [json.loads(l) for l in RESULTS.read_text(encoding='utf-8').splitlines() if l.strip()] if RESULTS.exists() else []
    by = {}
    for r in rows:
        k = (r['mode'], r['scenario'])
        by.setdefault(k, []).append(r)
    print(f'总run数: {len(rows)}')
    for k in sorted(by):
        rs = by[k]
        print(f'\n{mode_name(k[0])} / {k[1]}  n={len(rs)}')
        for r in rs:
            print(f'  {r.get("sid","?")[:20]}: end={r["natural_end"]} inject={r["inject"]} '
                  f'tools={sum(r["tools"].values())} {r["tools"]}')
        inj = [r['inject'] for r in rs]
        tc = [sum(r['tools'].values()) for r in rs]
        print(f'  → inject均值={sum(inj)/len(inj):.2f} 工具调用均值={sum(tc)/len(tc):.1f} '
              f'自然结束={sum(1 for r in rs if r["natural_end"])}/{len(rs)}')
    return 0


def mode_name(m):
    return 'ON(注入)' if m == 'on' else 'OFF(关闭)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'tally', 'rebuild', 'tasks'])
    ap.add_argument('mode', nargs='?', choices=['on', 'off'])
    ap.add_argument('scenario', nargs='?', choices=['common', 'rare'])
    ap.add_argument('idx', nargs='?', type=int)
    args = ap.parse_args()
    if args.cmd == 'run':
        if not all([args.mode, args.scenario, args.idx]):
            print('run 需要 mode scenario idx'); return 2
        return do_run(args.mode, args.scenario, args.idx)
    if args.cmd == 'tally': return tally()
    if args.cmd == 'rebuild': return rebuild_tally()
    if args.cmd == 'tasks':
        print(json.dumps(TASKS, ensure_ascii=False, indent=2)); return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
