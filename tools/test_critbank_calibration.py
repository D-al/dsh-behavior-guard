#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S19 CritBank 校准门禁的真实行为测试（≥3 条独立断言，零 LLM，不写正式产物）

判据对接：roadmap_check.py 的 test_pass 用 ^(?:PASS|\\[PASS\\s*\\]|✅|\\[OK\\]) 逐行计数，
因此每条通过断言必须**顶格**打印 '[PASS] ...'，行首不得有空格。

测试内容：
1. 真实 config/critbank.json 可加载且条目数 > 0；
2. SYNTHETIC（明确标注的合成数据，仅测纯函数数学）Brier / ECE 符合手算值；
3. SYNTHETIC ŷ/χ 聚合代理符合手算值；无样本时返回 None（N/M 不造数）；
4. B+/B− 检索区分度（AUC / χ 差异）能被计算；缺任一类返回 None（N/M）；
5. SYNTHETIC 报告集成：逐次日志→CALIBRATED 且 gate_pass；空证据→N/M 不放行。

用法: D:/Python/python.exe -B tools/test_critbank_calibration.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import critbank_calibration as cb  # noqa: E402

passed = failed = 0


def check(label, fn):
    """顶格打印通过标记；失败打印原因但不中断其余断言。"""
    global passed, failed
    try:
        ok = bool(fn())
    except Exception as exc:  # noqa: BLE001 - 测试需暴露任意断言异常
        ok = False
        print(f'  [FAIL detail] {type(exc).__name__}: {exc}')
    if ok:
        passed += 1
        print(f'[PASS] {label}')
    else:
        failed += 1
        print(f'[FAIL] {label}')


# ---- SYNTHETIC：仅用于验证纯函数数学，不写 critbank.json / 任何正式产物 ----
SYN = [(0.9, True), (0.8, True), (0.2, False), (0.1, False)]
# Brier = (0.1^2 + 0.2^2 + 0.2^2 + 0.1^2)/4 = 0.025
# ECE(10 等宽箱) = (|0.9-1| + |0.8-1| + |0.2-0| + |0.1-0|)/4 = 0.15
# AUC = 1.0（两个正例置信均高于两个负例）；χ 差异 = 0.85 - 0.15 = 0.70


def t1_real_bank_loadable():
    bank = cb.load_bank()
    assert isinstance(bank, list) and len(bank) > 0, '真实 critbank 条目为空'
    ids = [c.get('id') for c in bank if isinstance(c, dict)]
    assert len(ids) == len(set(ids)), '真实条目 id 重复'
    assert all(c.get('signal') and c.get('lesson') for c in bank), '真实条目缺 signal/lesson'
    return True


def t2_synthetic_brier_ece():
    b = cb.brier_score(SYN)
    e = cb.ece(SYN, bins=10)
    assert abs(b - 0.025) < 1e-9, f'Brier={b} != 0.025'
    assert abs(e - 0.15) < 1e-9, f'ECE={e} != 0.15'
    assert cb.brier_score([]) is None, '空样本 Brier 应为 None（N/M）'
    return True


def t3_synthetic_yhat_chi_proxy():
    p = cb.proxy_from_counters(3, 1)
    assert p is not None
    assert abs(p['y_hat'] - 0.75) < 1e-9, p
    assert p['chi'] == 1, p
    assert abs(p['chi_score'] - 0.5) < 1e-9, p
    assert abs(p['confidence'] - 0.5) < 1e-9, p
    assert abs(p['brier_const'] - 0.1875) < 1e-9, p
    n = cb.proxy_from_counters(1, 3)
    assert n['chi'] == -1 and abs(n['y_hat'] - 0.25) < 1e-9, n
    assert cb.proxy_from_counters(0, 0) is None, '无样本不得造 ŷ'
    return True


def t4_bplus_bminus_discrimination():
    a = cb.auc(SYN)
    d = cb.chi_discrimination(SYN)
    assert a is not None and abs(a - 1.0) < 1e-9, f'AUC={a} != 1.0'
    assert d is not None and abs(d - 0.7) < 1e-9, f'χ 差异={d} != 0.7'
    # 中性/缺类必须 N/M，不能拿全正例冒充 AUC=1
    assert cb.auc([(0.9, True), (0.7, True)]) is None
    assert cb.chi_discrimination([(0.2, False), (0.1, False)]) is None
    return True


def t5_report_integration():
    # SYNTHETIC 银行/侧表/逐次日志，全在内存构造，不落盘
    bank = [{'id': 'S-1', 'tags': ['合成']}, {'id': 'S-2', 'tags': ['合成']}]
    state = {'S-1': {'helpful': 3, 'harmful': 1},
             'S-2': {'helpful': 1, 'harmful': 3}}
    hits = [{'id': 'S-1', 'confidence': 0.9, 'productive': True},
            {'id': 'S-1', 'confidence': 0.8, 'productive': True},
            {'id': 'S-2', 'confidence': 0.2, 'productive': False},
            {'id': 'S-2', 'confidence': 0.1, 'productive': False}]
    rep = cb.build_report(bank, state, hits)
    assert rep['calibration']['source'] == 'hit_log', rep
    assert (rep['calibration']['B+'], rep['calibration']['B-']) == (2, 2), rep
    assert abs(rep['calibration']['auc'] - 1.0) < 1e-9, rep
    assert abs(rep['calibration']['brier'] - 0.025) < 1e-9, rep
    assert rep['verdict'] == 'CALIBRATED' and rep['gate_pass'] is True, rep
    assert all(e['pass'] for e in rep['entries'] if e['sufficient']), rep

    empty = cb.build_report([], {}, [])
    assert empty['verdict'] == 'N/M' and empty['insufficient'] is True, empty
    assert empty['gate_pass'] is False, empty
    return True


check('真实 CritBank 数据可加载且条目数>0', t1_real_bank_loadable)
check('SYNTHETIC Brier=0.025 / ECE=0.15（仅测函数数学，不写产物）', t2_synthetic_brier_ece)
check('SYNTHETIC ŷ/χ 代理=0.75/+1/conf=0.5，无样本→N/M 不造数', t3_synthetic_yhat_chi_proxy)
check('B+/B- 区分度可计算：AUC=1.0 / χ差异=0.7，缺类→N/M', t4_bplus_bminus_discrimination)
check('SYNTHETIC 报告集成：hit_log→CALIBRATED，空证据→N/M 不放行', t5_report_integration)

print(f'\n{passed}/{passed + failed} pass')
sys.exit(1 if failed else 0)
