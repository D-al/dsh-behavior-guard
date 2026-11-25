# -*- coding: utf-8 -*-
"""config_check —— 全栈配置一致性检查（0 成本）

背景（2026-11-18 实测坑）：reasoning-budget 在 .env 是 4096、INI 是 -1（无限制）——
.env 一旦加载失败，思考预算就失控。同类键不一致应被机械检出。

v2（2026-11-18）：从"env vs INI"扩展为全栈四处一致性：
  1. .env.llama vs llama-router-preset.ini（原有 23 键）
  2. cordis.patch.yml 的 **llama provider** contextWindow vs .env CTX
     （注意：ollama provider 的 1000000 是另一套，不参与比对）
  3. AGENTS.md 引用的 skill 名都真实存在（外置后防死链）
  4. skill frontmatter 的 keywords 非空、无重复（防检索失效）

用法: python bench/config_check.py
"""
import os
import re
import sys
from pathlib import Path

DSH_HOME = os.environ.get('DSH_HOME') or r'D:\Brain\dsh-data'
BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
ENV = str(Path(DSH_HOME) / 'profiles' / 'desktop' / '.env.llama')
INI = str(Path(BENCH_DIR) / 'llama-router-preset.ini')
CORDIS = str(Path(DSH_HOME) / 'profiles' / 'desktop' / 'cordis.patch.yml')
AGENTS = str(Path(DSH_HOME) / 'AGENTS.md')
SKILLS_DIR = str(Path(BENCH_DIR) / 'skills')


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
    """等价写法归一：true/1/yes/on、false/0/no/off，去包裹引号"""
    v = str(x).strip().strip('"').strip("'").lower()
    if v in ('true', '1', 'yes', 'on'):
        return 'true'
    if v in ('false', '0', 'no', 'off'):
        return 'false'
    return v


def check_env_ini(env, ini):
    """检查 1：env vs INI 重叠键"""
    problems = []
    checked = 0
    for k, v in ini.items():
        ek = env_key_for(k)
        if ek not in env:
            continue
        checked += 1
        ev = env[ek]
        if not ev:
            continue
        if normalize(ev) != normalize(v):
            problems.append(f'  {k}: INI="{v}" vs .env="{ev}"')
    return checked, problems


def check_cordis_ctx(env):
    """检查 2：cordis llama provider contextWindow vs .env CTX"""
    problems = []
    if not os.path.exists(CORDIS):
        return problems
    txt = open(CORDIS, encoding='utf-8').read()
    # 找 llama provider 段内的 contextWindow / defaultContextWindow（跳过 ollama 的 1000000）
    llama_ctx = None
    lines = txt.split('\n')
    in_llama = False
    for line in lines:
        if re.match(r'^\s{2,4}-\s*id:\s*llama\b', line) or re.search(r'^\s{2,4}llama:\s*$', line):
            in_llama = True
        elif re.match(r'^\s{2,4}-\s*id:\s*\w+', line) and not re.search(r'id:\s*llama\b', line):
            in_llama = False
        if in_llama:
            m = re.search(r'contextWindow:\s*(\d+)', line)
            if m:
                llama_ctx = m.group(1)
                break
    # 兜底：找所有 contextWindow，排除 1000000
    if llama_ctx is None:
        all_ctx = re.findall(r'contextWindow:\s*(\d+)', txt)
        cand = [x for x in all_ctx if x != '1000000']
        if cand:
            llama_ctx = cand[0]
    env_ctx = env.get('LLAMA_35B_CTX', '')
    if llama_ctx and env_ctx and llama_ctx != env_ctx:
        problems.append(f'  cordis llama contextWindow={llama_ctx} vs .env CTX={env_ctx}')
    return problems


def check_agents_skills():
    """检查 3：AGENTS.md 引用的 skill 都存在"""
    problems = []
    if not os.path.exists(AGENTS):
        return problems
    txt = open(AGENTS, encoding='utf-8').read()
    referenced = set(re.findall(r'skill\s+`([a-z0-9-]+)`', txt))
    if not referenced:
        return problems
    available = set()
    if os.path.isdir(SKILLS_DIR):
        for f in os.listdir(SKILLS_DIR):
            if f.endswith('.md'):
                available.add(f[:-3])
    missing = referenced - available
    if missing:
        problems.append(f'  AGENTS.md 引用但不存在的 skill: {", ".join(sorted(missing))}')
    return problems


