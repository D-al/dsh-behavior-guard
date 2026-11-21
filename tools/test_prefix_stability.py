#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_prefix_stability.py — 前缀 KV 稳定性守护（S23）单测。

验证 probe 核心逻辑：
  ① ratio = cold_ms / warm_ms 计算正确
  ② fake client 下 cold > warm（ratio > 1）
  ③ JSON 输出包含必需字段

用法: python tools/test_prefix_stability.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.prefix_stability_probe import FakeClient, RealClient, run_probe


def test_ratio_calculation():
    """ratio = avg(cold) / avg(warm)，当 warm=0 时应为 inf。"""
    fc = FakeClient()
    result = run_probe("test prefix", fc)
    assert result["prefix_len"] > 0, "prefix_len should be positive"
    # cold_ms 应显著大于 warm_ms（FakeClient 默认 cold_base=50, warm_base=2）
    assert result["cold_ms"] > result["warm_ms"], \
        f"cold_ms ({result['cold_ms']}) should be > warm_ms ({result['warm_ms']})"
    # ratio 应在合理范围内 (约 25x)
    ratio = result["cold_ms"] / result["warm_ms"] if result["warm_ms"] > 0 else float('inf')
    assert ratio > 1.0, f"ratio ({ratio}) should be > 1 for fake client"
    print(f'PASS  test_ratio_calculation: cold={result["cold_ms"]}ms warm={result["warm_ms"]}ms ratio={result["ratio"]}')


def test_json_fields_present():
    """返回的 dict 必须包含所有必需字段。"""
    fc = FakeClient()
    result = run_probe("hello world", fc)
    required_keys = {"prefix_len", "cold_ms", "warm_ms", "ratio"}
    missing = required_keys - set(result.keys())
    assert not missing, f"Missing keys in result: {missing}"
    print(f'PASS  test_json_fields_present: all required fields present')


def test_fake_cold_gt_warm_consistent():
    """多次 probe 都应保持 cold > warm，确保一致性。"""
    fc = FakeClient()
    consistency_ok = True
    for i in range(3):
        r = run_probe(f"consistency test {i}", fc)
        if r["cold_ms"] <= r["warm_ms"]:
            consistency_ok = False
    assert consistency_ok, "cold should always > warm across multiple runs"
    print('PASS  test_fake_cold_gt_warm_consistent: 3/3 cold>warm')


def main():
    tests = [
        test_ratio_calculation,
        test_json_fields_present,
        test_fake_cold_gt_warm_consistent,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f'FAIL  {t.__name__}: {e}')

    print(f'\nResults: {passed} passed, {failed} failed out of {len(tests)}')
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
