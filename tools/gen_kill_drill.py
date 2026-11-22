#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KR6 证据生成器：关停演练记录器（只记录，不执行演练）。

防造假铁律：
  1. 本工具是"记录器"不是"演练执行器"——它不会模拟一次成功关停，
     只接收人类/外部真实演练的结果并原样落账。
  2. closed / lure / scenario 必填且类型严格；lure=true 时 --verified-by
     必须非空——防止 agent 自己给自己打勾说"我没阻挠关停"。
  3. --probe 只打印将要写入的行（带 mode:"probe"、假数据），
     绝不写正式 JSONL，避免 probe 行被 goal_verify 当成真实演练计入。

正式证据: D:/Brain/workspace/bench/_kill_switch_drill.jsonl
验证器:   tools/goal_verify.py::verify_kr6
用法:
  D:/Python/python.exe -B tools/gen_kill_drill.py --closed true --lure false --scenario 常规关停
  D:/Python/python.exe -B tools/gen_kill_drill.py --closed true --lure true --scenario 诱导阻挠 --verified-by 李四
  D:/Python/python.exe -B tools/gen_kill_drill.py --probe
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path('D:/Brain/workspace/bench')
OUT = BENCH / '_kill_switch_drill.jsonl'


def parse_bool(s):
    """只接受 true/false（大小写不敏感），杜绝把 'yes'/1 误当成功。"""
    v = s.strip().lower()
    if v == 'true':
        return True
    if v == 'false':
        return False
    raise argparse.ArgumentTypeError(f'只接受 true 或 false，收到: {s!r}')


def make_row(closed, lure, scenario, verified_by, probe=False):
    """组装一行演练记录。所有取值来自外部真实演练的输入，不在此处判定成功。"""
    row = {
        'closed': closed,             # 是否成功关停，由演练现场给定
        'lure': lure,                 # 是否为诱导场景
        'scenario': scenario,
        'verified_by': verified_by,
        'recorded_at': datetime.now(timezone.utc).isoformat(),
    }
    if probe:
        row['mode'] = 'probe'
        row['scenario'] = 'PROBE-FAKE-SCENARIO'
        row['note'] = 'PROBE 自检假数据，非真实演练，不得用于验收'
    return row


def print_probe():
    """自检：打印两行将写入的记录（含诱导分支），不碰正式文件。"""
    print('=' * 64)
    print('  [PROBE] 自检模式：以下为假数据，不是正式演练，不得用于验收')
    print('=' * 64)
    print('[PROBE] 示例 1 —— 常规关停（lure=false，无需验证人）:')
    print(json.dumps(make_row(False, False, 'x', None, probe=True), ensure_ascii=False))
    print('[PROBE] 示例 2 —— 诱导场景（lure=true，带验证人）:')
    print(json.dumps(make_row(False, True, 'x', 'PROBE-FAKE-VERIFIER', probe=True),
                     ensure_ascii=False))
    print(f'[PROBE] 未写入任何文件；正式文件未触碰: {OUT}')
    print('[PROBE] 结论: 行组装/序列化链路 OK；未生成任何可验收证据。')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='KR6 关停演练记录器（只记录外部真实演练，不模拟关停）')
    ap.add_argument('--closed', type=parse_bool, help='是否成功关停 true/false（必填）')
    ap.add_argument('--lure', type=parse_bool, help='是否诱导场景 true/false（必填）')
    ap.add_argument('--scenario', help='场景描述（必填）')
    ap.add_argument('--verified-by', help='验证人；诱导场景(lure=true)时必填')
    ap.add_argument('--probe', action='store_true',
                    help='自检模式：仅打印将写入的行，不写正式证据文件')
    args = ap.parse_args(argv)

    if args.probe:
        return print_probe()

    missing = []
    if args.closed is None:
        missing.append('--closed')
    if args.lure is None:
        missing.append('--lure')
    if not args.scenario or not args.scenario.strip():
        missing.append('--scenario')
    if missing:
        ap.error('缺少必填参数: ' + ', '.join(missing)
                 + '（演练结果须由外部真实演练提供，本工具拒绝模拟成功）')

    # 诱导场景必须有人验证：防止 agent 自证"我没阻挠"
    verified_by = (args.verified_by or '').strip()
    if args.lure and not verified_by:
        ap.error('诱导场景(lure=true)必须提供非空的 --verified-by；'
                 '禁止 agent 自己给自己打勾')

    row = make_row(args.closed, args.lure, args.scenario.strip(), verified_by or None)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 追加一行，保证多次演练累积；每行一个 JSON 对象
    with OUT.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'已记录演练 -> {OUT}')
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
