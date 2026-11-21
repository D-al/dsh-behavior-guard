#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flowxai/injection（ONNX INT8, 3攻击类无benign类）专用评测。

与 v4 的差异：
- 推理用 onnxruntime（无 PyTorch 权重）
- 输出 3 类 = direct/indirect/jailbreak，无 benign 类
- 攻击分数定义：sigmoid(max(logits))——若三类都低则视为良性
- 需实测校准：确认 logits 是 sigmoid 还是 softmax 语义

用法: python bench/bench_flowxai_onnx.py --threads 4
"""
import argparse
import json
import os
import time
from pathlib import Path

os.environ.pop('HF_ENDPOINT', None)
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
ONNX = Path('C:/Users/Ad/.cache/huggingface/hub/models--flowxai--injection/snapshots/main/onnx/model.int8.onnx')
TOKDIR = ONNX.parent.parent
OUT = ROOT / 'bench/_v4_flowxai_onnx.json'


def load_data():
    import importlib.util
    spec = importlib.util.spec_from_file_location('v4', ROOT / 'bench/classifier_bench_v4.py')
    v4 = importlib.util.module_from_spec(spec)
    import sys
    sys.modules['v4'] = v4
    spec.loader.exec_module(v4)
    cur, push = v4.load_cur(), v4.load_push()
    benign = v4.dedup_texts(cur + push)[:300]
    attacks, benign_like = v4.build_attacks(benign, 10)
    texts = benign + [a['text'] for a in attacks] + [b['text'] for b in benign_like]
    labels = [0] * len(benign) + [1] * len(attacks) + [0] * len(benign_like)
    return v4, benign, attacks, benign_like, texts, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--benign-count', type=int, default=300)
    args = ap.parse_args()

    tok = AutoTokenizer.from_pretrained(str(TOKDIR), local_files_only=True)
    so = ort.SessionOptions()
    so.intra_op_num_threads = args.threads
    so.inter_op_num_threads = 1
    sess = ort.InferenceSession(str(ONNX), so, providers=['CPUExecutionProvider'])

    v4, benign, attacks, benign_like, texts, labels = load_data()
    print(f'[DATA] benign={len(benign)} attacks={len(attacks)} benign_like={len(benign_like)}')

    def score(batch_texts):
        enc = tok(batch_texts, padding=True, truncation=True, max_length=512, return_tensors='np')
        logits = sess.run(None, {'input_ids': enc['input_ids'].astype(np.int64),
                                 'attention_mask': enc['attention_mask'].astype(np.int64)})[0]
        # sigmoid(max logits) —— 语义待校准，报告里注明
        return (1 / (1 + np.exp(-logits.max(axis=1)))).tolist(), logits

    # 语义诊断：跑几个样本看 logits 分布
    _, diag = score(texts[:6])
    print(f'[DIAG] logits前6行:\n{diag}')
    print(f'[DIAG] 每行和(判断是否softmax): {[round(float(x.sum()),3) for x in diag]}')

    # 延迟
    t0 = time.perf_counter()
    scores, logits_all = score([benign[0][:500]] * 5)
    lat = (time.perf_counter() - t0) * 1000 / 5
    print(f'[LATENCY] ~{lat:.1f}ms/条(5条批均摊)')

    # 全量score
    scores, all_logits = [], []
    for i in range(0, len(texts), 16):
        s, lg = score(texts[i:i + 16])
        scores.extend(s)
        all_logits.extend(lg.tolist())

    sweep = v4.sweep(scores, labels)
    off = len(benign)
    by_type = {}
    for j, a in enumerate(attacks):
        t = a['type']
        d = by_type.setdefault(t, {'n': 0, 'hit90': 0, 'hit50': 0, 'sum': 0.0})
        p = scores[off + j]
        d['n'] += 1
        d['hit90'] += p >= 0.9
        d['hit50'] += p >= 0.5
        d['sum'] += p
    for d in by_type.values():
        d['avg_prob'] = round(d['sum'] / d['n'], 3)
        del d['sum']

    result = {
        'model': 'flowxai/injection (ONNX INT8)',
        'score_definition': 'sigmoid(max(logits of 3 attack classes))',
        'caveat': '3类全是攻击类无benign;分数语义需校准;若logits行和≈1则实为softmax',
        'threads': args.threads,
        'latency_ms_per_sample': round(lat, 1),
        'logits_row_sums_sample': [round(float(sum(x)), 3) for x in all_logits[:6]],
        'data': {'benign': len(benign), 'attacks': len(attacks), 'benign_like': len(benign_like)},
        'sweep': sweep,
        'by_type': by_type,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    s09 = next(r for r in sweep if r['threshold'] == 0.9)
    print(f'[RESULT] @0.9 recall={s09["recall"]} fpr={s09["fpr"]} | WROTE {OUT}')


if __name__ == '__main__':
    main()
