#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Horizon 长文本能力测试：利用 8192 上下文直接输入，对比滑窗。

用隔离 venv 跑: venv_horizon/Scripts/python.exe bench/test_horizon_longtext.py
"""
import json
import time
from pathlib import Path

import numpy as np
import tokenizers
import onnxruntime as ort

BASE = Path('C:/Users/Ad/.cache/huggingface/hub/models--Horizon-Labs--prompt-injection-guard-base/snapshots/main')
tk = tokenizers.Tokenizer.from_file(str(BASE / 'tokenizer.json'))
so = ort.SessionOptions()
so.intra_op_num_threads = 4
sess = ort.InferenceSession(str(BASE / 'onnx' / 'model_quantized.onnx'), so,
                            providers=['CPUExecutionProvider'])


def score(ids, mask):
    logits = sess.run(None, {'input_ids': ids, 'attention_mask': mask})[0]
    return 1 / (1 + np.exp(-(logits[0, 1] - logits[0, 0])))


push = json.loads(Path('D:/Brain/_cleanup_20261118/push_samples.json').read_text(encoding='utf-8'))
longs = sorted([x['text'] for x in push], key=len, reverse=True)[:3]
print('长文本字符数:', [len(t) for t in longs], flush=True)

for text in longs:
    # 模式1: 直接输入(8192上下文)
    tk.enable_truncation(max_length=8192)
    enc = tk.encode(text)
    ids = np.array([enc.ids], dtype=np.int64)
    mask = np.array([enc.attention_mask], dtype=np.int64)
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        p_direct = score(ids, mask)
        ts.append((time.perf_counter() - t0) * 1000)
    p_direct = score(ids, mask)

    # 模式2: 512滑窗(max pooling)
    tk.enable_truncation(max_length=512)
    all_ids = tk.encode(text, add_special_tokens=False).ids
    windows = []
    for start in range(0, len(all_ids), 384):
        chunk = all_ids[start:start + 512]
        if not chunk:
            break
        w_ids = np.array([chunk], dtype=np.int64)
        w_mask = np.ones((1, len(chunk)), dtype=np.int64)
        windows.append(score(w_ids, w_mask))
        if start + 512 >= len(all_ids):
            break
    p_slide = max(windows)

    print(f'  字符={len(text):5} tokens={len(enc.ids):5} | '
          f'直接(8192)={sorted(ts)[1]:.0f}ms 分={p_direct:.3f} | '
          f'滑窗({len(windows)}窗)分={p_slide:.3f}', flush=True)
