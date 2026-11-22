#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KR4 感知-行动：事件回放结果生成器（只读真实 trace，绝不造数）

严格对齐 tools/goal_verify.py::verify_kr4 的判据：
  证据文件 D:/Brain/workspace/bench/_event_replay_results.jsonl（JSONL）
  每行 action（非空字符串）+ evidence（非空字符串） → 全部满足才 PASS；空文件 → N/M。

防造假设计（铁律，改动前先读）：
  1. 唯一真实来源：_trace.jsonl 里真实发生的 tool_call → tool_result 配对
     （同 sid / 同 step / 同 name，按出现顺序 FIFO 配对），或用户显式传入的
     --event-file 预埋事件定义。action 只能取真实 tool_call.name，
     evidence 只能由真实 tool_result 字段拼出。缺字段就跳过，绝不补造。
  2. 绝不生成虚构的"事件发生了 + 有动作"记录。没有配对就没有输出行；
     配对为空 → N/M 退出（码 2），不写空文件、不用占位数据充数。
  3. 过滤 test_sids.json 黑名单中的 sid（s1 / budget-* / 各类测试会话）。
     这些是探针/测试会话，与 goal_verify.py 跳过 s1 的口径一致，
     不能拿它们冒充真实事件刷证据；mode=probe 的行也一并排除。
  4. 输出行附 sid / step / tool / source 便于外部抽检来源（判据忽略额外字段）。
  5. --probe 自测：只取前 N 对（默认 3），每行带 mode:"probe"，
     只打印到 stdout，绝不写正式证据文件，也绝不带 mode 写盘。

用法:
  python tools/gen_event_replay.py                       # 从真实 trace 生成正式证据
  python tools/gen_event_replay.py --probe               # 自测：前 3 对，仅打印
  python tools/gen_event_replay.py --probe --limit 10
  python tools/gen_event_replay.py --event-file events.jsonl
退出码: 0=已写出证据/probe 成功; 1=输入或校验错误; 2=N/M(缺真实来源，未写文件)
"""
import argparse
import json
import os
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = Path('D:/Brain/workspace/bench')
TRACE = BENCH / '_trace.jsonl'
OUT = BENCH / '_event_replay_results.jsonl'
TEST_SIDS_FILE = ROOT / 'test_sids.json'

# 退出码与 goal_verify.py 对齐：0=PASS/成功, 1=FAIL/错误, 2=NOT_MEASURABLE
EXIT_OK, EXIT_ERR, EXIT_NM = 0, 1, 2


def nm(why, prerequisite):
    """缺真实来源时明确报 N/M，不写任何文件（防假绿）。"""
    print(f'NOT_MEASURABLE: {why}', file=sys.stderr)
    print(f'  前置依赖: {prerequisite}', file=sys.stderr)
    return EXIT_NM


def load_test_sids(path):
    """读取 sid 黑名单（单一事实源）。缺失时告警并返回空集，不用内置名单硬编码。"""
    if not path.exists():
        print(f'警告: 找不到 sid 黑名单 {path}，本次不过滤测试会话', file=sys.stderr)
        return set()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        print(f'警告: 无法解析 {path}: {e}，本次不过滤测试会话', file=sys.stderr)
        return set()
    return set(str(x) for x in data.get('sids', []))


def iter_jsonl(path):
    """逐行解析 JSONL；坏行跳过（不猜、不修补）。"""
    bad = 0
    with path.open(encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f'警告: {path} 有 {bad} 行解析失败，已跳过', file=sys.stderr)


def pair_key(row):
    """配对键：同 sid + 同 step + 同名工具，避免跨会话/跨步骤错配。"""
    return (row.get('sid'), row.get('step'), row.get('name'))


def extract_pairs(trace_path, test_sids, limit=None):
    """从真实 trace 提取 tool_call→tool_result 配对（FIFO，不造缺结果的行）。"""
    pending = defaultdict(deque)
    pairs = []
    skipped_test = 0
    for row in iter_jsonl(trace_path):
        sid = row.get('sid')
        if sid in test_sids or row.get('mode') == 'probe':
            skipped_test += 1
            continue
        kind = row.get('kind')
        name = row.get('name')
        if kind not in ('tool_call', 'tool_result') or not name:
            continue
        key = pair_key(row)
        if kind == 'tool_call':
            pending[key].append(row)
        elif pending[key]:
            # 真实结果必须对应一个真实发生过的调用；无调用的结果直接丢弃
            pairs.append((pending[key].popleft(), row))
            if limit is not None and len(pairs) >= limit:
                break
    if skipped_test:
        print(f'已排除 {skipped_test} 条测试/探针会话事件（sid 黑名单或 mode=probe）',
              file=sys.stderr)
    return pairs


def row_from_pair(call, result, source):
    """action 取真实 tool_call.name；evidence 仅由真实 tool_result 字段拼出。"""
    action = str(call.get('name') or '').strip()
    status = result.get('status')
    # status 是 tool_result 的核心证据字段；缺失则视为无效配对，直接跳过
    if not action or not status:
        return None
    parts = [f'status={status}']
    for k in ('ms', 'outChars'):
        if result.get(k) is not None:
            parts.append(f'{k}={result[k]}')
    evidence = 'tool_result ' + ' '.join(parts) + (
        f' sid={call.get("sid")} step={call.get("step")}'
    )
    return {
        'action': action,
        'evidence': evidence,
        'sid': call.get('sid'),
        'step': call.get('step'),
        'tool': action,
        'source': str(source),
    }


def load_event_file(event_path, limit=None):
    """外部预埋事件定义：每行须自带非空 action + evidence，缺一不补造。"""
    rows = []
    skipped = 0
    for row in iter_jsonl(event_path):
        if not isinstance(row.get('action'), str) or not row['action'].strip():
            skipped += 1
            continue
        if not isinstance(row.get('evidence'), str) or not row['evidence'].strip():
            skipped += 1
            continue
        out = dict(row)
        out.setdefault('source', str(event_path))
        rows.append(out)
        if limit is not None and len(rows) >= limit:
            break
    if skipped:
        print(f'事件文件有 {skipped} 行缺 action/evidence，已跳过（不补造）', file=sys.stderr)
    return rows


def validate_rows(rows):
    """复刻 verify_kr4：每行都必须有非空 action + evidence。"""
    return all(isinstance(r.get('action'), str) and r['action'].strip()
               and isinstance(r.get('evidence'), str) and r['evidence'].strip()
               for r in rows)


def write_atomic(rows, out_path):
    """校验通过后才原子落盘，避免写半个证据文件。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    os.replace(str(tmp), str(out_path))


