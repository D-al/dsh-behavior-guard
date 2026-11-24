# -*- coding: utf-8 -*-
"""四杠杆上线后验证：L4 真实 sid trace + L5 独立产物 + L2 单测。

上线后必须跑这个脚本，全部 PASS 才算"生效"（不是只"加载"）。
铁律：过滤 s1 假数据（POSTMORTEM: 89% trace 是单测假数据）。

用法：python levers_verify.py [--trace <path>] [--fresh-min <ISO时间>]
"""
import sys, json, re, subprocess
from pathlib import Path

TRACE = Path('D:/Brain/workspace/bench/_trace.jsonl')
TESTS = Path('D:/Brain/publish/dsh-behavior-guard/tools')
KINDS = {
    1: 'verify_state_readback',
    2: 'state_board_inject',
    4: 'self_consistency_vote',
}
NAMES = {1: '确定性状态回读', 2: '显式状态板', 4: 'K=5 自洽投票'}


def check_trace(kind, fresh_min=None):
    """L4: 找真实 sid 的 trace kind（排除 s1 单测假数据）。"""
    if not TRACE.exists():
        return False, 'trace 文件不存在', []
    hits = []
    for line in TRACE.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        sid = str(r.get('sid', ''))
        if sid == 's1' or not sid:
            continue  # 排除单测假数据
        if r.get('kind') != kind:
            continue
        if fresh_min and str(r.get('ts', '')) < fresh_min:
            continue
        hits.append(r)
    if not hits:
        return False, f'无真实 sid 的 {kind} trace', []
    return True, f'{len(hits)} 条真实 trace', hits[-3:]


def check_unit_tests():
    """L2: 门禁全过（上线不能破坏现有机制）。"""
    r = subprocess.run(['bash', 'tools/run_all.sh'], cwd=str(TESTS.parent),
                       capture_output=True, text=True, timeout=300)
    m = re.search(r'(\d+) pass, (\d+) fail', r.stdout + r.stderr)
    if m:
        return int(m.group(2)) == 0, f'{m.group(1)} pass / {m.group(2)} fail', []
    return False, '无门禁结果', []


def check_sha_sync():
    """两副本 sha 一致（三副本教训）。"""
    import hashlib
    a = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
    b = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
    if not a.exists() or not b.exists():
        return False, '副本缺失', []
    ha = hashlib.sha256(a.read_bytes()).hexdigest()
    hb = hashlib.sha256(b.read_bytes()).hexdigest()
    return ha == hb, f'权威={ha[:12]} 运行={hb[:12]}', []


def main():
    fresh_min = None
    if '--fresh-min' in sys.argv:
        fresh_min = sys.argv[sys.argv.index('--fresh-min') + 1]
    all_ok = True
    print('=== 上线验证（L2 单测 + L4 trace + sha 同步）===')
    ok, msg, _ = check_sha_sync()
    print(f'[{"PASS" if ok else "FAIL"}] 两副本 sha 同步: {msg}')
    all_ok &= ok
    ok, msg, _ = check_unit_tests()
    print(f'[{"PASS" if ok else "FAIL"}] 门禁: {msg}')
    all_ok &= ok
    for lever, kind in KINDS.items():
        ok, msg, samples = check_trace(kind, fresh_min)
        print(f'[{"PASS" if ok else "FAIL"}] 杠杆{lever} {NAMES[lever]} L4 trace: {msg}')
        for s in samples[:1]:
            print(f'    样本: {json.dumps(s, ensure_ascii=False)[:180]}')
        all_ok &= ok
    print(f'\n总判定: {"PASS 全部生效" if all_ok else "FAIL 有未生效项，不得宣布上线"}')
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__': main()
