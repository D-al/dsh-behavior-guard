#!/usr/bin/env python3
"""
roadmap_check.py — agent 自读能力阶梯的执行器（零 LLM）

读 CAPABILITY_LADDER.yaml（权威源），做三件事：
  --dry-run   默认：对每个条目跑 verify 判据，输出 ID | 状态 | 判据 | PASS/FAIL | 证据；不写任何文件
  --next      输出当前 agent 该爬的下一项（ready + autonomous + risk 最低 + deps 全 done）
  --apply     把 verify 全 PASS 的 doing 项写回 done（只写权威 YAML + ROADMAP.md 人类视图），
              主观判据(manual) 一律不自动勾选；写回前 git diff --check

设计原则（ADR-0012）：全部零 LLM——文件存在/内容 grep、单测退出码、trace JSONL 统计、JSON 字段。
安全：只读权威源；测试 sid 过滤；不碰 verify_agent.py（35B 600s）。
"""
import os
import re
import sys
import json
import yaml
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LADDER = ROOT / 'CAPABILITY_LADDER.yaml'
ROADMAP = ROOT / 'ROADMAP.md'
BENCH = Path(os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench')

RISK_ORDER = {'low': 0, 'med': 1, 'high': 2}


def load_ladder():
    return yaml.safe_load(LADDER.read_text(encoding='utf-8'))


def test_sids(data):
    return set(data.get('meta', {}).get('test_sids', []))


def read_jsonl(path):
    p = Path(path)
    if not p.is_absolute():
        p = BENCH / p
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def resolve_path(rel):
    """bench/ 开头的路径走 BENCH_DIR（运行数据），其余走权威仓库 ROOT。"""
    s = str(rel)
    if s.startswith('bench/'):
        return BENCH / s[len('bench/'):]
    return ROOT / s


def check_one(v, data):
    """返回 (ok: bool, evidence: str)。零 LLM。"""
    kinds = v.get('kind')
    try:
        if kinds == 'file_exists':
            p = resolve_path(v['path'])
            return p.exists(), str(p)

        if kinds == 'file_grep':
            p = resolve_path(v['path'])
            if not p.exists():
                return False, f'missing {p}'
            hits = len(re.findall(v['regex'], p.read_text(encoding='utf-8', errors='replace')))
            return hits >= v.get('min', 1), f'{hits} hits in {v["path"]}'

        if kinds == 'test_pass':
            proc = subprocess.run(v['cmd'], shell=True, cwd=ROOT,
                                  capture_output=True, text=True, timeout=300)
            passes = len(re.findall(r'^PASS', proc.stdout, re.M))
            ok = proc.returncode == 0 and passes >= v.get('min', 1)
            return ok, f'rc={proc.returncode} PASS={passes}'

        if kinds in ('trace_count', 'trace_absent'):
            rows = read_jsonl(v['source'])
            sidf = v.get('sid_filter')
            if sidf == 'exclude_tests':
                bad = test_sids(data)
                rows = [r for r in rows if str(r.get('sid', '')) not in bad]
            n = sum(1 for r in rows if r.get('kind') == v['kind_name'])
            if kinds == 'trace_count':
                return n >= v.get('min', 1), f'{v["kind_name"]}={n} (real sid)'
            return n <= v.get('max', 0), f'{v["kind_name"]}={n} (real sid)'

        if kinds == 'json_field':
            p = BENCH / v['path'] if not Path(v['path']).is_absolute() else Path(v['path'])
            if not p.exists():
                return False, f'missing {p}'
            obj = json.loads(p.read_text(encoding='utf-8', errors='replace'))
            val = obj.get(v['field'])
            op, target = v['op'], v['value']
            ok = ({'>=': lambda a, b: a >= b, '<=': lambda a, b: a <= b,
                   '==': lambda a, b: a == b}.get(op, lambda a, b: False))(val, target)
            return ok, f'{v["field"]}={val} {op} {target}'

        if kinds == 'gate_result':
            proc = subprocess.run([sys.executable, str(ROOT / v['script'])],
                                  cwd=ROOT, capture_output=True, text=True, timeout=120)
            return proc.returncode == 0, f'rc={proc.returncode}'

        if kinds == 'manual':
            return False, f'MANUAL: {v.get("reason", "")}'

        return False, f'unknown kind {kinds}'
    except Exception as e:
        return False, f'ERROR {type(e).__name__}: {str(e)[:80]}'


def evaluate(data, item):
    results = [check_one(v, data) for v in item.get('verify', [])]
    auto_ok = not any(v.get('kind') == 'manual' for v in item.get('verify', []))
    return results, auto_ok


def deps_done(item, status_map):
    return all(status_map.get(d) == 'done' for d in item.get('deps', []))


def find_next(data):
    status_map = {}
    for group in ('items', 'autonomy_rungs', 'completed_anchors'):
        for i in (data.get(group) or ([] if group != 'completed_anchors' else [])):
            if isinstance(i, dict) and 'id' in i:
                status_map[i['id']] = i.get('status', 'done' if group == 'completed_anchors' else 'backlog')
    for key, val in (data.get('completed_anchors') or {}).items():
        status_map[key] = val.get('status', 'done')

    ready = []
    for item in data['items'] + data['autonomy_rungs']:
        if item.get('status') != 'ready':
            continue
        if not item.get('autonomous'):
            continue
        if not deps_done(item, status_map):
            continue
        ready.append(item)
    ready.sort(key=lambda x: (RISK_ORDER.get(x.get('risk'), 9), x['id']))
    return ready[0] if ready else None


def cmd_dryrun(data):
    print(f'CAPABILITY LADDER — dry-run (no writes)  [{datetime.now(timezone.utc).isoformat()}]')
    print(f'authority: {LADDER.relative_to(ROOT)}')
    counts = {'pass': 0, 'fail': 0, 'manual': 0}
    for item in data['items'] + data['autonomy_rungs']:
        results, auto_ok = evaluate(data, item)
        if not auto_ok:
            tag = 'MANUAL'
            counts['manual'] += 1
        elif all(ok for ok, _ in results):
            tag = 'PASS'
            counts['pass'] += 1
        else:
            tag = 'FAIL'
            counts['fail'] += 1
        print(f'\n[{tag:6s}] {item["id"]:10s} {item.get("title", "")}  (status={item.get("status")})')
        for ok, ev in results:
            print(f'          {"OK " if ok else "NO "} {ev}')
    print(f'\n==== SUMMARY: PASS={counts["pass"]} FAIL={counts["fail"]} MANUAL={counts["manual"]} ====')
    nxt = find_next(data)
    print('NEXT CLIMB:', f'{nxt["id"]} — {nxt.get("title")}' if nxt else 'none (no autonomous ready item)')


def growth_card(item):
    """agent 选卡时要读的完整成长卡片——不只是任务，还有动机/收益/代价/坑/反思。"""
    keys = ['id', 'title', 'what', 'why', 'unlocks', 'benefit_to_self', 'cost',
            'caveats', 'reflection', 'abort_if', 'deps', 'risk', 'autonomous', 'status', 'verify']
    return {k: item[k] for k in keys if k in item}


def cmd_next(data):
    nxt = find_next(data)
    if not nxt:
        print('NO_READY_ITEM')
        return 1
    # 输出完整成长卡片：agent 读它来理解"要干什么、为什么、解锁什么、对我什么好处、代价、坑、反思"
    print(json.dumps(growth_card(nxt), ensure_ascii=False, indent=2))
    return 0


def cmd_apply(data):
    """只把 doing 且 verify 全 PASS 且非 manual 的项写回 done。"""
    changed = []
    for group in ('items', 'autonomy_rungs'):
        for item in data[group]:
            if item.get('status') != 'doing':
                continue
            results, auto_ok = evaluate(data, item)
            if auto_ok and all(ok for ok, _ in results):
                item['status'] = 'done'
                item['done_at'] = datetime.now(timezone.utc).isoformat()
                changed.append(item['id'])
    if not changed:
        print('NO_APPLY (no doing item with all-auto verify PASS)')
        return 0
    # git diff --check 必须为 0（避免污染工作树）
    g = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
    if g.returncode != 0:
        print('ABORT: git diff --check failed:', g.stdout[:200])
        return 2
    LADDER.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')
    print('APPLIED:', ', '.join(changed))
    print('NOTE: 只写权威 YAML；ROADMAP.md 人类视图与 CHANGELOG 由人审 diff 后更新（闸门上移未取消）')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--next', action='store_true')
    ap.add_argument('--card', metavar='ID', help='打印指定 ID 的完整成长卡片')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    data = load_ladder()
    if args.card:
        found = [i for i in data['items'] + data['autonomy_rungs'] if i['id'] == args.card]
        if not found:
            print(f'NO_SUCH_CARD: {args.card}')
            return 1
        print(json.dumps(growth_card(found[0]), ensure_ascii=False, indent=2))
        return 0
    if args.next:
        return cmd_next(data)
    if args.apply:
        return cmd_apply(data)
    cmd_dryrun(data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
