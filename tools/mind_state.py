# -*- coding: utf-8 -*-
"""mind_state —— 心智状态快照原型（合成心智的状态层）

依据（合成心智框架）：
  器官齐全但缺"过程"——本模块把散落状态聚合成一个统一对象，同时是：
    ① 给模型的注入文本（元认知：让模型看到"我现在是谁、在做什么、做到哪"）
    ② 给 G1/G2 的结构化输入（可塑性：技能草稿/反向修订需要结构化数据）
    ③ 长期聚合的自我画像（自我模型：我常犯什么错）

治的三个病（2026-11-18 现场诊断）：
  1. 任务状态漂移：P0 存档 16 次注入同一份旧任务（"温度监测"），
     但当前任务已演化成"演示页面" → current_task 从最近用户消息重算，覆盖初始任务
  2. 分布式重复：D1 只查"连续 3 次同参"，现场是跨 140 步的
     读文件→列目录→写todo→再读文件 → loop_signature 用长窗口聚合检测
  3. 信号空窗：注入集中在 seq 464-637，退化发生在 780+ → signal_gap 统计距上次注入的事件数

用法（只读，不碰 dsh 进程/会话）：
  python mind_state.py                      # 自动找最新会话，输出注入文本 + JSON
  python mind_state.py --json               # 只输出结构化 JSON
  python mind_state.py --session <目录>     # 指定会话
  python mind_state.py --inject             # 只输出可注入文本（供 harness 调用）
"""
import json
import os
import re
import sys
import glob
from collections import Counter, defaultdict

SESS_ROOT = r'D:\Brain\dsh-data\sessions\--C-Users-Ad-Documents-deepseek-harness-default-workspace--'
BENCH = r'D:\Brain\workspace\bench'
OUT = os.path.join(BENCH, '_mind_state.json')

INJECT_MARKERS = ['[harness 任务存档]', '[harness 控制回合]', '[harness 独立审计]',
                  '[harness 系统修正]', '【相关教训', 'Updated instructions from']


def latest_session(src=None):
    if src:
        return src
    files = glob.glob(os.path.join(SESS_ROOT, '*', 'session.v4.jsonl.zstd'))
    return max(files, key=os.path.getmtime) if files else None


def load_session(src):
    import zstandard as zstd
    if src.endswith(('.zstd', '.zst')):
        raw = zstd.ZstdDecompressor().stream_reader(open(src, 'rb')).read().decode('utf-8')
        return [json.loads(l) for l in raw.split('\n') if l.strip()]
    return [json.loads(l) for l in open(src, encoding='utf-8') if l.strip()]


def text_of(ev):
    d = ev.get('data', {})
    c = d.get('content') if isinstance(d, dict) else None
    if isinstance(c, list):
        return ''.join(b.get('text', '') for b in c if isinstance(b, dict) and b.get('type') == 'text')
    if isinstance(c, str):
        return c
    return ''


def user_messages(events):
    """按时间顺序取真实用户消息（source.kind == user）"""
    out = []
    for i, ev in enumerate(events):
        d = ev.get('data', {})
        if not isinstance(d, dict):
            continue
        src = d.get('source') or {}
        if isinstance(src, dict) and src.get('kind') == 'user':
            t = text_of(ev).strip()
            if t and not t.startswith('[harness '):
                out.append({'seq': i, 'text': t[:600]})
    return out


def current_task(events):
    """当前任务 = 最近一条真实用户指令 + 存档里的初始任务（标注演化）"""
    msgs = user_messages(events)
    initial = ''
    for ev in events:
        t = text_of(ev)
        if '任务存档' in t and '【初始任务】' in t:
            m = re.search(r'【初始任务】(.+?)(?:\n|【已验证决策】|$)', t)
            if m:
                initial = m.group(1).strip()
            break
    latest = msgs[-1]['text'] if msgs else ''
    # 演化判据：初始任务的"独特关键词"是否出现在最新指令里（去掉通用词后比对）
    def keywords(t):
        stop = {'帮我','请你','一个','这个','一下','什么','怎么','可以','是否','以及','的','了','和','与','给'}
        return set(re.findall(r'[\u4e00-\u9fa5]{2,}', t)) - stop
    ik, lk = keywords(initial), keywords(latest)
    overlap = len(ik & lk) / max(len(ik), 1)
    evolved = bool(initial and latest and overlap < 0.25)
    return {'initial': initial, 'latest_user_instruction': latest,
            'evolved': evolved,
            'warning': '任务已演化：存档锚定旧任务，以最新用户指令为准' if evolved else ''}


def signal_gap(events):
    """距最后一次 harness 注入的事件数（治信号空窗）"""
    last = -1
    total_injections = 0
    for i, ev in enumerate(events):
        if any(m in json.dumps(ev, ensure_ascii=False) for m in INJECT_MARKERS):
            last = i
            total_injections += 1
    return {'events_since_last_signal': len(events) - 1 - last if last >= 0 else len(events),
            'total_signals': total_injections,
            'warning': '信号空窗：超过 40 个事件无 harness 注入' if len(events) - 1 - last > 40 else ''}


