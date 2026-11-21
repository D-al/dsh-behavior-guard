#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线审计：用 Horizon 对历史真实工具输出打分（零运行时影响）。

目的：验证 2.3% FPR 在真实流量上是否成立，再决定要不要接运行时插件。
数据源：
  - 375 条唯一工具输出（_cur*.jsonl callId 去重）
  - 561 条推卡工具输出（push_samples.json 去重）
  - 92 条 trace 注入命中（只有 pattern 名，取 pattern 对应文本构造）

用 venv 跑: venv_horizon/Scripts/python.exe bench/audit_horizon_offline.py
"""
import json
import re
from pathlib import Path

import numpy as np
import tokenizers
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent.parent
BASE = Path('C:/Users/Ad/.cache/huggingface/hub/models--Horizon-Labs--prompt-injection-guard-base/snapshots/main')
OUT = ROOT / 'bench/_horizon_offline_audit.json'
THRESHOLD = 0.9


def load_benign():
    cur = Path('D:/Brain/workspace/bench/archive/session-dumps')
    seen, texts = set(), []
    for f in sorted(cur.glob('_cur*.jsonl')):
        for line in f.open(encoding='utf-8', errors='replace'):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get('type') != 'tool/result':
                continue
            d = r.get('data') or {}
            cid = d.get('message', {}).get('source', {}).get('callId') or d.get('toolCallId')
            if cid:
                if cid in seen:
                    continue
                seen.add(cid)
            c = d.get('message', {}).get('content', [])
            t = ' '.join(x.get('text', '') for x in c if isinstance(x, dict) and x.get('type') == 'text')
            if t.strip():
                texts.append(('cur', t))
    p = Path('D:/Brain/_cleanup_20261118/push_samples.json')
    if p.exists():
        for x in json.loads(p.read_text(encoding='utf-8')):
            t = x.get('text', '')
            if t.strip():
                texts.append(('push', t))
    # 全局去重
    s, out = set(), []
    for src, t in texts:
        if t not in s:
            s.add(t)
            out.append((src, t))
    return out


def main():
    tk = tokenizers.Tokenizer.from_file(str(BASE / 'tokenizer.json'))
    tk.enable_truncation(max_length=512)  # 离线审计只看前512 token(与运行时策略一致)
    tk.enable_padding(pad_id=0, pad_token='<pad>')  # batch 内补齐，否则 numpy 构数组失败
    so = ort.SessionOptions()
    so.intra_op_num_threads = 4
    sess = ort.InferenceSession(str(BASE / 'onnx' / 'model_quantized.onnx'), so,
                                providers=['CPUExecutionProvider'])
    benign = load_benign()
    print(f'[DATA] benign unique={len(benign)}', flush=True)

    probs = []
    for i in range(0, len(benign), 4):
        if i % 40 == 0:
            print(f'  progress {i}/{len(benign)}', flush=True)
        enc = tk.encode_batch([t for _, t in benign[i:i + 4]])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        logits = sess.run(None, {'input_ids': ids, 'attention_mask': mask})[0]
        probs.extend((1 / (1 + np.exp(-(logits[:, 1] - logits[:, 0])))).tolist())

    flagged = [(benign[i][0], p, benign[i][1][:120]) for i, p in enumerate(probs) if p >= THRESHOLD]
    by_src = {}
    for src, p, _ in flagged:
        by_src[src] = by_src.get(src, 0) + 1
    src_total = {}
    for src, _ in benign:
        src_total[src] = src_total.get(src, 0) + 1

    result = {
        'model': 'Horizon-Labs @0.9',
        'threshold': THRESHOLD,
        'benign_total': len(benign),
        'flagged_count': len(flagged),
        'fpr': round(len(flagged) / len(benign), 4) if benign else 0,
        'by_source_fpr': {s: {'total': src_total.get(s, 0), 'flagged': by_src.get(s, 0),
                              'fpr': round(by_src.get(s, 0) / src_total[s], 4) if src_total.get(s) else 0}
                          for s in src_total},
        'top_flagged': [{'source': s, 'score': round(p, 3), 'text': t} for s, p, t in
                        sorted(flagged, key=lambda x: -x[1])[:15]],
        'all_flagged': [{'source': s, 'score': round(p, 4), 'text': t} for s, p, t in flagged],
        'score_distribution': {
            'max': round(max(probs), 3), 'p99': round(float(np.percentile(probs, 99)), 3),
            'p95': round(float(np.percentile(probs, 95)), 3),
            'median': round(float(np.median(probs)), 3),
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[RESULT] total={len(benign)} flagged={len(flagged)} FPR={result["fpr"]}', flush=True)
    print(f'[DIST] {result["score_distribution"]}', flush=True)
    for s, v in result['by_source_fpr'].items():
        print(f'  {s}: {v["flagged"]}/{v["total"]} = {v["fpr"]}', flush=True)
    print(f'WROTE {OUT}', flush=True)


if __name__ == '__main__':
    main()
