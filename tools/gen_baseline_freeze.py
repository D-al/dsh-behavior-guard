#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KR5 证据生成器：人类冻结能力基线（只记录，不标定）。

防造假铁律：
  1. target_score 只能由人类通过 --target-score 显式给出，绝不从 benchmark
     结果反推、绝不给默认值——agent 不能自己给自己定线。
  2. --approver / --adr 必填，且非空，确保冻结有署名和决策出处。
  3. sha256 是对"除 sha256 字段外的规范化内容"算出来的真实摘要，
     改任何一个字段都会让摘要对不上。
  4. --probe 只走临时路径 + 假数据，输出标 mode:"probe"，绝不写正式证据文件。

正式证据: D:/Brain/workspace/bench/_expert_baseline_frozen.json
验证器:   tools/goal_verify.py::verify_kr5
用法:
  D:/Python/python.exe -B tools/gen_baseline_freeze.py --target-score 0.82 --approver 张三 --adr ADR-012
  D:/Python/python.exe -B tools/gen_baseline_freeze.py --probe
"""
import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BENCH = Path('D:/Brain/workspace/bench')
OUT = BENCH / '_expert_baseline_frozen.json'


def canonical(obj):
    """规范化序列化：排序键 + 无多余空格，保证同一内容哈希稳定。"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def make_payload(target_score, approver, adr, probe=False):
    """组装待签名内容。target_score 原样来自人类参数，不做任何推断。"""
    payload = {
        'approved_by': approver,
        'adr': adr,
        'target_score': target_score,
        'frozen_at': datetime.now(timezone.utc).isoformat(),
        'note': 'target_score 由人类标定；本工具只记录与签名，不参与定线',
    }
    if probe:
        # PROBE 标记随内容一起进摘要，且明确标注数据为假
        payload['mode'] = 'probe'
        payload['note'] = 'PROBE 自检假数据，非人类冻结，不得用于验收'
    return payload


def sign(payload):
    """对除 sha256 外的内容做规范化哈希，返回带 sha256 的完整对象。"""
    digest = hashlib.sha256(canonical(payload).encode('utf-8')).hexdigest()
    return {**payload, 'sha256': digest}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run_probe():
    """自检：假数据 + 临时路径，验证哈希/序列化链路但不碰正式证据。"""
    fake = sign(make_payload(0.5, 'PROBE-FAKE-APPROVER', 'ADR-PROBE', probe=True))
    with tempfile.TemporaryDirectory(prefix='baseline_freeze_probe_') as tmp:
        probe_path = Path(tmp) / '_expert_baseline_frozen.json'
        write_json(probe_path, fake)
        # 回读校验哈希链完好，证明工具链可用
        back = json.loads(probe_path.read_text(encoding='utf-8'))
        signed = {k: v for k, v in back.items() if k != 'sha256'}
        assert sign(signed)['sha256'] == back['sha256'], 'probe: 摘要自检失败'
    print('=' * 64)
    print('  [PROBE] 自检模式：以下为假数据，不是正式证据，不得用于验收')
    print('=' * 64)
    print(json.dumps(fake, ensure_ascii=False, indent=2))
    print(f'[PROBE] 已写入临时路径并在退出时删除；正式文件未触碰: {OUT}')
    print('[PROBE] 结论: 哈希/序列化链路 OK；未生成任何可验收证据。')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='KR5 人类冻结基线生成器（target_score 必须由人类给出）')
    ap.add_argument('--target-score', type=float,
                    help='人类标定的目标分（必填，无默认值，禁止 agent 自定）')
    ap.add_argument('--approver', help='批准人（必填）')
    ap.add_argument('--adr', help='ADR 决策编号（必填）')
    ap.add_argument('--probe', action='store_true',
                    help='自检模式：假数据+临时路径，不写正式证据文件')
    args = ap.parse_args(argv)

    if args.probe:
        return run_probe()

    # 防造假：三个必填参数缺一即报错退出，绝不补默认值/绝不拿 benchmark 反推
    missing = []
    if args.target_score is None:
        missing.append('--target-score')
    if not args.approver or not args.approver.strip():
        missing.append('--approver')
    if not args.adr or not args.adr.strip():
        missing.append('--adr')
    if missing:
        ap.error('缺少必填参数: ' + ', '.join(missing)
                 + '（target_score 必须由人类标定，本工具拒绝猜测/造数）')

    obj = sign(make_payload(args.target_score, args.approver.strip(), args.adr.strip()))
    if OUT.exists():
        # 冻结基线是一次性人类决策，不静默覆盖；要改由人类删除后重新冻结
        print(f'ERROR: 正式基线已存在，拒绝覆盖: {OUT}', file=sys.stderr)
        return 1
    write_json(OUT, obj)
    print(f'已冻结基线 -> {OUT}')
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
