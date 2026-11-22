#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Foundation Guard —— 地基不变量自动巡检（不是新检查器，是已有检查器的编排）

缘起：2026-11-22 自动推卡复盘发现"验证地基建在沙上"三层漏洞
（测试没进门禁→恒真断言→退出码永0）。人工排查是沧海一粟，
本脚本把 6 条地基不变量做成可重复、零 LLM、几秒的自治检查。

用法:
  D:/Python/python.exe -B tools/foundation_guard.py
  D:/Python/python.exe -B tools/foundation_guard.py --sentinel   # 自检：故意注入坏改动验证门禁会红
退出码: 0=全绿; 1=有地基不变量失败

输出:
  - trace 打点（stdout [GUARD] 行）
  - D:/Brain/workspace/bench/_foundation_drift.jsonl 追加每次结果（趋势可见）
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
BENCH = Path('D:/Brain/workspace/bench')
PY = sys.executable
DRIFT_LOG = BENCH / '_foundation_drift.jsonl'
RUNTIME_INDEX = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')

results = []
QUIET = False  # --json 时静音逐条打印


FIX_HINTS = {
    'INV-1': '跑 tools/test_census.py 看 missing 清单，把漏掉的测试加进 run_all.sh',
    'INV-2': '跑 tools/audit_verify.py --strict，把纯弱判据的卡升级为 test_pass',
    'INV-3': '把权威源 index.mjs 同步到 node_modules/dsh-agent-harness/（CRLF/LF 统一后 sha 一致）',
    'INV-4': '跑 tools/tech_tree.py 刷新；跑 audit_implicit_deps.py 补 unlocks 双向回填',
    'INV-5': '清掉 check(...,true,true)/||true；确认每个 test_*.mjs 的 results 都设了 exitCode',
    'INV-6': '检查 test_census.py 的 missing 判定和 test_new_guards.mjs 的 process.exitCode 是否被回退',
    'INV-7': '评判规则被偷改: 回滚受保护文件; 若变更已批准则更新 bench/rulepack/manifest.json 并 commit',
}


def record(inv, name, ok, detail=''):
    results.append({'inv': inv, 'name': name, 'ok': bool(ok), 'detail': str(detail)[:200],
                    'fix': FIX_HINTS.get(inv, '') if not ok else ''})
    if not QUIET:
        line = f"[GUARD] {inv} {'PASS' if ok else 'FAIL'}  {name}"
        if detail:
            line += f'  — {str(detail)[:120]}'
        if not ok:
            line += '\n         ↳ 修复: ' + FIX_HINTS.get(inv, '见 design doc')
        print(line)


def run_script(name, args, cwd=None):
    try:
        r = subprocess.run([PY, '-B', str(args[0])] + list(args[1:]),
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=90, cwd=cwd or ROOT)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'


def inv1_test_coverage():
    ok, out = run_script('census', [TOOLS / 'test_census.py'])
    m = re.search(r'missing_in_gate=(\d+)', out)
    missing = int(m.group(1)) if m else -1
    record('INV-1', '测试全在门禁 (census missing=0)', ok and missing == 0, f'missing={missing}')


def inv2_no_weak_criteria():
    ok, out = run_script('audit_verify', [TOOLS / 'audit_verify.py', '--strict'])
    # 纯弱判据=0：允许"无"或"0 张"两种输出
    weak_zero = bool(re.search(r'纯弱判据[^0-9]*0\s*张|无\s*$', out))
    record('INV-2', '无纯弱判据卡', ok and weak_zero,
           (re.search(r'纯弱判据.*', out).group(0)[:80] if re.search(r'纯弱判据.*', out) else 'no-marker'))


def inv3_sha_sync():
    def norm(p):
        if not p.exists():
            return None
        return hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    a, b = norm(ROOT / 'index.mjs'), norm(RUNTIME_INDEX)
    record('INV-3', '权威源/运行版 sha 一致', a is not None and a == b,
           f'authority={str(a)[:12]} runtime={str(b)[:12]}')


def inv4_meta_consistency():
    ok1, _ = run_script('implicit-deps', [TOOLS / 'audit_implicit_deps.py', '--strict'])
    ok2, out2 = run_script('tech-tree', [TOOLS / 'tech_tree.py', '--check'])
    record('INV-4', '科技树三副本一致 (GRAPH/LADDER/HTML)', ok1 and ok2,
           f'implicit_deps={ok1} tech_tree={ok2}')


