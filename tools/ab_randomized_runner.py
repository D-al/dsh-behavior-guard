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

def wait_done(sid, timeout=240):
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = bridge(['sessions'])
        line = next((l for l in out.splitlines() if sid in l), '')
        if line and 'running=false' in line:
            time.sleep(3)
            return True
        time.sleep(5)
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
    random.seed(seed)
    order = GROUPS * rounds
    random.shuffle(order)  # 同批次内随机交错
    print(f'批次={LABEL} rounds={rounds} seed={seed} 总会话={len(order)}')
    print('顺序:', '→'.join(order))
    results = []
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
        ok = wait_done(sid)
        m = metrics_for(sid)
        m.update(group=group, sid=sid, completed=ok, batch=LABEL, seed=seed, order=i)
        results.append(m)
        print(f'[{i+1}/{len(order)}] {group:10s} {sid[:14]} '
              f'calls={m["tool_calls"]} fail={m["failures"]} hs={m["hard_stop"]} '
              f'mined={m["mined"]} inject={m["live_injected"]} done={ok}', flush=True)
        # 增量保存（防中断丢数据）：保留非本批次记录 + 本批次已完成记录
        old = []
        if os.path.isfile(RESULT):
            try: old = json.load(open(RESULT, encoding='utf-8'))
            except Exception: old = []
        keep = [r for r in old if r.get('batch') != LABEL]
        json.dump(keep + results, open(RESULT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    set_mode('off')  # 实验结束恢复默认（生产安全）
    print('完成，模式已恢复 off')

if __name__ == '__main__':
    main()
