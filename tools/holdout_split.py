#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hold-out 切分器 —— S18「自改进正则化（RRSI 纪律）」的第一个真实前置工具。

============================ 为什么 hold-out 必须真隔离 ============================
路线图 S18 (ROADMAP_GRAPH.md:1168) 写得很直白：
  - 给 agentlab / projectlab 切 30% hold-out 任务，**永不用于选卡**；
  - 一次只改一个可归因机制；
  - 先测基线方差设噪声地板（±10% 内的「提升」不算提升）。

这不是形式主义。STRATEGY.md:82 明确记着教训：
  「不把演化集 gain 当作能力提升（54% 是过拟合）」。
RRSI (arXiv2609.24972) 的结论是：没有正则化的自改进会在 OOD 上跌破初始基线；
增益归因研究里那 54% 的「增益」大部分是过拟合、只有 14% 来自 test-time scaling。

如果我们用**同一批任务**既调机制又验收机制，那么「加了机制 → 门禁全绿 → 宣称完成」
是自欺闭环：agent 会把那 54% 的过拟合当成真实能力进步。隔离 hold-out 就是把
「选卡用的题目」和「验收用的题目」在物理上分开，让改进必须证伪而不是自证。
一旦 hold-out ID 泄漏进训练/选卡集，整个 KR2「经验改进」的证据链就作废，
所以本工具在**写文件之前**做严格的集合不相交校验，发现交集直接拒绝落盘。

另一个纪律是噪声地板：即使 hold-out 上看起来涨了，±10% 以内的波动也不算提升
（与 tools/roadmap_check.py 的 NOISE_FLOOR=0.10 对齐）。本工具只负责切分与隔离，
不负责算 gain —— 配对结算交给 tools/gen_holdout_pairs.py。

============================ 输入 ============================
1) 位置参数 INPUT：JSON / JSONL 任务定义文件，至少含一个任务 ID 字段
   （task_id / task / project / id / key / name，与 gen_holdout_pairs 一致）。
   支持 JSON 数组、JSONL 逐行、`{"tasks":[...]}` 包装、以及 `{task_id: spec}` 映射。
2) --tasks-from PATH：指向 bench 下现有的任务定义 **Python 源文件**
   （如 tools/agentlab.py 的 TASKS、tools/projectlab.py 的 PROJECTS）。
   用 AST 静态解析提取字典键，**不 import、不执行源码** —— projectlab.py 在模块
   顶层读取 p5_ref/SPEC.md（该文件当前不存在），直接 import 会炸，静态解析不会。
   该参数也接受 JSON / JSONL 文件。

============================ 输出 ============================
  <output-dir>/_holdout_tasks.json   保留集：头部 do_not_use_for_selection=true
  <output-dir>/_train_tasks.json     训练/选卡集
两者都是 JSON 对象：_meta（生成时间/seed/ratio/sha256/来源/用途警告）+ task_ids + tasks。
默认 output-dir = 本仓库 bench/；可用 --output-dir 覆盖。

============================ 退出码 ============================
  0 = 切分完成或 probe 自检通过
  1 = probe 自检失败 / 隔离校验失败
  2 = N/M：缺输入、输入非法、参数非法
  3 = 真实切分出现 ID 交集，拒绝写入（隔离铁律触发）

用法:
  python tools/holdout_split.py --tasks-from tools/projectlab.py
  python tools/holdout_split.py --tasks-from tools/agentlab.py --ratio 0.3 --seed 20261122
  python tools/holdout_split.py tasks.json --output-dir D:/Brain/workspace/bench
  python tools/holdout_split.py --tasks-from tools/projectlab.py --dry-run
  python tools/holdout_split.py --probe        # 合成数据自检，不写任何正式文件
