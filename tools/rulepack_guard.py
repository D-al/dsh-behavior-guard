#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则包版本钉住校验：防止执行者(agent)偷改评判规则

设计（版本钉住 ≠ 永不改变）：
- 受保护文件（评判者）的权威 digest 存在 git 里的 manifest（git show HEAD:...），
  而不是工作区文件——改工作区 manifest 无效，必须 commit 才生效（commit 留痕）。
- 校验：当前工作区受保护文件的 sha256 必须匹配 git 里的 manifest。
- 漂移 = 有人改了评判规则但没走"新版本 + 显式批准"流程 → 门禁变红。
- agent 想改规则：走 rulepack_propose.py 提 staging diff，由维护者(人)审核后
  更新 manifest 并 commit——这才产生新版本。

权限边界说明（诚实）：
当前 agent 与维护者同为 Windows 标准用户 Ad，OS ACL 无法隔离同一用户。
所以本机制是"检测 + 留痕 + 纪律"，不是"物理阻止"——它把"偷改"变成"立刻可见的红灯"。

用法:
  D:/Python/python.exe -B tools/rulepack_guard.py
  D:/Python/python.exe -B tools/rulepack_guard.py --json
退出码: 0=规则包未漂移; 1=漂移或未初始化
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_REL = 'bench/rulepack/manifest.json'
PROPOSALS = ROOT / 'bench/rulepack/STAGING'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def git_head_manifest():
    """权威 manifest 从 git HEAD 读，不信工作区文件"""
    try:
        r = subprocess.run(['git', 'show', f'HEAD:{MANIFEST_REL}'], cwd=ROOT,
                           capture_output=True, text=True, encoding='utf-8', timeout=15)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    m = git_head_manifest()
    if m is None:
        msg = '规则包 manifest 未在 git HEAD 中初始化'
        if args.json:
            print(json.dumps({'ok': False, 'error': msg}, ensure_ascii=False))
        else:
            print(f'[RULEPACK] FAIL  {msg}')
        return 1

    protected = m.get('protected', {})
    drifts = []
    for rel, meta in protected.items():
        p = ROOT / rel
        if not p.exists():
            drifts.append({'file': rel, 'why': 'missing'})
            continue
        want = meta.get('sha256', '')
        got = sha256(p)
        if want and got != want[:16]:
            drifts.append({'file': rel, 'why': 'digest-mismatch',
                           'want': want[:16], 'got': got[:16]})

    # 未决提案数（信息性，不算失败——提案本来就是允许的）
    pending = len(list(PROPOSALS.glob('*.diff'))) if PROPOSALS.exists() else 0
    ok = not drifts

    if args.json:
        print(json.dumps({'ok': ok, 'version': m.get('version'),
                          'drifts': drifts, 'pending_proposals': pending}, ensure_ascii=False))
    else:
        print(f'[RULEPACK] version={m.get("version")} protected={len(protected)} '
              f'pending_proposals={pending}')
        if drifts:
            for d in drifts:
                if d['why'] == 'digest-mismatch':
                    print(f'[RULEPACK] FAIL  {d["file"]} digest {d["got"]} != pinned {d["want"]}')
                else:
                    print(f'[RULEPACK] FAIL  {d["file"]} {d["why"]}')
            print('[RULEPACK] ↳ 修复: 若变更已获批准，更新 manifest 并 commit；否则回滚该文件')
        else:
            print('[RULEPACK] PASS  规则包未漂移')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
