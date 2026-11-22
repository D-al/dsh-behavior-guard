#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""S22 门面审计：调用 tool_audit 做频次统计 + 低频/零调用识别 + 描述碰撞自检。

设计原则：
- tool_audit.py = 底层库（load_rows / audit / report）
- tool_surface_audit.py = S22 的门面（import 复用 + 扩展）
- 不复制两份实现

用法:
  python tools/tool_surface_audit.py                          # 默认报告模式
  python tools/tool_surface_audit.py --json                   # JSON 输出（供闸门使用）
  python tools/tool_surface_audit.py --collisions             # 仅跑描述碰撞自检
  python tools/tool_surface_audit.py <file.jsonl>             # 单个 dump
"""
import collections
import json
import os
import sys

# ── 底层复用 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tool_audit import audit as _audit_raw, DEFAULT_GLOB, DUMP_DIR

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(ROOT)


def _freq_threshold(total_calls, top_n_ratio=0.9):
    """计算低频阈值：前 N 种工具累计占比 ≥ top_n_ratio 时的第 N+1 种的调用数。"""
    return None  # placeholder; actual logic in surface_report()


def check_description_collisions(tool_descriptions, threshold=0.6):
    """轻量描述碰撞自检：用中文 bigram + 英文词的 Jaccard 相似度。

    2026-11-21 修正：原实现数 bigram 交集(阈值5)，会抓出「关任/具处」这种
    跨词边界的无意义碎片，且 --collisions 用 mock_desc(每工具同一句话)——
    整个检查是自造数据的假绿。现改为：真实描述 + Jaccard 相似度阈值。

    参数: tool_descriptions = {tool_name: real_description_text}
    返回: [(tool_a, tool_b, score)] — Jaccard >= threshold 的配对
    """
    import re
    if not isinstance(tool_descriptions, dict) or len(tool_descriptions) < 2:
        return []

    def tokens(text):
        out = set()
        text = str(text).lower()
        for i in range(len(text) - 1):
            a, b = text[i], text[i + 1]
            if '\u4e00' <= a <= '\u9fff' and '\u4e00' <= b <= '\u9fff':
                out.add(a + b)
        out.update(w.lower() for w in re.findall(r'[a-z_]{3,}', text))
        return out

    tmap = {name: tokens(desc) for name, desc in tool_descriptions.items()}
    collisions = []
    names = sorted(tmap)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = tmap[names[i]], tmap[names[j]]
            if not a or not b:
                continue
            score = len(a & b) / len(a | b)
            if score >= threshold:
                collisions.append((names[i], names[j], round(score, 3)))
    return collisions


def load_trigger_descriptions():
    """从 AGENTS.md「工具选择触发条件」表解析真实描述（S22 产物）。"""
    import re
    path = os.path.join(REPO_ROOT, 'config', 'AGENTS.md')
    if not os.path.exists(path):
        return {}
    text = open(path, encoding='utf-8').read()
    m = re.search(r'## 工具选择触发条件.*?(?=\n### |\n## )', text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(0).splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 3 or cells[1].startswith('---') or '工具' in cells[1]:
            continue
        names = re.findall(r'\*\*([^*]+)\*\*', cells[1]) or [cells[1]]
        for name in names:
            if name and name not in ('#',):
                out[name] = cells[2]
    return out


def surface_report(paths, as_json=False):
    """S22 门面审计主逻辑：频次统计 + 零调用/低频候选 + 描述碰撞。"""
    total, per_sess, schema, dup_count = _audit_raw(paths)  # tool_audit.audit 已返回4值(含去重量)
    n = sum(total.values())
    if not n:
        print("没有 tool/call 事件，无法审计")
        return 1

    # ── 识别零调用 / 低频工具 ──
    # 从 index.mjs 加载已知工具列表（用于对比）
    known_tools = _load_known_tools()

    # 频次计数
    freq_counter = collections.Counter()
    for sess_name, sess_counts in per_sess.items():
        freq_counter.update(sess_counts)

    # 跨会话出现次数
    tool_sessions = {}
    for sess_name, counts in per_sess.items():
        for tname, cnt in counts.items():
            tool_sessions.setdefault(tname, []).append(sess_name)

    # 低频定义：总调用 < 50 次 或 只在 ≤1 个会话中出现
    LOW_FREQ_COUNT = 50
    LOW_FREQ_SESSIONS = 1

    low_freq_candidates = []
    zero_call_tools = []
    active_tools = list(total.keys())

    for tname in sorted(known_tools):
        count = total.get(tname, 0)
        sess_cnt = len(tool_sessions.get(tname, []))
        if count == 0:
            zero_call_tools.append(tname)
        elif count < LOW_FREQ_COUNT or sess_cnt <= LOW_FREQ_SESSIONS:
            low_freq_candidates.append((tname, count, sess_cnt))

    # 前 N 占比
    top_n_ratios = [(3, "前3"), (5, "前5"), (8, "前8")]
    sorted_tools = total.most_common()

    def _top_ratio(k):
        s = sum(v for _, v in sorted_tools[:k])
        return f"{s * 100 // n}%"

    # ── JSON 输出 ──
    if as_json:
        result = {
            'sessions': len(paths),
            'total_calls': n,
            'distinct_tools': len(total),
            'by_tool': dict(sorted_tools),
            'zero_call_tools': zero_call_tools,
            'low_freq_candidates': [{'tool': t, 'count': c, 'sessions': s} for t, c, s in low_freq_candidates],
            'top_n_ratios': {label: _top_ratio(k) for k, label in top_n_ratios},
            'schema_defined': len(schema) if schema else None,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ── 人类可读报告 ──
    print(f"=== S22 工具面审计报告 ===")
    print(f"会话 dump: {len(paths)} 个 | 总调用 {n} | 不同工具 {len(total)}")
    print(f"{'工具':<24} {'调用':>6} {'占比':>6} {'跨会话数':>7}")
    print("-" * 50)
    for name, cnt in sorted_tools:
        pct = cnt * 100 // n
        sess = len(tool_sessions.get(name, []))
        marker = ""
        if cnt == 0:
            marker = " [零调用]"
        elif cnt < LOW_FREQ_COUNT:
            marker = " ⚠低频"
        print(f"{name:<24} {cnt:>6} {pct:>4}%  {sess:>7}{marker}")

    print("\n--- 前 N 占比 ---")
    for k, label in top_n_ratios:
        print(f"{label} 种工具占调用 {_top_ratio(k)}")

    print(f"\n--- 零调用工具 ({len(zero_call_tools)}) ---")
    if zero_call_tools:
        for t in zero_call_tools:
            print(f"  ✗ {t}")
    else:
        print("  (无)")

    print(f"\n--- 低频工具候选 ({len(low_freq_candidates)}) ---")
    if low_freq_candidates:
        for t, c, s in sorted(low_freq_candidates, key=lambda x: -x[1]):
            reason = []
            if c < LOW_FREQ_COUNT:
                reason.append(f"调用{c}<阈值{LOW_FREQ_COUNT}")
            if s <= LOW_FREQ_SESSIONS:
                reason.append(f"仅{1 if s==1 else s}个会话出现")
            print(f"  ? {t}: {c}次/{s}会话 — {', '.join(reason)}")
    else:
        print("  (无)")

    # ── 描述碰撞自检 ──
    collisions = check_description_collisions(known_tools)
    print(f"\n--- 描述碰撞自检 ({len(collisions)} 组高相似度) ---")
    if collisions:
        for a, b, shared in collisions[:10]:
            shared_str = ", ".join(shared[:5])
            print(f"  ! {a} ↔ {b}: 重叠关键词 [{shared_str}]")
    else:
        print("  (未发现明显碰撞)")

    return 0


def _load_known_tools():
    """从 index.mjs 提取已知工具名列表。"""
    import re
    tools_path = os.path.join(REPO_ROOT, 'index.mjs')
    try:
        with open(tools_path, encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        # fallback：返回常见 DSH 工具集
        return {
            'read', 'write', 'edit', 'pwsh', 'glob', 'grep',
            'todo_write', 'job_output', 'job_kill', 'web_fetch',
            'load_workspace_dependencies', 'ask_user_question'
        }

    known = set()
    # 匹配 "tool/call", name: "xxx" 或 tool/call patterns
    for m in re.finditer(r"name:\s*['\"]([^'\"]+)['\"']", content):
        known.add(m.group(1))
    # 额外匹配常见的 DSH 工具名
    for candidate in [
        'read', 'write', 'edit', 'pwsh', 'glob', 'grep',
        'todo_write', 'job_output', 'job_kill', 'web_fetch',
        'load_workspace_dependencies', 'ask_user_question',
        'present', 'skill', 'web_search', 'check_artifact_deep',
        'verify_on_edit', 'apply_patch', 'multi_edit',
    ]:
        known.add(candidate)

    return known


def main():
    args = sys.argv[1:]
    as_json = '--json' in args
    only_collisions = '--collisions' in args
    paths_args = [a for a in args if not a.startswith('--')]

    from tool_audit import DEFAULT_GLOB
    paths = paths_args or sorted(__import__('glob').glob(DEFAULT_GLOB))
    if not paths:
        print('未找到会话 dump: ' + DEFAULT_GLOB)
        return 1

    if only_collisions:
        desc = load_trigger_descriptions()
        if not desc:
            print('未找到 AGENTS.md 工具选择触发条件表，无法碰撞自检')
            return 1
        collisions = check_description_collisions(desc)
        print(json.dumps({
            'source': 'config/AGENTS.md 工具选择触发条件表（真实描述）',
            'tools_compared': len(desc),
            'total_pairs_checked': len(desc) * (len(desc) - 1) // 2,
            'collisions': [{'tool_a': a, 'tool_b': b, 'jaccard': sc}
                           for a, b, sc in collisions],
        }, ensure_ascii=False, indent=2))
        return 0

    return surface_report(paths, as_json=as_json)


if __name__ == '__main__':
    sys.exit(main())
