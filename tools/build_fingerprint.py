# -*- coding: utf-8 -*-
"""build 一致性检查：A/B 前必跑，锁定引擎二进制与 DLL 哈希。

背景：生产用 D:/llama.cpp/build/bin，测速脚本用 D:/llama-gdn-src/build-gdn/bin，
两者同为 94f3af3 源码但 DLL 哈希全不同 → 跨 build 的性能数据不可比。

用法：python build_fingerprint.py [dir1] [dir2] ...
默认检查生产 build 和测速 build。
"""
import sys, hashlib
from pathlib import Path

BUILDS = [
    ('生产', 'D:/llama.cpp/build/bin'),
    ('测速(gdn)', 'D:/llama-gdn-src/build-gdn/bin'),
]
Dlls = ['llama.dll', 'ggml.dll', 'ggml-cuda.dll', 'llama-server-impl.dll']
CORE = ['llama-server.exe']


def fp(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()[:12]


def main():
    dirs = [(f'自定义{i}', d) for i, d in enumerate(sys.argv[1:])] if len(sys.argv) > 1 else BUILDS
    sigs = {}
    for label, d in dirs:
        p = Path(d)
        print(f'=== {label}: {d} ===')
        if not p.exists():
            print('  不存在'); continue
        sigs[label] = {}
        for name in CORE + Dlls:
            f = p / name
            if f.exists():
                h = fp(f); sigs[label][name] = h
                print(f'  {name:24} {h}  {f.stat().st_size}')
            else:
                print(f'  {name:24} 缺失')
    if len(sigs) >= 2:
        labels = list(sigs.keys())
        a, b = sigs[labels[0]], sigs[labels[1]]
        common = set(a) & set(b)
        diff = [n for n in common if a[n] != b[n]]
        print(f'\n=== 对比 {labels[0]} vs {labels[1]} ===')
        print(f'  共同文件 {len(common)}，差异 {len(diff)}')
        if diff:
            print('  ⚠ 不同 build：' + ', '.join(diff))
            print('  → A/B 数据不可跨 build 比较，必须先统一')
        else:
            print('  ✅ 一致')


if __name__ == '__main__':
    main()
