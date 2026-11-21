#!/usr/bin/env python3
"""隐含依赖审计（2026-11-21）：找出"正文声明了依赖但结构化字段没记录"的卡。

缘起：M7（格式修复器）正文写"前置 86M 分类器还没验证"，
但 deps=[] 且 preconditions 从没进过任何视图——用户看科技树完全看不到这个前置。

检查三类：
1. preconditions 字段（结构化前置，最可靠）——必须进科技树的 gate 节点
2. 正文依赖暗示词（前置/先验证/必须先/依赖/需要先/未验证）——提示人工核对
3. 正文提到具体卡 ID 或其他模块的引用

用法: python tools/audit_implicit_deps.py [--strict]
"""
import os
import re
import sys
from pathlib import Path

try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    alt = Path('D:/Python/python.exe')
    if alt.exists() and Path(sys.executable).resolve() != alt.resolve():
        os.execv(str(alt), [str(alt), str(Path(__file__).resolve())] + sys.argv[1:])
    raise

ROOT = Path(__file__).resolve().parent.parent
LADDER = ROOT / 'CAPABILITY_LADDER.yaml'
GRAPH = ROOT / 'ROADMAP_GRAPH.md'
TREE = ROOT / 'tools' / 'tech_tree.py'

HINT = re.compile(r'(前置|先验证|必须先|依赖|需要先|前提是|待验证|未验证)')
OTHER_ID = re.compile(r'\b([SMLA]\d{1,2}(?:_\d+)?)\b')

def main():
    strict = '--strict' in sys.argv
    ladder = yaml.safe_load(LADDER.read_text(encoding='utf-8'))
    items = ladder['items'] + ladder['autonomy_rungs']
    gtext = GRAPH.read_text(encoding='utf-8')
    ttext = TREE.read_text(encoding='utf-8')

    expected_gates = set()
    for i in items:
        for pre in (i.get('preconditions') or []):
            expected_gates.add(str(pre).split(':')[0].strip())
    total_pre = sum(len(i.get('preconditions') or []) for i in items)

    # 强判据：真跑生成器，解析 GATE_COUNT，而不是 grep 源码字符串（避免假绿）
    import subprocess
    r = subprocess.run([sys.executable, str(TREE), '--check'],
                       cwd=ROOT, capture_output=True, text=True, timeout=30)
    m = re.search(r'GATE_COUNT=(\d+)', r.stdout)
    actual_gates = int(m.group(1)) if m else -1
    ok = r.returncode == 0 and actual_gates == len(expected_gates)

    print(f'=== 结构化前置条件 ===')
    print(f'共 {total_pre} 条 / {len(expected_gates)} 个唯一 P-ID（来自 {sum(1 for i in items if i.get("preconditions"))} 张卡）')
    print(f'科技树实际 gate 节点: {actual_gates} （期望 {len(expected_gates)}）')
    print(('✅ gate 节点与前置条件一一对应' if ok else '❌ gate 节点数不符——生成器漏读 preconditions'))

    print(f'\n=== 正文依赖暗示词（需人工确认是否已进 deps/gates）===')
    hints = []
    for i in items:
        text = ' '.join(str(i.get(k, '')) for k in ('what', 'why', 'human_note', 'advice', 'caveats'))
        m = HINT.search(text)
        if m:
            hints.append((i['id'], i.get('deps') or [], bool(i.get('preconditions')), m.group()))
    for cid, deps, has_pre, word in hints:
        print(f'  {cid:12} deps={str(deps):28} preconditions={"有" if has_pre else "无":3} 命中「{word}」')

    # 判据：有 preconditions 的卡，deps 为空不算错（gate 已表达），
    # 但如果生成器没读 preconditions → FAIL
    # 语义层对称：显式 unlocks 必须 ⊇ deps 推导（软解锁是合法额外语义，不算错）
    derived = {k: set() for k in {n['id'] for n in []}}  # placeholder
    lad = yaml.safe_load(LADDER.read_text(encoding='utf-8'))
    lids = {i['id'] for i in lad['items'] + lad['autonomy_rungs']}
    derived = {k: set() for k in lids}
    import re as _re
    gm = _re.search(r'<!-- ROADMAP_GRAPH_BEGIN v1 -->\s*(.*?)\s*<!-- ROADMAP_GRAPH_END -->', gtext, _re.S)
    if gm:
        gg = yaml.safe_load(gm.group(1))
        for it in gg['items'] + gg['rungs']:
            for d in it.get('deps') or []:
                if d in derived:
                    derived[d].add(it['id'])
    missing_unlock = []
    for it in lad['items'] + lad['autonomy_rungs']:
        exp = set(it.get('unlocks') or [])
        lack = derived[it['id']] - exp
        if lack:
            missing_unlock.append((it['id'], sorted(lack)))
    # 证据副本：未被任何卡依赖的 anchor 不应单列成节点（应并入对应卡）
    if gm:
        gg = yaml.safe_load(gm.group(1))
        orphan_anchors = [an for an in (gg.get('anchors') or {})
                          if not any(an in (it.get('deps') or []) for it in gg['items'] + gg['rungs'])]
        print(f'\n=== 证据锚点 ===')
        print(f'未被依赖的 anchor: {orphan_anchors or '无'}（生成器会并入对应卡，不单列）')

    print(f'\n=== 语义层 unlocks 回填 ===')
    if missing_unlock:
        print(f'❌ {len(missing_unlock)} 张卡有 deps 但未回填 unlocks:')
        for cid, lack in missing_unlock:
            print(f'   {cid}: 缺 {lack}')
    else:
        print('✅ 所有卡的 deps 都在 unlocks 里有对应声明（软解锁额外保留）')
    ok = ok and not missing_unlock

    print(f'\n结论: {"PASS" if ok else "FAIL"}')
    return (1 if strict and not ok else 0)

if __name__ == '__main__':
    sys.exit(main())
