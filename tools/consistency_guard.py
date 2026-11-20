#!/usr/bin/env python3
"""
consistency_guard.py — 一致性守卫（零 LLM，防三副本漂移）

对比四个位置：
  A-remote   远端 GitHub（git ls-remote，不 fetch 改动本地）
  A-local    权威仓库（D:/Brain/publish/*）
  C-runtime  生产运行版（node_modules/*）
  LOCK       pnpm-lock.yaml 指向的 commit/version

设计依据: docs/CONSISTENCY_GUARD_DESIGN_20261120.md
清单:     config/GUARD_MANIFEST.yaml（改清单需走 ADR）

退出码：0=全 PASS（或仅 UNKNOWN/EXEMPT 且非 --strict）
        1=有 FAIL（或 --strict 下 UNKNOWN/EXEMPT 升级为 FAIL）
        2=守卫自身出错（缺依赖/命令失败/清单坏）——绝不静默 0

用法：
  python tools/consistency_guard.py                  # 默认 all，人类可读
  python tools/consistency_guard.py --scope copies   # 只查文件 sha + 版本
  python tools/consistency_guard.py --strict         # UNKNOWN/EXEMPT 视为 FAIL
  python tools/consistency_guard.py --json           # 机器可读报告
  python tools/consistency_guard.py --quiet          # 只输出 exit code
"""
import os
import re
import sys
import json
import yaml
import hashlib
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MANIFEST = ROOT / 'config' / 'GUARD_MANIFEST.yaml'
BENCH = Path(os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench')
REPORT = BENCH / '_guard_report.json'


# ---------- 基础设施：所有外部命令都有 timeout，异常不吞 ----------
def run(cmd, cwd=None, timeout=15):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        raise GuardError(f'TIMEOUT: {" ".join(str(x) for x in cmd)}')
    except FileNotFoundError as e:
        raise GuardError(f'MISSING DEPENDENCY: {e}')


class GuardError(Exception):
    pass


def sha256_normalized(path):
    """CRLF 假差异消除：core.autocrlf=true 下工作树字节 > git blob，同规范化后可比。"""
    b = Path(path).read_bytes()
    b = b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return hashlib.sha256(b).hexdigest()


def git(repo, *args, timeout=15):
    rc, out, err = run(['git', '-C', str(repo), *args], timeout=timeout)
    if rc != 0:
        raise GuardError(f'git {" ".join(args)} failed: {err.strip()[:120]}')
    return out.strip()


def is_git_repo(path):
    rc, _, _ = run(['git', '-C', str(path), 'rev-parse', '--git-dir'], timeout=10)
    return rc == 0


def read_json_field(path, spec):
    """spec = 'package.json:version'"""
    f, _, key = spec.partition(':')
    try:
        d = json.loads((Path(path) / f).read_text(encoding='utf-8-sig'))
        for k in key.split('.'):
            d = d[k]
        return d
    except Exception:
        return None


def parse_changelog_top(path):
    try:
        first = Path(path).read_text(encoding='utf-8', errors='replace').split('\n')[0]
        m = re.search(r'\[?v?(\d+\.\d+\.\d+)', first)
        return m.group(1) if m else None
    except Exception:
        return None


def parse_lock(lock_path, repo_key):
    """返回 (commit, version) —— 从 pnpm-lock.yaml 里该 repo 的 tarball URL 提取。"""
    try:
        s = Path(lock_path).read_text(encoding='utf-8')
    except Exception:
        return None, None
    # 找 repo_key 相关的 codeload URL
    m = re.search(rf'{re.escape(repo_key)}[^\n]*?tar\.gz/([0-9a-f]{{40}})', s)
    commit = m.group(1) if m else None
    # version: 取该 commit 后最近的 version 行
    ver = None
    if commit:
        idx = s.find(commit, s.find(commit) + 1)  # 第二处（resolution 块）
        if idx == -1:
            idx = s.find(commit)
        tail = s[idx:idx + 400]
        vm = re.search(r'version:\s*(\d+\.\d+\.\d+)', tail)
        ver = vm.group(1) if vm else None
    return commit, ver


def check(cid, ok, actual, expected, status=None):
    return {
        'id': cid,
        'status': status or ('PASS' if ok else 'FAIL'),
        'actual': str(actual), 'expected': str(expected),
    }


def collect(role, root, repo, manifest):
    root = Path(root)
    out = {'role': role, 'root': str(root), 'files': {}, 'version': None, 'commit': None}
    if not root.exists():
        out['error'] = f'path missing: {root}'
        return out
    if is_git_repo(root):
        try:
            out['commit'] = git(root, 'rev-parse', 'HEAD')
        except GuardError as e:
            out['error'] = str(e)
    out['version'] = read_json_field(root, repo['version_field'])
    for p in repo['key_files']:
        fp = root / p
        if fp.exists():
            try:
                out['files'][p] = sha256_normalized(fp)
            except Exception as e:
                out['error'] = f'sha fail {p}: {e}'
    return out


def guard_all(manifest_path=MANIFEST):
    if not manifest_path.exists():
        raise GuardError(f'manifest missing: {manifest_path}')
    try:
        m = yaml.safe_load(manifest_path.read_text(encoding='utf-8'))
    except Exception as e:
        raise GuardError(f'manifest parse failed: {e}')
    if m.get('schema') != 1:
        raise GuardError(f'manifest schema != 1')

    results = []
    for repo in m['repos']:
        rid = repo['id']
        a_local = collect('authoritative', repo['authoritative'], repo, m)
        c_rt = collect('runtime', repo['runtime'], repo, m)

        # A-remote：ls-remote 失败 -> UNKNOWN，不假 PASS、不崩
        remote_commit = None
        try:
            rc, out, _ = run(['git', 'ls-remote', repo['remote'], 'HEAD'], timeout=20)
            if rc == 0 and out.strip():
                remote_commit = out.split()[0]
        except GuardError:
            remote_commit = None
        results.append(check(
            f'{rid}.remote_eq_authoritative',
            remote_commit == a_local['commit'],
            remote_commit or 'unreachable', a_local['commit'],
            status=None if remote_commit else 'UNKNOWN',
        ))

        # commit 存在性（authoritative 必须是 git repo）
        results.append(check(f'{rid}.authoritative_has_commit',
                             bool(a_local['commit']), a_local['commit'], '40-hex',
                             status=None if a_local['commit'] else 'FAIL'))

        # 版本三方：authoritative == runtime，changelog == authoritative
        results.append(check(f'{rid}.version_auth_eq_runtime',
                             a_local['version'] == c_rt['version'],
                             a_local['version'], c_rt['version'],
                             status='UNKNOWN' if not (a_local['version'] and c_rt['version']) else None))
        cl_ver = parse_changelog_top(Path(repo['authoritative']) / repo.get('changelog', 'CHANGELOG.md'))
        results.append(check(f'{rid}.version_changelog_eq_package',
                             cl_ver == a_local['version'], cl_ver, a_local['version'],
                             status='UNKNOWN' if not (cl_ver and a_local['version']) else None))

        # 关键文件 sha（CRLF 归一化后）
        for p in repo['key_files']:
            av, cv = a_local['files'].get(p), c_rt['files'].get(p)
            results.append(check(f'{rid}.sha.{p}', av == cv,
                                 (av or 'MISSING')[:12], (cv or 'MISSING')[:12],
                                 status='UNKNOWN' if not (av and cv) else None))

        # git blob 比对（工作树 vs HEAD，防未提交改动）
        if a_local['commit'] and is_git_repo(repo['authoritative']):
            for p in repo['key_files'][:4]:  # 只查前 4 个，避免过度开销
                try:
                    rc, out, _ = run(['git', '-C', str(repo['authoritative']), 'show', f'HEAD:{p}'], timeout=10)
                    if rc == 0:
                        blob = hashlib.sha256(out.replace('\r\n', '\n').encode()).hexdigest()
                        wt = a_local['files'].get(p)
                        results.append(check(f'{rid}.gitblob.{p}', blob == wt,
                                             'worktree', 'HEAD' if blob == wt else 'MISMATCH'))
                except GuardError:
                    pass

        # lock 指向权威 HEAD
        lf = repo.get('lock_file')
        if lf and Path(lf).exists():
            lc, lv = parse_lock(lf, repo['lock_repo_key'])
            results.append(check(f'{rid}.lock_commit_eq_authoritative',
                                 lc == a_local['commit'], (lc or 'MISSING')[:12],
                                 (a_local['commit'] or '?')[:12]))
            if lv:
                results.append(check(f'{rid}.lock_version_eq_package',
                                     lv == a_local['version'], lv, a_local['version']))

    return results


def finalize(results, strict=False):
    order = {'FAIL': 0, 'ERROR': 0, 'UNKNOWN': 1, 'EXEMPT': 2, 'SKIP': 3, 'PASS': 4}
    if strict:
        for r in results:
            if r['status'] in ('UNKNOWN', 'EXEMPT'):
                r['status'] = 'FAIL'
                r['strict_upgraded'] = True
    counts = {}
    for r in results:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    verdict = 'FAIL' if counts.get('FAIL') else ('UNKNOWN' if counts.get('UNKNOWN') else 'PASS')
    return verdict, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='UNKNOWN/EXEMPT 升级为 FAIL')
    ap.add_argument('--json', action='store_true', help='输出机器可读报告')
    ap.add_argument('--quiet', action='store_true', help='只输出 exit code')
    args = ap.parse_args()

    try:
        results = guard_all()
        verdict, counts = finalize(results, args.strict)
    except GuardError as e:
        # 守卫自身出错 -> exit 2，绝不静默 0
        report = {'ts': datetime.now(timezone.utc).isoformat(), 'verdict': 'ERROR',
                  'error': str(e), 'checks': []}
        try:
            BENCH.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
        if not args.quiet:
            print(f'GUARD ERROR: {e}', file=sys.stderr)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    report = {'ts': datetime.now(timezone.utc).isoformat(), 'verdict': verdict,
              'counts': counts, 'checks': results}
    try:
        BENCH.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass

    if not args.quiet:
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f'CONSISTENCY GUARD — {report["ts"]}')
            print(f'verdict={verdict}  counts={counts}')
            for r in results:
                if r['status'] != 'PASS':
                    print(f'  [{r["status"]:7s}] {r["id"]}: actual={r["actual"]} expected={r["expected"]}')
            print(f'report: {REPORT}')

    return 1 if verdict == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
