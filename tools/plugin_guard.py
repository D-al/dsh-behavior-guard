#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plugin_guard —— 插件配置实时守卫（独立进程，跑在 dsh 权限系统之外）

缘起（2026-11-26 事故）：
  dsh 在 danger-full-access 会话里把 bundle 名改成 @local/xxx（语法合法、语义错误），
  又因 plugin_manager remove_bundle 内部的 pnpm EPERM 把 autostart 插件目录清空。
  harness 的提示词护栏在这种配置下全部失效——唯一可靠的门禁必须在 dsh 进程外。

三条规则（零 LLM，纯哈希 + 正则）：
  1. bundle 名合法性：cordis.patch.yml 里每个 name: 必须等于该插件 package.json 的 name
     （或合法 scoped 名 @scope/pkg）。臆造前缀如 @local/xxx → 告警 + 自动改回。
  2. 关键文件存在性：核心插件的 index.mjs/package.json/cordis.patch.yml/frame_limiter.py
     消失 → 告警 + 从权威源自动恢复。
  3. 变更哈希审计：每次变更记 _plugin_guard.jsonl（时间、路径、前后哈希、动作）。

用法:
  D:/Python/python.exe -B tools/plugin_guard.py --once        # 单次巡检（可接启动门禁）
  D:/Python/python.exe -B tools/plugin_guard.py --watch       # 常驻监听（默认 2s 轮询）
  D:/Python/python.exe -B tools/plugin_guard.py --watch --parent-pid 1234
      ↑ 由 dsh autostart 插件拉起时传父 pid：父进程消失则自动退出，与 dsh 同生命周期
  D:/Python/python.exe -B tools/plugin_guard.py --dry-run     # 只记不修（可观测优先起点）
  D:/Python/python.exe -B tools/plugin_guard.py --selftest    # 自检：注入坏改动验证会红

退出码: 0=全绿/已修复; 1=有未修复的问题（--once 模式）; 2=自检失败

日志: D:/Brain/workspace/bench/_plugin_guard.jsonl
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

DSH_HOME = os.environ.get('DSH_HOME') or r'D:\Brain\dsh-data'
PROFILE = Path(DSH_HOME) / 'profiles' / 'desktop'
NODE_MODULES = PROFILE / 'node_modules'
BENCH = Path(os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench')
LOG = BENCH / '_plugin_guard.jsonl'

# 权威源映射：插件名 -> 权威源目录。hardware-monitor 用 GitHub clone 的工作副本。
AUTHORITATIVE = {
    'dsh-agent-harness': Path(r'D:\Brain\publish\dsh-agent-harness'),
    'dsh-llama-server-autostart': Path(r'D:\Brain\publish\dsh-llama-server-autostart'),
    'dsh-hardware-monitor': Path(r'C:\Users\Ad\Documents\deepseek-harness\default-workspace\hardware-monitor-plugin'),
}

# 每个核心插件必须存在的文件（相对插件目录）
CRITICAL_FILES = {
    'dsh-agent-harness': ['index.mjs', 'package.json', 'cordis.patch.yml'],
    'dsh-llama-server-autostart': ['index.mjs', 'package.json', 'cordis.patch.yml', 'frame_limiter.py'],
    'dsh-hardware-monitor': ['index.js', 'package.json', 'cordis.patch.yml'],
}

# 合法 bundle 名：普通包名或 scoped 包名。@local/ 前缀是我们明确禁止的臆造别名。
BUNDLE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*(/[A-Za-z0-9._-]+)?$|^@[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$')
NAME_LINE_RE = re.compile(r'^(\s*name:\s*)([\'"]?)([^\'"\s]+)\2\s*$', re.M)


def sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except Exception:
        return '<missing>'


def now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def log(ev: str, **kw) -> None:
    """append-only 审计日志；同步写，避免进程快速退出丢失。"""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'ts': now(), 'ev': ev, **kw}, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f'[plugin_guard] log failed: {e}', file=sys.stderr)


def pkg_name(plugin_dir: Path) -> str | None:
    p = plugin_dir / 'package.json'
    try:
        return json.loads(p.read_text(encoding='utf-8')).get('name')
    except Exception:
        return None


def check_bundle_name(patch: Path, expected: str, dry_run: bool) -> list[str]:
    """规则1：patch 里所有 name: 必须合法且等于 package.json 的 name。
    返回修复说明列表。"""
    issues = []
    try:
        text = patch.read_text(encoding='utf-8')
    except Exception as e:
        return [f'READ_FAIL {patch.name}: {e}']
    before = sha(patch)
    fixes = []
    for m in NAME_LINE_RE.finditer(text):
        raw = m.group(3)
        # 注释行里的 name 不管，只管形如 `      name: xxx` 的 YAML 键
        if raw.startswith('#'):
            continue
        # @local/ 是事故中 dsh 臆造的别名前缀，显式禁止（即使它符合 scoped 包名格式）
        if raw.startswith('@local/') or not BUNDLE_RE.match(raw):
            fixes.append((m.group(1), m.group(2), raw, expected))
        elif raw != expected:
            # 合法但不是本插件名（可能是别的 bundle 引用）——只警告不自动改
            issues.append(f'WARN_NAME_MISMATCH {patch.parent.name}: {raw} != {expected}')

    if fixes:
        for prefix, quote, bad, good in fixes:
            issues.append(f'BAD_BUNDLE {patch.parent.name}: {bad} -> {good}')
        if not dry_run:
            new_text = text
            for prefix, quote, bad, good in reversed(fixes):
                old_line = f'{prefix}{quote}{bad}{quote}'
                new_line = f'{prefix}{quote}{good}{quote}'
                new_text = new_text.replace(old_line, new_line, 1)
            patch.write_text(new_text, encoding='utf-8')
            log('AUTO_FIX_BUNDLE', path=str(patch), before=before, after=sha(patch), bad=[f[2] for f in fixes])
        else:
            log('DRY_FIX_BUNDLE', path=str(patch), bad=[f[2] for f in fixes])
    return issues


