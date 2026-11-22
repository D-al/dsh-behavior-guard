#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判据执行层体检：检测"判据本身腐化"（不是判据逻辑病，也不是判据跑不过）

缘起：2026-11-22 六张 done 卡虚报，根因全是判据执行层腐化：
  ①Python 跑 .mjs（解释器不匹配）②脚本输出格式不匹配 PASS 正则
  ③路径指向不存在文件/漂移 ④正则查旧机制名 ⑤门槛脱离真实分布 ⑥脚本写死路径
这些都能静态检测，不需要"学习"。

与已有工具的分工（不重复造轮子）：
  - check_verify.py：判据**逻辑**病（自引用/恒真/格式/sid污染）
  - audit_delivery.py：判据**真跑结果**（账面done vs 实物）
  - 本脚本：判据**执行环境**健康（命令能不能跑对东西）

用法:
  D:/Python/python.exe -B tools/audit_criteria_health.py [--json] [--fix-hints]
退出码: 0=健康; 1=有执行层隐患
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import roadmap_check as rc

PASS_RE = re.compile(r'^(?:PASS|\[PASS\s*\]|✅|\[OK\])')
KNOWN_PATTERNS = {
    'INTERVAL', 'CONSOLIDATE_EVERY', 'freq', 'FREQUENCY', 'heartbeat',
    'verifyEvidence', 'readCalls', 'writeCalls', 'todo_write',
}


def check_interpreter(cmd, v):
    """① 解释器与文件类型匹配"""
    issues = []
    toks = shlex.split(cmd, posix=False)
    # 找 .mjs/.js 文件参数
    for tok in toks:
        t = tok.strip('"\'')
        if t.endswith(('.mjs', '.js')):
            exe = Path(toks[0].strip('"\'')).name.lower() if toks else ''
            if 'python' in exe:
                issues.append(f'Python({exe}) 执行 JS 文件 {t} — 应用 node')
    # gate_result 的 script 路径
    if v.get('kind') == 'gate_result':
        sc = v.get('script', '')
        if sc.endswith('.mjs') and 'python' in str(v.get('python', '')).lower():
            issues.append('gate_result 指向 .mjs 但用 python')
    return issues


def check_paths(cmd, v):
    """③ 判据指向的路径存在"""
    issues = []
    # file_exists / file_grep 的 path
    for key in ('path', 'script'):
        if key in v:
            # json_field 走 BENCH（与 roadmap_check.check_one 一致），其余走 resolve_path
            if v.get('kind') == 'json_field' and key == 'path':
                raw = Path(v[key])
                p = raw if raw.is_absolute() else rc.BENCH / v[key]
            else:
                p = rc.resolve_path(v[key])
            if not p.exists():
                issues.append(f'{key}={v[key]} 不存在（解析为 {p}）')
    # cmd 里的 tools/xxx.py|mjs 路径
    for m in re.finditer(r'(?:tools|config)/[\w./-]+\.(?:py|mjs|sh)', str(cmd)):
        p = ROOT / m.group(0)
        if not p.exists():
            issues.append(f'cmd 引用不存在的文件: {m.group(0)}')
    return issues


def check_output_contract(cmd, v):
    """② 脚本输出格式能否被判据 PASS 正则识别（真跑一次）"""
    if v.get('kind') != 'test_pass':
        return []
    issues = []
    try:
        r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=120)
    except Exception as e:
        return [f'命令无法执行: {type(e).__name__}: {e}']
    if r.returncode != 0:
        return []  # 跑挂了由 audit_delivery 报，这里只管格式
    passes = sum(1 for line in r.stdout.splitlines() if PASS_RE.match(line))
    if passes == 0 and r.stdout.strip():
        first = r.stdout.splitlines()[0][:60]
        issues.append(f'rc=0 但无 ^PASS 标记（首行="{first}"）— 判据会假 FAIL；'
                      '脚本应输出一行 "PASS  ..." 或声明 format_hint')
    return issues


