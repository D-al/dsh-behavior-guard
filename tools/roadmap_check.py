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
ROADMAP = ROOT / 'ROADMAP.md'                 # 人类可读视图（§1-§8 + 自动进度表），机器不写正文
GRAPH_FILE = ROOT / 'ROADMAP_GRAPH.md'        # 机器权威块唯一真相源（agent 读写状态）
LADDER = ROOT / 'CAPABILITY_LADDER.yaml'      # 语义镜像（what/why/caveats 等，非状态真相源）
BENCH = Path(os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench')
GRAPH_BEGIN = '<!-- ROADMAP_GRAPH_BEGIN v1 -->'
GRAPH_END = '<!-- ROADMAP_GRAPH_END -->'
HUMAN_BEGIN = '<!-- HUMAN_PROGRESS_BEGIN v1'
HUMAN_END = '<!-- HUMAN_PROGRESS_END -->'
CARDS_BEGIN = '<!-- HUMAN_CARDS_BEGIN v1'
CARDS_END = '<!-- HUMAN_CARDS_END -->'

RISK_ORDER = {'low': 0, 'med': 1, 'high': 2}


def load_ladder():
    """权威源 = ROADMAP_GRAPH.md 里的 HTML 注释块；CAPABILITY_LADDER.yaml 只提供语义字段。"""
    md = GRAPH_FILE.read_text(encoding='utf-8')
    m = re.search(re.escape(GRAPH_BEGIN) + r'(.*?)' + re.escape(GRAPH_END), md, re.S)
    if not m:
        raise RuntimeError(f'{GRAPH_FILE.name} 缺少权威块 {GRAPH_BEGIN} / {GRAPH_END}')
    graph = yaml.safe_load(m.group(1))
    if graph.get('schema_version') != 1:
        raise RuntimeError(f'权威块 schema_version 不是 1')
    # 合并语义字段（what/why/benefit_to_self/caveats/reflection）从 YAML 镜像
    mirror = yaml.safe_load(LADDER.read_text(encoding='utf-8')) if LADDER.exists() else {}
    sem = {i['id']: i for i in mirror.get('items', []) + mirror.get('autonomy_rungs', [])}
    for group in ('items', 'rungs'):
        for item in graph.get(group, []):
            src = sem.get(item['id'], {})
            for k in ('title', 'what', 'why', 'unlocks', 'benefit_to_self', 'cost', 'caveats',
                      'reflection', 'abort_if', 'preconditions', 'instrumentation_needed'):
                if k in src:
                    item[k] = src[k]
    return graph


def test_sids(data):
    """测试 sid 黑名单：唯一真相源 = test_sids.json（A0 交付物）。

    历史遗留三处副本（GRAPH 顶层/meta、LADDER meta）已归一；保留 fallback 是为了
    旧生产副本未同步时不至于把真实 sid 当测试过滤掉（fail-safe：宁可少过滤不多过滤）。
    2026-11-20 审计抓到的承重 bug：以前只读 meta，以 ROADMAP 为源时过滤集为空。
    """
    sid_file = ROOT / 'test_sids.json'
    if sid_file.exists():
        try:
            sids = json.loads(sid_file.read_text(encoding='utf-8')).get('sids')
            if isinstance(sids, list) and sids:
                return set(sids)
        except Exception:
            pass
    return set((data.get('meta') or {}).get('test_sids') or data.get('test_sids') or [])


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
            # 兼容两种 PASS 输出：裸 'PASS xxx'（test_*.mjs）与 '[PASS  ] ID ...'（本工具 dry-run）
            passes = len(re.findall(r'^(?:PASS|\[PASS\s*\])', proc.stdout, re.M))
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


def status_map_of(data):
    sm = {}
    for group in ('items', 'rungs', 'anchors'):
        for i in (data.get(group) or ([] if group != 'anchors' else [])):
            if isinstance(i, dict) and 'id' in i:
                sm[i['id']] = i.get('status', 'done' if group == 'anchors' else 'backlog')
    for key, val in (data.get('anchors') or {}).items():
        sm[key] = val.get('status', 'done')
    return sm


def tier_unlocked(item, sm, data):
    """SKILLGRAPH 渐进解锁：本 tier 平均成功率 >= 60% 才解锁下一 tier。
    tier 0/1 恒解锁；更高 tier 要求低一 tier 的 done 比例 >= 0.6。
    """
    tier = item.get('tier', 0)
    if tier <= 1:
        return True
    prev = [i for i in data['items'] if i.get('tier') == tier - 1]
    if not prev:
        return True
    done_n = sum(1 for i in prev if sm.get(i['id']) == 'done')
    return done_n / len(prev) >= 0.6


def waiting_not_blocked(item, sm, data):
    """CASCADE: Waiting ≠ Blocked。
    真 blocked = 依赖未完成 且 tier 未解锁；waiting = 前置在途（deps doing），不算阻塞。
    这里只让 'ready 且 deps 全 done' 的项进入候选；其余不返回（由 cmd_next 报告级配）。
    """
    return deps_done(item, sm) and all(
        sm.get(d) != 'doing' for d in item.get('deps', []))  # doing=在途≠blocked，但暂不领取


def find_next(data):
    """选择算法 = SKILLGRAPH 渐进解锁 + MR learnability 门控 + risk 排序。
    ready 集：status=ready ∧ autonomous ∧ deps 全 done ∧ tier 已解锁。
    排序：(risk 低) → (tier 低) → (id)，避免过早碰复杂项。
    """
    sm = status_map_of(data)
    ready = []
    for item in data['items'] + data['rungs']:
        if item.get('status') != 'ready' or not item.get('autonomous'):
            continue
        if not deps_done(item, sm) or not tier_unlocked(item, sm, data):
            continue
        ready.append(item)
    # 2026-11-20 重排：在 risk/tier 两个硬约束之后、id 之前插入 ROI 平局打破键。
    # 旧算法 (risk, tier, id) 按字母序派活，导致性价比最高的 S14 永远排在 A1_7 之后——
    # ROADMAP 展示按 ROI 排、实际推卡按 id 排，两套机制脱节。现在同 risk+tier 内按 ROI 选。
    # risk/tier 优先级不变（低风险、低 tier 仍是硬约束），只打破同层平局。
    ready.sort(key=lambda x: (RISK_ORDER.get(x.get('risk'), 9), x.get('tier', 0),
                              -roi_score(x), x['id']))
    return ready[0] if ready else None


def cmd_dryrun(data):
    print(f'CAPABILITY LADDER — dry-run (no writes)  [{datetime.now(timezone.utc).isoformat()}]')
    print(f'authority: {GRAPH_FILE.name}（语义镜像: {LADDER.name}；人读视图: {ROADMAP.name}）')
    counts = {'pass': 0, 'fail': 0, 'manual': 0}
    for item in data['items'] + data['rungs']:
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


def fmt_field(v):
    """把语义字段（str 或 list）渲染成一行人读文本。

    全局事故教训（每张卡 caveats 都带）抽成块顶部脚注，避免人读层重复 20 次噪声。
    """
    if isinstance(v, list):
        v = [x for x in v if not str(x).startswith('[事故教训]')]
        return '；'.join(str(x) for x in v) if v else '—'
    return str(v) if v else '—'


def fmt_list(v):
    """把 list 渲染成中文顿号串（空则 —）。"""
    if isinstance(v, list):
        return '、'.join(str(x) for x in v) if v else '—'
    return str(v) if v else '—'



# 中文评级 → 数值（线性，收益÷成本；35B 建议的立方放大因自相矛盾不采纳，见 docs/ROI_SORT_DECISION）
BENEFIT_NUM = {'极高': 5, '高': 4, '中高': 3, '中': 2, '中低': 1.5, '低': 1}
COST_NUM = {'低': 1, '中低': 2, '中': 3, '中高': 4, '高': 5, '极高': 6}
HINT_ORDER = {'normal': 0, 'blocked': 1, 'explore': 2, 'last': 3}


def _level_num(s, table):
    s = str(s or '')
    for k in sorted(table, key=len, reverse=True):
        if k in s:
            return table[k]
    return 2


def roi_score(c):
    """线性性价比 = 收益 ÷ 成本（可解释：每单位成本换多少收益）。"""
    b = _level_num(c.get('benefit'), BENEFIT_NUM)
    cost = _level_num(c.get('cost'), COST_NUM)
    return round(b / cost, 3)


def sort_cards_by_roi(allc, sm, sem):
    """Kahn 拓扑（依赖先行）+ 层内性价比降序 + rank_hint 结构约束分桶。

    结构约束来自卡片显式字段 rank_hint（normal/blocked/explore/last），不硬编码卡 id、
    不扫中文文本——避免"守卫正则扫内容误判"类坑。35B 与我的方案在 Kahn 算法上独立一致。
    """
    active = [c for c in allc if sm.get(c['id']) != 'done']
    byid = {c['id']: c for c in active}
    ids = set(byid)
    deps = {cid: [d for d in (sem.get(cid, {}).get('deps') or c.get('deps') or []) if d in ids]
            for cid, c in byid.items()}
    indeg = {cid: len(ds) for cid, ds in deps.items()}
    children = {}
    for cid, ds in deps.items():
        for d in ds:
            children.setdefault(d, []).append(cid)

    def key(cid):
        hint = sem.get(cid, {}).get('rank_hint', 'normal')
        return (HINT_ORDER.get(hint, 0), -roi_score(sem.get(cid, byid[cid])), cid)

    # 分桶：先按 rank_hint 分组，组内做拓扑（结构约束优先于性价比）
    result = []
    for hint in ('normal', 'blocked', 'explore', 'last'):
        bucket = [cid for cid in byid if sem.get(cid, {}).get('rank_hint', 'normal') == hint]
        bset = set(bucket)
        bindeg = {cid: sum(1 for d in deps[cid] if d in bset) for cid in bucket}
        bchildren = {}
        for cid in bucket:
            for d in deps[cid]:
                if d in bset:
                    bchildren.setdefault(d, []).append(cid)
        ready = sorted([cid for cid in bucket if bindeg[cid] == 0], key=key)
        while ready:
            cid = ready.pop(0)
            result.append(byid[cid])
            for ch in bchildren.get(cid, []):
                bindeg[ch] -= 1
                if bindeg[ch] == 0:
                    ready.append(ch); ready.sort(key=key)
    return result


def render_human_cards(data, mirror):
    """从 LADDER 语义源渲染非 done 卡的人读详情（what/why/benefit/坑/反思/何时停）。

    状态取机器源 data，语义取 mirror——两源各司其职，块内零手工副本。
    按性价比自动排序（Kahn 拓扑 + 结构约束分桶），高性价比在前、探索/last 在后。
    """
    sm = status_map_of(data)
    sem = {i['id']: i for i in mirror.get('items', []) + mirror.get('autonomy_rungs', [])}
    allc = list(data['rungs']) + list(data['items'])
    ordered = sort_cards_by_roi(allc, sm, sem)
    out = [f'{CARDS_BEGIN}：由 roadmap_check.py --apply 从 LADDER 语义源生成，勿手改 -->',
           '> ### 📇 卡片详情（按性价比自动排序 · 高在前）',
           '> 排序 = 收益÷成本（线性性价比）+ 依赖拓扑（依赖必在前）+ 结构约束桶（normal→blocked→explore→last）。',
           '> 全部字段来自卡片单一真相源（CAPABILITY_LADDER.yaml），状态来自 ROADMAP_GRAPH.md；本块自动重写，勿手改。',
           '> 机器判据见 `--card <ID>`；每行 `分` = 性价比分数，`桶` = rank_hint（见卡片字段）。',
           '> ⚠️ 全局铁律（所有卡通用，故不再逐条重复）：说"完成/推送/全绿"前必须核对远端/权威/运行版三处 commit+sha256；health 200 ≠ 进程活着。',
           '']
    total = 0
    for c in ordered:
            s = sem.get(c['id'], {})
            st = sm.get(c['id'], '?')
            hint = s.get('rank_hint', 'normal')
            out.append(f"**`{c['id']}` {c.get('title', s.get('title', ''))}** · 分 `{roi_score(s)}` · "
                       f"状态 `{st}` · 桶 `{hint}`")
            # 速查字段也进卡片详情——两者同源、互不脱节
            out.append(f"- **性价比**：收益 {fmt_list(s.get('benefit'))} / 成本 {fmt_list(s.get('cost'))} "
                       f"/ 建议 {fmt_list(s.get('advice'))}")
            out.append(f"- **依赖→解锁**：{fmt_list(s.get('deps') or c.get('deps'))} → "
                       f"{fmt_list(s.get('unlocks') or s.get('unlock'))}")
            out.append(f"- **做什么**：{fmt_field(s.get('what') or c.get('what'))}")
            out.append(f"- **为什么**：{fmt_field(s.get('why') or c.get('why'))}")
            out.append(f"- **对 agent 的好处**：{fmt_field(s.get('benefit_to_self') or c.get('benefit_to_self'))}")
            out.append(f"- **坑/边界**：{fmt_field(s.get('caveats') or c.get('caveats'))}")
            if s.get('reflection') or c.get('reflection'):
                out.append(f"- **做完要反思**：{fmt_field(s.get('reflection') or c.get('reflection'))}")
            out.append(f"- **何时停**：{fmt_field(s.get('abort_if') or c.get('abort_if'))}")
            out.append('')
            total += 1
    out.append(CARDS_END)
    return '\n'.join(out), total


def save_authoritative(data):
    """写回机器权威块（ROADMAP_GRAPH.md）+ 人类进度表（ROADMAP.md）+ 语义镜像；apply/claim 共用。

    三处写操作物理隔离：agent 的 --apply 只碰机器文件与 HUMAN 块，不会误伤 §1-§8 叙述。
    """
    gm = GRAPH_FILE.read_text(encoding='utf-8')
    inner = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    # 用 lambda 返回替换文本：直接传字符串会让 re.sub 把内文里的 \B 等当转义序列（实测 bug）
    new_gm = re.sub(re.escape(GRAPH_BEGIN) + r'.*?' + re.escape(GRAPH_END),
                    lambda _m: GRAPH_BEGIN + '\n' + inner + GRAPH_END, gm, flags=re.S)
    GRAPH_FILE.write_text(new_gm, encoding='utf-8')
    # 同步人类可读进度表（设计稿承诺：机器块与人类视图不再漂移）
    md = ROADMAP.read_text(encoding='utf-8')
    new_md = md
    sm = status_map_of(data)
    # 人工视图必须同时列自主化阶(A)与心智器官(M/L)——只看 rungs 会漏掉 M1 这类已完成卡
    all_cards = list(data['rungs']) + list(data['items'])
    done = [i for i in all_cards if sm.get(i['id']) == 'done']
    nxt = find_next(data)
    rows = '\n'.join(
        f'> | **{i["id"]} {i.get("title", "")}** | ✅ done | 证据见 `evidence_log` + `docs/reflection-{i["id"]}.md` |'
        for i in done
    ) or '> | （尚无已完成卡片） | — | — |'
    next_line = (f'> | **下一项** | ⏸ 空 | `--next` 无 autonomous ready 项，剩余需人工开闸 |'
                 if not nxt else
                 f'> | **下一项** | 🟢 {nxt["id"]} | `{nxt["id"]}` 已 ready，可 `--claim` |')
    human = (f'{HUMAN_BEGIN}：由 roadmap_check.py --apply 自动生成，勿手改 -->\n'
             f'> ### 🟢 自主化进度（自动同步）\n>\n'
             f'> | 卡片 | 状态 | 完成证据 |\n> |---|---|---|\n{rows}\n{next_line}\n>\n'
             f'> 机器真相 = [ROADMAP_GRAPH.md](ROADMAP_GRAPH.md)；本表由 `--apply` 自动写，人读与机器不漂移。\n'
             f'{HUMAN_END}')
    if HUMAN_BEGIN in new_md and HUMAN_END in new_md:
        pat = re.escape(HUMAN_BEGIN) + r'[^\n]*-->' + r'.*?' + re.escape(HUMAN_END)
        new_md = re.sub(pat, lambda _m: human, new_md, flags=re.S)
    # 人读视图全部从卡片单一源渲染：卡片详情按性价比排序（零手工副本、无独立速查表）
    mirror_pre = yaml.safe_load(LADDER.read_text(encoding='utf-8')) if LADDER.exists() else {}
    cards_md, n_cards = render_human_cards(data, mirror_pre)
    if CARDS_BEGIN in new_md and CARDS_END in new_md:
        pat = re.escape(CARDS_BEGIN) + r'[^\n]*-->' + r'.*?' + re.escape(CARDS_END)
        new_md = re.sub(pat, lambda _m: cards_md, new_md, flags=re.S)
    ROADMAP.write_text(new_md, encoding='utf-8')
    mirror = yaml.safe_load(LADDER.read_text(encoding='utf-8')) if LADDER.exists() else {}
    sm = status_map_of(data)
    for group, key in (('items', 'items'), ('rungs', 'autonomy_rungs')):
        dst = {i['id']: i for i in mirror.get(key, [])}
        for item in data[group]:
            if item['id'] in dst:
                dst[item['id']]['status'] = sm[item['id']]
                for k in ('evidence_log', 'attempts', 'claimer', 'claimed_at'):
                    if k in item: dst[item['id']][k] = item[k]
    if mirror:
        LADDER.write_text(yaml.safe_dump(mirror, allow_unicode=True, sort_keys=False), encoding='utf-8')


def cmd_claim(data, item_id):
    """修正4: CAS 原子领取 ready→doing（防双领），记录 claimer/claimed_at。"""
    found = [i for i in data['items'] + data['rungs'] if i['id'] == item_id]
    if not found:
        print(f'NO_SUCH_CARD: {item_id}'); return 1
    it = found[0]
    if it.get('status') != 'ready':
        print(f'CLAIM_REFUSED: {item_id} status={it.get("status")} != ready'); return 1
    if not it.get('autonomous'):
        print(f'CLAIM_REFUSED: {item_id} not autonomous（需人工）'); return 1
    sm = status_map_of(data)
    if not deps_done(it, sm) or not tier_unlocked(it, sm, data):
        print(f'CLAIM_REFUSED: {item_id} deps/tier 未满足'); return 1
    # 检查 attempts（fail_policy: >=3 → manual-blocked）
    if it.get('attempts', 0) >= 3:
        it['status'] = 'manual-blocked'; save_authoritative(data)
        print(f'MOVED_TO_MANUAL_BLOCKED: {item_id} attempts>=3'); return 1
    it['status'] = 'doing'
    it['claimed_at'] = datetime.now(timezone.utc).isoformat()
    it['claimer'] = os.environ.get('AGENT_ID', 'unknown-agent')
    save_authoritative(data)
    print(f'CLAIMED: {item_id} by {it["claimer"]}')
    return 0


def cmd_apply(data):
    """只把 doing 且 verify 全 PASS 且非 manual 的项写回 done。"""
    changed = []
    for group in ('items', 'rungs'):
        for item in data[group]:
            if item.get('status') != 'doing':
                continue
            results, auto_ok = evaluate(data, item)
            if auto_ok and all(ok for ok, _ in results):
                item['status'] = 'done'
                item['done_at'] = datetime.now(timezone.utc).isoformat()
                # 修正3: evidence_log —— done 必须携带 commit+命令+退出码，否则视为假完成
                commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT,
                                        capture_output=True, text=True).stdout.strip()
                item.setdefault('evidence_log', []).append({
                    'at': item['done_at'], 'commit': commit,
                    'checks': [ev for _, ev in results],
                })
                changed.append(item['id'])
    if not changed:
        print('NO_APPLY (no doing item with all-auto verify PASS)')
        return 0
    g = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
    if g.returncode != 0:
        print('ABORT: git diff --check failed:', g.stdout[:200])
        return 2
    save_authoritative(data)
    print('APPLIED:', ', '.join(changed))
    print(f'WROTE: {GRAPH_FILE.name} 权威块 + {ROADMAP.name} 人类进度表 + {LADDER.name} 镜像同步')
    return 0


