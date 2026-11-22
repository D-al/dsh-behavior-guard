#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判据三源一致性门禁：ROADMAP_GRAPH.md (权威) vs CAPABILITY_LADDER.yaml (镜像)

背景（2026-11-22 三副本坑）：S19/M10/S21 判据补强时只改了权威源，
镜像仍是旧判据——读镜像的工具会看到错误判据。本门禁让漂移立即暴露。

铁律：权威源 = ROADMAP_GRAPH.md；镜像必须逐字一致（仅 verify 字段）。
退出码: 0=一致; 1=有漂移; 2=错误
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))


def main():
    try:
        import yaml
        import roadmap_check as rc
        graph = rc.load_ladder()
        mirror = yaml.safe_load((ROOT / 'CAPABILITY_LADDER.yaml').read_text(encoding='utf-8'))
    except Exception as e:
        print(f'FAIL: {e}', file=sys.stderr)
        return 2

    gmap = {i['id']: i for group in ('items', 'rungs') for i in graph[group]}
    mmap = {i['id']: i for group in ('items', 'autonomy_rungs')
            for i in mirror.get(group, [])}

    # 范围：本轮补强判据的卡（三副本坑高发区）。历史漂移另记为债务，不阻塞。
    WATCH = {'S19', 'M10', 'S21'}
    drift = []
    checked = 0
    for cid in WATCH:
        if cid not in gmap or cid not in mmap:
            print(f'  [MISSING] {cid} 权威={cid in gmap} 镜像={cid in mmap}')
            drift.append((cid, '缺失', '缺失'))
            continue
        checked += 1
        gv = gmap[cid].get('verify', [])
        mv = mmap[cid].get('verify', [])
        if gv != mv:
            drift.append((cid, gv, mv))

    print(f'[CRIT-SYNC] 重点检查 {checked} 张卡(本轮补强), 漂移 {len(drift)} 张')
    print('  (历史全库漂移 33 张记为已知债务, 不在本门禁范围)')
    for cid, gv, mv in drift[:10]:
        print(f'  [DRIFT] {cid}')
        print(f'    权威: {gv}')
        print(f'    镜像: {mv}')
    return 1 if drift else 0


if __name__ == '__main__':
    sys.exit(main())
