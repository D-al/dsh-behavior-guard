#!/usr/bin/env python3
"""gpu_guard 行为判据：验聚合逻辑真能区分 3D/Copy/CUDA（不是只查文件存在）。

记忆铁律：聚合 util% 会骗人（空闲时 nvidia-smi 也报 100%），
真正判据是 Copy 引擎 + 显存带宽。此测试验证 totals 不把 3D 误算成 Copy。

用法: python tools/test_gpu_guard.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gpu_engine_guard as gg

passed = failed = 0
def check(label, ok):
    global passed, failed
    if ok: passed += 1
    else: failed += 1
    print(f'{"PASS" if ok else "FAIL"}  {label}')

# 1. 空输入 → 全 0
t = gg.totals({})
check('空输入全0', t == {'3d': 0.0, 'copy': 0.0, 'cuda': 0.0})

# 2. 3D 高、Copy 低 → 区分开（关键：不把 UI 渲染当推理）
t = gg.totals({100: {'3d': 64.0, 'copy': 0.8}, 200: {'3d': 34.0, 'copy': 0.2}})
check('3D高不污染Copy', t['3d'] == 98.0 and t['copy'] == 1.0)

# 3. 多进程 Copy 累加正确
t = gg.totals({100: {'copy': 12.0}, 200: {'copy': 8.0, 'cuda': 5.0}})
check('Copy跨进程累加', t['copy'] == 20.0 and t['cuda'] == 5.0)

# 4. 未知引擎 key 被忽略（不污染三个通道）
t = gg.totals({100: {'3d': 10.0, 'video': 99.0}})
check('未知引擎不污染', t == {'3d': 10.0, 'copy': 0.0, 'cuda': 0.0})

print(f'\n{passed}/{passed + failed} pass')
sys.exit(1 if failed else 0)