"""
import argparse
import ast
import hashlib
import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = ROOT / 'bench'
HOLDOUT_NAME = '_holdout_tasks.json'
TRAIN_NAME = '_train_tasks.json'

DEFAULT_SEED = 20261122
DEFAULT_RATIO = 0.30

# 与 gen_holdout_pairs.py 的 TASK_ID_KEYS 保持一致，避免两个工具对同一个任务
# 识别出不同的 ID —— 那会让 hold-out 集和配对结算对不上号。
TASK_ID_KEYS = ('task_id', 'task', 'project', 'id', 'key', 'name')

# 在 Python 任务定义文件里优先找这些模块级字典。
CANDIDATE_SYMBOLS = ('TASKS', 'PROJECTS', 'TASK_DEFS', 'BENCH_TASKS', 'CASES')

TASK_ID_LIKE = re.compile(r'^[A-Za-z][A-Za-z0-9_\-]*\d+[A-Za-z0-9_\-]*$')

JSON_LIST_KEYS = ('tasks', 'items', 'records', 'data', 'results', 'cases')


class NotMeasurable(Exception):
    """N/M：输入缺失或非法，绝不产出切分结果。"""


class IsolationError(Exception):
    """隔离铁律被破坏：hold-out 与 train 有交集，必须拒绝落盘。"""


# ------------------------------------------------------------------ 输入读取
def _extract_task_id(record, where):
    """从一个 task 记录里取任务 ID；取不到就 N/M，不猜、不造。"""
    if isinstance(record, str):
        tid = record.strip()
    elif isinstance(record, dict):
        tid = None
        for k in TASK_ID_KEYS:
            if k in record:
                tid = record[k]
                break
    else:
        tid = None
    if tid is None or isinstance(tid, bool) or not isinstance(tid, (str, int)):
        raise NotMeasurable(f'{where}: 记录缺少合法任务 ID（需字段 {TASK_ID_KEYS}）: {record!r}')
    tid = str(tid).strip()
    if not tid:
        raise NotMeasurable(f'{where}: 任务 ID 为空')
    return tid


def _records_from_json_obj(obj, where):
    """把已解析的 JSON 对象规整成 (task_id, 原始记录) 列表。"""
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict):
        for k in JSON_LIST_KEYS:
            if isinstance(obj.get(k), list):
                items = obj[k]
                break
        else:
            # {"T1": {...}, "T2": {...}} 形式的 task_id -> spec 映射
            # 跳过下划线开头的元数据键，避免把 _meta 当成任务。
            items = []
            for k, v in obj.items():
                if k.startswith('_'):
                    continue
                if isinstance(v, dict):
                    row = dict(v)
                    row.setdefault('task_id', k)
                    items.append(row)
                else:
                    items.append({'task_id': k, 'spec': v})
    else:
        raise NotMeasurable(f'{where}: 顶层必须是 JSON 数组/对象或 JSONL')

    out = []
    for i, item in enumerate(items, 1):
        tid = _extract_task_id(item, f'{where}#{i}')
        raw = item if isinstance(item, dict) else {'task_id': tid}
        out.append({'task_id': tid, 'raw': raw})
    return out


def load_tasks_from_json(path):
    """读 JSON / JSONL 任务定义文件。JSON 解析失败时退化为逐行 JSONL。"""
    p = Path(path).expanduser()
    if not p.is_file():
        raise NotMeasurable(f'任务文件不存在: {p}')
    text = p.read_text(encoding='utf-8', errors='replace')
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise NotMeasurable(f'{p} 第 {i} 行不是合法 JSON: {e}')
        obj = rows
    return _records_from_json_obj(obj, str(p))


def _dict_keys_literal(node):
    """若 ast.Dict 的所有键都是字符串字面量，返回这些键；否则返回 None。"""
    if not isinstance(node, ast.Dict) or not node.keys:
        return None
    keys = []
    for k in node.keys:
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keys.append(k.value)
        else:
            return None  # 动态键（如 for 循环里拼出来的 key）不猜
    return keys


def load_task_ids_from_python(path):
    """用 AST 静态提取任务定义字典的键，不执行源码（避免模块顶层副作用/缺文件）。

    优先取 CANDIDATE_SYMBOLS 里的字典；找不到时回退到任意「字符串键 -> dict 值」
    的模块级字典，并在 warning 里说明是启发式识别。
    """
    p = Path(path).expanduser()
    if not p.is_file():
        raise NotMeasurable(f'任务定义文件不存在: {p}')
    try:
        tree = ast.parse(p.read_text(encoding='utf-8', errors='replace'), filename=str(p))
    except SyntaxError as e:
        raise NotMeasurable(f'{p} 不是合法 Python 源码: {e}')

    primary, fallback = [], []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        keys = _dict_keys_literal(value)
        if not keys:
            continue
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names:
            continue
        name = names[0]
        entry = (name, keys)
        if name in CANDIDATE_SYMBOLS:
            primary.append(entry)
        else:
            # 回退候选：值大多是 dict 的字符串键字典（任务定义通常长这样）
            dict_vals = sum(1 for v in value.values if isinstance(v, ast.Dict))
            if dict_vals and dict_vals >= len(value.values) * 0.5:
                fallback.append(entry)

    warnings = []
    chosen = primary or fallback
    if not chosen:
        raise NotMeasurable(
            f'{p}: 未找到任务定义字典（找 {CANDIDATE_SYMBOLS}）。'
            f'若为 JSON/JSONL 请直接用位置参数传入。')
    if not primary:
        warnings.append(f'{p.name}: 用启发式识别到字典 {[n for n, _ in chosen]}，请核对是否为任务集')

    records = []
    for symbol, keys in chosen:
        for tid in keys:
            # 只保留看起来像任务 ID 的键，挡掉误识别的普通配置字典
            if TASK_ID_LIKE.match(tid):
                records.append({
                    'task_id': tid,
                    'raw': {'task_id': tid, 'source_file': p.name, 'source_symbol': symbol},
                })
    if not records:
        raise NotMeasurable(f'{p}: 字典键里没有形如任务 ID 的条目（如 T1 / P4）')
    return records, warnings


def resolve_source(input_path, tasks_from):
    """统一解析输入来源，返回 (records, source_meta, warnings)。"""
    if input_path and tasks_from:
        raise NotMeasurable('INPUT 与 --tasks-from 只能二选一')
    if not input_path and not tasks_from:
        raise NotMeasurable('需给 INPUT（JSON/JSONL）或 --tasks-from（bench 任务定义文件）')

    src = Path(tasks_from or input_path).expanduser()
    warnings = []
    if src.suffix.lower() == '.py':
        records, warnings = load_task_ids_from_python(src)
        meta = {'kind': 'python', 'path': str(src)}
    else:
        records = load_tasks_from_json(src)
        meta = {'kind': 'json', 'path': str(src)}
    return records, meta, warnings


# ------------------------------------------------------------------ 切分与隔离
def make_split(task_ids, ratio, seed):
    """固定 seed 的可复现切分：先排序再 sample，避免源文件顺序影响结果。"""
    unique = sorted(set(task_ids))
    n = len(unique)
    if n < 2:
        raise NotMeasurable(f'至少需要 2 个任务才能切分，当前只有 {n} 个')
    n_holdout = max(1, min(n - 1, round(n * ratio)))
    rng = random.Random(seed)
    holdout = set(rng.sample(unique, n_holdout))
    train = set(unique) - holdout
    return holdout, train


def assert_isolated(holdout_ids, train_ids, universe=None):
    """隔离铁律：写文件前必须调用。发现任何交集/重复/遗漏就拒绝。

    probe 会故意传入重叠集合调用本函数，验证它真的会拒绝 —— 不是摆设。
    """
    h, t = set(holdout_ids), set(train_ids)
    overlap = h & t
    if overlap:
        raise IsolationError(f'hold-out 与 train 出现交集，拒绝写入: {sorted(overlap)}')
    if len(h) != len(holdout_ids) or len(t) != len(train_ids):
        raise IsolationError('输入含重复任务 ID，无法保证隔离')
    if universe is not None:
        u = set(universe)
        if h | t != u:
            raise IsolationError('切分未覆盖全部任务（有遗漏或额外 ID）')
        if len(u) != len(universe):
            raise IsolationError('任务全集含重复 ID')


# ------------------------------------------------------------------ 输出
def _sha256_of_tasks(tasks):
    """对 tasks 数组做稳定序列化后取 SHA-256，便于审计「这批任务有没有被调包」。"""
    canonical = json.dumps(tasks, sort_keys=True, ensure_ascii=False,
                           separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest()


def build_payload(split_name, records, id_set, meta, ratio, seed):
    """组装输出对象；holdout 头部带 do_not_use_for_selection=true。"""
    selected = [r for r in records if r['task_id'] in id_set]
    selected.sort(key=lambda r: r['task_id'])
    task_ids = [r['task_id'] for r in selected]
    tasks = [r['raw'] for r in selected]
    is_holdout = split_name == 'holdout'
    meta_block = {
        'schema_version': 1,
        'split': split_name,
        'do_not_use_for_selection': is_holdout,
        'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'seed': seed,
        'ratio': ratio,
        'task_count': len(task_ids),
        'source': meta,
        'sha256': _sha256_of_tasks(tasks),
        'sha256_scope': 'sha256(json.dumps(tasks, sort_keys=True, ensure_ascii=False, separators=(",",":")))',
    }
    if is_holdout:
        meta_block['warning'] = (
            'RRSI 纪律：本文件是永不用于选卡的 hold-out 集。任何机制选择/调参读取它即视为泄漏，'
            'KR2 证据作废（参见 STRATEGY.md:82「54% 是过拟合」）。'
            '噪声地板 ±10% 内的提升不算提升。')
    else:
        meta_block['warning'] = (
            '训练/选卡集。只允许用本文件里的任务做机制选择；验收必须另用 hold-out 集。')
    return {
        '_meta': meta_block,
        'do_not_use_for_selection': is_holdout,
        'task_ids': task_ids,
        'tasks': tasks,
    }


def write_json(path, payload):
    """原子写入：先写 .tmp 再 os.replace，避免半截文件被当成已完成切分。"""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, p)


# ------------------------------------------------------------------ probe
def probe():
    """合成数据自检：切分比例/可复现性/隔离校验负例。绝不写正式文件。"""
    print('[PROBE] 合成数据自检（SYNTHETIC，不写任何正式文件）')
    synthetic = [f'T{i}' for i in range(1, 21)]
    ratio, seed = 0.30, DEFAULT_SEED
    h1, t1 = make_split(synthetic, ratio, seed)
    assert_isolated(h1, t1, synthetic)

    ok = True
    checks = []
    checks.append(('任务总数守恒', len(h1) + len(t1) == len(synthetic)))
    checks.append(('hold-out 比例=30%', len(h1) == 6, f'{len(h1)}/20'))
    checks.append(('无交集', not (h1 & t1)))

    h2, t2 = make_split(synthetic, ratio, seed)
    checks.append(('同 seed 可复现', h1 == h2 and t1 == t2))
    h3, _ = make_split(synthetic, ratio, seed + 1)
    checks.append(('换 seed 会变化', h1 != h3))

    # 负例：故意构造重叠集合，隔离校验必须拒绝
    rejected = False
    try:
        assert_isolated({'T1', 'T2'}, {'T2', 'T3'}, synthetic)
    except IsolationError as e:
        rejected = True
        overlap_msg = str(e)
    checks.append(('故意重叠被拒绝', rejected))
    # 负例 2：有遗漏也要拒绝
    rejected_missing = False
    try:
        assert_isolated({'T1'}, {'T2'}, synthetic)
    except IsolationError:
        rejected_missing = True
    checks.append(('覆盖不全被拒绝', rejected_missing))

    for item in checks:
        name, passed = item[0], item[1]
        detail = item[2] if len(item) > 2 else ''
        print(f'  [{"PASS" if passed else "FAIL"}] {name} {detail}')
        if not passed:
            ok = False
    if rejected:
        print(f'  隔离拒绝证据: {overlap_msg}')

    # 确认 probe 没有生成正式文件
    for name in (HOLDOUT_NAME, TRAIN_NAME):
        if (DEFAULT_OUTPUT_DIR / name).exists():
            print(f'  [WARN] probe 未写文件，但输出目录已存在 {name}（非本次生成，不改动）')

    print('[PROBE] ' + ('全部通过' if ok else '存在失败项'))
    return 0 if ok else 1


# ------------------------------------------------------------------ CLI
def build_parser():
    p = argparse.ArgumentParser(
        description='按固定 seed 把任务切成 30% hold-out + 训练/选卡集，写入前强制隔离校验。')
    p.add_argument('input', nargs='?', help='JSON/JSONL 任务定义文件（含 task_id 字段）')
    p.add_argument('--tasks-from', help='bench 下现有任务定义文件（agentlab.py/projectlab.py）或 JSON/JSONL')
    p.add_argument('--ratio', type=float, default=DEFAULT_RATIO,
                   help=f'hold-out 比例，默认 {DEFAULT_RATIO}')
    p.add_argument('--seed', type=int, default=DEFAULT_SEED,
                   help=f'固定随机种子保证可复现，默认 {DEFAULT_SEED}')
    p.add_argument('--output-dir', default=str(DEFAULT_OUTPUT_DIR),
                   help=f'输出目录，默认 {DEFAULT_OUTPUT_DIR}')
    p.add_argument('--dry-run', action='store_true', help='只校验与打印切分结果，不写文件')
    p.add_argument('--probe', action='store_true', help='合成数据自检切分/隔离逻辑，不写正式文件')
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.probe:
        return probe()
    if not (0.0 < args.ratio < 1.0):
        print(f'[N/M] --ratio 必须在 (0,1) 内，收到 {args.ratio}', file=sys.stderr)
        return 2

    try:
        records, source_meta, warnings = resolve_source(args.input, args.tasks_from)
        ids = [r['task_id'] for r in records]
        holdout, train = make_split(ids, args.ratio, args.seed)
        # 隔离铁律：写文件前校验，绝不先写再检查
        assert_isolated(holdout, train, ids)
    except NotMeasurable as e:
        print(f'[N/M] {e}', file=sys.stderr)
        return 2
    except IsolationError as e:
        print(f'[隔离拒绝] {e}', file=sys.stderr)
        return 3

    for w in warnings:
        print(f'[WARN] {w}', file=sys.stderr)

    print(f'来源: {source_meta["path"]} ({source_meta["kind"]}) | 任务 {len(ids)} 个')
    print(f'hold-out ({len(holdout)}): {sorted(holdout)}')
    print(f'train    ({len(train)}): {sorted(train)}')
    print('隔离校验: hold-out ∩ train = ∅  [PASS]')

    if args.dry_run:
        print('[DRY-RUN] 未写文件')
        return 0

    out_dir = Path(args.output_dir).expanduser()
    hp = out_dir / HOLDOUT_NAME
    tp = out_dir / TRAIN_NAME
    write_json(hp, build_payload('holdout', records, holdout, source_meta, args.ratio, args.seed))
    write_json(tp, build_payload('train', records, train, source_meta, args.ratio, args.seed))
    print(f'已写: {hp}')
    print(f'已写: {tp}')
    print('提示: hold-out 头部 do_not_use_for_selection=true，禁止用于选卡；'
          '真实 gain 由 gen_holdout_pairs.py 在配对对照中结算，±10% 内不算提升。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
