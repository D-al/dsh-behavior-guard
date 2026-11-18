# -*- coding: utf-8 -*-
"""skill_draft —— 从 _trace.jsonl 的成功/失败轨迹生成 skill 草稿（离线，人工确认后入库）

依据（Part 8 G1）：
- Trace2Skill (arXiv 2603.25158)：并行分析多条轨迹 + 统一归纳，避免顺序更新把技能越改越碎
- SkillCAT (arXiv 2606.13317)：成功 vs 失败配成对照组，只找解释结果差异的证据
- SkillComposer (arXiv 2606.06079)：Create/Merge/Improve 三动作

设计原则（重要）：
1. **只生成草稿到 bench/_skill_drafts/，不直接改 bench/skills/**——必须人工确认
2. G1 必须与 G2（记忆反向修订）成对——只生成新技能不修订旧技能，错误经验会加速积累
3. 输出 frontmatter（name/summary/keywords）+ 证据引用（step/sid），便于人工核验

用法:
  python bench/skill_draft.py                    # 全部会话
  python bench/skill_draft.py --min-fails 3     # 至少 3 次重复失败才生成草稿
"""
import json
import os
import re
import sys
from collections import defaultdict

TRACE = r'D:\Brain\workspace\bench\_trace.jsonl'
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_skill_drafts')


def load():
    rows = []
    if not os.path.exists(TRACE):
        print('无 trace:', TRACE)
        sys.exit(0)
    for line in open(TRACE, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def main():
    args = sys.argv[1:]
    min_fails = 3
    if '--min-fails' in args:
        min_fails = int(args[args.index('--min-fails') + 1])

    rows = load()
    # 按工具名聚合成功/失败
    by_tool = defaultdict(lambda: {'ok': [], 'fail': []})
    for r in rows:
        if r.get('kind') != 'tool_result':
            continue
        name = r.get('name') or '(unknown)'
        status = r.get('status') or ''
        rec = {'sid': r.get('sid', '?'), 'step': r.get('step', 0), 'status': status,
               'ms': r.get('ms'), 'outChars': r.get('outChars', 0)}
        if status == 'OK':
            by_tool[name]['ok'].append(rec)
        else:
            by_tool[name]['fail'].append(rec)

    candidates = [(name, d) for name, d in by_tool.items()
                  if len(d['fail']) >= min_fails]
    if not candidates:
        print(f'没有工具达到失败阈值（≥{min_fails} 且失败多于成功）——无需生成草稿')
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    created = 0
    for name, d in sorted(candidates, key=lambda kv: -len(kv[1]['fail'])):
        fails = d['fail'][:5]
        oks = d['ok'][:3]
        safe = re.sub(r'[^a-z0-9_-]', '-', name.lower()).strip('-') or 'tool'
        path = os.path.join(OUT_DIR, f'draft-{safe}.md')
        lines = [
            '---',
            f'name: {safe}-usage',
            f'summary: 从 trace 归纳的 {name} 工具使用经验（草稿，待人工确认）',
            f'keywords: [{name}, {safe}, 工具使用]',
            'status: DRAFT',
            '---',
            '',
            f'# {name} 使用草稿（自动生成）',
            '',
            f'失败 **{len(d["fail"])}** 次 / 成功 **{len(d["ok"])}** 次。',
            '',
            '## 失败样本（证据）',
        ]
        for f in fails:
            lines.append(f'- sid={f["sid"]} step={f["step"]} status={f["status"]} chars={f["outChars"]}')
        if oks:
            lines.append('')
            lines.append('## 成功样本（对照）')
            for o in oks:
                lines.append(f'- sid={o["sid"]} step={o["step"]} status=OK')
        lines += [
            '',
            '## 待补（人工）',
            '- [ ] 读失败样本对应的实际轨迹，确认根因（不是工具坏，而是参数/路径/时机错）',
            '- [ ] 写具体 lesson（动词开头、可执行）',
            '- [ ] 若教训被证伪，用 G2 反向修订通道标记降级，不要直接删',
            '',
            '> 生成依据：Trace2Skill (2603.25158) / SkillCAT (2606.13317) / SkillComposer (2606.06079)',
            '> **不要直接复制到 bench/skills/**——人工确认后入库。',
        ]
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines) + '\n')
        created += 1
        print(f'  生成 {os.path.basename(path)}（失败 {len(d["fail"])} 次）')

    print(f'\n共 {created} 个草稿 → {OUT_DIR}')
    print('下一步：人工核验 → 确认后移入 bench/skills/；被证伪的教训走 G2 反向修订')


if __name__ == '__main__':
    main()
