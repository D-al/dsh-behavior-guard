# -*- coding: utf-8 -*-
"""Self-Harness P0 acceptance gate + 基线方差检查（ADR-0018）。
纯统计判定，零 LLM 调用。用法:
  D:/Python/python.exe tools/self_harness_gate.py --self-test

A3_5 升级：增加 real_diff_check() 真实 diff 校验 + deploy_with_rollback()
"""
import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SURFACES = 'D:/Brain/publish/dsh-behavior-guard/surfaces.json'
ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = ROOT / 'archive' / 'snapshots'


def load_surfaces():
    with open(SURFACES, encoding='utf-8') as f:
        return json.load(f)


def variance_ok(runs):
    """基线 pass-rate 方差 <10%(用极差近似,样本少时更保守)。"""
    if not runs or len(runs) < 2:
        return False, 0.0
    vals = [float(x) for x in runs]
    mean = statistics.mean(vals)
    if mean == 0:
        return True, 0.0
    spread = (max(vals) - min(vals)) / mean
    return spread < 0.10, round(spread, 4)


def accept(baseline, candidate):
    """论文规则：任一 split 不退化且至少一个 split 提升。
    baseline/candidate: {'held-in': [r1,r2,...], 'held-out': [...]}
    """
    acc = load_surfaces()['acceptance']
    if any(len(baseline.get(s, [])) < acc['min_repeats'] or len(candidate.get(s, [])) < acc['min_repeats']
           for s in acc['splits']):
        return {'decision': 'no-op', 'reason': 'insufficient repeats'}
    # P1：基线方差门槛必须生效——基线自身噪声 >10% 时，任何"提升"都不可信（论文 P0 前置）
    noisy = {s: variance_ok(baseline[s]) for s in acc['splits']}
    bad = [s for s, (ok, spread) in noisy.items() if not ok]
    if bad:
        return {'decision': 'no-op', 'reason': f'baseline variance >{acc["max_pass_rate_variance"]:.0%} on {bad} — 先降噪声', 'variance': {s: v[1] for s, v in noisy.items()}}
    b_means = {s: statistics.mean(baseline[s]) for s in acc['splits']}
    c_means = {s: statistics.mean(candidate[s]) for s in acc['splits']}
    degraded = [s for s in acc['splits'] if c_means[s] < b_means[s] - 1e-9]
    improved = [s for s in acc['splits'] if c_means[s] > b_means[s] + 1e-9]
    if degraded:
        return {'decision': 'reject', 'reason': f'degraded on {degraded}', 'baseline': b_means, 'candidate': c_means}
    if not improved:
        return {'decision': 'no-op', 'reason': 'no improvement', 'baseline': b_means, 'candidate': c_means}
    return {'decision': 'accept', 'reason': f'improved on {improved}', 'baseline': b_means, 'candidate': c_means}


# ============================================================
# A3_5 — Real diff-based surface_check + deploy_with_rollback
# ============================================================

def _load_editable_targets():
    """Load all editable targets from surfaces.json."""
    try:
        with open(SURFACES_JSON := ROOT / 'surfaces.json', encoding='utf-8') as f:
            data = json.load(f)
        targets = []
        forbidden_always = ['approval-delegate', 'L0-L3', 'verifyRan', 'GWT', 'FEP',
                            'AGENTS.md', 'CritBank', 'protected', 'D1-D5', 'turn-guard',
                            'llama-server', '权重', '权限预设', 'GWT/FEP']
        for entry in data.get('editable', []):
            target_str = entry.get('target', '')
            if target_str:
                targets.append({
                    'id': entry['id'],
                    'kind': entry.get('kind', ''),
                    'target': target_str,
                    'allows': entry.get('allows', []),
                    'forbids': entry.get('forbids', [])
                })
        return targets, forbidden_always
    except Exception:
        return [], []


