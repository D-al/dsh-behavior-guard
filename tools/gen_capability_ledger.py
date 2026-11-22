#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KR3 自我模型：能力账本生成器（predicted 必须事前、actual 必须事后、且不同源）

严格对齐 tools/goal_verify.py::verify_kr3 的判据：
  证据文件 D:/Brain/workspace/bench/_capability_ledger.json
  {"capabilities":[{"name":...,"predicted":数,"actual":数,"known_unknowns":[...]}, ...]}
  ≥3 条含 predicted+actual 配对 且 ≥3 条含非空 known_unknowns → PASS。

防造假设计（铁律，改动前先读）：
  1. predicted 只能来自"事前预测"真实产物：bench 下 *_predict*.json /
     *_predict*.jsonl，或 audit_calibrate 预测产物（*_calibrat*.json/jsonl）。
     找不到 → N/M 退出（码 2），绝不从实测数据反推一个"预测"填进去——那是
     循环论证/假绿。实测数据不能既当 predicted 又当 actual。
  2. actual 只能来自"事后实测"真实产物：_projectlab_result.json /
     _benchmark_holdout.jsonl / _small_model_bench.json / _benchmark_results.jsonl。
  3. 同源拒绝（assert_independent）：predicted 与 actual 来自同一文件 → 拒绝；
     两边都带时间戳且 predicted 不早于 actual → 拒绝（不是事前预测）；
     一方声明 computed_from 指向另一方来源 → 拒绝（同一次计算）。
  4. known_unknowns 只从明确"未测/无数据"的条目生成：STRATEGY.md §2.1 中
     状态为 N/M 的 KR（状态列即"无数据"声明）。不编造"未知"清单充数。
  5. --probe 自测：内存临时数据（mode:"probe"）跑通配对/同源校验/账本校验全链路，
     只打印不写正式文件；同时自检"同源拒绝"确实生效。
  6. 任一真实来源缺失或配对不足 3 条 → N/M，不写账本、不用占位数字凑数。

用法:
  python tools/gen_capability_ledger.py                       # 真实来源生成账本
  python tools/gen_capability_ledger.py --probe               # 自测：仅打印，不写文件
  python tools/gen_capability_ledger.py --predict-file X.json --actual-file Y.json
退出码: 0=已写出账本/probe 成功; 1=同源或格式错误; 2=N/M(缺真实来源，未写文件)
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = Path('D:/Brain/workspace/bench')
OUT = BENCH / '_capability_ledger.json'
STRATEGY = ROOT / 'STRATEGY.md'

# 事前预测来源模式（真实存在才可用，否则 N/M）
PREDICT_PATTERNS = ('*_predict*.json', '*_predict*.jsonl',
                    '*_calibrat*.json', '*_calibrat*.jsonl')
# 事后实测来源（按优先级使用；必须存在且含真实数值）
ACTUAL_FILES = ('_projectlab_result.json', '_benchmark_holdout.jsonl',
                '_small_model_bench.json', '_benchmark_results.jsonl')

EXIT_OK, EXIT_ERR, EXIT_NM = 0, 1, 2


def nm(why, prerequisite):
    print(f'NOT_MEASURABLE: {why}', file=sys.stderr)
    print(f'  前置依赖: {prerequisite}', file=sys.stderr)
    return EXIT_NM


