# -*- coding: utf-8 -*-
"""通用「只输出好」重放器。

用法:
  python bench/replay_good.py <seq> [session_jsonl] [runs] [template_path]

从 dsh session.v4.jsonl 还原出某一步的真实 OpenAI payload（含压缩摘要、tools、
system、历史 thinking/tool_calls/tool_results），请求本机 llama-server 并打印输出。
可用第 4 个参数传一个 jinja 模板路径注入 chat_template，做不改服务端的 A/B。
"""
import json, urllib.request, time, sys, os

SESS = sys.argv[2] if len(sys.argv) > 2 else 'bench/_cur8.jsonl'
STOP = int(sys.argv[1]) if len(sys.argv) > 1 else 2312
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
TPL = sys.argv[4] if len(sys.argv) > 4 else None

def text_of(blocks):
    return "".join(c.get("text", "") for c in (blocks or []) if isinstance(c, dict) and c.get("type") == "text")

rows = [json.loads(l) for l in open(SESS, encoding='utf-8') if l.strip()]

sys_msg = [o for o in rows if o.get("type") == "system/message" and o.get("seq", 0) < STOP][-1]
sys_txt = text_of(sys_msg["data"]["message"]["content"])

hdr = [o for o in rows if o.get("type") == "request/header" and o.get("seq", 0) < STOP][-1]["data"]["header"]
tools = [{"type": "function", "function": {"name": t["name"], "description": t.get("description", ""),
        "parameters": t.get("parameters") or {"type": "object", "properties": {}}}}
       for t in (hdr.get("tools") or [])]

ce = [o for o in rows if o.get("type") == "compaction/end" and o.get("seq", 0) < STOP]
boundary = ce[-1]["seq"] if ce else 0
summary = ""
if ce:
    cand = [o for o in rows if o.get("type") == "compaction/summary" and o.get("seq", 0) < boundary]
    if cand:
        summary = text_of(cand[-1]["data"]["summary"])

msgs = [{"role": "system", "content": sys_txt}]
if summary:
    msgs.append({"role": "user", "content": "【此前对话的压缩摘要】\n" + summary})

for o in rows:
    if o.get("seq", 0) <= boundary or o.get("seq", 0) >= STOP:
        continue
    t = o.get("type")
    if t == "user/message":
        txt = text_of(o["data"].get("content"))
        if txt.strip():
            msgs.append({"role": "user", "content": txt})
    elif t == "assistant/message":
        cs = o["data"].get("message", {}).get("content", []) or []
        d = {"role": "assistant", "content": text_of(cs)}
        rsn = "".join(c.get("text", "") for c in cs if isinstance(c, dict) and c.get("type") == "reasoning")
        if rsn and os.environ.get("WITH_REASON", "1") == "1":
            d["reasoning_content"] = rsn
        tcs = [{"id": c.get("id"), "type": "function",
                "function": {"name": c.get("name"), "arguments": c.get("arguments") or "{}"}}
               for c in cs if isinstance(c, dict) and c.get("type") == "tool-call"]
        if tcs:
            d["tool_calls"] = tcs
        msgs.append(d)
    elif t == "tool/result":
        m = o["data"].get("message", {})
        msgs.append({"role": "tool", "tool_call_id": m.get("toolCallId"), "content": text_of(m.get("content"))})

while msgs and msgs[-1]["role"] == "assistant":
    msgs.pop()

# 历史「短正文无工具调用」统计（上下文污染计数）
pollution = [(i, m.get("content", "")[:12]) for i, m in enumerate(msgs)
             if m["role"] == "assistant" and len((m.get("content") or "").strip()) <= 3
             and not m.get("tool_calls")]

print("STOP=%d  boundary=%d  system=%d字  tools=%d  消息=%d  尾部role=%s" %
      (STOP, boundary, len(sys_txt), len(tools), len(msgs), msgs[-1]["role"]))
print("历史上残留的退化 assistant 消息:", pollution[-12:], " 共", len(pollution))
print("尾部内容:", repr(str(msgs[-1].get("content"))[:220]))
print("尾部 3 条:", [(m["role"], str(m.get("content"))[:70]) for m in msgs[-3:]])

body = {"model": "Qwen3.6-35B-A3B-UD-Q4_K_XL", "messages": msgs, "tools": tools or None,
        "tool_choice": "auto", "max_tokens": 2048, "temperature": 0.6, "stream": False,
        "cache_prompt": False}
if TPL:
    body["chat_template"] = open(TPL, encoding='utf-8').read()
    print("注入模板:", TPL)

for k in range(RUNS):
    req = urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions",
        data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=2400).read())
    except Exception as e:
        print("run%d ERROR %s" % (k, e))
        continue
    ch = r["choices"][0]; m = ch["message"]
    rc = m.get("reasoning_content") or ""
    ct = m.get("content") or ""
    tc = m.get("tool_calls") or []
    print("\n--- run%d  %.1fs finish=%s out_tok=%s prompt_tok=%s" %
          (k, time.time() - t0, ch.get("finish_reason"), r["usage"]["completion_tokens"], r["usage"]["prompt_tokens"]))
    print("  think(%d):" % len(rc), repr(rc[:260]))
    print("  body(%d):" % len(ct), repr(ct[:260]))
    print("  tools:", [t["function"]["name"] for t in tc])
    print("  VERDICT:", "GOOD-ONLY(坏)" if (len(ct.strip()) <= 3 and not tc) else "正常")
