# -*- coding: utf-8 -*-
"""trace_report —— 读 _trace.jsonl，按会话统计成本与行为分布

用法:
  python bench/trace_report.py                 # 最近 3 个会话
  python bench/trace_report.py --all           # 全部
  python bench/trace_report.py --sid abc12345  # 指定会话
"""
import json
import os
import sys
from collections import Counter, defaultdict

TRACE = r'D:\Brain\workspace\bench\_trace.jsonl'


def load():
    if not os.path.exists(TRACE):
        print('尚无 trace 记录:', TRACE)
        sys.exit(0)
    rows = []
    for line in open(TRACE, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def main():
    args = sys.argv[1:]
    rows = load()
    if not rows:
        print('trace 为空')
        return

    # 按会话分组
    by_sid = defaultdict(list)
    for r in rows:
        by_sid[r.get('sid', '?')].append(r)

    if '--sid' in args:
        target = args[args.index('--sid') + 1]
        sids = [target] if target in by_sid else []
    elif '--all' in args:
        sids = list(by_sid)
    else:
        # 最近 3 个（按最后一条时间）
        ordered = sorted(by_sid.items(), key=lambda kv: kv[1][-1].get('ts', ''))
        sids = [k for k, _ in ordered[-3:]]

    total_llm_ms = 0
    total_llm_calls = 0
    total_retries = 0
    tool_counter = Counter()
    status_counter = Counter()

    for sid in sids:
        rs = by_sid[sid]
        steps = max((r.get('step') or 0) for r in rs) if rs else 0
        llm = [r for r in rs if r.get('kind') == 'llm']
        tools = [r for r in rs if r.get('kind') == 'tool_call']
        results = [r for r in rs if r.get('kind') == 'tool_result']
        llm_ms = sum(r.get('ms') or 0 for r in llm)
        fails = [r for r in results if r.get('status') not in ('OK', None)]
        print(f'── 会话 {sid} ──')
        print(f'  步数 {steps}｜工具调用 {len(tools)} 次｜工具失败 {len(fails)} 次')
        print(f'  LLM 调用 {len(llm)} 次（审计/纠正/评审/规划）｜累计 {llm_ms / 1000:.1f}s｜重试 {sum(1 for r in llm if r.get("retry"))} 次')
        if tools:
            top = Counter(r.get('name') for r in tools).most_common(6)
            print('  工具分布: ' + '｜'.join(f'{k}×{v}' for k, v in top))
        if llm:
            tags = Counter(r.get('tag') for r in llm)
            print('  LLM 按类型: ' + '｜'.join(f'{k}×{v}' for k, v in tags.items()))
            bad = [r for r in llm if not r.get('ok')]
            if bad:
                print(f'  ⚠ 解析失败 {len(bad)} 次（已含重试）')
        total_llm_ms += llm_ms
        total_llm_calls += len(llm)
        total_retries += sum(1 for r in llm if r.get('retry'))
        tool_counter.update(r.get('name') for r in tools)
        status_counter.update(r.get('status') for r in results)
        print()

    print('══ 合计 ══')
    print(f'  LLM 调用 {total_llm_calls} 次｜{total_llm_ms / 1000:.1f}s｜重试 {total_retries} 次')
    if tool_counter:
        print('  工具总分布: ' + '｜'.join(f'{k}×{v}' for k, v in tool_counter.most_common(10)))
    if status_counter:
        print('  工具状态: ' + '｜'.join(f'{k}×{v}' for k, v in status_counter.items()))
    print()
    print('提示：LLM 调用耗时占比 = 审计/评审开销；工具失败率高 → 查 CritBank 对应条目')


if __name__ == '__main__':
    main()
