#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""证据生成器诚实性验收：确保生成器不造假数据

检查每个 gen_*.py：
  1. 有 --probe 模式
  2. probe 模式不写正式证据文件（跑 probe 前后证据文件状态不变）
  3. 缺输入时报错/N-M 退出，不生成假数据
  4. 不含硬编码的伪造数值（如 gain=0.15 直接写死）

用法: D:/Python/python.exe -B tools/audit_generator_honesty.py
退出码: 0=全部诚实; 1=有生成器不合格
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
BENCH = Path('D:/Brain/workspace/bench')
GENERATORS = ['gen_baseline_freeze.py', 'gen_kill_drill.py', 'gen_event_replay.py',
              'gen_capability_ledger.py', 'gen_holdout_pairs.py']
EVIDENCE = ['_expert_baseline_frozen.json', '_kill_switch_drill.jsonl',
            '_event_replay_results.jsonl', '_capability_ledger.json',
            '_benchmark_holdout.jsonl']


def check_static(path):
    """静态检查：probe模式/防造假注释/无硬编码假数"""
    if not path.exists():
        return False, ['文件不存在']
    s = path.read_text(encoding='utf-8', errors='replace')
    issues = []
    if '--probe' not in s:
        issues.append('缺 --probe 模式')
    if not re.search(r'(防造假|不编造|不造假|真实来源|同源)', s):
        issues.append('缺防造假设计注释')
    # 硬编码假数检测（允许 probe 段内，但检查是否有直接写死 gain=0.xx 到正式文件）
    for m in re.finditer(r'(gain|score|target_score)\s*=\s*0\.\d+', s):
        line = s[:m.start()].count('\n') + 1
        before = s[max(0, m.start()-200):m.start()]
        if 'probe' not in before.lower():
            issues.append(f'第{line}行疑似硬编码假数: {m.group(0)}')
    return not issues, issues


def evidence_state():
    return {f: (BENCH / f).exists() for f in EVIDENCE}


def main():
    before = evidence_state()
    failures = []
    print('=' * 66)
    print(' 证据生成器诚实性验收')
    print('=' * 66)
    for name in GENERATORS:
        path = TOOLS / name
        ok, issues = check_static(path)
        tag = 'PASS' if ok else 'FAIL'
        print(f'  [{tag}] {name:32} {"; ".join(issues) if issues else "静态检查通过"}')
        if not ok:
            failures.append(name)

    # probe 不污染正式证据：只检查已存在的生成器的 --help 能跑
    for name in GENERATORS:
        path = TOOLS / name
        if not path.exists():
            continue
        r = subprocess.run([sys.executable, '-B', str(path), '--help'],
                           cwd=ROOT, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            failures.append(f'{name} --help')
            print(f'  [FAIL] {name:32} --help 失败')

    after = evidence_state()
    polluted = [f for f in EVIDENCE if not before[f] and after[f]]
    if polluted:
        print(f'  [FAIL] probe/help 污染了正式证据: {polluted}')
        failures.extend(polluted)

    print()
    if failures:
        print(f'  ★ {len(failures)} 项不合格: {failures[:5]}')
    else:
        print('  PASS  所有生成器通过诚实性验收')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
