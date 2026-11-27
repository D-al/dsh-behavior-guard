# -*- coding: utf-8 -*-
"""A/B 实验执行器：同一任务，对比反思捕获开/关。

方法：
  1. 通过 dsh-session-bridge 在每个会话发同一条任务消息
  2. 等会话完成（轮询 sessions）
  3. 从 trace 抽取该 sid 的指标：tool_failure / step_hard_stop / 步数 / reflection_mined
  4. 输出结构化结果到 bench/_ab_reflection_result.json

注意：开关切换需要改 preset + 重启 harness，本脚本只负责"发任务+收数据"，
      两组之间由调用方（人或上层脚本）切换配置。

用法:
  python tools/ab_reflection_runner.py <group> <n>   # group = on | off
"""
import json, subprocess, time, os, sys, datetime

BRIDGE = r'D:/Brain/workspace/bench/dsh-session-bridge'
TRACE = r'D:/Brain/workspace/bench/_trace.jsonl'
RESULT = r'D:/Brain/workspace/bench/_ab_reflection_result.json'

TASK = ('请读取 D:/Brain/workspace/bench/definitely-not-exist-ab-test.txt，'
        '如果报错就换用 D:/Brain/workspace/bench/critbank.json 读取前 3 行，'
        '然后告诉我第二段文件第一行的 id 是什么。不要做其他事。')

def bridge(args):
    r = subprocess.run(['node', 'bridge.mjs'] + args, cwd=BRIDGE,
                       capture_output=True, text=True, timeout=40)
    return r.stdout

def wait_done(sid, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = bridge(['sessions'])
        line = next((l for l in out.splitlines() if sid in l), '')
        if line and 'running=false' in line: return True
        time.sleep(5)
    return False

def metrics_for(sid):
    rows = []
    with open(TRACE, encoding='utf-8') as f:
        for l in f:
            try: d = json.loads(l)
            except Exception: continue
            if str(d.get('sid','')).startswith(sid[:8]): rows.append(d)
    from collections import Counter
    c = Counter(r.get('kind') for r in rows)
    return dict(tool_calls=c.get('tool_call',0), failures=c.get('tool_failure',0),
                hard_stop=c.get('step_hard_stop',0), mined=c.get('reflection_mined',0),
                total=len(rows))

def main():
    group = sys.argv[1] if len(sys.argv)>1 else 'on'
    n = int(sys.argv[2]) if len(sys.argv)>2 else 3
    results = []
    for i in range(n):
        out = bridge(['create', f'AB-{group}-{i}'])
        try: sid = json.loads(out)['sessionId']
        except Exception:
            print('create failed:', out[:100]); continue
        bridge(['send', sid, TASK])
        ok = wait_done(sid)
        m = metrics_for(sid)
        m.update(group=group, sid=sid, completed=ok)
        results.append(m)
        print(group, i, json.dumps(m, ensure_ascii=False))
    # 追加写结果
    old = []
    if os.path.isfile(RESULT):
        try: old = json.load(open(RESULT, encoding='utf-8'))
        except Exception: pass
    json.dump(old + results, open(RESULT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print('saved', RESULT)

if __name__ == '__main__':
    main()
