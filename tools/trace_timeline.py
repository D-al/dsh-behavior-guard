# -*- coding: utf-8 -*-
"""trace_timeline —— 失败时间线分析（t_err / t_lock / t_obs）

依据（Part 8 G3）：
- Failure as a Process (UCL+NJU, 2026-07)：1,794 条 CLI agent 轨迹——决定性错误中位
  **step 7**、step 8 锁定、step 16 才首次可见；epistemic 错误占 57.9%，
  "基于未验证假设行动"是最大触发（30.7%）；82% 的 agent 在不可恢复后仍继续执行。
- AgentRx (arXiv 2602.02475)：关键失败步定位 +75%。

我们的启发式映射（针对 _trace.jsonl 的字段）：
  t_err  ≈ 首个 tool_result 非 OK（第一次认知错误的外在表现）
  t_lock ≈ 连续 2 次同类失败（D2 触发点 =  empirically unrecoverable 的代理）
  t_obs  ≈ 首次 harness 风险注入（audit / critic / 深检 / D4）——系统"发现"问题的时刻
  lag = t_obs - t_err  → 我们的门控滞后多少步（论文中位数是 9 步）

用途：回答"D5 门控是否太晚"——若 lag 大，则考虑把触发条件前移（G5 校准的输入）。

用法:
  python bench/trace_timeline.py           # 分析最近 5 个会话
  python bench/trace_timeline.py --all     # 全部
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
TRACE = str(Path(BENCH_DIR) / '_trace.jsonl')


def analyze(seq):
    """返回 (t_err, t_lock, t_obs, kind) 或 None"""
    t_err = t_lock = t_obs = None
    consecutive_fail = 0
    prev_fail_name = None
    for r in seq:
        step = r.get('step', 0) or 0
        kind = r.get('kind', '')
        if kind == 'tool_result':
            ok = r.get('status') == 'OK'
            name = r.get('name')
            if not ok:
                if t_err is None:
                    t_err = step
                if name == prev_fail_name:
                    consecutive_fail += 1
                else:
                    consecutive_fail = 1
                prev_fail_name = name
                if consecutive_fail >= 2 and t_lock is None:
                    t_lock = step
            else:
                consecutive_fail = 0
                prev_fail_name = None
        elif kind == 'llm':
            tag = r.get('tag', '')
            if tag in ('audit', 'critic', 'planner') and t_obs is None:
                if t_err is None or step >= t_err:
                    t_obs = step
        elif kind in ('control_turn',) and t_obs is None:
            # 控制回合不算"问题被观察"，只是例行——跳过
            pass
    if t_err is None:
        return None
    # 有效性约束：t_lock/t_obs 不能早于 t_err（测试数据的 step=0 会违反）
    if t_lock is not None and t_lock < t_err:
        t_lock = None
    if t_obs is not None and t_obs < t_err:
        t_obs = None
    return t_err, t_lock, t_obs


def main():
    args = sys.argv[1:]
    rows = []
    if not os.path.exists(TRACE):
        print('无 trace:', TRACE)
        sys.exit(0)
    for line in open(TRACE, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass

    by_sid = defaultdict(list)
    for r in rows:
        by_sid[r.get('sid', '?')].append(r)
    for sid in by_sid:
        by_sid[sid].sort(key=lambda x: x.get('ts', ''))

    sids = list(by_sid) if '--all' in args else list(by_sid)[-5:]
    lags = []
    print('会话       t_err  t_lock  t_obs  lag(obs-err)  说明')
    print('-' * 68)
    for sid in sids:
        res = analyze(by_sid[sid])
        if not res:
            print(f'{sid:<10} (无失败)')
            continue
        t_err, t_lock, t_obs = res
        lag = (t_obs - t_err) if t_obs is not None else None
        if lag is not None:
            lags.append(lag)
        note = ''
        if t_lock is not None and t_obs is not None and t_obs > t_lock:
            note = '观察到时已锁定（滞后）'
        elif lag is not None and lag <= 1:
            note = '及时'
        print(f'{sid:<10} {str(t_err):>5}  {str(t_lock):>6}  {str(t_obs):>5}  '
              f'{str(lag) if lag is not None else "—":>12}  {note}')

    if lags:
        lags.sort()
        med = lags[len(lags) // 2]
        print('-' * 68)
        print(f'滞后中位数 {med} 步（论文中位 9 步）；样本 {len(lags)} 个会话')
        if med >= 3:
            print('→ 建议：D5 门控前移（G5 校准阈值），或用 t_err 启发式做事前信号')
        else:
            print('→ 门控基本及时，优先做 G5 概率校准而非前移阈值')


if __name__ == '__main__':
    main()