# 硬值断言（2026-11-25 门禁化迁移）：只放"破坏后必出事"的项。
# 设计铁律：不断言可调参数（会误报），只断言实测证明过是承重墙的值。
# 每条带 reason——失败时输出为什么，不逼人去翻 BRIEF。
HARDENED_RULES = [
    ('LLAMA_35B_CTX_CHECKPOINTS', '2',
     '降到 1 → 每步全量重预填 +23% 耗时（11-18 实测）'),
    ('LLAMA_35B_MMPROJ_OFFLOAD', '1',
     '关掉 → 截图走 CPU 编码 141s（实测）'),
    ('LLAMA_35B_DRY_ALLOWED_LENGTH', '32',
     '设 2 → 模型改字形躲惩罚（DRY 必须给足窗口）'),
    ('LLAMA_35B_MOE_CACHE_CPU_SHARE', '1.0',
     '全host 布局下 share=1.0 端到端 -10.6%（11-23 五轮中位）'),
    ('LLAMA_35B_NMAX', '3',
     'nmax=5→3 已 95% 验证；7 占更多显存+CPU draft 更差'),
    ('LLAMA_35B_SPEC_TYPE', 'draft-mtp',
     'ngram 加生产参数后 e2e CI 跨 0，不落地'),
    ('LLAMA_35B_TOP_P', '0.95',
     '温度/top_p 组合是 Q4 实测最优区（0.7/0.95）'),
    ('LLAMA_35B_REASONING_BUDGET', '4096',
     '硬切会截断半句引发回路；4096+message 是平滑版'),
]


def check_hardened_config(env):
    """检查 5：BRIEF 铁律中可机械判定的硬值（fail-closed）。"""
    problems = []
    if not env:
        return problems
    for key, expected, reason in HARDENED_RULES:
        actual = env.get(key)
        if actual is None:
            continue  # 键缺失由 env-vs-INI 检查覆盖，不重复报
        if normalize(actual) != normalize(expected):
            problems.append(f'  {key}={actual}（应为 {expected}）— {reason}')
    # TEMP 必须留空：CLI 会覆盖 preset 的 temp=0.7
    temp = env.get('LLAMA_35B_TEMP')
    if temp is not None and temp.strip() and temp.strip() != '""':
        problems.append(f'  LLAMA_35B_TEMP={temp}（必须留空）— CLI 会覆盖 preset 的 temp=0.7，破坏按模型配温')
    return problems


def check_skill_keywords():
    """检查 4：skill frontmatter keywords 非空、无重复"""
    problems = []
    if not os.path.isdir(SKILLS_DIR):
        return problems
    for f in sorted(os.listdir(SKILLS_DIR)):
        if not f.endswith('.md'):
            continue
        txt = open(os.path.join(SKILLS_DIR, f), encoding='utf-8').read()
        m = re.search(r'^keywords:\s*\[(.*?)\]', txt, re.M)
        if not m:
            problems.append(f'  {f}: 缺 keywords 字段（插件无法检索）')
            continue
        kws = [x.strip() for x in m.group(1).split(',') if x.strip()]
        if not kws:
            problems.append(f'  {f}: keywords 为空')
        if len(kws) != len(set(kws)):
            problems.append(f'  {f}: keywords 有重复')
    return problems


def main():
    env = parse_env(ENV)
    ini = parse_ini(INI)
    problems = []

    # 1. env vs INI
    if ini:
        checked, p = check_env_ini(env, ini)
        print(f'[1] env vs INI：比对 {checked} 个重叠键')
        problems += p
    else:
        print(f'[1] INI 不存在，跳过: {INI}')
    if not env:
        print(f'[警告] .env 不存在: {ENV}（INI 是唯一配置源）')

    # 2. cordis contextWindow
    p2 = check_cordis_ctx(env)
    print(f'[2] cordis llama contextWindow vs .env CTX：{"一致" if not p2 else "不一致"}')
    problems += p2

    # 3. AGENTS skill 引用
    p3 = check_agents_skills()
    print(f'[3] AGENTS.md skill 引用：{"全部存在" if not p3 else "有缺失"}')
    problems += p3

    # 4. skill keywords
    p4 = check_skill_keywords()
    print(f'[4] skill keywords 完整性：{"OK" if not p4 else "有问题"}')
    problems += p4

    # 5. BRIEF 铁律硬值（门禁化迁移）
    p5 = check_hardened_config(env)
    print(f'[5] 硬值断言（{len(HARDENED_RULES)}条+TEMP）：{"OK" if not p5 else "违规"}')
    problems += p5

    if problems:
        print('\n[不一致] 以下问题需修复：')
        print('\n'.join(problems))
        return 1
    print('\n[一致] 全栈无冲突')
    return 0


if __name__ == '__main__':
    sys.exit(main())