def main():
    ap = argparse.ArgumentParser(
        description='KR4 事件回放结果生成器：只从真实 trace/预埋事件取数，绝不造数')
    ap.add_argument('--probe', action='store_true',
                    help='自测模式：只处理前 N 条并打印，带 mode:probe，不写正式文件')
    ap.add_argument('--limit', type=int, default=None,
                    help='只处理前 N 条（probe 默认 3）；真实模式默认处理全部')
    ap.add_argument('--trace', type=Path, default=TRACE,
                    help=f'trace 路径（默认 {TRACE}）')
    ap.add_argument('--event-file', type=Path, default=None,
                    help='外部预埋事件定义 JSONL（提供时替代 trace 作为真实来源）')
    ap.add_argument('--out', type=Path, default=OUT,
                    help=f'正式输出路径（默认 {OUT}）')
    args = ap.parse_args()

    limit = args.limit if args.limit is not None else (3 if args.probe else None)
    if limit is not None and limit <= 0:
        print('错误: --limit 必须为正整数', file=sys.stderr)
        return EXIT_ERR

    if args.event_file is not None:
        if not args.event_file.exists():
            return nm(f'事件文件不存在: {args.event_file}', '提供含 action/evidence 的真实事件定义')
        rows = load_event_file(args.event_file, limit=limit)
    else:
        if not args.trace.exists():
            return nm(f'trace 不存在: {args.trace}', '生成 _trace.jsonl（真实 tool_call/result 打点）')
        pairs = extract_pairs(args.trace, load_test_sids(TEST_SIDS_FILE), limit=limit)
        rows = []
        for call, result in pairs:
            row = row_from_pair(call, result, args.trace)
            if row is not None:
                rows.append(row)

    if not rows:
        return nm('未找到任何真实 tool_call→tool_result 配对（或事件文件无有效行）',
                  '积累真实工具调用打点，或提供 --event-file 预埋事件定义')

    if not validate_rows(rows):
        print('错误: 存在缺 action/evidence 的行，拒绝写出', file=sys.stderr)
        return EXIT_ERR

    if args.probe:
        for r in rows:
            print(json.dumps({**r, 'mode': 'probe'}, ensure_ascii=False))
        print(f'[probe] 已打印 {len(rows)} 条（mode=probe），未写正式文件 {args.out}',
              file=sys.stderr)
        return EXIT_OK

    write_atomic(rows, args.out)
    print(f'已写出 {len(rows)} 条真实事件回放结果 → {args.out}')
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