def loop_signature(rows, window=60, top=5):
    """长窗口分布式重复检测（治 D1 只查连续的盲区）——数据来自 _trace.jsonl"""
    # rows 是 _trace.jsonl 的原始行（工具调用事件）
    tail = rows[-window:]
    calls = Counter()
    for r in tail:
        if r.get('kind') != 'tool_call':
            continue
        name = r.get('name') or '?'
        # 从 args/arguments/path 里提取目标文件
        arg = str(r.get('args') or r.get('arguments') or r.get('path') or '')
        m = re.search(r'([\w\\/.-]+\.(?:html|py|md|json|js|yml))', arg)
        target = m.group(1) if m else ''
        calls[(name, target)] += 1
    hot = [(f'{n} {t or "(无目标)"}', c) for (n, t), c in calls.most_common(top) if c >= 3]
    return {'window': window, 'repeated': [{'call': k, 'count': c} for k, c in hot],
            'warning': '分布式重复：长窗口内同一调用反复出现（换策略，不要第 N 次）' if hot else ''}


def tool_error_profile(events, window=160):
    """最近窗口的工具错误类型（自我模型：我常犯什么错）"""
    errs = Counter()
    for ev in events[-window:]:
        t = text_of(ev)
        if not t:
            continue
        for pat, label in [
            (r'does not declare a supported image format', 'read_image 误用（非图片）'),
            (r'Error: cannot (?:read|modify|find)', '路径/权限错误'),
            (r'unknown tool', '工具 id 错误'),
            (r'\[已排除\]', '重复失败标注'),
        ]:
            if re.search(pat, t, re.I):
                errs[label] += 1
    return dict(errs)


def load_trace():
    rows = []
    p = os.path.join(BENCH, '_trace.jsonl')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def failure_profile(rows):
    """失败画像：从 trace 提取非 OK 工具结果与审计事件"""
    fails = [r for r in rows if r.get('kind') == 'tool_result' and r.get('status') not in ('OK', None)]
    by_tool = Counter(r.get('name') for r in fails)
    return {'total_failures': len(fails), 'by_tool': dict(by_tool),
            'llm_audits': sum(1 for r in rows if r.get('kind') == 'llm'),
            'control_turns': sum(1 for r in rows if r.get('kind') == 'control_turn')}


def audit_ledger():
    p = os.path.join(BENCH, '_audit_feedback.jsonl')
    rows = []
    if os.path.exists(p):
        for line in open(p, encoding='utf-8'):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    eff = sum(1 for r in rows if r.get('effective'))
    return {'total': len(rows), 'effective': eff,
            'warning': '数据不足：需 ≥5 条才能校准阈值' if len(rows) < 5 else ''}


def skill_ledger():
    """技能账本：从 skills frontmatter 读登记信息（有效率待 G2 数据）"""
    skills = []
    d = os.path.join(BENCH, 'skills')
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if not f.endswith('.md'):
                continue
            t = open(os.path.join(d, f), encoding='utf-8').read()
            m = re.search(r'^summary:\s*(.+)$', t, re.M)
            skills.append({'name': f[:-3], 'summary': (m.group(1)[:60] if m else '')})
    return {'registered': len(skills), 'skills': skills,
            'effectiveness': '待 G1/G2 数据（当前只有登记，无命中/有效率）'}


def build(src=None):
    src = latest_session(src)
    if not src:
        return {'error': '无会话文件'}
    events = load_session(src)
    trows = load_trace()
    return {
        'source_session': os.path.basename(os.path.dirname(src)),
        'events': len(events),
        'current_task': current_task(events),
        'signal': signal_gap(events),
        'loops': loop_signature(trows),
        'error_profile': tool_error_profile(events),
        'failure': failure_profile(trows),
        'audit': audit_ledger(),
        'skills': skill_ledger(),
    }


def render(m):
    """渲染为可注入文本（给模型看的元认知快照）"""
    lines = ['[harness 心智状态快照] 以下为你当前的完整状态，先核对再行动：']
    ct = m['current_task']
    lines.append(f"① 当前任务：{ct['latest_user_instruction'][:140] or '(未取到)'}")
    if ct['evolved']:
        lines.append(f"   ⚠ {ct['warning']}（存档旧任务：{ct['initial'][:80]}）")
    sg = m['signal']
    lines.append(f"② 距离上次 harness 信号：{sg['events_since_last_signal']} 个事件"
                 + (f" —— ⚠ {sg['warning']}" if sg['warning'] else ''))
    lp = m['loops']['repeated']
    if lp:
        lines.append('③ ⚠ 检测到分布式重复（长窗口内反复执行，换策略而不是第 N 次）：')
        for x in lp[:3]:
            lines.append(f"   - {x['call']} × {x['count']}")
    else:
        lines.append('③ 无重复调用模式')
    ep = m['error_profile']
    if ep:
        lines.append('④ 你最近常犯的错（自我画像）：' + '、'.join(f'{k}×{v}' for k, v in ep.items()))
    fl = m['failure']
    lines.append(f"⑤ 累计工具失败 {fl['total_failures']} 次；LLM 审计 {fl['llm_audits']} 次；"
                 f"控制回合 {fl['control_turns']} 次")
    lines.append('⑥ 收尾前自检：我是否已经完成并交付？若已完成，停止验证、直接结束本轮。')
    return '\n'.join(lines)


def main():
    args = sys.argv[1:]
    src = args[args.index('--session') + 1] if '--session' in args else None
    m = build(src)
    if '--json' not in args:
        print(render(m))
        print('\n' + '=' * 60)
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    if '--inject' not in args:
        print(json.dumps(m, ensure_ascii=False, indent=2)[:2500])
        print(f'\n结构化快照 → {OUT}')


if __name__ == '__main__':
    main()
