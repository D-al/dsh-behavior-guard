"""全量提取项目里所有外部引用：arXiv ID、GitHub issue/PR、URL、论文标题。"""
import os
import re
from collections import defaultdict

ROOT = r'D:\Brain\publish\dsh-behavior-guard'
SKIP_DIRS = {'.git', '__pycache__', 'node_modules', 'archive', 'docs/archive'}

# arXiv 编号（各种写法）
ARXIV = re.compile(r'arXiv[:\s]*(\d{4}\.\d{4,5})', re.I)
ARXIV_URL = re.compile(r'arxiv\.org/abs/(\d{4}\.\d{4,5})', re.I)
# GitHub issue/PR
GH_ISSUE = re.compile(r'(?:github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/(\d+))', re.I)
# 裸 issue #号（带上下文工具名）
BARE_ISSUE = re.compile(r'([A-Za-z][\w.-]*)\s*(?:issue|Issue|PR)\s*#?(\d+)')
# 所有 http URL（排除本地）
URLS = re.compile(r'https?://[^\s)\]>"`，,；;]+')

refs = defaultdict(lambda: defaultdict(set))  # type -> id -> files

for dirpath, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fn in files:
        if not (fn.endswith(('.md', '.json', '.py', '.mjs', '.yaml', '.yml'))):
            continue
        fp = os.path.join(dirpath, fn)
        try:
            txt = open(fp, encoding='utf-8').read()
        except Exception:
            continue
        rel = os.path.relpath(fp, ROOT)
        for m in ARXIV.finditer(txt):
            refs['arxiv'][m.group(1)].add(rel)
        for m in ARXIV_URL.finditer(txt):
            refs['arxiv'][m.group(1)].add(rel)
        for m in GH_ISSUE.finditer(txt):
            refs['github'][m.group(1)].add(rel)
        for m in BARE_ISSUE.finditer(txt):
            refs['bare_issue'][f'{m.group(1)}#{m.group(2)}'].add(rel)
        for m in URLS.finditer(txt):
            u = m.group(0).rstrip('.,;)')
            if 'localhost' not in u and '127.0.0.1' not in u:
                refs['url'][u].add(rel)

print('=== arXiv 编号 ===')
for k in sorted(refs['arxiv']):
    print(f'{k:14s} {", ".join(sorted(refs["arxiv"][k])[:4])}')
print(f'\n共 {len(refs["arxiv"])} 个 arXiv 编号\n')

print('=== GitHub issue/PR 完整URL ===')
for k in sorted(refs['github']):
    print(f'{k:8s} {", ".join(sorted(refs["github"][k])[:3])}')

print('\n=== 裸 issue# 引用 ===')
for k in sorted(refs['bare_issue']):
    print(f'{k:28s} {", ".join(sorted(refs["bare_issue"][k])[:2])}')

print(f'\n=== 外部URL（去重，最多80条）===')
urls = sorted(refs['url'])
for u in urls[:80]:
    print(u[:120])
print(f'共 {len(urls)} 个唯一URL')
