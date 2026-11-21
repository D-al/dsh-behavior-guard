#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载分类器候选的配置文件（小文件，绕开 MITM SSL 校验）。

用法: python bench/fetch_configs.py
把 config/tokenizer 等放到 HF 缓存对应 snapshots/main/ 下。
"""
import json
import os
import ssl
import urllib.request
from pathlib import Path

os.environ.pop('HF_ENDPOINT', None)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
CACHE = Path('C:/Users/Ad/.cache/huggingface/hub')

MODELS = {
    'devndeploy/bert-prompt-injection-detector': [
        'config.json', 'tokenizer.json', 'tokenizer_config.json',
        'special_tokens_map.json', 'vocab.txt', 'added_tokens.json'],
    'Verm1ion/injection-sentry-xlmr': [
        'config.json', 'tokenizer.json', 'tokenizer_config.json',
        'special_tokens_map.json', 'added_tokens.json', 'sentencepiece.bpe.model'],
    'RelyD/prompt-injection-detector': [
        'config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json'],
    'flowxai/injection': [
        'config.json', 'tokenizer.json', 'tokenizer_config.json',
        'special_tokens_map.json', 'added_tokens.json', 'sentencepiece.bpe.model'],
}


def fetch_one(model_id, fn):
    org, name = model_id.split('/')
    d = CACHE / f'models--{org}--{name}' / 'snapshots' / 'main'
    d.mkdir(parents=True, exist_ok=True)
    (d.parent.parent / 'refs').mkdir(exist_ok=True)
    (d.parent.parent / 'refs' / 'main').write_text('main', encoding='utf-8')
    dest = d / fn
    if dest.exists() and dest.stat().st_size > 0:
        return f'skip({dest.stat().st_size}B)'
    url = f'https://hf-mirror.com/{model_id}/resolve/main/{fn}'
    for host in ['hf-mirror.com', 'huggingface.co', 'hf-mirror.com']:
        try:
            url = f'https://{host}/{model_id}/resolve/main/{fn}'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'})
            r = urllib.request.urlopen(req, timeout=15, context=CTX)
            data = r.read()
            if len(data) < 5:
                continue
            dest.write_bytes(data)
            return f'OK({len(data)}B via {host})'
        except Exception as e:
            last = type(e).__name__
    return f'FAIL({last})'


if __name__ == '__main__':
    for model_id, files in MODELS.items():
        print(f'\n=== {model_id} ===')
        for fn in files:
            print(f'  {fn}: {fetch_one(model_id, fn)}', flush=True)
