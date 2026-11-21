#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""注入检测分类器常驻服务（随 dsh 启停）。

设计：
- 纯 HTTP（标准库 http.server），无第三方 web 框架
- 只用 tokenizers + onnxruntime（绕开 transformers 4.44 不认 modernbert）
- 绑 E 核（psutil affinity，Logical CPU 12-15，CoreInfo 实证）
- batch=1（避免 ONNX batch16+512token+4线程死锁）
- 只返回分数，不写 trace、不 steer —— 判定逻辑在 harness 侧

端点：
  GET  /health  -> {"status":"ok","model":...}
  POST /classify {"text": "..."} -> {"score": 0.0-1.0, "skipped": bool, "reason": ...}

用法（由 dsh-classifier-autostart 插件拉起）:
  python classifier_service.py --port 9899 --threads 4
"""
import argparse
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.pop('HF_ENDPOINT', None)
import numpy as np
import tokenizers
import onnxruntime as ort

BASE = 'C:/Users/Ad/.cache/huggingface/hub/models--Horizon-Labs--prompt-injection-guard-base/snapshots/main'
MODEL = BASE + '/onnx/model_quantized.onnx'
TOKENIZER = BASE + '/tokenizer.json'
MAX_LEN = 512

# 前置过滤：错误堆栈/乱码文本不是注入载体，跳过分类器（离线审计：可砍79%误报）
SKIP_PATTERNS = [
    re.compile(r'^\s*(\[stderr\]|Traceback|Error:|ParserError|PermissionError)', re.I),
    re.compile(r'^\s*Error: \[sandbox', re.I),
    re.compile(r'CLAIM_REFUSED|CLAIMED:', re.I),
]


def is_garbled(text):
    """乱码/base64 高占比检测（离线审计：11/24 误报是这类）"""
    if '\ufffd' in text:
        return True
    if re.search(r'\\u[0-9a-fA-F]{4}', text):
        return True
    long_b64 = re.findall(r'[A-Za-z0-9+/]{60,}={0,2}', text)
    return bool(long_b64)


def should_skip(text):
    if any(p.search(text) for p in SKIP_PATTERNS):
        return 'error_output'
    if is_garbled(text):
        return 'garbled'
    return None


class Classifier:
    def __init__(self, threads=4):
        self.tok = tokenizers.Tokenizer.from_file(TOKENIZER)
        self.tok.enable_truncation(max_length=MAX_LEN)
        self.tok.enable_padding(pad_id=0, pad_token='<pad>')
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(MODEL, so, providers=['CPUExecutionProvider'])
        # E 核绑定（CoreInfo 实证：0-11=P核, 12-15=E核）
        try:
            import psutil
            p = psutil.Process()
            p.cpu_affinity([12, 13, 14, 15][:threads])
            self.affinity = p.cpu_affinity()
        except Exception as e:
            self.affinity = ['bind-failed', str(e)[:80]]

    def score(self, text):
        enc = self.tok.encode_batch([text[:8000]])  # 先粗截，避免超长输入
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        logits = self.sess.run(None, {'input_ids': ids, 'attention_mask': mask})[0]
        return float(1 / (1 + np.exp(-(logits[0, 1] - logits[0, 0]))))


class Handler(BaseHTTPRequestHandler):
    clf = None

    def log_message(self, fmt, *args):
        pass  # 静默，避免刷屏

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            self._send(200, {'status': 'ok', 'model': 'Horizon-Labs@0.9',
                             'affinity': self.clf.affinity, 'max_len': MAX_LEN})
        else:
            self._send(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/classify':
            self._send(404, {'error': 'not found'})
            return
        try:
            n = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(n) or b'{}')
            text = str(data.get('text', ''))
            if not text:
                self._send(400, {'error': 'empty text'})
                return
            reason = should_skip(text)
            if reason:
                self._send(200, {'score': 0.0, 'skipped': True, 'reason': reason})
                return
            score = self.clf.score(text)
            self._send(200, {'score': round(score, 4), 'skipped': False,
                             'flag': score >= 0.9})
        except Exception as e:
            self._send(500, {'error': str(e)[:200]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=9899)
    ap.add_argument('--threads', type=int, default=4)
    args = ap.parse_args()
    Handler.clf = Classifier(args.threads)
    print(f'[classifier-service] ready on 127.0.0.1:{args.port} affinity={Handler.clf.affinity}', flush=True)
    srv = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    srv.serve_forever()


if __name__ == '__main__':
    main()
