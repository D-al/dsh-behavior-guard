"""扫描全库文档里的可疑引用数字——找可能编造的基准/论文数据。"""
import os
import re

ROOT = r'D:\Brain\publish\dsh-behavior-guard'
# 已由我 WebFetch 核实过的真实数据锚点（用来对照）
VERIFIED = {
    'arXiv:2607.16072': 'Frontier LMs Struggle to Copy (2026-07-17, 已核实)',
    'arXiv:2510.12487': 'Diff-XYZ (2025-10-14, 已核实)',
    'arXiv:2307.03172': 'Lost in the Middle (TACL2024)',
    'arXiv:2310.01798': 'LLMs Cannot Self-Correct (ICLR2024)',
    'arXiv:2406.12045': 'tau-bench',
    'arXiv:2406.16657': 'BFCL',
    'arXiv:2410.14684': 'RepoGraph',
    'arXiv:2408.03910': 'CodexGraph',
    'arXiv:2307.16789': 'ToolBench',
}
# 可疑模式：百分比 + 模型名/基准名的组合
SUSPECT = [
    r'(?:不一致率|不遵守率|复现).{0,30}\d+%',
    r'(?:GPT-4o|GPT-4|35B|Opus|Sonnet|Grok|Gemini).{0,40}\d+%',
    r'\d+%.{0,30}(?:GPT-4o|35B|Opus|Sonnet|Grok|Gemini)',
    r'(?:benchmark|基准|评测).{0,20}20\d\d[-年]\d{1,2}',
    r'issue\s*#\d+',
]

hits = []
for dirpath, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules', 'archive')]
    for fn in files:
        if not fn.endswith('.md'):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            lines = open(fp, encoding='utf-8').read().split('\n')
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for pat in SUSPECT:
                if re.search(pat, line, re.I):
                    rel = os.path.relpath(fp, ROOT)
                    hits.append((rel, i, line.strip()[:150]))
                    break

print(f'=== 可疑引用扫描：{len(hits)} 条 ===\n')
for rel, i, line in hits:
    print(f'{rel}:{i}: {line}')
