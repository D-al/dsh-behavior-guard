# -*- coding: utf-8 -*-
"""audit_session —— 独立会话审计员（2604.11465 纠正器思路的会话级实现）

依据：
  - 三角色编排（arXiv 2604.11465）：纠正器看不到对话历史以打破重复失败循环。
    本工具把"独立无历史"用在会话级：审计员没有参与会话，只看轨迹摘要。
  - Q4@0.7 实测缺陷：假完成（贴产物不写盘）、重述回路、重复失败——这些在
    主 agent 自己的视角里不可见（它不认为自己失败了）。独立审计是环境级判定。

用法：
  python audit_session.py <会话目录|session.v4.jsonl.zstd|解压后的jsonl> [--json]
  例：python audit_session.py "C:/Users/Ad/.dsh/sessions/.../session-xxx" 

输出：浪费步骤 / 跑偏点 / 假完成声明 / 根因假设（JSON + 人读版）
退出码：0=审计完成（无论结论），2=基础设施错误
"""
import sys, json, os, glob

MAX_TRAJECTORY_CHARS = 14000

def load_events(src):
    """支持：目录(自动找 session.v4.jsonl.zstd) / zstd 文件 / 已解压 jsonl"""
    if os.path.isdir(src):
        cands = glob.glob(os.path.join(src, "*.jsonl.zstd"))
        if not cands:
            # 目录下还有一层（session-xxx/session.v4.jsonl.zstd）
            cands = glob.glob(os.path.join(src, "*", "*.jsonl.zstd"))
        if not cands:
            raise FileNotFoundError("目录下没有 *.jsonl.zstd: %s" % src)
        src = cands[0]
    if src.endswith(".zst") or src.endswith(".zstd"):
        import zstandard as zstd
        raw = zstd.ZstdDecompressor().stream_reader(open(src, 'rb')).read().decode('utf-8')
        return [json.loads(l) for l in raw.split('\n') if l.strip()]
    return [json.loads(l) for l in open(src, encoding='utf-8') if l.strip()]

def blocks_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(b.get('text', '') for b in content if isinstance(b, dict))
    return ''

def build_trajectory(events):
    last_todo = {}
    """抽出审计所需的轨迹摘要（紧凑、面向判断）"""
    initial = ""
    steps = []
    calls = {}  # callId -> {name, args, step}
    for d in events:
        t = d.get('type')
        if t == 'user/message':
            txt = blocks_text(d['data'].get('content', ''))
            if d['data'].get('source', {}).get('kind') == 'user' and txt and not txt.startswith('<system-reminder>'):
                if not initial:
                    initial = txt[:600]
        elif t == 'tool/call':
            dd = d['data']
            a = dd.get('arguments', '')
            try:
                aj = json.loads(a)
                a = json.dumps(aj, ensure_ascii=False)
            except Exception:
                pass
            calls[dd.get('callId')] = {'name': dd.get('name'), 'args': a[:150], 'step': dd.get('step')}
        elif t == 'tool/result':
            dd = d['data']
            cid = (dd.get('message', {}).get('source') or {}).get('callId') or dd.get('toolCallId')
            c = calls.get(cid)
            if not c:
                continue
            content = dd.get('message', {}).get('content', '')
            txt = blocks_text(content)
            err = dd.get('error') is not None or txt.startswith('Error:') or '[stderr]' in txt[:30]
            steps.append({
                'step': c['step'], 'tool': c['name'], 'args': c['args'],
                'ok': not err, 'result_len': len(txt), 'result_head': txt[:120].replace('\n', ' ')
            })
        elif t == 'assistant/message':
            dd = d['data']
            cs = dd['message']['content']
            body = ''.join(b.get('text', '') for b in cs if b.get('type') == 'text').strip()
            tools = [b.get('function', {}).get('name') or b.get('name') for b in cs if b.get('type') == 'tool-call']
            if body or not tools:
                steps.append({'step': dd.get('step'), 'assistant_body': body[:150].replace('\n', ' ')})
        # v3.3 子智能体治理：todo/write + spawn + 回注 全部进轨迹（审计员可见完整时间线）
        elif t == 'todo/write':
            dd = d['data']
            todos = dd.get('todos') or []
            done = sum(1 for x in todos if x.get('status') == 'completed')
            sig = json.dumps(todos, sort_keys=True)
            mark = '' if sig != last_todo.get('sig') else ' [冗余更新：与上次完全一致]'
            last_todo['sig'] = sig
            first = todos[0].get('content', '')[:40] if todos else ''
            steps.append({'step': dd.get('step'), 'special': '[todo] %d项(完成%d) 首项:%s%s' % (len(todos), done, first, mark)})
    # spawn/回注单独扫（它们不在 step 流内）
    spawn_steps = []
    inbox_notes = []
    for d in events:
        if d.get('type') == 'tool/call' and d['data'].get('name') == 'spawn_teammate':
            a = d['data'].get('arguments', '')[:120]
            spawn_steps.append("step%s spawn_teammate(%s)" % (d['data'].get('step'), a.replace('\n', ' ')))
        if d.get('type') == 'subagent/descriptor':
            dd = d.get('data') or {}
            spawn_steps.append("subagent/descriptor: %s" % json.dumps(dd, ensure_ascii=False)[:120])
        if d.get('type') == 'agent/inbox/spliced':
            ins = (d.get('data') or {}).get('inserted') or []
            for m in ins:
                txt = ''.join(b.get('text', '') for b in (m.get('content') or []) if isinstance(b, dict))
                if txt:
                    inbox_notes.append("回注: " + txt[:120].replace('\n', ' '))
    for x in spawn_steps:
        steps.append({'step': '?', 'special': x})
    for x in inbox_notes:
        steps.append({'step': '?', 'special': x})
    return initial, steps

