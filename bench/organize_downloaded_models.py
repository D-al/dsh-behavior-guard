#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""整理用户下载到桌面的模型文件 → HF 缓存标准结构。

用法:
  python bench/organize_downloaded_models.py "C:/Users/Ad/Desktop/model"

自动识别每个权重文件属于哪个候选（按 safetensors 头部维度 / ONNX 格式），
改名为模型要求的原始文件名，放到:
  C:/Users/Ad/.cache/huggingface/hub/models--<org>--<name>/snapshots/main/
"""
import json
import shutil
import struct
import sys
from pathlib import Path

CACHE = Path('C:/Users/Ad/.cache/huggingface/hub')
SRC = Path(sys.argv[1] if len(sys.argv) > 1 else 'C:/Users/Ad/Desktop/model')

# 候选：org/name -> 权重目标文件名 + 架构指纹
TARGETS = {
    'devndeploy/bert-prompt-injection-detector': {'weight': 'model.safetensors', 'kind': 'safetensors', 'layers': 12, 'hidden': 768},
    'Verm1ion/injection-sentry-xlmr': {'weight': 'model.safetensors', 'kind': 'safetensors', 'layers': 12, 'hidden': 768},
    'RelyD/prompt-injection-detector': {'weight': 'model.safetensors', 'kind': 'safetensors', 'layers': 6, 'hidden': 768},
    'flowxai/injection': {'weight': 'onnx/model.int8.onnx', 'kind': 'onnx'},
}

CONFIG_FILES = ['config.json', 'tokenizer.json', 'tokenizer_config.json',
                'special_tokens_map.json', 'vocab.txt', 'added_tokens.json',
                'sentencepiece.bpe.model']


def safetensors_header(path):
    with path.open('rb') as f:
        n = struct.unpack('<Q', f.read(8))[0]
        header = json.loads(f.read(n))
    return header


def identify(path):
    head = path.open('rb').read(8)
    if head[:2] in (b'\x08\x08', b'\x08\x12') or head[:4] == b'\x08\x08\x12\x0d':
        return 'flowxai/injection'  # ONNX = flowxai 的 INT8
    if path.suffix in ('.safetensors', '.crdownload'):
        try:
            h = safetensors_header(path)
            keys = list(h.keys())
            # 数层数：找 layer.N. 的最大 N
            import re
            layers = max((int(m.group(1)) for k in keys for m in [re.search(r'layer\.(\d+)\.', k)] if m), default=-1)
            hidden = None
            for k, v in h.items():
                if isinstance(v, dict) and v.get('dtype') and len(v.get('shape', [])) == 2:
                    hidden = v['shape'][-1]
                    break
            return layers, hidden, keys[:3]
        except Exception as e:
            return 'safetensors-parse-error', str(e)[:60]
    return 'unknown'


def dest_for(model_id):
    org, name = model_id.split('/')
    d = CACHE / f'models--{org}--{name}' / 'snapshots' / 'main'
    d.mkdir(parents=True, exist_ok=True)
    (d.parent.parent / 'refs').mkdir(exist_ok=True)
    (d.parent.parent / 'refs' / 'main').write_text('main', encoding='utf-8')
    return d


def main():
    if not SRC.exists():
        print(f'目录不存在: {SRC}')
        return
    files = [f for f in SRC.iterdir() if f.is_file() and f.stat().st_size > 1000]
    print(f'找到 {len(files)} 个文件:')
    for f in files:
        print(f'  {f.name}: {f.stat().st_size/1024/1024:.1f} MB -> {identify(f)}')

    # 先识别权重
    assignments = {}
    for f in files:
        info = identify(f)
        if info == 'flowxai/injection':
            assignments['flowxai/injection'] = f
        elif isinstance(info, tuple) and len(info) == 3 and isinstance(info[0], int):
            layers, hidden, keys = info
            print(f'  权重 {f.name}: layers={layers} hidden={hidden} keys={keys}')
            # BERT 12层 vs DistilBERT 6层
            if layers >= 10:
                # 12层: devndeploy 或 Verm1ion —— 之后按大小/配置区分，先默认 devndeploy
                assignments.setdefault('_12layer', []).append(f)
            elif 0 <= layers <= 7:
                assignments['RelyD/prompt-injection-detector'] = f

    # 12层的两个模型按文件大小区分（XLM-R 278M > BERT 179M）
    twelves = assignments.pop('_12layer', [])
    for f in twelves:
        size_mb = f.stat().st_size / 1024 / 1024
        target = 'Verm1ion/injection-sentry-xlmr' if size_mb > 400 else 'devndeploy/bert-prompt-injection-detector'
        assignments[target] = f

    # 复制权重到缓存 + 改名
    for model_id, src in assignments.items():
        if model_id.startswith('_'):
            continue
        d = dest_for(model_id)
        name = TARGETS[model_id]['weight']
        dest = d / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size == src.stat().st_size:
            print(f'[skip] {model_id}/{name} 已存在')
            continue
        shutil.copy2(src, dest)
        print(f'[copy] {src.name} -> {model_id}/{name} ({dest.stat().st_size/1024/1024:.1f} MB)')

    # 复制配置文件（按文件名归类：用户若分文件夹放，则从对应子目录读）
    for model_id in TARGETS:
        org, name = model_id.split('/')
        d = dest_for(model_id)
        # 优先从以模型名命名的子目录读
        candidates = [SRC / name, SRC / f'{org}--{name}', SRC]
        for cf in CONFIG_FILES:
            for base in candidates:
                src = base / cf
                if src.exists() and not src.name.endswith('.crdownload'):
                    dest = d / cf
                    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                        shutil.copy2(src, dest)
                        print(f'[cfg] {model_id}/{cf}')
                    break

    print('\n=== 整理完成，缓存状态 ===')
    for model_id in TARGETS:
        d = dest_for(model_id)
        w = d / TARGETS[model_id]['weight']
        print(f'  {model_id}: {"OK" if w.exists() else "缺权重"} ({w.stat().st_size/1024/1024:.1f} MB)' if w.exists()
              else f'  {model_id}: 缺权重')


if __name__ == '__main__':
    main()