def iter_jsonl(path):
    with path.open(encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


# ---------- 事前预测：只读真实文件，绝不从实测反推 ----------

def discover_predict_files(explicit=None):
    if explicit is not None:
        return [explicit] if explicit.exists() else []
    found = []
    for pattern in PREDICT_PATTERNS:
        found.extend(p for p in BENCH.glob(pattern) if p.is_file())
    # 去重并保持稳定顺序
    return sorted(set(found), key=lambda p: str(p))


def _pred_record(row, path):
    if not isinstance(row, dict):
        return None
    name = row.get('name') or row.get('capability') or row.get('cap')
    pred = row.get('predicted')
    if isinstance(pred, dict):          # 容忍 {"predicted":{"value":0.8}} 包装
        pred = pred.get('value')
    if not name or not isinstance(pred, (int, float)):
        return None
    return {
        'name': str(name),
        'predicted': float(pred),
        'source': str(path),
        'ts': row.get('ts') or row.get('timestamp'),
        'computed_from': row.get('computed_from'),
    }


def parse_predicted(path):
    """解析一份事前预测产物；只认显式 predicted 数值字段。"""
    rows = []
    if path.suffix == '.json':
        data = json.loads(path.read_text(encoding='utf-8'))
        candidates = []
        if isinstance(data, dict):
            for key in ('capabilities', 'predictions', 'items', 'records'):
                if isinstance(data.get(key), list):
                    candidates.extend(data[key])
            if not candidates:
                # {"RECON": 0.8, "PLAN": 0.7} 形式（name → 预测值）
                candidates = [{'name': k, 'predicted': v}
                              for k, v in data.items() if isinstance(v, (int, float))]
        elif isinstance(data, list):
            candidates = data
        for row in candidates:
            rec = _pred_record(row, path)
            if rec:
                rows.append(rec)
    else:  # .jsonl
        for row in iter_jsonl(path):
            rec = _pred_record(row, path)
            if rec:
                rows.append(rec)
    return rows


# ---------- 事后实测：只读真实 benchmark / projectlab 产物 ----------

def _mean(values):
    return sum(values) / len(values)


def parse_actual_file(path):
    rows = []
    if path.suffix == '.json':
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, list):
            # _projectlab_result.json：按 phase 的 OK 比例作实测值
            phases = {}
            overall = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                if item.get('ok') is True:
                    overall.append(1.0)
                elif item.get('ok') is False:
                    overall.append(0.0)
                profile = item.get('profile')
                if isinstance(profile, dict):
                    for phase, status in profile.items():
                        if status == 'OK':
                            v = 1.0
                        elif status in ('WEAK', 'FAIL', 'BAD'):
                            v = 0.0
                        else:
                            continue          # 未知状态不臆测数值
                        phases.setdefault(phase, []).append(v)
            for phase, vals in phases.items():
                rows.append({'name': f'projectlab:{phase}', 'actual': _mean(vals),
                             'source': str(path)})
            if overall:
                rows.append({'name': 'projectlab:overall', 'actual': _mean(overall),
                             'source': str(path)})
        elif isinstance(data, dict):
            tasks = data.get('tasks')
            if isinstance(tasks, dict):
                for task, detail in tasks.items():
                    if not isinstance(detail, dict):
                        continue
                    jv = detail.get('json_valid')       # 形如 "5/5"
                    if isinstance(jv, str) and '/' in jv:
                        try:
                            num, den = jv.split('/', 1)
                            val = float(num) / float(den)
                        except (ValueError, ZeroDivisionError):
                            continue
                        rows.append({'name': f'small_model:{task}:json_valid',
                                     'actual': val, 'source': str(path)})
            for key in ('actuals', 'results', 'scores'):
                block = data.get(key)
                if isinstance(block, list):
                    for item in block:
                        if not isinstance(item, dict):
                            continue
                        val = item.get('actual', item.get('score'))
                        name = item.get('name') or item.get('capability') or item.get('task')
                        if name and isinstance(val, (int, float)):
                            rows.append({'name': str(name), 'actual': float(val),
                                         'source': str(path), 'ts': item.get('ts')})
    else:  # .jsonl —— holdout 配对结果 / benchmark 绝对分
        for item in iter_jsonl(path):
            if not isinstance(item, dict):
                continue
            name = item.get('capability') or item.get('task') or item.get('name')
            val = item.get('gain', item.get('score', item.get('actual')))
            if name and isinstance(val, (int, float)):
                rows.append({'name': str(name), 'actual': float(val),
                             'source': str(path), 'ts': item.get('ts')})
    return rows


def load_actual_records(explicit=None):
    paths = [explicit] if explicit is not None else [
        BENCH / name for name in ACTUAL_FILES if (BENCH / name).exists()]
    rows = []
    for p in paths:
        if not p.exists():
            continue
        try:
            rows.extend(parse_actual_file(p))
        except (OSError, json.JSONDecodeError) as e:
            print(f'警告: 实测来源 {p} 解析失败: {e}', file=sys.stderr)
    return rows


# ---------- 同源 / 时序校验（防循环论证的核心） ----------

