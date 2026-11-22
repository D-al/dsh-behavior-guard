#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skills 双轨 A/B 受控实验（2026-11-22）

用户要求："测试一下，尤其是针对常用工具和不常用工具都有试试"
对比：自研关键词技能卡注入 ON vs OFF（OFF 时官方 skill 工具仍在）

设计（控制变量）：
- 场景1 常用工具：读文件+grep 统计，不含 skills 关键词 → 两模式都不注入，测注入机制是否干扰高频工具
- 场景2 低频关键：排查 llama-server 卡死（命中 debug-llama-server 关键词）→ ON 注入技能卡，OFF 不注入
- 每次要求模型"只用工具完成，不要只给建议"
- 证据：会话文件的 tool/call 事件（data.name），只认真实 sid，不用关键词计数

用法：
  python tools/skills_ab_probe.py prepare-off   # 关自研注入(改运行版cordis.patch,须重启dsh生效)
  python tools/skills_ab_probe.py restore       # 恢复原配置
  python tools/skills_ab_probe.py collect <sid路径>  # 采集单会话工具分布
"""
import argparse, json, os, re, shutil, sys
from collections import Counter
from pathlib import Path

PUB = Path('D:/Brain/publish/dsh-behavior-guard')
RUN_PATCH = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/cordis.patch.yml')
BACKUP = Path('D:/Brain/_cleanup_20261118/cordis.patch.before_skills_ab.yml')
SESSIONS = Path('D:/Brain/dsh-data/sessions')

# 两个场景的任务文本（发给 dsh 的用户消息）
TASKS = {
    'common': ('请只使用工具完成，不要只写建议：'
               '列出 D:/Brain/publish/dsh-behavior-guard/tools 目录下所有 .py 文件，'
               '统计数量，并用 grep 找出其中包含 "def main" 的文件。最后把统计结果写到 '
               'D:/Brain/_cleanup_20261118/ab_common_result.txt。'),
    'rare': ('请只使用工具完成，不要只写建议：'
             '本机 llama-server 启动后卡死、显存不足 OOM，请按排查顺序诊断，'
             '先用工具查看当前进程和显存状态，把诊断步骤和结论写到 '
             'D:/Brain/_cleanup_20261118/ab_rare_result.txt。'),
}


def prepare_off(args):
    """关闭自研技能卡注入（运行版配置，需重启 dsh 生效）。"""
    if not BACKUP.exists():
        shutil.copy2(RUN_PATCH, BACKUP)
        print(f'备份: {BACKUP}')
    s = RUN_PATCH.read_text(encoding='utf-8')
    if 'skillsEnabled: false' in s:
        print('已经是 OFF'); return 0
    # 在 agent-harness config 块加 skillsEnabled: false
    anchor = '    - id: agent-harness\n      name: dsh-agent-harness\n      config:\n'
    assert anchor in s, '找不到 agent-harness config 锚点'
    s = s.replace(anchor, anchor + '        skillsEnabled: false  # A/B 实验临时关闭（2026-11-22）\n', 1)
    RUN_PATCH.write_text(s, encoding='utf-8')
    print('OFF 已写入（需重启 dsh 生效）')
    return 0


def restore(args):
    if not BACKUP.exists():
        print('无备份，无需恢复'); return 0
    shutil.copy2(BACKUP, RUN_PATCH)
    print('已恢复原配置（需重启 dsh 生效）')
    return 0


def collect(args):
    """从会话目录/zstd 采集 tool/call 分布 + skill_card 注入证据。"""
    import zstandard
    src = Path(args.session)
    if src.is_dir():
        cands = list(src.glob('*.jsonl.zstd'))
        if not cands:
            print('目录无 zstd'); return 2
        src = cands[0]
    d = zstandard.ZstdDecompressor()
    data = d.stream_reader(open(src, 'rb')).read().decode('utf-8', errors='replace')
    events = [json.loads(l) for l in data.splitlines() if l.strip()]

    tools = Counter()
    skill_calls = 0
    skill_mentions = 0
    for e in events:
        if e.get('type') == 'tool/call':
            name = (e.get('data') or {}).get('name', '?')
            tools[name] += 1
            if name in ('skill', 'load_skill'):
                skill_calls += 1
        # 注入的技能卡是 harness 以 user/message 角色插入的（不是 assistant/message）
        # 2026-11-22 实测修正：原查 assistant/message 导致注入痕迹永远为 0
        if e.get('type') in ('user/message', 'agent/inbox/spliced'):
            txt = json.dumps(e, ensure_ascii=False)
            if '[harness 技能可用]' in txt:
                skill_mentions += 1

    print(f'会话: {src}')
    print(f'事件数: {len(events)} | 工具调用总数: {sum(tools.values())}')
    print(f'工具分布: {dict(tools.most_common())}')
    print(f'官方 skill 工具调用: {skill_calls} | 技能卡注入痕迹: {skill_mentions}')
    if args.json:
        print(json.dumps({'tools': dict(tools), 'skill_calls': skill_calls,
                          'skill_mentions': skill_mentions, 'total': sum(tools.values())},
                         ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description='skills 双轨 A/B 实验')
    ap.add_argument('cmd', choices=['prepare-off', 'restore', 'collect', 'tasks'])
    ap.add_argument('--session', help='collect: 会话目录或zstd路径')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    if args.cmd == 'prepare-off': return prepare_off(args)
    if args.cmd == 'restore': return restore(args)
    if args.cmd == 'collect':
        if not args.session:
            print('需要 --session'); return 2
        return collect(args)
    if args.cmd == 'tasks':
        print(json.dumps(TASKS, ensure_ascii=False, indent=2)); return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