def file_diff(base_content, candidate_content):
    """Return changed lines as (line_num, old_line, new_line).

    Use difflib.SequenceMatcher so pure insertions/deletions do NOT shift
    subsequent lines into false "modified" entries (A3_5 逐行比对假阴性 bug).
    Insertions are represented as ('', new_line) so token matching still sees them.
    """
    import difflib
    base_lines = base_content.split('\n')
    cand_lines = candidate_content.split('\n')
    changes = []
    sm = difflib.SequenceMatcher(a=base_lines, b=cand_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace':
            for k in range(max(i2 - i1, j2 - j1)):
                b = base_lines[i1 + k] if i1 + k < i2 else ''
                c = cand_lines[j1 + k] if j1 + k < j2 else ''
                changes.append((j1 + k + 1, b, c))
        elif tag == 'insert':
            for k in range(j2 - j1):
                changes.append((j1 + k + 1, '', cand_lines[j1 + k]))
        elif tag == 'delete':
            for k in range(i2 - i1):
                changes.append((i1 + k + 1, base_lines[i1 + k], ''))
    return changes


def real_diff_check(surface_id, modified_files_with_content):
    """Real diff-based validation against surfaces.json editable targets.

    Args:
        surface_id: The surface ID being modified (e.g., 'SURF-PROMPT-CRITIC')
        modified_files_with_content: dict {filepath: {'base': content, 'candidate': content}}

    Returns:
        dict with 'allowed' bool and 'reason' string
    """
    editable_targets, forbidden_always = _load_editable_targets()

    # Find matching target for this surface_id
    matched_target = None
    for t in editable_targets:
        if t['id'] == surface_id:
            matched_target = t
            break

    if not matched_target:
        return {'allowed': False, 'reason': f'unknown surface {surface_id}'}

    # Check each file modification
    violations = []
    for filepath, contents in modified_files_with_content.items():
        base = contents.get('base', '')
        cand = contents.get('candidate', '')

        if not base or base == cand:
            continue  # No actual change

        changes = file_diff(base, cand)
        if not changes:
            continue

        target_matches_list = [t['target'] for t in editable_targets if t['id'] == surface_id]

        # 连续插入/修改块级校验：一段功能代码必然含通用行(try/{/const q)，
        # 逐行 token 匹配会误拒。按行号连续性分组，块内任一行含白名单 token 即整块允许。
        groups = []
        for ch in changes:
            ln = ch[0]
            if groups and ln <= groups[-1][-1][0] + 1:
                groups[-1].append(ch)
            else:
                groups.append([ch])

        violations = []
        for grp in groups:
            blob = ' '.join((old + ' ' + new) for _, old, new in grp)
            is_allowed = False
            for tgt in target_matches_list:
                parts = tgt.split(':', 1)
                if len(parts) != 2:
                    continue
                target_file, target_region = parts
                if target_file not in str(filepath):
                    continue
                core_ids = [t.strip() for t in target_region.split('/') if t.strip()]
                if any(cid in blob for cid in core_ids):
                    is_allowed = True
                    break
            hits = [m for m in forbidden_always if m.lower() in blob.lower()]
            if hits:
                is_allowed = False
            if not is_allowed:
                violations.append({
                    'lines': [g[0] for g in grp],
                    'sample': blob[:160],
                    'forbidden_hits': hits,
                })

        if violations:
            return {'allowed': False, 'reason': f'diff violation blocks: {violations[:5]}'}
    return {'allowed': True, 'reason': 'diff-based check passed'}


def _make_snapshot_dir():
    """Create snapshot directory with timestamp."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snap_path = SNAPSHOT_DIR / ts
    snap_path.mkdir(exist_ok=True)
    return snap_path


def deploy_with_rollback(target_file, candidate_content, e2e_script=None):
    """Deploy a candidate file with automatic rollback on failure.

    Args:
        target_file: Path to the target file to modify
        candidate_content: Content of the candidate file
        e2e_script: Optional path to e2e script

    Returns:
        dict with deployment result details
    """
    target_path = Path(target_file)
    if not target_path.exists():
        return {
            'deployed': False,
            'rolled_back': False,
            'error': 'target file does not exist',
            'original_sha256': None,
            'final_sha256': None
        }

    # Step 1: Backup original (snapshot)
    original_content = target_path.read_text(encoding='utf-8')
    original_sha256 = hashlib.sha256(original_content.encode('utf-8')).hexdigest()

    snap_path = _make_snapshot_dir()
    backup_file = snap_path / target_path.name
    shutil.copy2(str(target_path), str(backup_file))

    # Step 2: Write candidate
    try:
        target_path.write_text(candidate_content, encoding='utf-8')
    except Exception as e:
        shutil.copy2(str(backup_file), str(target_path))
        final_sha256 = hashlib.sha256(target_path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        return {
            'deployed': False,
            'rolled_back': True,
            'error': f'write failed: {e}',
            'original_sha256': original_sha256,
            'final_sha256': final_sha256
        }

    # Step 3: Run e2e verification
    e2e_passed = False
    e2e_error = None

    if e2e_script and Path(e2e_script).exists():
        try:
            result = subprocess.run(
                ['D:/Python/python.exe', str(e2e_script)],
                capture_output=True, text=True, timeout=120,
                cwd=str(ROOT), env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            )
            e2e_passed = result.returncode == 0
            e2e_error = result.stderr[:500] if result.stderr else None
        except Exception as e:
            e2e_passed = False
            e2e_error = str(e)[:500]
    else:
        # Default e2e: run node --check on index.mjs + config_check.py
        e2e_ok_list = []

        # Check 1: node --check index.mjs
        try:
            r1 = subprocess.run(
                ['node', '--check', str(ROOT / 'index.mjs')],
                capture_output=True, text=True, timeout=30, cwd=str(ROOT)
            )
            e2e_ok_list.append(r1.returncode == 0)
        except Exception:
            e2e_ok_list.append(False)

        # Check 2: python config_check.py
        try:
            r2 = subprocess.run(
                ['D:/Python/python.exe', str(ROOT / 'tools' / 'config_check.py')],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT),
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            )
            e2e_ok_list.append(r2.returncode == 0)
        except Exception:
            e2e_ok_list.append(False)

        e2e_passed = all(e2e_ok_list)
        e2e_error = '; '.join(f'check{i+1}: {"PASS" if v else "FAIL"}' for i, v in enumerate(e2e_ok_list))

    # Step 4: Decide rollback or keep
    if not e2e_passed:
        # Rollback
        shutil.copy2(str(backup_file), str(target_path))
        final_sha256 = hashlib.sha256(target_path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()

        log_entry = {
            'event': 'rollback_triggered',
            'target': str(target_path),
            'snapshot': str(snap_path),
            'original_sha256': original_sha256,
            'final_sha256': final_sha256,
            'e2e_result': e2e_error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Write trace log
        trace_log = ROOT / 'archive' / 'snapshots' / '_deploy_trace.jsonl'
        with open(trace_log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

        return {
            'deployed': False,
            'rolled_back': True,
            'error': f'e2e failed: {e2e_error}',
            'original_sha256': original_sha256,
            'final_sha256': final_sha256,
            'trace_logged': True
        }
    else:
        return {
            'deployed': True,
            'rolled_back': False,
            'error': None,
            'original_sha256': original_sha256,
            'final_sha256': hashlib.sha256(candidate_content.encode('utf-8')).hexdigest(),
            'trace_logged': False
        }


def surface_check(surface_id, modified_files_with_content):
    """Surface-level gate check (A3_5 upgraded to real diff validation).

    Args:
        surface_id: The surface ID being modified
        modified_files_with_content: dict {filepath: {'base': content, 'candidate': content}}
            Legacy callers passing a plain list cannot supply real diff -> FAIL safe
            (never pretend PASS without evidence; see ADR-0012 / C-01).

    Returns:
        dict with 'allowed' bool and 'reason' string
    """
    if not isinstance(modified_files_with_content, dict):
        return {'allowed': False,
                'reason': 'legacy signature: real diff unavailable (caller must pass base/candidate dict)'}
    return real_diff_check(surface_id, modified_files_with_content)


def self_test():
    """11 项原有判定测试 + A3_5 新功能测试（旁观者恢复：长会话退化后代为完成）。"""
    passed = total = 0
    def check(label, ok):
        nonlocal passed, total
        total += 1; passed += 1 if ok else 0
        print(('PASS' if ok else 'FAIL') + '  ' + label)

    base = {'held-in': [0.5, 0.52], 'held-out': [0.4, 0.42]}
    check('accept: 两个 split 都提升', accept(base, {'held-in': [0.6, 0.62], 'held-out': [0.5, 0.52]})['decision'] == 'accept')
    check('accept: 一个提升一个持平', accept(base, {'held-in': [0.6, 0.62], 'held-out': [0.4, 0.42]})['decision'] == 'accept')
    check('reject: 一个 split 退化', accept(base, {'held-in': [0.6, 0.62], 'held-out': [0.3, 0.3]})['decision'] == 'reject')
    check('no-op: 全部持平', accept(base, {'held-in': [0.5, 0.52], 'held-out': [0.4, 0.42]})['decision'] == 'no-op')
    check('no-op: repeats 不足', accept({'held-in': [0.5], 'held-out': [0.4]}, base)['decision'] == 'no-op')
    ok, spread = variance_ok([0.50, 0.52])
    check('variance_ok: 窄分布通过', ok and spread < 0.10)
    ok, spread = variance_ok([0.30, 0.55])
    check('variance_ok: 宽分布拒绝', not ok)
    check('variance_ok: 样本不足拒绝', not variance_ok([0.5])[0])
    # A3_5: surface_check 新签名 {path:{base,candidate}}
    b = 'const CRITIC_PROMPT = "old"\nconst OTHER = 1\n'
    c = 'const CRITIC_PROMPT = "new"\nconst OTHER = 1\n'
    check('surface_check: 白名单内改动允许', surface_check('SURF-PROMPT-CRITIC', {'index.mjs': {'base': b, 'candidate': c}})['allowed'])
    check('surface_check: 未知 surface 拒绝', not surface_check('SURF-EVERYTHING', {'index.mjs': {'base': b, 'candidate': c}})['allowed'])
    c2 = 'const CRITIC_PROMPT = "old"\nconst OTHER = 2\n'
    check('surface_check: 白名单外改动拒绝', not surface_check('SURF-PROMPT-CRITIC', {'index.mjs': {'base': b, 'candidate': c2}})['allowed'])
    # A3_5 新增: real_diff_check 正反例（CONTROL_PROMPT 拆 token 后应允许）
    b3 = 'const CONTROL_PROMPT = "old"\nconst KEEP = 1\n'
    c3 = 'const CONTROL_PROMPT = "new"\nconst KEEP = 1\n'
    check('real_diff: CONTROL_PROMPT 白名单改动允许', real_diff_check('SURF-PROMPT-CONTROL', {'index.mjs': {'base': b3, 'candidate': c3}})['allowed'])
    check('real_diff: 无变化允许', real_diff_check('SURF-PROMPT-CONTROL', {'index.mjs': {'base': b3, 'candidate': b3}})['allowed'])
    check('surface_check: legacy list 签名安全拒绝', not surface_check('SURF-PROMPT-CRITIC', ['x'])['allowed'])
    # ── S22: 真断言 — 两会话各自独立disabledWarned，互不污染 ──
    import re as _re
    src = open(gate_py.parent / 'index.mjs', encoding='utf-8').read()
    # ① 禁止模块级 _s22_disabled_warned（旧bug）
    has_module_global = bool(_re.search(r'^let\s+_s22_disabled_warned\b', src, _re.M))
    check('s22-no-module-global: _s22_disabled_warned已移除', not has_module_global)
    # ② session-state中有disabledWarned字段
    has_session_field = "'disabledWarned'" in src or '"disabledWarned"' in src
    check('s22-session-field: state含disabledWarned', has_session_field)
    # ③ tool/call handler用 s.disabledWarned.has() 判断
    uses_session_check = 's.disabledWarned.has(s22_name)' in src or 's.disabledWarned.has( s22_name )' in src
    check('s22-handler-check: tool/call使用session级disabledWarned', uses_session_check)
    # ④ DISABLED_TOOLS集合存在且含3个工具
    has_set = 'DISABLED_TOOLS = new Set([' in src or 'DISABLED_TOOLS=new Set([' in src
    contains_web_fetch = "web_fetch" in src and 'DISABLED_TOOLS' in src.split('DISABLED_TOOLS')[0].split('\n')[-1] if 'DISABLED_TOOLS' in src else False
    check('s22-disabled-set: DISABLED_TOOLS定义正确', has_set and ('job_output' in src and 'job_kill' in src and 'web_fetch' in src))
    
    print(f'\n══════ {passed}/{total} 通过 ══════')
    ap = argparse.ArgumentParser(description='Self-Harness P0 acceptance gate')
    ap.add_argument('--baseline', help='JSON file with baseline run data')
    ap.add_argument('--candidate', help='JSON file with candidate run data')
    ap.add_argument('--self-test', action='store_true', help='Run self-tests')
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    if a.baseline and a.candidate:
        b = json.load(open(a.baseline, encoding='utf-8'))
        c = json.load(open(a.candidate, encoding='utf-8'))
        print(json.dumps(accept(b, c), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(load_surfaces(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
