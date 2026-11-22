#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S21 验证层真实测试（≥3 断言，顶格 [PASS] 供 roadmap_check 判据识别）

对齐 tools/verifier_layer.py 的真实 API（load_rubrics / build_report / run_probe）。
测试覆盖：rubric 结构、成对交换一致性、无数据 N/M 不造 PASS、probe 三场景自检、CLI JSON。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))

PASS = 0
FAIL = 0


def check(name, ok, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f'[PASS] {name}: {detail}')
    else:
        FAIL += 1
        print(f'[FAIL] {name}: {detail}')


def main():
    import verifier_layer as v

    # 1) rubric 真实加载 + 结构
    rubrics = v.load_rubrics()
    names = [r.get('name') or r.get('id') or '?' for r in rubrics] if isinstance(rubrics, list) else list(rubrics)
    check('rubric_load_and_structure', bool(rubrics),
          f'rubrics={len(rubrics)} names={names[:4]}')

    # 2) 成对交换判分一致性：稳健对应 PASS，位置偏差被检出
    stable, biased, indep = v.probe_payload()
    r1 = v.build_report(stable, rubrics)
    r2 = v.build_report(biased, rubrics)
    ok = (r1['verdict'] == 'PASS' and r2['verdict'] == 'FAIL'
          and r1['position_bias']['rate'] == 0)
    check('pairwise_swap_consistency', ok,
          f'stable={r1["verdict"]} bias={r1["position_bias"]["rate"]}, '
          f'biased={r2["verdict"]} bias={r2["position_bias"]["rate"]}')

    # 3) 无数据 N/M，不造 PASS
    empty = v.build_report([], rubrics)
    ok = empty['verdict'] == 'N/M' and empty['insufficient'] is True
    check('empty_returns_NM_not_fake_pass', ok,
          f'empty={empty["verdict"]} insufficient={empty["insufficient"]}')

    # 4) probe 三场景自检（实现自带）
    p = v.run_probe()
    ok = p['self_check_pass'] is True
    check('probe_three_scenarios_selfcheck', ok,
          f'cases={ {k: c["verdict"] for k, c in p["cases"].items()} }')

    # 5) CLI --json 契约
    r = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/verifier_layer.py'), '--json'],
                       cwd=ROOT, capture_output=True, text=True, timeout=60)
    try:
        out = json.loads(r.stdout)
        ok = out.get('verdict') in ('PASS', 'FAIL', 'N/M')
    except json.JSONDecodeError:
        ok = False
        out = {}
    check('cli_json_contract', ok, f'rc={r.returncode} verdict={out.get("verdict")}')

    print(f'\n{PASS}/{PASS + FAIL} pass')
    return 0 if FAIL == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
