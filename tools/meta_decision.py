#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A4 元决策器：把"卡住"信号从 prompt 软提示升级为代码级决策

决策输出（一等公民）：CONTINUE / REPLAN / SKIP / ESCALATE
依据：docs/DECC_ARCHITECTURE_REVIEW_20261122.md
  - 当前 D1 重复探测只在 prompt 层提醒，代码无 abandon/skip 路径
  - 终止/升级应是架构组件而非事后补丁（社区共识）

输入信号（都已存在，只是没被统一裁决）：
  1. attempts >= 3        → roadmap_check cmd_claim 的 manual-blocked 阈值
  2. noProgressSteps >= 6 → index.mjs D5 门控的无进展阈值
  3. goal drift           → s.bdi.goal / s.frame.goal / 当前行为 三者不一致
  4. WIP full             → flow_orchestrator 的 Rope（这不是卡住，是等待）

用法:
  D:/Python/python.exe -B tools/meta_decision.py --card ID [--attempts N] [--no-progress N]
  D:/Python/python.exe -B tools/meta_decision.py --card ID --goal-drift   # 模拟目标漂移
  D:/Python/python.exe -B tools/meta_decision.py --demo                   # 四种决策演示
  D:/Python/python.exe -B tools/meta_decision.py --card ID --json
退出码: 0=CONTINUE; 2=REPLAN; 3=SKIP; 4=ESCALATE（供调用方代码分支）

⚠ 本模块只**输出决策建议**，不自动改路线图状态——写回仍需走
   roadmap_check --apply 的人工/门禁链（保持 A2 的闸门）。
"""
import argparse
import json
import sys

CONTINUE, REPLAN, SKIP, ESCALATE = 'CONTINUE', 'REPLAN', 'SKIP', 'ESCALATE'
EXIT = {CONTINUE: 0, REPLAN: 2, SKIP: 3, ESCALATE: 4}

ATTEMPTS_ESCALATE = 3       # 与 roadmap_check cmd_claim 一致
NO_PROGRESS_ESCALATE = 6    # 与 index.mjs noProgressSteps 一致
NO_PROGRESS_REPLAN = 3      # 早期信号：还没到 6，但已值得换方法


def decide(card, attempts=0, no_progress=0, goal_drift=False, wip_full=False,
           consecutive_same_file=0):
    """返回 (decision, reasons, suggested_action)

    优先级（最严厉优先）：ESCALATE > SKIP > REPLAN > CONTINUE
    """
    reasons, action = [], ''

    # ESCALATE：连续失败已达上限 / 目标漂移（方向错了，必须人介入）
    if attempts >= ATTEMPTS_ESCALATE:
        reasons.append(f'attempts={attempts}>={ATTEMPTS_ESCALATE}（与claim层阈值一致）')
    if goal_drift:
        reasons.append('goal drift: 行为已偏离 bdi/frame 记录的原目标')
    if reasons:
        return ESCALATE, reasons, f'停止 {card}，向人报告：附已排除清单与漂移证据；等待人工裁决'

    # SKIP：同一任务连续重复探测（同参双败），换方法也无益
    if consecutive_same_file >= 2:
        reasons.append(f'同一文件连续失败 {consecutive_same_file} 次（换方法纪律）')
        return SKIP, reasons, f'跳过 {card} 当前路径，标记 requires-human-method；不消耗更多 attempts'

    # REPLAN：无进展早期信号 / WIP 满（不是卡住，是节拍问题）
    if no_progress >= NO_PROGRESS_ESCALATE:
        reasons.append(f'no_progress={no_progress}>={NO_PROGRESS_ESCALATE}')
        return REPLAN, reasons, f'重规划 {card}：拆小任务或换执行路径（不是重试同一动作）'
    if no_progress >= NO_PROGRESS_REPLAN:
        reasons.append(f'no_progress={no_progress}（早期停滞）')
        return REPLAN, reasons, f'考虑重规划 {card}：先做一个最小可验证步骤打破停滞'
    if wip_full:
        reasons.append('WIP full: 决策环无空位')
        return REPLAN, reasons, '等待当前卡完成（DBR Rope）；不是失败，是节拍'

    return CONTINUE, ['无停滞/漂移/失败信号'], f'继续 {card} 的当前执行路径'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', default='DEMO')
    ap.add_argument('--attempts', type=int, default=0)
    ap.add_argument('--no-progress', type=int, default=0)
    ap.add_argument('--goal-drift', action='store_true')
    ap.add_argument('--wip-full', action='store_true')
    ap.add_argument('--same-file-fails', type=int, default=0)
    ap.add_argument('--demo', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    if args.demo:
        cases = [
            ('正常推进', dict(attempts=0, no_progress=0)),
            ('早期停滞', dict(attempts=0, no_progress=4)),
            ('长期停滞', dict(attempts=0, no_progress=7)),
            ('同文件双败', dict(attempts=1, consecutive_same_file=2)),
            ('目标漂移', dict(attempts=1, goal_drift=True)),
            ('失败达上限', dict(attempts=3)),
        ]
        print('=' * 60)
        print(' A4 元决策器 — 六种信号的决策输出')
        print('=' * 60)
        for name, kw in cases:
            d, why, act = decide('DEMO', **kw)
            print(f'  {name:10} → {d:9} | {why[0][:44]}')
            print(f'  {"":10}    {act[:70]}')
        return 0

    d, why, act = decide(args.card, args.attempts, args.no_progress,
                         args.goal_drift, args.wip_full, args.same_file_fails)
    out = {'card': args.card, 'decision': d, 'reasons': why, 'suggested_action': act,
           'exit_code': EXIT[d]}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f'[META] card={args.card} decision={d}')
        for r in why:
            print(f'  · {r}')
        print(f'  ↳ {act}')
    return EXIT[d]


if __name__ == '__main__':
    sys.exit(main())
