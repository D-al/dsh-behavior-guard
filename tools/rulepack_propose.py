#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则包变更提案通道：agent 只能提 diff，不能直接生效

用途：agent 发现评判规则需要改（能力缺口/误报超预算/需回滚）时，
不直接编辑受保护文件，而是用本脚本生成一个 staging 提案。
维护者(人)审核后，手动应用变更 + 更新 manifest + commit——才产生新版本。

用法:
  D:/Python/python.exe -B tools/rulepack_propose.py <受保护文件> --reason "理由"
  D:/Python/python.exe -B tools/rulepack_propose.py --list
  D:/Python/python.exe -B tools/rulepack_propose.py --reject <提案ID> --reason "理由"

提案存储: bench/rulepack/STAGING/<文件>.<timestamp>.diff
每个提案是标准 git diff，可直接  git apply --check  验证。

注意：本脚本不检查"当前工作区是否已漂移"——那是 rulepack_guard 的职责。
如果 agent 已经直接改了文件（违规），提案不会掩盖它，guard 仍会报红。
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / 'bench/rulepack/STAGING'


def load_manifest():
    r = subprocess.run(['git', 'show', 'HEAD:bench/rulepack/manifest.json'], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', timeout=15)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', nargs='?', help='受保护文件路径(相对仓库根)')
    ap.add_argument('--reason', default='', help='变更理由(必填)')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--reject', metavar='ID', help='拒绝并删除某提案')
    args = ap.parse_args()

    STAGING.mkdir(parents=True, exist_ok=True)

    if args.list:
        props = sorted(STAGING.glob('*.diff'))
        if not props:
            print('[PROPOSE] 无待审提案')
            return 0
        for p in props:
            head = p.read_text(encoding='utf-8', errors='replace').splitlines()[:3]
            print(f'[PROPOSE] {p.name}')
            for line in head:
                print(f'    {line[:100]}')
        return 0

    if args.reject:
        if not args.reason:
            print('[PROPOSE] FAIL  拒绝必须给理由 (--reason)')
            return 1
        target = STAGING / args.reject
        if not target.exists():
            print(f'[PROPOSE] FAIL  提案不存在: {args.reject}')
            return 1
        target.write_text(target.read_text(encoding='utf-8') +
                          f'\n\n<!-- REJECTED {datetime.now().isoformat()}: {args.reason} -->\n',
                          encoding='utf-8')
        renamed = target.with_suffix('.diff.rejected')
        target.rename(renamed)
        print(f'[PROPOSE] 已拒绝: {renamed.name}')
        return 0

    if not args.file or not args.reason:
        print('[PROPOSE] 用法: rulepack_propose.py <文件> --reason "理由"')
        print('[PROPOSE] 或: --list / --reject <ID> --reason "理由"')
        return 1

    m = load_manifest()
    if m is None:
        print('[PROPOSE] FAIL  规则包 manifest 未初始化')
        return 1
    if args.file not in m.get('protected', {}):
        print(f'[PROPOSE] FAIL  {args.file} 不是受保护文件')
        print(f'[PROPOSE] 受保护: {", ".join(m["protected"].keys())}')
        return 1

    # 生成当前工作区相对 HEAD 的 diff（提案 = 想做的事，不自动生效）
    r = subprocess.run(['git', 'diff', 'HEAD', '--', args.file], cwd=ROOT,
                       capture_output=True, text=True, encoding='utf-8', timeout=15)
    diff = r.stdout.strip()
    if not diff:
        print(f'[PROPOSE] FAIL  {args.file} 工作区相对 HEAD 无改动——没有可提案的内容')
        print('[PROPOSE] 提示: 先改文件，再提提案；或确认你改的不是受保护文件')
        return 1

    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    name = Path(args.file).stem + '.' + ts + '.diff'
    out = STAGING / name
    header = (f'# 规则包变更提案\n'
              f'# 文件: {args.file}\n'
              f'# 理由: {args.reason}\n'
              f'# 提出时间: {datetime.now().isoformat()}\n'
              f'# 状态: PENDING (需维护者审核 + 更新 manifest + commit 才生效)\n\n')
    out.write_text(header + diff + '\n', encoding='utf-8')
    print(f'[PROPOSE] 提案已生成: {out.name}')
    print('[PROPOSE] 提案本身不生效——维护者审核后需手动应用并更新 manifest')
    return 0


if __name__ == '__main__':
    sys.exit(main())