def cmd_graph(data):
    """修正5: DAG 无环校验 + 拓扑序（SKILLGRAPH 前置图的健康证明）。"""
    sm = status_map_of(data)
    nodes = list(sm)
    indeg = {n: 0 for n in nodes}
    adj = {n: [] for n in nodes}
    for item in data['items'] + data['rungs']:
        for dep in item.get('deps', []):
            if dep in adj:
                adj[dep].append(item['id']); indeg[item['id']] += 1
    queue = [n for n in nodes if indeg[n] == 0]; order = []
    while queue:
        n = queue.pop(0); order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0: queue.append(m)
    cyclic = [n for n in nodes if n not in order]
    print(f'nodes={len(nodes)} edges={sum(len(v) for v in adj.values())}')
    print('cyclic:', cyclic or 'NONE ✓')
    print('topo:', ' → '.join(order))
    return 0 if not cyclic else 1


def cmd_verify(data, item_id):
    """修正5: 单条卡片判据验证（dry-run 单卡）。"""
    found = [i for i in data['items'] + data['rungs'] if i['id'] == item_id]
    if not found:
        print(f'NO_SUCH_CARD: {item_id}'); return 1
    results, auto_ok = evaluate(data, found[0])
    sm = status_map_of(data)
    print(f'[{found[0]["id"]}] status={sm[found[0]["id"]]} auto_verifiable={auto_ok}')
    for ok, ev in results:
        print(f'  {"OK " if ok else "NO "} {ev}')
    return 0 if (auto_ok and all(ok for ok, _ in results)) else 1


