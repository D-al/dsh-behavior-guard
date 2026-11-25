# -*- coding: utf-8 -*-
"""变异测试：验证硬值断言真的会抓住违规（2026-11-25）。

项目铁律：机制生效 ≠ 有效。本脚本故意把每条规则改成错误值，
确认 check_hardened_config 返回问题——即"故意改坏，门禁变红"。
不改真实配置，纯内存变异。

用法: python tools/test_hardened_rules.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config_check as cc


def main():
    good = {
        'LLAMA_35B_CTX_CHECKPOINTS': '2',
        'LLAMA_35B_MMPROJ_OFFLOAD': '1',
        'LLAMA_35B_DRY_ALLOWED_LENGTH': '32',
        'LLAMA_35B_MOE_CACHE_CPU_SHARE': '1.0',
        'LLAMA_35B_NMAX': '3',
        'LLAMA_35B_SPEC_TYPE': 'draft-mtp',
        'LLAMA_35B_TOP_P': '0.95',
        'LLAMA_35B_REASONING_BUDGET': '4096',
        'LLAMA_35B_TEMP': '',
    }
    # 每条规则的违规值（TEMP 单列）
    mutants = {
        'LLAMA_35B_CTX_CHECKPOINTS': '1',
        'LLAMA_35B_MMPROJ_OFFLOAD': '0',
        'LLAMA_35B_DRY_ALLOWED_LENGTH': '2',
        'LLAMA_35B_MOE_CACHE_CPU_SHARE': '0.0',
        'LLAMA_35B_NMAX': '7',
        'LLAMA_35B_SPEC_TYPE': 'ngram-simple',
        'LLAMA_35B_TOP_P': '0.5',
        'LLAMA_35B_REASONING_BUDGET': '0',
        'LLAMA_35B_TEMP': '0.7',
    }

    ok = 0
    fail = 0

    # 0. 正例：全对时不应有问题
    p0 = cc.check_hardened_config(good)
    if p0:
        print(f'FAIL 正例：全对配置被误报 {p0}')
        fail += 1
    else:
        print('PASS 正例：全对配置零误报')
        ok += 1

    # 1. 每个变异都必须被抓到，且报的是被改的那个键
    for key, bad in mutants.items():
        cfg = dict(good)
        cfg[key] = bad
        problems = cc.check_hardened_config(cfg)
        caught = any(key in p for p in problems)
        reason_ok = any('—' in p and len(p.split('—')[-1].strip()) > 8 for p in problems)
        if caught and reason_ok:
            print(f'PASS 变异 {key}={bad} → {problems[0].split("—")[-1].strip()[:34]}')
            ok += 1
        else:
            print(f'FAIL 变异 {key}={bad} 未被正确抓到: {problems}')
            fail += 1

    print(f'\n结果: {ok} pass, {fail} fail')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