def _parse_ts(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def assert_independent(pred, actual):
    """predicted 与 actual 必须异源、且预测早于实测；否则拒绝。"""
    if pred.get('source') == actual.get('source'):
        raise ValueError('同源拒绝：predicted 与 actual 来自同一文件，构成循环论证')
    if pred.get('computed_from') and pred['computed_from'] == actual.get('source'):
        raise ValueError('同源拒绝：predicted 声明由 actual 来源计算得出')
    if actual.get('computed_from') and actual['computed_from'] == pred.get('source'):
        raise ValueError('同源拒绝：actual 声明由 predicted 来源计算得出')
    pts, ats = _parse_ts(pred.get('ts')), _parse_ts(actual.get('ts'))
    if pts is not None and ats is not None and pts >= ats:
        raise ValueError('时序拒绝：predicted 不早于 actual，不是事前预测')


def _norm(name):
    return str(name).strip().lower().replace('-', '_').replace(' ', '_')


def find_actual(pred, actuals):
    """按能力名匹配实测值：精确 → 带前缀 → 反向带前缀。"""
    key = _norm(pred['name'])
    for a in actuals:
        if _norm(a['name']) == key:
            return a
    for a in actuals:
        n = _norm(a['name'])
        if n.endswith(':' + key) or n.endswith('_' + key):
            return a
    for a in actuals:
        n = _norm(a['name'])
        if key.endswith(':' + n) or key.endswith('_' + n):
            return a
    return None


# ---------- known_unknowns：只从明确的"未测/无数据"声明生成 ----------

def load_known_unknowns(path=STRATEGY):
    """STRATEGY.md §2.1 状态列为 N/M 的 KR = 明确声明的未测/无数据能力项。"""
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s.startswith('|') or 'N/M' not in s:
            continue
        cells = [c.strip().replace('**', '') for c in s.strip('|').split('|')]
        if not cells or 'KR' not in cells[0]:
            continue
        items.append(f'{cells[0]}: STRATEGY §2.1 状态 N/M（未测/无数据）')
    return list(dict.fromkeys(items))


def build_items(preds, actuals, unknowns, mode=None):
    """只把通过同源/时序校验的配对写成能力条目。"""
    items = []
    for p in preds:
        a = find_actual(p, actuals)
        if a is None:
            continue
        assert_independent(p, a)            # 同源/时序不符则直接抛错，拒绝生成
        item = {
            'name': p['name'],
            'predicted': p['predicted'],
            'actual': a['actual'],
            'known_unknowns': list(unknowns),
            'predicted_source': p['source'],
            'actual_source': a['source'],
            'known_unknowns_source': str(STRATEGY) + ' §2.1',
        }
        if mode:
            item['mode'] = mode
        items.append(item)
    return items


def validate_ledger(ledger):
    """复刻 verify_kr3：≥3 配对 且 ≥3 条含 known_unknowns。"""
    items = ledger.get('capabilities', [])
    calibrated = [i for i in items
                  if i.get('predicted') is not None and i.get('actual') is not None]
    has_unknown = sum(1 for i in items if i.get('known_unknowns'))
    return len(calibrated) >= 3 and has_unknown >= 3, len(calibrated), has_unknown


def write_atomic(ledger, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + '.tmp')
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n',
                   encoding='utf-8')
    os.replace(str(tmp), str(out_path))


# ---------- probe：临时数据跑通全链路，绝不写正式文件 ----------

def run_probe():
    preds = [
        {'name': 'probe:RECON', 'predicted': 0.80, 'source': '<probe:predicted>',
         'ts': '2026-01-01T00:00:00Z'},
        {'name': 'probe:PLAN', 'predicted': 0.65, 'source': '<probe:predicted>',
         'ts': '2026-01-01T00:00:00Z'},
        {'name': 'probe:ATOMIC', 'predicted': 0.90, 'source': '<probe:predicted>',
         'ts': '2026-01-01T00:00:00Z'},
        {'name': 'probe:VERIFY', 'predicted': 0.75, 'source': '<probe:predicted>',
         'ts': '2026-01-01T00:00:00Z'},
    ]
    actuals = [
        {'name': 'probe:RECON', 'actual': 1.0, 'source': '<probe:actual>',
         'ts': '2026-01-02T00:00:00Z'},
        {'name': 'probe:PLAN', 'actual': 0.0, 'source': '<probe:actual>',
         'ts': '2026-01-02T00:00:00Z'},
        {'name': 'probe:ATOMIC', 'actual': 1.0, 'source': '<probe:actual>',
         'ts': '2026-01-02T00:00:00Z'},
        {'name': 'probe:VERIFY', 'actual': 1.0, 'source': '<probe:actual>',
         'ts': '2026-01-02T00:00:00Z'},
    ]
    # 同源拒绝自检：故意把 actual 的来源改成 predicted 的来源，必须抛错
    try:
        assert_independent(preds[0], {**actuals[0], 'source': preds[0]['source']})
    except ValueError:
        print('[probe] 同源拒绝自检: OK', file=sys.stderr)
    else:
        print('[probe] 同源拒绝自检: 失败（未拦截同源数据）', file=sys.stderr)
        return EXIT_ERR

    unknowns = load_known_unknowns()
    if not unknowns:
        unknowns = ['probe: STRATEGY.md §2.1 不可读，未能取得真实未测项']
        print('[probe] 警告: 未能从 STRATEGY.md 读取真实未测项', file=sys.stderr)

    items = build_items(preds, actuals, unknowns, mode='probe')
    ledger = {
        'mode': 'probe',
        'capabilities': items,
        'principle': 'mode=probe 为自测临时数据，不作 KR3 验收证据、不写正式文件',
    }
    ok, n_pair, n_unknown = validate_ledger(ledger)
    print(json.dumps(ledger, ensure_ascii=False, indent=2))
    print(f'[probe] {n_pair} 条配对 / {n_unknown} 条含 known_unknowns，'
          f'校验={"通过" if ok else "未通过"}；未写正式文件 {OUT}', file=sys.stderr)
    return EXIT_OK if ok else EXIT_ERR


