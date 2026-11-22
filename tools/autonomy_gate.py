#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自主决策环准入门控：判断一张卡能否安全地被自动 claim→verify→apply

依据（2026-11-22 实测）：ready 队列判据强度参差——
  S19 MIXED(1强1弱) / M10 MIXED(1强5弱) / STRAT1 DOCUMENT(0强2文档) / S21 STRUCTURAL(0强2弱)
自动 apply 弱判据卡 = 批量假绿。本工具是"开自主心跳"的安全前置。

铁律：
  ★ 强判据 = test_pass / gate_result / trace_count / trace_absent / json_field
    （与 tools/audit_verify.py 的 STRONG 集合一致，不复制粘贴，运行时读取）
  ★ 准入 = 至少有 1 条强判据 且 无 manual 判据 且 状态可自动
  ★ 不自动把"文档卡/结构卡/纯弱判据卡"标 done
  ★ 只输出判定，不改权威源（决策权仍在人）

用法:
  D:/Python/python.exe -B tools/autonomy_gate.py [--card ID] [--json] [--ready]
退出码: 0=有可准入卡; 1=全部不准入; 2=错误
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))


def load_strong_set():
    """从 audit_verify.py 运行时读取 STRONG 集合，避免定义漂移。"""
    s = (ROOT / 'tools/audit_verify.py').read_text(encoding='utf-8', errors='replace')
    m = re.search(r'STRONG\s*=\s*\{([^}]*)\}', s)
    if not m:
        raise RuntimeError('无法从 audit_verify.py 读取 STRONG 集合')
    return {x.strip().strip("'\"") for x in m.group(1).split(',') if x.strip()}


def load_cards():
    import roadmap_check as rc
    d = rc.load_ladder()
    return [i for g in ('items', 'rungs') for i in d[g]]


def assess(card, strong):
    """判定单卡准入。返回 dict（可读理由，不暗箱）。"""
    cid = card.get('id', '?')
    status = card.get('status', '?')
    verify = card.get('verify', []) or []
    kinds = [v.get('kind', '?') for v in verify]
    n_strong = sum(1 for k in kinds if k in strong)
    n_manual = sum(1 for k in kinds if k == 'manual')
    n_weak = len(kinds) - n_strong - n_manual

    reasons = []
    allowed = True
    if n_strong == 0:
        allowed = False
        reasons.append('无强判据（test_pass/gate_result/trace_count等）——自动apply会假绿')
    if n_manual:
        allowed = False
        reasons.append(f'含 {n_manual} 条 manual 判据——须人工裁决')
    # 强判据不仅要"类型对"，命令/文件还必须真实存在（S19 踩坑：test_pass 指向的文件不存在）
    for v in verify:
        if v.get('kind') in strong:
            cmd = str(v.get('cmd') or '')
            path = str(v.get('path') or v.get('file') or '')
            if cmd:
                # 取命令中的脚本路径 token
                toks = [t for t in cmd.replace('"','').split() if t.endswith(('.py', '.mjs', '.sh'))]
                for t in toks:
                    fp = Path(t) if Path(t).is_absolute() else ROOT / t
                    if not fp.exists():
                        allowed = False
                        reasons.append(f'强判据命令脚本不存在: {t}——类型对但跑不了')
            if path and not (ROOT / path).exists() and not Path(path).exists():
                allowed = False
                reasons.append(f'强判据目标不存在: {path}')
    if not card.get('autonomous'):
        allowed = False
        reasons.append('autonomous=false——卡本身标记为需人工')
    if status not in ('ready', 'doing'):
        allowed = False
        reasons.append(f'status={status} 非 ready/doing')
    # 报告 G5：test_pass min=1 一条即过=恒真假绿风险，要求 min>=2
    for v in verify:
        if v.get('kind') == 'test_pass' and int(v.get('min', 1) or 1) < 2:
            allowed = False
            reasons.append(f'test_pass min={v.get("min",1)}<2——单条断言易假绿')
    # 报告"软门槛转人工"：weak>3 或 强/弱比<1/3
    if n_weak > 3:
        allowed = False
        reasons.append(f'弱判据 {n_weak}>3——证据结构失衡，转人工')
    if n_strong and n_weak and n_strong / n_weak < 1/3:
        allowed = False
        reasons.append(f'强/弱比 {n_strong}/{n_weak}<1/3——转人工')
    # 报告"陈旧卡"：verify 全过但 status 仍 ready（如 STRAT1）——不自动关，由人
    # （此处只标记；实际 verify 执行代价高，交给调用方）
    if card.get('touches_metagovernance') or cid == 'STRAT1':
        allowed = False
        reasons.append('触及元治理——须人类按ADR流程推进，禁止自动环代关')

    if allowed:
        reasons.append(f'{n_strong} 条强判据可机验，无人工判据——可安全自动推进')
    return {'id': cid, 'status': status, 'allowed': allowed,
            'strong': n_strong, 'weak': n_weak, 'manual': n_manual,
            'kinds': kinds, 'reasons': reasons}


def main():
    ap = argparse.ArgumentParser(description='自主决策环准入门控（只判定，不改权威源）')
    ap.add_argument('--card', help='只判定指定卡')
    ap.add_argument('--ready', action='store_true', help='只判定 ready 卡')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--check-report', action='store_true', help='门禁用:工具正常即0,不管准入数')
    args = ap.parse_args()

    try:
        strong = load_strong_set()
        cards = load_cards()
    except Exception as e:
        print(f'FAIL: {e}', file=sys.stderr)
        return 2

    if args.card:
        cards = [c for c in cards if c.get('id') == args.card]
        if not cards:
            print(f'NO_SUCH_CARD: {args.card}', file=sys.stderr)
            return 2
    elif args.ready:
        cards = [c for c in cards if c.get('status') == 'ready']

    results = [assess(c, strong) for c in cards]
    allowed = [r for r in results if r['allowed']]
    if args.check_report:
        # 门禁模式：报告有效即可（0准入是安全状态，不是工具故障）
        print(f'CHECK-REPORT OK: 评估 {len(results)} 张, 可自动 {len(allowed)} 张')
        return 0

    if args.json:
        print(json.dumps({'strong_kinds': sorted(strong), 'results': results,
                          'allowed_count': len(allowed)}, ensure_ascii=False, indent=2))
    else:
        print('=' * 66)
        print(' 自主决策环准入门控 — 只判定，不改权威源')
        print('=' * 66)
        print(f'  强判据种类: {", ".join(sorted(strong))}')
        for r in results:
            tag = 'ALLOW' if r['allowed'] else 'DENY '
            print(f'  [{tag}] {r["id"]:10} {r["status"]:8} 强{r["strong"]}/弱{r["weak"]}/人工{r["manual"]}')
            for why in r['reasons'][:2]:
                print(f'           ↳ {why}')
        print()
        print(f'  可安全自动推进: {len(allowed)}/{len(results)} 张')
        if not allowed:
            print('  ⚠ 无卡可自动推进——不要开自主心跳')

    return 0 if allowed else 1


if __name__ == '__main__':
    sys.exit(main())
