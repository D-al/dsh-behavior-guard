# -*- coding: utf-8 -*-
"""config_check —— .env.llama 与 llama-router-preset.ini 的一致性检查（0 成本）

背景（2026-11-18 实测坑）：reasoning-budget 在 .env 是 4096、INI 是 -1（无限制）——
.env 一旦加载失败，思考预算就失控。同类键不一致应被机械检出。
用法: python bench/config_check.py
"""
import os
import re
import sys

ENV = r'D:\Brain\dsh-data\profiles\desktop\.env.llama'
INI = r'D:\Brain\workspace\bench\llama-router-preset.ini'

# 映射：INI 键 → .env 键（LLAMA_35B_ 前缀 + 大写）
def env_key_for(ini_key: str) -> str:
    return 'LLAMA_35B_' + ini_key.replace('-', '_').replace('.', '_').upper()

def parse_ini(path):
    d = {}
    if not os.path.exists(path):
        return d
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('[') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        d[k.strip()] = v.strip()
    return d

def parse_env(path):
    d = {}
    if not os.path.exists(path):
        return d
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        d[k.strip()] = v.strip()
    return d

def normalize(x: str) -> str:
    """把等价写法归一：true/1/yes/on、false/0/no/off，去掉包裹引号"""
    v = str(x).strip().strip('"').strip("'").lower()
    if v in ('true', '1', 'yes', 'on'):
        return 'true'
    if v in ('false', '0', 'no', 'off'):
        return 'false'
    return v


def main():
    ini = parse_ini(INI)
    env = parse_env(ENV)
    if not ini:
        print(f'[跳过] INI 不存在: {INI}')
        return 0
    if not env:
        print(f'[警告] .env 不存在: {ENV}（INI 是唯一配置源）')
    problems = []
    checked = 0
    for k, v in ini.items():
        ek = env_key_for(k)
        if ek not in env:
            continue
        checked += 1
        ev = env[ek]
        if not ev:
            continue  # .env 留空表示"用默认"，不比对
        if normalize(ev) != normalize(v):
            problems.append(f'  {k}: INI="{v}" vs .env="{ev}"')
    print(f'比对 {checked} 个重叠键')
    if problems:
        print('[不一致] 以下键两处取值不同（.env 优先，注意 INI 兜底值）：')
        print('\n'.join(problems))
        return 1
    print('[一致] 无冲突')
    return 0

if __name__ == '__main__':
    sys.exit(main())
