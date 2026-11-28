# -*- coding: utf-8 -*-
"""同批次随机化 A/B 判优实验执行器（2026-11-27）

关键改进：运行时动态开关（bench/_ab_mode.json），一次重启内交替跑三组，
消除之前分批跑造成的时序混杂。

用法:
  python tools/ab_randomized_runner.py <rounds> [seed]
    rounds = 每组的轮数（例如 5 = 每组5次，共15会话）
    seed   = 随机种子（默认 42，可复现）

每组样本按 seed 打乱顺序交替执行，避免"前一半 off 后一半 on"的时序偏差。
"""
import json, subprocess, time, os, sys, re, random, datetime

BRIDGE = r'D:/Brain/workspace/bench/dsh-session-bridge'
TRACE = r'D:/Brain/workspace/bench/_trace.jsonl'
MODE_FILE = r'D:/Brain/workspace/bench/_ab_mode.json'
RESULT = r'D:/Brain/workspace/bench/_ab_reflection_result.json'
LABEL = 'v2'  # 第二批实验标签（同批次随机化）

TASK = ('请读取 D:/Brain/workspace/bench/definitely-not-exist-ab-test.txt，'
        '如果报错就换用 D:/Brain/workspace/bench/critbank.json 读取前 3 行，'
        '然后告诉我第二段文件第一行的 id 是什么。不要做其他事。')

GROUPS = ['off', 'on', 'inject-on']

def bridge(args):
    r = subprocess.run(['node', 'bridge.mjs'] + args, cwd=BRIDGE,
                       capture_output=True, text=True, timeout=40)
    return r.stdout

def set_mode(mode):
    json.dump({'mode': mode, 'ts': datetime.datetime.now().isoformat()},
              open(MODE_FILE, 'w', encoding='utf-8'))

def _trace_last_ts(sid):
    """该 sid 最后一条 trace 的时间戳（ms）；无 trace 返回 0。"""
    m = re.search(r'([0-9a-f]{8})', sid)
    key = m.group(1) if m else sid[:8]
    last = 0
    try:
        with open(TRACE, encoding='utf-8') as f:
            for l in f:
                try: d = json.loads(l)
                except Exception: continue
                if str(d.get('sid','')).startswith(key):
                    ts = d.get('ts','')
                    if ts:
                        import datetime as _dt
                        try:
                            t = _dt.datetime.fromisoformat(ts.replace('Z','+00:00')).timestamp()*1000
                            last = max(last, t)
                        except Exception: pass
    except Exception: pass
    return last

def cancel_session(sid):
    """会话级硬刹车（bridge.mjs 有 cancel 命令，帮助文本没列）。
    2026-11-28 根治：runner 超时后必须 cancel，否则残留会话继续抢 llama 单槽位，
    雪球式累积到 14 个并发 → 全部排队超时。"""
    try:
        out = bridge(['cancel', sid])
        ok = 'accepted' in out
        time.sleep(3)
        # 确认已停
        s = bridge(['sessions'])
        line = next((l for l in s.splitlines() if sid in l), '')
        stopped = bool(line and 'running=false' in line)
        return ok and stopped
    except Exception as e:
        print(f'  [cancel失败] {e}', flush=True)
        return False

def wait_done(sid, soft_timeout=240, stall_ms=120000):
    """等待会话完成。根治雪球效应的关键：

    - soft_timeout: 总时长上限（240s，覆盖正常 audit 20-28s）
    - stall_ms: trace 无新事件超过 120s → 判定真卡死
    - 超时/卡死时调用 cancel_session() 硬刹车，绝不留残留
    """
    t0 = time.time()
    last_progress = time.time()
    last_ts = 0
    while time.time() - t0 < soft_timeout:
        out = bridge(['sessions'])
        line = next((l for l in out.splitlines() if sid in l), '')
        if line and 'running=false' in line:
            time.sleep(3)
            return True, None
        # trace 有推进 → 重置卡死计时
        cur = _trace_last_ts(sid)
        if cur > last_ts:
            last_ts = cur
            last_progress = time.time()
        if (time.time() - last_progress) * 1000 > stall_ms:
            stopped = cancel_session(sid)
            return False, f'stall>{stall_ms//1000}s cancel={stopped}'
        time.sleep(5)
    stopped = cancel_session(sid)
    return False, f'total>{soft_timeout}s cancel={stopped}'

