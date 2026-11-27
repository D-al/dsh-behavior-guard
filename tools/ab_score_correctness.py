# -*- coding: utf-8 -*-
"""事后判分：从会话记录抽最终答案，判任务是否真正完成（质量指标）

主指标 tool_calls 只测"效率"，可能判反（2步给错答案 vs 8步正确完成）。
本脚本补一个质量指标：最终文本是否给出正确答案 C-001。
"""
import json, glob, subprocess, os, re, sys

RESULT = r'D:/Brain/workspace/bench/_ab_reflection_result.json'
DUMP = r'D:/tmp/dsh-investigate/dump_session.mjs'
SESSION_ROOT = r'D:/Brain/dsh-data/sessions'

def final_text(sid):
    m = re.search(r'([0-9a-f]{8}-[0-9a-f-]{27,})', sid)
    if not m: return ''
    full = m.group(1)
    pat = os.path.join(SESSION_ROOT, '**', f'session-{full}', 'session.v4.jsonl.zstd')
    hits = glob.glob(pat, recursive=True)
    if not hits: return ''
    try:
        out = subprocess.run(['node', DUMP, hits[0]], capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return ''
    last = ''
    for l in out.splitlines():
        try: d = json.loads(l)
        except Exception: continue
        if d.get('type') != 'assistant/message': continue
        msg = d.get('data',{}).get('message',{})
        text = ''.join(str(c.get('text','')) for c in (msg.get('content') or [])
                       if isinstance(c,dict) and c.get('type')=='text')
        if text.strip(): last = text
    return last

def main():
    rows = json.load(open(RESULT, encoding='utf-8'))
    batch = [r for r in rows if r.get('batch')=='v2']
    print(f'判分 {len(batch)} 个会话（v2 同批次）')
    from collections import defaultdict
    by = defaultdict(list)
    for r in batch:
        ft = final_text(r['sid'])
        correct = 'C-001' in ft
        r['answer_correct'] = correct
        r['final_text_len'] = len(ft)
        by[r['group']].append(r)
        print(f"  {r['group']:10s} {r['sid'][:14]} correct={correct} len={len(ft)}")
    json.dump(rows, open(RESULT,'w',encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n=== 正确率 ===')
    for g, rs in sorted(by.items()):
        c = sum(1 for r in rs if r['answer_correct'])
        print(f'  {g:10s} {c}/{len(rs)} ({100*c/len(rs):.0f}%)')

if __name__ == '__main__':
    main()