def check_regex_freshness(v):
    """④ 正则查的是否是旧机制名（启发式：正则词在代码里已 0 命中）"""
    if v.get('kind') != 'file_grep' or 'regex' not in v:
        return []
    p = rc.resolve_path(v.get('path', ''))
    if not p.exists():
        return []  # 路径问题由 check_paths 报
    try:
        text = p.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    hits = len(re.findall(v['regex'], text))
    if hits == 0:
        # 提取正则里的字面词，看是不是已知旧机制名
        words = set(re.findall(r'[A-Za-z_][A-Za-z_0-9]{2,}', v['regex']))
        old = [w for w in words if w in {'freq', 'FREQUENCY', 'heartbeat', 'OLD', 'deprecated'}]
        if old:
            return [f'正则命中 0 且含疑似旧机制名 {old} — 机制可能已改名']
        return [f'正则命中 0（{v["regex"][:40]}）— 判据可能过时']
    return []


def check_threshold(v, data):
    """⑤ 门槛是否脱离真实分布（trace_count 类）"""
    if v.get('kind') not in ('trace_count', 'trace_absent'):
        return []
    min_n = v.get('min', 1)
    source = v.get('source', '')
    p = Path(source) if Path(source).is_absolute() else rc.BENCH / source
    if not p.exists():
        return []
    try:
        rows = rc.read_jsonl(source)
    except Exception:
        return []
    if v.get('sid_filter') == 'exclude_tests':
        bad = rc.test_sids(data)
        rows = [r for r in rows if str(r.get('sid', '')) not in bad]
    n = sum(1 for r in rows if r.get('kind') == v.get('kind_name'))
    if v['kind'] == 'trace_count' and n < min_n:
        return [f'trace_count min={min_n} 但真实只有 {n} 条（{v.get("kind_name")}）— '
                f'判据永远 FAIL；降门槛前确认是证据流失还是触发变少']
    return []


def audit():
    data = rc.load_ladder()
    cards = data['items'] + data['rungs']
    issues = []
    sm = rc.status_map_of(data)
    for c in cards:
        # 只对声称已完成/进行中的卡体检——backlog/ready 的判据引用未来文件是预期的
        if sm.get(c['id']) not in ('done', 'doing'):
            continue
        for i, v in enumerate(c.get('verify', [])):
            found = []
            found += check_interpreter(str(v.get('cmd', '')), v)
            found += check_paths(str(v.get('cmd', '')), v)
            found += check_regex_freshness(v)
            found += check_threshold(v, data)
            # check_output_contract 要真跑命令，成本高，单独在 --full 时做
            for f in found:
                issues.append({'card': c['id'], 'verify_index': i,
                               'kind': v.get('kind'), 'issue': f})
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--full', action='store_true', help='含真跑命令检查输出契约')
    ap.add_argument('--fix-hints', action='store_true')
    args = ap.parse_args()

    issues = audit()
    if args.full:
        data = rc.load_ladder()
        sm = rc.status_map_of(data)
        for c in data['items'] + data['rungs']:
            if sm.get(c['id']) not in ('done', 'doing'):
                continue
            for i, v in enumerate(c.get('verify', [])):
                for f in check_output_contract(str(v.get('cmd', '')), v):
                    issues.append({'card': c['id'], 'verify_index': i,
                                   'kind': v.get('kind'), 'issue': f})

    if args.json:
        print(json.dumps({'issues': issues, 'total': len(issues)}, ensure_ascii=False, indent=2))
    else:
        print('=' * 66)
        print(f' 判据执行层体检 — 发现 {len(issues)} 处隐患')
        print('=' * 66)
        for x in issues:
            print(f'  [{x["card"]}] {x["kind"]}: {x["issue"]}')
        if not issues:
            print('  PASS  未发现执行层腐化')
    return 1 if issues else 0


if __name__ == '__main__':
    sys.exit(main())
