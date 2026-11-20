"""用 arXiv 官方批量 API 核实全部编号：拿真实标题+摘要，与项目声称的标题比对。
这是权威源直连，不依赖任何中间转述。"""
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {'a': 'http://www.w3.org/2005/Atom'}
# 2026-11-20 收编进项目：默认读写项目内 data/evidence/，可用命令行覆盖
import sys
ROOT = Path(__file__).resolve().parent.parent.parent
NOTES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'evidence' / 'all_citations_20261120.txt'
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'data' / 'evidence' / 'arxiv_verified_20261120.json'

# 提取全部编号
txt = Path(NOTES).read_text(encoding='utf-8')
sec = txt.split('=== arXiv 编号 ===')[1].split('共 ')[0]  # 切到下一个统计段
ids = sorted(set(re.findall(r'^(\d{4}\.\d{4,5})', sec, re.M)))

# 提取每个编号在项目里声称的上下文
proj_ctx = {}
for line in sec.split('\n'):
    m = re.match(r'^(\d{4}\.\d{4,5})\s+(.*)$', line)
    if m:
        proj_ctx[m.group(1)] = m.group(2)

results = {}
BATCH = 20
for i in range(0, len(ids), BATCH):
    chunk = ids[i:i+BATCH]
    url = 'https://export.arxiv.org/api/query?' + urllib.parse.urlencode({
        'id_list': ','.join(chunk), 'max_results': BATCH})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                xml = r.read()
            break
        except Exception as e:
            if attempt == 2:
                print(f'batch {i//BATCH} FAILED: {e}')
                xml = None
            else:
                time.sleep(2)
    if not xml:
        continue
    root = ET.fromstring(xml)
    for entry in root.findall('a:entry', NS):
        aid = entry.find('a:id', NS).text.split('/abs/')[-1].split('v')[0]
        title = ' '.join(entry.find('a:title', NS).text.split())
        summary = ' '.join((entry.find('a:summary', NS).text or '').split())
        cats = [c.get('term') for c in entry.findall('a:category', NS)]
        results[aid] = {'title': title, 'summary': summary, 'categories': cats[:4]}
    print(f'batch {i//BATCH+1}: got {len(results)}/{len(ids)}')
    time.sleep(1)

missing = [x for x in ids if x not in results]
payload = {'total_requested': len(ids), 'total_found': len(results),
           'missing': missing, 'papers': results, 'project_context': proj_ctx}
Path(OUT).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'\n保存 {OUT}: found={len(results)} missing={len(missing)}')
if missing:
    print('missing:', ' '.join(missing))