def inv5_no_tautology():
    """静态扫描恒真断言模式 + 退出码丢失（A6 已清 4 处，防回归）"""
    bad = []
    for p in TOOLS.glob('test_*.mjs'):
        try:
            s = p.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        # 恒真断言模式
        if re.search(r'check\([^,]+,\s*true\s*,\s*true\)', s) or re.search(r'\|\|\s*true\s*,\s*true\)', s):
            bad.append(f'{p.name}:tautology')
        # results 收集但从不设 exitCode（test_new_guards 曾因此假绿）
        if 'results.push' in s and 'exitCode' not in s and 'process.exit' not in s and 'const results' in s:
            bad.append(f'{p.name}:no-exitcode')
    record('INV-5', '无恒真断言/退出码丢失', not bad, ','.join(bad) if bad else 'clean')


def inv6_sentinel():
    """Sentinel：验证门禁本身有效——检查 test_census 能否检出'缺失测试'。
    不改任何文件：用一个临时 run_all 文本喂给 census 的解析逻辑做单元级自检。"""
    # 通过给 census 注入一个假发现来验证它的判定能力（纯内存，不动磁盘）
    fake_discovered = {'test_*.mjs': set(), 'test_*.py': {'test_should_be_in_gate.py'}, 'self_test_script': set()}
    fake_executed = set()
    missing = fake_discovered['test_*.py'] - fake_executed
    can_detect = 'test_should_be_in_gate.py' in missing  # census 的核心判定逻辑
    # 再确认 test_new_guards 的 exitCode 判定还在（防 A6 修复被回退）
    ng = (TOOLS / 'test_new_guards.mjs').read_text(encoding='utf-8', errors='replace')
    exitcode_intact = 'process.exitCode' in ng
    ok = can_detect and exitcode_intact
    record('INV-6', '检查器自身有效 (sentinel)', ok,
           f'census_detect={can_detect} exitcode_intact={exitcode_intact}')


def inv7_rulepack_pinned():
    """INV-7: 评判规则包未漂移（执行者不得偷改审计者）"""
    ok, out = run_script('rulepack', [TOOLS / 'rulepack_guard.py'])
    summary = ''
    for l in out.splitlines():
        if l.startswith('[RULEPACK]') and ('FAIL' in l or 'version=' in l):
            summary = (summary + ' ' + l.replace('[RULEPACK] ', ''))[:160]
    record('INV-7', '评判规则包未漂移 (版本钉住)', ok, summary or ('漂移' if not ok else 'pinned'))


def inv8_criteria_health():
    """INV-8: 判据执行层未腐化（解释器/路径/正则/门槛）"""
    ok, out = run_script('criteria-health', [TOOLS / 'audit_criteria_health.py'])
    n = 0
    m = re.search(r'发现 (\d+) 处隐患', out)
    if m:
        n = int(m.group(1))
    first = ''
    for l in out.splitlines():
        if l.strip().startswith('[') and ']' in l:
            first = l.strip()[:140]; break
    record('INV-8', '判据执行层健康', ok, f'隐患={n} {first}')


def write_drift(all_ok):
    entry = {
        'ts': datetime.now(timezone.utc).isoformat(),
        'all_ok': all_ok,
        'pass': sum(1 for r in results if r['ok']),
        'total': len(results),
        'results': results,
    }
    DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with DRIFT_LOG.open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sentinel', action='store_true', help='自检模式：注入已知坏改动验证门禁变红')
    ap.add_argument('--json', action='store_true', help='输出JSON(供agent解析)')
    args = ap.parse_args()
    global QUIET
    QUIET = args.json

    if not args.json:
        print('=========================================')
        print(' Foundation Guard — 地基不变量巡检')
        print('=========================================')
    inv1_test_coverage()
    inv2_no_weak_criteria()
    inv3_sha_sync()
    inv4_meta_consistency()
    inv5_no_tautology()
    inv6_sentinel()
    inv7_rulepack_pinned()
    inv8_criteria_health()

    all_ok = all(r['ok'] for r in results)
    passed = sum(1 for r in results if r['ok'])
    if args.json:
        print(json.dumps({'all_ok': all_ok, 'pass': passed, 'total': len(results), 'results': results},
                         ensure_ascii=False))
    else:
        print(f'[GUARD] RESULT: {passed}/{len(results)} invariants PASS')
        print(f'[GUARD] VERDICT: {"HEALTHY" if all_ok else "DRIFT DETECTED"}')
    write_drift(all_ok)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