def restart_dsh():
    """重启 dsh 清理冻死会话（需已登录，走计划任务）。"""
    try:
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        "Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue | Stop-Process -Force; "
                        "Start-Sleep -Seconds 5; "
                        "Get-Process -Name 'llama-server' -ErrorAction SilentlyContinue | Stop-Process -Force; "
                        "Start-Sleep -Seconds 3; "
                        "Stop-ScheduledTask -TaskName RestartDsh -ErrorAction SilentlyContinue; "
                        "Start-ScheduledTask -TaskName RestartDsh"],
                       capture_output=True, text=True, timeout=60)
        time.sleep(25)
        return True
    except Exception as e:
        print(f'  [重启失败] {e}', flush=True)
        return False

def metrics_for(sid):
    m = re.search(r'([0-9a-f]{8})', sid)
    key = m.group(1) if m else sid[:8]
    from collections import Counter
    c = Counter()
    with open(TRACE, encoding='utf-8') as f:
        for l in f:
            try: d = json.loads(l)
            except Exception: continue
            if str(d.get('sid','')).startswith(key): c[d.get('kind')] += 1
    return dict(tool_calls=c.get('tool_call',0), failures=c.get('tool_failure',0),
                hard_stop=c.get('step_hard_stop',0), mined=c.get('reflection_mined',0),
                live_injected=c.get('reflection_live_injected',0),
                total=sum(c.values()))

def main():
    rounds = int(sys.argv[1]) if len(sys.argv)>1 else 5
    seed = int(sys.argv[2]) if len(sys.argv)>2 else 42
    append = '--append' in sys.argv  # 追加到已有批次（换seed避免重复顺序）
    random.seed(seed)
    order = GROUPS * rounds
    random.shuffle(order)  # 同批次内随机交错
    print(f'批次={LABEL} rounds={rounds} seed={seed} 总会话={len(order)}')
    print('顺序:', '→'.join(order))
    results = []
    frozen_streak = 0  # 2026-11-28: 连续冻死计数，>=2 自动重启
    for i, group in enumerate(order):
        set_mode(group)
        time.sleep(1)  # 等 harness mtime 缓存失效（下次事件读取）
        out = bridge(['create', f'AB2-{group[:2]}-{i}'])
        try: sid = json.loads(out)['sessionId']
        except Exception:
            print('create failed:', out[:100]); continue
        # create 之后再写一次，确保会话开始时模式已生效
        set_mode(group)
        bridge(['send', sid, TASK])
        ok, reason = wait_done(sid)
        if ok:
            frozen_streak = 0
        else:
            frozen_streak += 1
            print(f'  [已取消] {sid[:14]} {reason}', flush=True)
            # 根治：超时已 cancel，不再累积残留 → 不需要粗暴重启
            # 仅当 cancel 连续失败多次才重启兜底
            if frozen_streak >= 4:
                print('  [兜底重启] 连续 4 次失败，重启 dsh', flush=True)
                restart_dsh()
                frozen_streak = 0
            continue  # 不记录污染数据
        m = metrics_for(sid)
        m.update(group=group, sid=sid, completed=ok, batch=LABEL, seed=seed, order=i)
        # 错误类型记录（2026-11-28 用户要求：尤其标记新类型）
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from ab_error_recorder import record_session
            codes, novel_n, novel_b = record_session(sid, group, mode=group)
            m['error_codes'] = codes
            m['novel_narrow'] = novel_n
            m['novel_broad'] = novel_b
        except Exception as e:
            m['error_codes'] = []
            m['error_record_error'] = str(e)[:100]
        results.append(m)
        print(f'[{i+1}/{len(order)}] {group:10s} {sid[:14]} '
              f'calls={m["tool_calls"]} fail={m["failures"]} hs={m["hard_stop"]} '
              f'mined={m["mined"]} inject={m["live_injected"]} done={ok}', flush=True)
        # 增量保存（防中断丢数据）：按 sid 全局去重，避免重复追加
        old = []
        if os.path.isfile(RESULT):
            try: old = json.load(open(RESULT, encoding='utf-8'))
            except Exception: old = []
        merged, seen = [], set()
        for r in old + results:
            s = r.get('sid')
            if s and s in seen: continue
            if s: seen.add(s)
            merged.append(r)
        json.dump(merged, open(RESULT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    set_mode('off')  # 实验结束恢复默认（生产安全）
    print('完成，模式已恢复 off')

if __name__ == '__main__':
    main()
