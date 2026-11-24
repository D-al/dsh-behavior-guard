# -*- coding: utf-8 -*-
"""四杠杆上线总控：前置检查 → 备份 → 应用 → 验证 → 回滚。

⚠️ 核心纪律：
1. 评测未完成时拒绝上线（防止重启 dsh 打断评测）
2. 两处副本（权威源 + 运行版）必须同步，sha256 校验
3. 应用前必须备份，回滚必须可一键执行
4. 上线 ≠ 生效：必须用真实 sid trace (L4) + 独立产物 (L5) 验证

用法：
  python levers_deploy.py preflight       # 前置检查
  python levers_deploy.py backup          # 备份两处 index.mjs
  python levers_deploy.py apply <lever>   # 应用单个杠杆补丁（1/2/3/4）
  python levers_deploy.py verify <lever>  # 验证单个杠杆
  python levers_deploy.py rollback        # 回滚到备份
  python levers_deploy.py status          # 看当前状态
"""
import sys, json, hashlib, shutil, subprocess
from pathlib import Path

AUTHORITATIVE = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
RUNTIME = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
BACKUP_DIR = Path('D:/Brain/publish/dsh-behavior-guard/.backups/levers-20261124')
STATE_FILE = BACKUP_DIR / 'state.json'
EVAL_RESULT = Path('D:/Brain/workspace/bench/_bfcl_irrelevance_result.jsonl')
EVAL_TARGET = 100

LEVERS = {1: 'state_readback', 2: 'state_board', 3: 'tool_stage', 4: 'self_consistency'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def L(m):
    print(m, flush=True)


def preflight():
    """上线前置检查：评测完成 + 两副本一致 + 语法 OK。"""
    ok = True
    # 1. 评测必须完成
    n = len([l for l in EVAL_RESULT.read_text(encoding='utf-8').splitlines() if l.strip()]) if EVAL_RESULT.exists() else 0
    if n < EVAL_TARGET:
        L(f'[FAIL] 评测未完成: {n}/{EVAL_TARGET} —— 拒绝上线（重启 dsh 会打断评测）')
        ok = False
    else:
        L(f'[OK] 评测完成: {n}/{EVAL_TARGET}')

    # 2. 两副本存在且一致
    for name, p in [('权威源', AUTHORITATIVE), ('运行版', RUNTIME)]:
        if not p.exists():
            L(f'[FAIL] {name} 不存在: {p}'); ok = False
    if AUTHORITATIVE.exists() and RUNTIME.exists():
        a, b = sha(AUTHORITATIVE), sha(RUNTIME)
        if a != b:
            L(f'[FAIL] 两副本不一致: 权威={a[:16]} 运行={b[:16]} —— 先同步再上线')
            ok = False
        else:
            L(f'[OK] 两副本一致 sha={a[:16]}')

    # 3. 语法检查
    for name, p in [('权威源', AUTHORITATIVE), ('运行版', RUNTIME)]:
        if p.exists():
            r = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True)
            if r.returncode != 0:
                L(f'[FAIL] {name} 语法错误: {r.stderr[:200]}'); ok = False
            else:
                L(f'[OK] {name} 语法通过')
    return ok


def backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    state = {}
    for name, p in [('authoritative', AUTHORITATIVE), ('runtime', RUNTIME)]:
        dst = BACKUP_DIR / f'index.mjs.{name}.bak'
        shutil.copy2(p, dst)
        state[name] = {'path': str(p), 'sha': sha(p), 'backup': str(dst)}
        L(f'[备份] {name}: {sha(p)[:16]} -> {dst.name}')
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
    L(f'[OK] 状态写入 {STATE_FILE}')


def status():
    L(f'权威源 sha={sha(AUTHORITATIVE)}')
    L(f'运行版 sha={sha(RUNTIME)}')
    if STATE_FILE.exists():
        st = json.loads(STATE_FILE.read_text(encoding='utf-8'))
        for k, v in st.items():
            L(f'备份[{k}] sha={v["sha"]} -> {v["backup"]}')
    else:
        L('无备份记录')


def apply_lever(lever_id):
    """应用补丁（由各杠杆补丁脚本实现，这里只做调度 + 一致性保证）。"""
    if lever_id not in LEVERS:
        L(f'[FAIL] 未知杠杆 {lever_id}，可选: {list(LEVERS)}'); return
    if not preflight():
        L('[ABORT] 前置检查失败，不应用'); return
    patch = Path(__file__).parent / f'lever{lever_id}_{LEVERS[lever_id]}_patch.py'
    if not patch.exists():
        L(f'[FAIL] 补丁脚本不存在: {patch}'); return
    r = subprocess.run([sys.executable, str(patch)], capture_output=True, text=True)
    L(r.stdout[-2000:])
    if r.returncode != 0:
        L(f'[FAIL] 补丁失败: {r.stderr[:500]}'); return
    # 补丁改权威源后同步到运行版
    shutil.copy2(AUTHORITATIVE, RUNTIME)
    L(f'[OK] 杠杆{lever_id} 已应用到两副本，sha={sha(AUTHORITATIVE)[:16]}')


def rollback():
    if not STATE_FILE.exists():
        L('[FAIL] 无备份记录，无法回滚'); return
    st = json.loads(STATE_FILE.read_text(encoding='utf-8'))
    for k, v in st.items():
        dst = Path(v['path']); src = Path(v['backup'])
        shutil.copy2(src, dst)
        L(f'[回滚] {k}: sha={sha(dst)[:16]} (期望 {v["sha"][:16]})')
    ok = sha(AUTHORITATIVE) == st['authoritative']['sha'] and sha(RUNTIME) == st['runtime']['sha']
    L(f'[{"OK" if ok else "FAIL"}] 回滚校验')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if cmd == 'preflight': sys.exit(0 if preflight() else 1)
    elif cmd == 'backup': backup()
    elif cmd == 'status': status()
    elif cmd == 'rollback': rollback()
    elif cmd == 'apply': apply_lever(int(sys.argv[2]))
    else: L(f'未知命令: {cmd}')


if __name__ == '__main__': main()