def cmd_status(data, item_id):
    """修正5: 单条状态详情（含依赖是否满足、tier 是否解锁）。"""
    found = [i for i in data['items'] + data['rungs'] if i['id'] == item_id]
    if not found:
        print(f'NO_SUCH_CARD: {item_id}'); return 1
    it = found[0]; sm = status_map_of(data)
    print(json.dumps({'id': it['id'], 'status': sm[it['id']],
                      'deps': {d: sm.get(d) for d in it.get('deps', [])},
                      'tier_unlocked': tier_unlocked(it, sm, data),
                      'tier': it.get('tier'), 'attempts': it.get('attempts', 0),
                      'evidence_log': it.get('evidence_log', [])}, ensure_ascii=False, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--next', action='store_true')
    ap.add_argument('--card', metavar='ID', help='打印指定 ID 的完整成长卡片')
    ap.add_argument('--graph', action='store_true', help='DAG 无环校验 + 拓扑序')
    ap.add_argument('--claim', metavar='ID', help='原子领取 ready→doing（防双领）')
    ap.add_argument('--verify', metavar='ID', help='验证单条卡片判据')
    ap.add_argument('--status', metavar='ID', help='单条状态详情')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--refresh', action='store_true', help='从卡片字段重渲染 ROADMAP.md 全部自动块（不改卡片状态）')
    args = ap.parse_args()
    data = load_ladder()
    if args.graph:
        return cmd_graph(data)
    if args.claim:
        return cmd_claim(data, args.claim)
    if args.verify:
        return cmd_verify(data, args.verify)
    if args.status:
        return cmd_status(data, args.status)
    if args.card:
        found = [i for i in data['items'] + data['rungs'] if i['id'] == args.card]
        if not found:
            print(f'NO_SUCH_CARD: {args.card}')
            return 1
        print(json.dumps(growth_card(found[0]), ensure_ascii=False, indent=2))
        return 0
    if args.next:
        return cmd_next(data)
    if args.apply:
        return cmd_apply(data)
    if args.refresh:
        # 只重渲染 ROADMAP.md 的三个自动块，不改 GRAPH/LADDER（纯视图刷新）
        md = ROADMAP.read_text(encoding='utf-8')
        mirror = yaml.safe_load(LADDER.read_text(encoding='utf-8')) if LADDER.exists() else {}
        cards, n = render_human_cards(data, mirror)
        for begin, end, body in ((CARDS_BEGIN, CARDS_END, cards),):
            if begin in md and end in md:
                pat = re.escape(begin) + r'[^\n]*-->' + r'.*?' + re.escape(end)
                md = re.sub(pat, lambda _m, b=body: b, md, flags=re.S)
        ROADMAP.write_text(md, encoding='utf-8')
        print(f'REFRESHED: 卡片详情按性价比排序（{n} 张卡）；卡片状态未改动')
        return 0
    cmd_dryrun(data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
