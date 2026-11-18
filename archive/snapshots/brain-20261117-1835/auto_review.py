# -*- coding: utf-8 -*-
"""auto_review —— 会话自动复盘（P3：行为漂移监控 + CritBank 自动沉淀）

扫描最近 N 小时的 dsh 会话 → 逐个跑 audit_session 审计员 → 汇总失效模式 →
输出 CritBank 候选清单（不自动写 AGENTS.md——失效模式进规则需人工确认，HITL）。

用法：
  python bench/auto_review.py [--hours 24] [--top 5]
  常驻：计划任务每 6 小时跑一次（或手动）。
对照（Living-Harness 2607.26598）：rollout–evaluate–update 循环的 evaluate 环节自动化。
"""
import os, sys, glob, time, subprocess, json

BENCH = os.path.dirname(os.path.abspath(__file__))
SESSIONS = r'C:\Users\Ad\.dsh\sessions'
PY = sys.executable

def find_recent_sessions(hours):
    cutoff = time.time() - hours * 3600
    out = []
    # 结构: sessions/<profile>/<session-id>/session.v4.jsonl.zstd（两层）
    for f in glob.glob(os.path.join(SESSIONS, '*', '*', 'session.v4.jsonl.zstd')):
        mtime = os.path.getmtime(f)
        if mtime >= cutoff:
            out.append((mtime, os.path.dirname(f), f))
    return sorted(out, reverse=True)

def audit_session(src):
    try:
        r = subprocess.run([PY, os.path.join(BENCH, 'audit_session.py'), src],
                           capture_output=True, text=True, timeout=900,
                           cwd=BENCH, encoding='utf-8', errors='replace')
        return r.stdout or ('[STDERR] ' + r.stderr[:400])
    except Exception as e:
        return '[审计异常] ' + str(e)

def extract_issues(text):
    """从审计员输出提取失效模式关键词行，作为 CritBank 候选"""
    issues = []
    for sec in ('浪费步骤', '假完成声明', '重复尝试', '跑偏点'):
        idx = text.find(sec)
        if idx < 0:
            continue
        seg = text[idx:text.find('===', idx + 3) if text.find('===', idx + 3) > 0 else idx + 600]
        for line in seg.split('\n'):
            line = line.strip(' -')
            if line and not line.startswith('===') and not line.startswith(sec) and len(line) > 8:
                issues.append(sec.rstrip('(0123456789) ') + ': ' + line[:110])
    rc = text.find('=== 根因')
    if rc >= 0:
        nxt = text.find('\n', rc)
        if nxt >= 0:
            end = text.find('\n', nxt + 1)
            seg = text[nxt + 1:end if end > 0 else nxt + 200]
            issues.append('根因: ' + seg.strip()[:110])
    return issues

def main():
    hours = 24
    if '--hours' in sys.argv:
        hours = float(sys.argv[sys.argv.index('--hours') + 1])
    sessions = find_recent_sessions(hours)
    print('最近 %g 小时会话 %d 个\n' % (hours, len(sessions)))
    all_issues = []
    for mtime, sdir, f in sessions[:10]:
        name = os.path.basename(sdir)[:44]
        print('══ %s (%s) ══' % (name, time.strftime('%m-%d %H:%M', time.localtime(mtime))))
        out = audit_session(f)
        print(out[-1200:])
        issues = extract_issues(out)
        for x in issues:
            all_issues.append((name[:20], x))
        print()
    print('══════ CritBank 候选汇总（%d 条，人工确认后并入 AGENTS.md）══════' % len(all_issues))
    seen = set()
    for src, x in all_issues:
        key = x[:60]
        if key in seen:
            continue
        seen.add(key)
        print('  [%s] %s' % (src, x))

if __name__ == '__main__':
    main()
