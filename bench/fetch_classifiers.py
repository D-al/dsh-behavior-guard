#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载分类器候选到 HF 缓存（绕开 MITM 代理的 SSL 校验失败）。

用法: python bench/fetch_classifiers.py <model_id> [model_id ...]
下载后可用本地 snapshot 路径或 model_id（离线）加载。
"""
import os
import ssl
import sys
import urllib.request
import json
from pathlib import Path

os.environ.pop('HF_ENDPOINT', None)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

CACHE = Path('C:/Users/Ad/.cache/huggingface/hub')
# config 里出现的权重/tokenizer 文件名
CANDIDATE_FILES = [
    'config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json',
    'vocab.txt', 'spm.model', 'sentencepiece.bpe.model', 'added_tokens.json',
    'model.safetensors', 'pytorch_model.bin',
]


def fetch(model_id):
    """用 HF API 列真实文件，逐个下载到 snapshots/main。"""
    parts = model_id.split('/')
    local = CACHE / ('models--' + parts[0] + '--' + parts[1])
    snap = local / 'snapshots' / 'main'
    snap.mkdir(parents=True, exist_ok=True)
    (local / 'refs').mkdir(exist_ok=True)
    (local / 'refs' / 'main').write_text('main', encoding='utf-8')
    # 查真实文件列表
    api = f'https://huggingface.co/api/models/{model_id}'
    try:
        r = urllib.request.urlopen(api, timeout=30, context=CTX)
        meta = json.loads(r.read())
    except Exception as e:
        print(f'  API失败: {e}')
        return None
    files = [x['rfilename'] for x in meta.get('siblings', [])]
    # 只要配置/词表/权重，跳过 README/gitattributes
    keep = [f for f in files if f.endswith(('.json', '.txt', '.model', '.safetensors', '.bin', '.onnx', '.pt'))
            and f != 'README.md']
    ok = []
    for fn in keep:
        dest = snap / fn
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            ok.append(fn)
            continue
        url = f'https://huggingface.co/{model_id}/resolve/main/{fn}'
        for attempt in range(2):
            try:
                r = urllib.request.urlopen(url, timeout=120, context=CTX)
                data = r.read()
                if len(data) < 10:
                    break
                dest.write_bytes(data)
                ok.append(fn)
                print(f'  {fn}: {len(data)//1024} KB', flush=True)
                break
            except Exception as e:
                if attempt == 1:
                    print(f'  {fn}: FAIL {type(e).__name__}', flush=True)
    config_ok = any(f == 'config.json' for f in ok)
    has_weight = any(f.endswith(('.safetensors', '.bin', '.onnx', '.pt')) for f in ok)
    return snap if config_ok and has_weight else None


if __name__ == '__main__':
    for mid in sys.argv[1:]:
        print(f'\n=== {mid} ===')
        p = fetch(mid)
        print(f'  -> {p}' if p else '  FAILED')