def compress_trajectory(initial, steps):
    lines = ["【任务】" + (initial or "(未捕获)"), "【轨迹】"]
    for s in steps:
        if 'special' in s:
            lines.append("%s" % s['special'])
        elif 'tool' in s:
            lines.append("step%s %s(%s) -> %s len=%d | %s" % (
                s['step'], s['tool'], s['args'][:80], "OK" if s['ok'] else "FAIL",
                s['result_len'], s['result_head'][:90]))
        else:
            lines.append("step%s [assistant] %s" % (s['step'], s['assistant_body']))
    traj = '\n'.join(lines)
    if len(traj) > MAX_TRAJECTORY_CHARS:
        traj = traj[:MAX_TRAJECTORY_CHARS] + "\n…[轨迹截断]"
    return traj

PROMPT = """你是独立会话审计员，没有参与产生这段 agent 会话轨迹，只依据下面的记录判断。

【任务】%s

【轨迹（每步工具调用+结果状态+助手正文要点）】
%s

请审计并只输出一个 JSON 对象（不要 markdown 代码块，不要其他文字）：
{
  "wasted": [{"step": "步号", "why": "为什么浪费（一句话）"}],
  "drift": {"step": "开始跑偏的步号或null", "why": "一句话"},
  "false_claims": [{"step": "步号", "what": "声称了什么，但轨迹里缺乏证据"}],
  "retries": [{"target": "重复尝试的目标", "count": 次数}],
  "root_cause": "这次会话的核心失败模式，一句话"
}
判定纪律（防误伤）：
- todo 清单的状态更新（标记完成/进行中）是任务管理协议的正常行为，**不算浪费步骤**。
- 只把"对推进任务无贡献且换不来新信息"的调用判为浪费（如：原样重试已知会失败的调用、
  读取与任务无关的内容、在无新证据时反复探测同一目标）。
- 只依据轨迹里的事实；没有证据的项输出空数组/null；不要编造。"""

def audit(traj_prompt):
    req = json.dumps({
        "model": "Qwen3.6-35B-A3B-UD-Q4_K_XL",
        "messages": [{"role": "user", "content": traj_prompt}],
        "max_tokens": 3000, "temperature": 0.0, "top_k": 1,
    }).encode('utf-8')
    r = urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions",
                               data=req, headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(r, timeout=900).read())
    out = (resp["choices"][0]["message"].get("content") or "").strip()
    # 容错：剥掉可能的 markdown 包裹
    if out.startswith("```"):
        out = out.strip('`')
        if out.startswith("json"):
            out = out[4:]
    try:
        return json.loads(out), out
    except Exception:
        return None, out

import urllib.request

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    as_json = '--json' in sys.argv
    if not src:
        print(__doc__)
        sys.exit(2)
    events = load_events(src)
    initial, steps = build_trajectory(events)
    traj = compress_trajectory(initial, steps)
    print("轨迹摘要 %d 字符 / %d 条目。审计中（temperature=0，无历史）..." % (len(traj), len(steps)))
    result, raw = audit(PROMPT % (initial[:300], traj))
    if result is None:
        print("[WARN] 模型输出不是合法 JSON，原始输出：")
        print(raw[:800])
        sys.exit(2)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        w = result.get('wasted') or []
        d = result.get('drift') or {}
        fc = result.get('false_claims') or []
        rt = result.get('retries') or []
        print("=== 浪费步骤 (%d) ===" % len(w))
        for x in w: print("  step%s: %s" % (x.get('step'), x.get('why')))
        print("=== 跑偏点 ===")
        if d.get('step'): print("  step%s: %s" % (d.get('step'), d.get('why')))
        else: print("  (无)")
        print("=== 假完成声明 (%d) ===" % len(fc))
        for x in fc: print("  step%s: %s" % (x.get('step'), x.get('what')))
        print("=== 重复尝试 (%d) ===" % len(rt))
        for x in rt: print("  %s x%s" % (x.get('target'), x.get('count')))
        print("=== 根因 ===")
        print("  " + str(result.get('root_cause')))

if __name__ == "__main__":
    main()
