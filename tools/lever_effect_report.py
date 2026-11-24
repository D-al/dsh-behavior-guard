# -*- coding: utf-8 -*-
"""四杠杆上线效果评估（诚实口径）。

区分：
- L4 命中：真实 sid 的 trace kind 出现（机制触发了）
- L5 效果：独立产物证明行为改变（fileState / 拦截 / 状态板内容）
- 效果 ≠ 命中：命中只是机制跑了，效果要看它改变了什么

用法：python lever_effect_report.py <since_iso>  # 只看上线后的 trace
"""
import sys, json, collections
from pathlib import Path

TRACE = Path('D:/Brain/workspace/bench/_trace.jsonl')
KINDS = {
    'verify_state_readback': '杠杆1 确定性状态回读',
    'state_board_inject': '杠杆2 显式状态板',
    'self_consistency_vote': '杠杆4 K=5 投票',
}


def load_since(since):
    rows = []
    for line in TRACE.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if since and str(r.get('ts', '')) < since:
            continue
        rows.append(r)
    return rows


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else None
    rows = load_since(since)
    print(f'=== 效果评估（since={since or "全部"}，共 {len(rows)} 条 trace）===\n')
    for kind, name in KINDS.items():
        hits = [r for r in rows if r.get('kind') == kind]
        real = [r for r in hits if str(r.get('sid', '')) != 's1' and r.get('sid')]
        print(f'[{name}] 总 {len(hits)} 条，真实会话 {len(real)} 条')
        if not real:
            print('  效果判定：未命中（机制没跑到，或默认关）'); print(); continue
        if kind == 'verify_state_readback':
            ok = sum(1 for r in real if r.get('ok') is True)
            skip = sum(1 for r in real if r.get('skipped') is True)
            fail = len(real) - ok - skip
            print(f'  L4 命中 {len(real)}：ok={ok} skipped={skip} fail={fail}')
            for r in real[-2:]:
                ev = r.get('evidence') or []
                print(f'    证据: sid={str(r.get("sid"))[:16]} ok={r.get("ok")} evidence={str(ev)[:90]}')
            print(f'  效果判定：{"生效——真实回读证据已落 trace" if ok else "未生效——全跳过/失败"}')
        elif kind == 'state_board_inject':
            steps = [r.get('step') for r in real]
            bytes_ = [r.get('bytes') for r in real]
            print(f'  L4 命中 {len(real)}：steps={steps} bytes={bytes_}')
            print(f'  效果判定：{"生效——状态板已注入控制回合 prompt" if all((b or 0) > 0 and (b or 0) <= 4096 for b in bytes_) else "异常——字节数越界"}')
        elif kind == 'self_consistency_vote':
            print(f'  L4 命中 {len(real)}：verdicts={[r.get("verdict") for r in real]}')
            print('  效果判定：默认关；需开 voteOnCritic 后再评估')
        print()
    # 关联：回读门命中时，verify_on_stop 是否还独立触发（机制并存不互斥）
    print('=== 机制并存检查 ===')
    real_rb = [r for r in rows if r.get('kind') == 'verify_state_readback' and str(r.get('sid', '')) != 's1']
    for r in real_rb[-3:]:
        sid = r.get('sid')
        vos = [x for x in rows if x.get('kind') == 'verify_on_stop' and x.get('sid') == sid]
        print(f'  sid={str(sid)[:16]} 回读ok={r.get("ok")} verify_on_stop={len(vos)}次')


if __name__ == '__main__': main()