def main():
    ap = argparse.ArgumentParser(
        description='KR3 能力账本生成器：predicted 事前、actual 事后、异源才生成，绝不造数')
    ap.add_argument('--probe', action='store_true',
                    help='自测模式：内存临时数据，带 mode:probe，仅打印不写文件')
    ap.add_argument('--predict-file', type=Path, default=None,
                    help='显式指定事前预测文件（默认在 bench 下发现 *_predict*.json 等）')
    ap.add_argument('--actual-file', type=Path, default=None,
                    help='显式指定事后实测文件（默认使用 projectlab/holdout/bench 产物）')
    ap.add_argument('--strategy', type=Path, default=STRATEGY,
                    help=f'未测项声明文档（默认 {STRATEGY}）')
    ap.add_argument('--out', type=Path, default=OUT,
                    help=f'正式输出路径（默认 {OUT}）')
    args = ap.parse_args()

    if args.probe:
        return run_probe()

    pred_files = discover_predict_files(args.predict_file)
    if not pred_files:
        return nm('未找到任何事前预测记录（*_predict*.json / *_predict*.jsonl / '
                  'audit_calibrate 产物）',
                  '由人类或独立脚本冻结 predicted 记录；不可用实测数据反推预测')
    preds = []
    for f in pred_files:
        try:
            preds.extend(parse_predicted(f))
        except (OSError, json.JSONDecodeError) as e:
            print(f'错误: 预测文件 {f} 解析失败: {e}', file=sys.stderr)
            return EXIT_ERR
    if not preds:
        return nm(f'预测文件 {[str(f) for f in pred_files]} 中无有效 predicted 数值',
                  '预测记录须含 name + predicted 数值字段')

    actuals = load_actual_records(args.actual_file)
    if not actuals:
        return nm('未找到任何事后实测产物（projectlab / holdout / benchmark）',
                  '生成 _projectlab_result.json / _benchmark_holdout.jsonl 等真实结果')

    unknowns = load_known_unknowns(args.strategy)
    if not unknowns:
        return nm(f'{args.strategy} §2.1 无 N/M 未测项，无法生成 known_unknowns',
                  '在 STRATEGY.md §2.1 明确标注未测/无数据能力项')

    try:
        items = build_items(preds, actuals, unknowns)
    except ValueError as e:
        print(f'拒绝生成: {e}', file=sys.stderr)
        return EXIT_ERR

    if len(items) < 3:
        return nm(f'预测-实测配对仅 {len(items)} 条 < 3（且须异名异源）',
                  '积累至少 3 项能力的异源预测-实测配对')

    ledger = {
        'capabilities': items,
        'principle': 'predicted 事前预测、actual 事后实测、二者异源；缺源则 N/M 不造数',
        'sources': {
            'predicted': sorted(set(i['predicted_source'] for i in items)),
            'actual': sorted(set(i['actual_source'] for i in items)),
            'known_unknowns': str(args.strategy) + ' §2.1',
        },
    }
    ok, n_pair, n_unknown = validate_ledger(ledger)
    if not ok:
        print(f'错误: 账本校验未通过（{n_pair} 配对 / {n_unknown} 未测项）', file=sys.stderr)
        return EXIT_ERR

    write_atomic(ledger, args.out)
    print(f'已写出 {len(items)} 条能力账本 → {args.out}')
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