def check_critical_files(plugin: str, dry_run: bool) -> list[str]:
    """规则2：核心文件消失 -> 从权威源恢复。"""
    issues = []
    target_dir = NODE_MODULES / plugin
    source_dir = AUTHORITATIVE.get(plugin)
    if not source_dir or not source_dir.exists():
        issues.append(f'NO_AUTHORITATIVE_SOURCE {plugin}: {source_dir}')
        return issues
    for rel in CRITICAL_FILES.get(plugin, []):
        dst = target_dir / rel
        src = source_dir / rel
        if dst.exists():
            continue
        issues.append(f'MISSING {plugin}/{rel}')
        if not src.exists():
            issues.append(f'  SOURCE_ALSO_MISSING {src}')
            continue
        if not dry_run:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                log('AUTO_RESTORE', plugin=plugin, file=rel, src=str(src), sha=sha(dst))
            except Exception as e:
                issues.append(f'  RESTORE_FAIL {e}')
                log('RESTORE_FAIL', plugin=plugin, file=rel, err=str(e)[:160])
        else:
            log('DRY_RESTORE', plugin=plugin, file=rel, src=str(src))
    return issues


def snapshot() -> dict[str, str]:
    """当前所有被监听文件的哈希快照。"""
    out = {}
    for d in sorted(NODE_MODULES.glob('*/')):
        patch = d / 'cordis.patch.yml'
        if patch.exists():
            out[str(patch)] = sha(patch)
    for plugin in CRITICAL_FILES:
        d = NODE_MODULES / plugin
        for rel in CRITICAL_FILES[plugin]:
            f = d / rel
            if f.exists():
                out[str(f)] = sha(f)
    return out


def check_once(dry_run: bool, prev: dict | None) -> tuple[list[str], dict]:
    issues = []
    cur = snapshot()

    # 变更哈希审计（规则3）
    if prev is not None:
        for path, h in cur.items():
            if path in prev and prev[path] != h:
                log('CHANGED', path=path, before=prev[path], after=h)

    # 规则1：遍历所有插件的 patch
    for d in sorted(NODE_MODULES.glob('*/')):
        patch = d / 'cordis.patch.yml'
        if not patch.exists():
            continue
        expected = pkg_name(d)
        if not expected:
            continue
        issues.extend(check_bundle_name(patch, expected, dry_run))

    # 规则2：核心插件关键文件
    for plugin in CRITICAL_FILES:
        issues.extend(check_critical_files(plugin, dry_run))

    return issues, cur


def pid_alive(pid: int) -> bool:
    """父进程存活检查（Windows/OpenOS 通用）。父死则 watcher 自动退出，避免孤儿常驻。"""
    if not pid or pid <= 0:
        return True
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            SYNCHRONIZE = 0x00100000
            k = ctypes.windll.kernel32
            h = k.OpenProcess(SYNCHRONIZE, False, pid)
            if not h:
                return False
            k.CloseHandle(h)
            return True
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def selftest() -> int:
    """自检：在临时目录注入坏 bundle 名，验证规则1能检出。"""
    import tempfile
    good = 'dsh-test-plugin'
    bad = '@local/dsh-test-plugin'
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / 'package.json').write_text(json.dumps({'name': good}), encoding='utf-8')
        p = d / 'cordis.patch.yml'
        p.write_text(f'- insert:\n    - id: test\n      name: \'{bad}\'\n', encoding='utf-8')
        issues = check_bundle_name(p, good, dry_run=True)
        ok = any('BAD_BUNDLE' in i for i in issues)
        print(f'[selftest] bad bundle detected: {ok}')
        print(f'[selftest] issues: {issues}')
        # 验证好名字不误报
        p.write_text(f'- insert:\n    - id: test\n      name: {good}\n', encoding='utf-8')
        issues2 = check_bundle_name(p, good, dry_run=True)
        ok2 = not any('BAD_BUNDLE' in i for i in issues2)
        print(f'[selftest] good bundle no false positive: {ok2}')
        return 0 if (ok and ok2) else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--once', action='store_true', help='单次巡检后退出（适合启动门禁）')
    ap.add_argument('--watch', action='store_true', help='常驻监听')
    ap.add_argument('--interval', type=float, default=2.0, help='轮询间隔秒（默认2）')
    ap.add_argument('--parent-pid', type=int, default=0, help='父进程 pid；父进程消失则自动退出（与 dsh 同生命周期）')
    ap.add_argument('--dry-run', action='store_true', help='只记不修（可观测优先）')
    ap.add_argument('--selftest', action='store_true', help='自检')
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    log('START', mode='once' if args.once else ('watch' if args.watch else 'once'), dry_run=args.dry_run)
    prev = snapshot()

    while True:
        # 与 dsh 同生命周期：父进程（autostart 插件所在进程）消失则自动退出。
        if not pid_alive(args.parent_pid):
            log('PARENT_GONE', parent=args.parent_pid)
            print(f'[plugin_guard] parent {args.parent_pid} gone, exiting')
            return 0
        issues, cur = check_once(args.dry_run, prev)
        prev = cur
        mode = 'DRY' if args.dry_run else 'FIX'
        for i in issues:
            print(f'[{mode}] {i}')
            log('ISSUE', detail=i)
        if args.once or not args.watch:
            return 1 if issues else 0
        time.sleep(args.interval)


if __name__ == '__main__':
    sys.exit(main())
