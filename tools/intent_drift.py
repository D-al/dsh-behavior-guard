# -*- coding: utf-8 -*-
"""intent_drift —— 意图漂移监测（离线，零 LLM，零风险）

依据（2026-11-18 广搜）：
- 长任务中目标逐渐跑偏是长程 agent 主要失败模式；RGE/LivePlan 用 (role, goal, evidence)
  三元组 + 确定性状态机做到漂移 F1 >93%、良性覆盖 ≥95.8%，成本近零。
- 我们的现场实证：一次会话 P0 存档 16 次注入同一份"写插件"初始任务，
  但用户最新指令已变成"给个测试窗口展示效果"——典型意图漂移，且 P0 存档没有跟上。

本脚本是这个方向的**离线最小版**：从会话文件抽取所有真实用户指令，
用关键词集合的 Jaccard/覆盖率算与初始任务的偏离，输出漂移时间线。

用法（只读，不碰会话）：
  python intent_drift.py                       # 自动找最新会话
  python intent_drift.py --session <目录>
  python intent_drift.py --threshold 0.25      # 覆盖率低于此值判漂移（默认 0.25）
"""
import json
import os
import re
import sys
import glob

SESS_ROOT = r'D:\Brain\dsh-data\sessions\--C-Users-Ad-Documents-deepseek-harness-default-workspace--'
OUT = r'D:\Brain\workspace\bench\_intent_drift.json'

STOP = set('帮我 请你 一个 这个 一下 什么 怎么 可以 是否 以及 然后 现在 需要 给个 展示 一下'.split())


def keywords(t):
    """中文 2+ 字词 + 英文词，去停用词"""
    words = set(re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z][\w-]{1,}', t))
    return {w for w in words if w not in STOP}


def load(src):
    import zstandard as zstd
    if src.endswith(('.zstd', '.zst')):
        raw = zstd.ZstdDecompressor().stream_reader(open(src, 'rb')).read().decode('utf-8')
        return [json.loads(l) for l in raw.split('\n') if l.strip()]
    return [json.loads(l) for l in open(src, encoding='utf-8') if l.strip()]


def user_instructions(events):
    out = []
    for i, e in enumerate(events):
        d = e.get('data', {})
        if not isinstance(d, dict):
            continue
        src = d.get('source') or {}
        if not (isinstance(src, dict) and src.get('kind') == 'user'):
            continue
        c = d.get('content', [])
        t = ''.join(b.get('text', '') for b in c if isinstance(b, dict) and b.get('type') == 'text').strip()
        if not t or t.startswith('[harness ') or t.startswith('<system-reminder>'):
            continue
        out.append({'seq': i, 'text': t[:500]})
    return out


def main():
    args = sys.argv[1:]
    threshold = 0.25
    if '--threshold' in args:
        threshold = float(args[args.index('--threshold') + 1])
    files = glob.glob(os.path.join(SESS_ROOT, '*', 'session.v4.jsonl.zstd'))
    if '--session' in args:
        files = [args[args.index('--session') + 1]]
    if not files:
        print('无会话文件')
        return
    src = max(files, key=os.path.getmtime)
    events = load(src)
    insts = user_instructions(events)
    if not insts:
        print('无用户指令')
        return

    initial = insts[0]
    ikw = keywords(initial['text'])
    print(f'会话: {os.path.basename(os.path.dirname(src))}')
    print(f'初始任务 (seq {initial["seq"]}): {initial["text"][:100]}')
    print(f'用户指令总数: {len(insts)}\n')
    print(f'{"seq":>6} {"覆盖":>6}  指令（截取）')
    print('-' * 76)

    drifts = []
    for x in insts[1:]:
        kw = keywords(x['text'])
        cover = len(ikw & kw) / max(len(ikw), 1)
        flag = ' ⚠漂移' if cover < threshold else ''
        print(f'{x["seq"]:>6} {cover:>6.2f}  {x["text"][:60]}{flag}')
        if cover < threshold:
            drifts.append({'seq': x['seq'], 'coverage': round(cover, 3), 'text': x['text'][:200]})

    print('-' * 76)
    print(f'漂移指令 {len(drifts)}/{len(insts)-1} 条（阈值 {threshold}）')
    if drifts:
        last = drifts[-1]
        print(f'最近一次漂移在 seq {last["seq"]}: {last["text"][:100]}')
        print('→ 建议：P0 存档应标注最新指令优先于初始任务；心智状态快照已做此检测。')

    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'session': os.path.basename(os.path.dirname(src)),
                   'initial': initial, 'threshold': threshold,
                   'drifts': drifts, 'total_instructions': len(insts)},
                  f, ensure_ascii=False, indent=2)
    print(f'\n结构化结果 → {OUT}')


if __name__ == '__main__':
    main()
