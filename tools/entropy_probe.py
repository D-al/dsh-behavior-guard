# -*- coding: utf-8 -*-
"""entropy_probe —— GUARD 式熵尖峰诊断（ACL 2026, GUARD 的检测半边）

依据（GUARD, ACL 2026）：
  - 85% 的首个推理错误发生在轨迹前 30%；错误段的 token 熵局部飙高
    （错误段平均熵 1.09 vs 正确段 0.39）——尖峰在信号上可见。
  - 模型顺着错误前提继续写"局部通顺、整体错误"的认知螺旋。
  - 本工具是 GUARD 的"检测"半边（分支重采样需要改 llama.cpp 采样层，暂缓）：
    用 top-10 logprobs 近似每 token 熵，按段聚合，标出超过历史 0.9 分位的尖峰段。

用途：诊断某类 prompt 是否会诱发认知螺旋（先高熵后漂移），验证缓解措施前后差异。
用法：
  python entropy_probe.py "<prompt>" [--max N]
输出：逐段平均熵表 + 尖峰段标记 + 全轨迹统计。
"""
import sys, json, math, urllib.request

BASE = "http://127.0.0.1:8081"
TOP_N = 10

def token_entropy(logprob_str_list):
    """llama.cpp 返回的 top_logprobs: [{token, logprob}, ...] -> 近似香农熵（top-10）"""
    ps = [math.exp(x['logprob']) for x in logprob_str_list]
    s = sum(ps)
    if s <= 0:
        return 0.0
    ps = [p / s for p in ps]  # 归一化到 top10（低估全表熵，但相对差异保留）
    return -sum(p * math.log(p + 1e-12) for p in ps)

def probe(prompt, max_tokens):
    body = json.dumps({
        "model": "Qwen3.6-35B-A3B-UD-Q4_K_XL",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens, "temperature": 0.7, "top_p": 0.95,
        "logprobs": True, "top_logprobs": TOP_N,
    }).encode('utf-8')
    req = urllib.request.Request(BASE + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req, timeout=900).read())
    choice = resp["choices"][0]
    lp = choice.get("logprobs") or {}
    content_lp = lp.get("content") or []
    reasoning_lp = lp.get("reasoning_content") or lp.get("reasoning") or []
    th = choice["message"].get("reasoning_content") or ""
    bd = (choice["message"].get("content") or "").strip()
    return content_lp, reasoning_lp, th, bd, choice.get("finish_reason")

def segment_entropies(tokens_with_text):
    """按换行/句号切段，段内 token 熵平均。tokens: [{ent, text}]"""
    segs, cur = [], {'ents': [], 'text': ''}
    for t in tokens_with_text:
        cur['ents'].append(t['ent'])
        cur['text'] += t['text']
        if t['text'].strip() in ('\n', '。', '；', '.', '；'):
            segs.append(cur)
            cur = {'ents': [], 'text': ''}
    if cur['ents']:
        segs.append(cur)
    out = []
    for s in segs:
        avg = sum(s['ents']) / max(1, len(s['ents']))
        peak = max(s['ents'])
        out.append({'text': s['text'][:50].replace('\n', '¶'), 'avg': avg, 'peak': peak, 'ntok': len(s['ents'])})
    return out

def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "解释什么是缓存命中。"
    max_tokens = 3000
    if '--max' in sys.argv:
        max_tokens = int(sys.argv[sys.argv.index('--max') + 1])

    content_lp, reasoning_lp, th, bd, fr = probe(prompt, max_tokens)
    # 优先分析思考段（GUARD 的对象是推理轨迹）；没有则分析正文
    lp = reasoning_lp if reasoning_lp else content_lp
    text = th if reasoning_lp else bd
    print("思考 %d 字 / 正文 %d 字 / finish=%s / logprob 覆盖 %d token%s" % (
        len(th), len(bd), fr, len(lp), "（思考段）" if reasoning_lp else "（正文段）"))
    if not lp:
        print("[WARN] 服务端未返回 logprobs，无法分析")
        sys.exit(2)

    toks = []
    for x in lp:
        toks.append({'ent': token_entropy(x.get('top_logprobs') or []),
                     'text': x.get('token', '')})
    segs = segment_entropies(toks)
    if not segs:
        print("无分段")
        sys.exit(0)

    # 尖峰：段平均熵 > 历史 0.9 分位
    avgs = sorted(s['avg'] for s in segs)
    k = max(0, int(0.9 * (len(avgs) - 1)))
    thr = avgs[k]
    spikes = [s for s in segs if s['avg'] > thr and s['ntok'] >= 3]

    print("\n段平均熵（%d 段，尖峰阈值 %.2f）：" % (len(segs), thr))
    for i, s in enumerate(segs):
        mark = "  <<< 尖峰" if s in spikes else ""
        if s in spikes or s['avg'] > thr * 0.75:
            print("  seg%02d avg=%.2f peak=%.2f n=%d | %s%s" % (i, s['avg'], s['peak'], s['ntok'], s['text'], mark))
    n = len(spikes)
    print("\n尖峰段 %d/%d（%.0f%%）" % (n, len(segs), 100.0 * n / len(segs)))
    print("全文近熵均值 %.2f（GUARD 参考线：错误段 1.09 / 正确段 0.39，top10 近似偏低）"
          % (sum(avgs) / len(avgs)))

if __name__ == "__main__":
    main()
