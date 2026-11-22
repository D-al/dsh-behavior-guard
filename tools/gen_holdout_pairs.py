#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hold-out 配对对照结算器 —— KR2「经验改进」的证据生成器。

把两组**真实运行结果**（baseline 组 + improved 组，不同时点/不同版本）逐任务配对，
结算成 gain / 95%CI / OOD 子集结果，按 goal_verify.py 严格要求的 schema 写出
    D:/Brain/workspace/bench/_benchmark_holdout.jsonl
每行一条：{"type":"paired_run","gain":<相对提升比例>,"ood_gain":<OOD相对提升比例>}

============================ 防造假设计（铁律） ============================
1) 绝不编造 gain / CI：
   每个 gain 严格由两个独立输入文件中同一 task_id 的数值算得
   gain = (improved - baseline) / baseline。
   缺文件、缺任务、任务集不对齐、baseline=0（除零无意义）→ 一律 N/M 退出
   （退出码 2），不写占位数字、不写空文件、不用合成数冒充真实结果。

2) predicted / actual 同源检查（借鉴 KR3 的教训）：
   KR3 要求 predicted 与 actual 配对才能算校准误差；若两者出自同一次自述
   （同一文件/同一时点），校准就是自欺。本工具对应地强制：
     - baseline / improved 必须是两个不同路径的文件（同一文件传两次 → 拒绝）；
     - 逐任务校验 seed 必须一致（projectlab 用 QL_SEED 固定随机流做逐次对照，
       种子不同的两次运行不构成配对对照）；
     - temp 不同只告警（温度变化本身可能是改进手段）。
   这样避免把同一份结果拆成两组、或拿 agent 自述当实测。

3) probe 模式用合成数据只验证数学正确性，显式打印 SYNTHETIC 警告，
   不写正式文件，也不删除已有正式文件。正式证据只能来自真实运行。

============================ 结算方法（不含糊） ============================
- gain_i      = (improved_i - baseline_i) / baseline_i，按 task_id 配对。
- mean        = 所有 pair 的 gain 算术平均。
- 95% CI（默认 method=t）：配对样本 t 区间
        mean ± t_{0.975, n-1} * s / sqrt(n)
   s 为 gain 的样本标准差（ddof=1），n-1 为自由度；t 临界值取双尾 95%
   查表值（df 1..30），df>30 用 1.96 正态近似。报告会打印 t 临界值与 df。
- 95% CI（method=bootstrap）：有放回重采样 bootstrap-n 次（固定 bootstrap-seed
   可复现），取第 2.5 / 97.5 百分位的 percentile 区间。
- OOD 子集：--ood-task 指定（或记录里 ood=true）的任务单独统计 mean/min/负数个数；
   每条 paired_run 的 ood_gain = 该任务 gain（若属 OOD），否则 0.0（中性，非负）。
- 判定（与 goal_verify.verify_kr2 对齐）：n>=8 且 mean>0.10 且所有 ood_gain>=0；
   本工具额外要求 CI 下界 > 0（即 CI 不跨零），否则结算结论为 FAIL。

用法:
  # 真实结算（写正式文件）
  D:/Python/python.exe -B tools/gen_holdout_pairs.py \
      --baseline-file BASE.json --improved-file IMPROVED.json \
      --ood-task P5 --ood-task P6
  # 数学自证（合成数据，不写文件）
  D:/Python/python.exe -B tools/gen_holdout_pairs.py --probe
  # 只算不写（验证真实输入，不落盘）
  D:/Python/python.exe -B tools/gen_holdout_pairs.py --baseline-file ... --improved-file ... --dry-run

退出码: 0=结算完成且判定PASS/probe自检通过; 1=判定FAIL或自检失败; 2=N/M(缺输入/输入不合法)
"""
import argparse
import json
import math
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH = Path('D:/Brain/workspace/bench')
HOLDOUT = BENCH / '_benchmark_holdout.jsonl'

MIN_PAIRS = 8           # goal_verify.py:105 要求至少 8 次配对
GAIN_THRESHOLD = 0.10   # goal_verify.py:112 要求 mean(gain) > 0.10

# 双尾 95% 的 t 临界值 t_{0.975, df}，df = n-1（df>30 用 1.96 正态近似）
T_CRIT_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}

TASK_ID_KEYS = ('task', 'project', 'task_id', 'id', 'name', 'key')


class NotMeasurable(Exception):
    """N/M：缺真实输入或输入不合法，绝不能产证据。"""


# ---------------------------------------------------------------- 输入读取
def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def load_records(path):
    """读取一组运行结果：支持 JSON 数组 / JSON 对象 / JSONL。返回记录 dict 列表。"""
    p = Path(path)
    if not p.exists():
        raise NotMeasurable(f'结果文件不存在: {p}')
    text = p.read_text(encoding='utf-8', errors='replace')
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 退化为 JSONL：逐行解析（与 goal_verify 读证据的方式一致）
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise NotMeasurable(f'{p} 第 {i} 行不是合法 JSON: {e}')
        data = rows

    if isinstance(data, dict):
        # {"results": [...]} / {"records": [...]} / {"data": [...]}
        for k in ('results', 'records', 'data', 'runs'):
            if isinstance(data.get(k), list):
                data = data[k]
                break
        else:
            # {"P3": 0.83, "P4": 0.75, ...} 形式的 task_id -> score
            if data and all(_is_num(v) for v in data.values()):
                data = [{'task': k, 'score': v} for k, v in data.items()]
            else:
                data = [data]
    if not isinstance(data, list) or not data:
        raise NotMeasurable(f'{p} 未解析出任何运行记录（需 JSON 数组/对象/JSONL）')
    out = []
    for i, r in enumerate(data):
        if not isinstance(r, dict):
            raise NotMeasurable(f'{p} 第 {i + 1} 条记录不是 JSON 对象')
        out.append(r)
    return out


def task_id_of(rec, where):
    for k in TASK_ID_KEYS:
        v = rec.get(k)
        if v is not None and str(v).strip():
            return str(v)
    raise NotMeasurable(f'{where} 缺 task_id 字段（需 {"/".join(TASK_ID_KEYS)} 之一）')


def score_of(rec, score_field, score_mode, where):
    """取一条记录的数值分。规则明确，不允许隐式猜测出假分数。"""
    if score_field:
        v = rec.get(score_field)
        if not _is_num(v):
            raise NotMeasurable(f'{where} 缺数值字段 {score_field!r}（--score-field 指定）')
        return float(v)
    if _is_num(rec.get('score')):
        return float(rec['score'])
    prof, ok = rec.get('profile'), rec.get('ok')
    if score_mode == 'auto':
        if isinstance(prof, dict) and prof:
            mode = 'profile'
        elif isinstance(ok, bool):
            mode = 'ok'
        else:
            raise NotMeasurable(
                f'{where} 既无数值 score，也无 profile/ok，无法结算（请用 --score-field 指定分数字段）')
    else:
        mode = score_mode
    if mode == 'profile':
        if not isinstance(prof, dict) or not prof:
            raise NotMeasurable(f'{where} profile 缺失或为空，无法按 --score-mode profile 结算')
        vals = [str(v).upper() for v in prof.values()]
        bad = [v for v in vals if v not in ('OK', 'MISS', 'WEAK', 'FAIL')]
        if bad:
            raise NotMeasurable(f'{where} profile 出现未知取值 {bad}，拒绝猜分')
        return vals.count('OK') / len(vals)
    if mode == 'ok':
        if not isinstance(ok, bool):
            raise NotMeasurable(f'{where} ok 字段非布尔，无法按 --score-mode ok 结算')
        return 1.0 if ok else 0.0
    raise NotMeasurable(f'未知 score_mode: {mode}')


def index_by_task(records, score_field, score_mode, label):
    idx = {}
    for i, rec in enumerate(records):
        where = f'{label} 第 {i + 1} 条'
        tid = task_id_of(rec, where)
        if tid in idx:
            raise NotMeasurable(f'{label} 中 task_id 重复: {tid}（无法唯一配对）')
        idx[tid] = (score_of(rec, score_field, score_mode, where), rec)
    return idx


# ---------------------------------------------------------------- 统计
def mean(xs):
    return sum(xs) / len(xs)


def sample_sd(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def ci_t(gains):
    """配对样本 t 置信区间：mean ± t_{0.975,n-1} * s/sqrt(n)。"""
    n = len(gains)
    if n < 2:
        raise NotMeasurable('配对数 < 2，无法计算样本标准差与 CI')
    m, sd = mean(gains), sample_sd(gains)
    df = n - 1
    tcrit = T_CRIT_95.get(df, 1.96)
    half = tcrit * sd / math.sqrt(n)
    return m - half, m + half, {'method': 'paired-t', 'n': n, 'df': df,
                                't_crit_0.975': tcrit, 'sd': sd, 'half_width': half}


def ci_bootstrap(gains, n_resamples, seed):
    """有放回 bootstrap percentile 区间（固定 seed 可复现）。"""
    n = len(gains)
    rng = random.Random(seed)
    sums = []
    for _ in range(n_resamples):
        s = 0.0
        for _ in range(n):
            s += gains[rng.randrange(n)]
        sums.append(s / n)
    sums.sort()
    lo = sums[int(0.025 * n_resamples)]
    hi = sums[min(n_resamples - 1, int(0.975 * n_resamples))]
    return lo, hi, {'method': 'bootstrap-percentile', 'n_resamples': n_resamples,
                    'seed': seed, 'n': n}


# ---------------------------------------------------------------- 配对结算
def build_pairs(base_idx, imp_idx, ood_ids):
    base_ids, imp_ids = set(base_idx), set(imp_idx)
    only_base, only_imp = sorted(base_ids - imp_ids), sorted(imp_ids - base_ids)
    if only_base or only_imp:
        raise NotMeasurable(
            f'两组任务集不对齐（仅 baseline: {only_base[:8]}; 仅 improved: {only_imp[:8]}）'
            '——不能配对，拒绝结算')

    pairs, skipped_zero, confounds = [], [], []
    for tid in sorted(base_ids):
        b, brec = base_idx[tid]
        i, irec = imp_idx[tid]
        if b < 0 or i < 0:
            raise NotMeasurable(f'task {tid} 分数为负（{b}/{i}），不是合法通过率')
        bs, isd = brec.get('seed'), irec.get('seed')
        if bs is not None and isd is not None and bs != isd:
            confounds.append(f'{tid}: seed {bs} != {isd}')
        bt, it = brec.get('temp'), irec.get('temp')
        if bt is not None and it is not None and bt != it:
            confounds.append(f'{tid}: temp {bt} != {it}（告警，温度变化可能是改进手段）')
        if b == 0:
            # 除零无意义：跳过且如实报告，绝不用 0 或 1 伪造 gain。
            skipped_zero.append(tid)
            continue
        g = (i - b) / b
        pairs.append({'task': tid, 'baseline': b, 'improved': i,
                      'gain': g, 'ood': tid in ood_ids})

    if confounds:
        seeds = [c for c in confounds if 'seed' in c]
        if seeds:
            raise NotMeasurable('固定种子不一致，不是有效配对对照: ' + '; '.join(seeds[:8]))
    return pairs, skipped_zero, confounds


def as_evidence_lines(pairs):
    """严格对齐 goal_verify 的逐行 schema：每行一个 paired_run。"""
    lines = []
    for p in pairs:
        lines.append({'type': 'paired_run',
                      'gain': p['gain'],
                      # 非 OOD 任务的 OOD 增益记 0（中性、非负），不参与 OOD 结论的抬高。
                      'ood_gain': p['gain'] if p['ood'] else 0.0})
    return lines


def verify_kr2_logic(lines):
    """镜像 goal_verify.verify_kr2 的判定逻辑（用于 probe 自检与结算报告）。"""
    runs = [r for r in lines if r.get('type') == 'paired_run' or 'gain' in r]
    if not runs:
        return 'NOT_MEASURABLE', '无配对运行记录'
    if len(runs) < MIN_PAIRS:
        return 'NOT_MEASURABLE', f'配对运行 {len(runs)} < {MIN_PAIRS}'
    gains = [r.get('gain', 0) for r in runs]
    ood = [r.get('ood_gain', 0) for r in runs]
    mg = sum(gains) / len(gains)
    if mg > GAIN_THRESHOLD and all(g >= 0 for g in ood):
        return 'PASS', f'平均提升 {mg:.2%}, OOD 最差 {min(ood):.2%}'
    return 'FAIL', f'平均提升 {mg:.2%}, OOD 最差 {min(ood):.2%}'


def report(title, pairs, lines, ci_lo, ci_hi, ci_meta, ood_ids, skipped, confounds, verdict):
    gains = [p['gain'] for p in pairs]
    ood_vals = [p['gain'] for p in pairs if p['ood']]
    print('\n' + '=' * 66)
    print(' ' + title)
    print('=' * 66)
    print(f'  配对任务数        : {len(pairs)} (门槛 >= {MIN_PAIRS})')
    print(f'  平均 gain         : {mean(gains):.4f} ({mean(gains):.2%})')
    print(f'  95% CI            : [{ci_lo:.4f}, {ci_hi:.4f}]')
    print(f'  CI 方法           : {ci_meta["method"]}')
    if ci_meta['method'] == 'paired-t':
        print(f'    自由度 df={ci_meta["df"]}, t(0.975)={ci_meta["t_crit_0.975"]}, '
              f's={ci_meta["sd"]:.4f}, 半宽={ci_meta["half_width"]:.4f}')
    else:
        print(f'    重采样 {ci_meta["n_resamples"]} 次, seed={ci_meta["seed"]}, '
              f'percentile 2.5/97.5')
    print(f'  CI 是否跨零       : {"是（结论不可信）" if ci_lo <= 0 <= ci_hi else "否（不跨零）"}')
    print(f'  OOD 任务          : {sorted(ood_ids) if ood_ids else "未指定"}')
    if ood_vals:
        print(f'  OOD mean/min/负个数: {mean(ood_vals):.4f} / {min(ood_vals):.4f} / '
              f'{sum(1 for v in ood_vals if v < 0)}')
    else:
        print('  OOD mean/min/负个数: 无 OOD 配对（KR2 的 OOD 非负无法验证）')
    if skipped:
        print(f'  因 baseline=0 跳过 : {skipped}（除零无意义，绝不用假数填充）')
    for c in confounds:
        print(f'  告警: {c}')
    print(f'  goal_verify 逻辑   : {verdict[0]} — {verdict[1]}')
    print('=' * 66)


# ---------------------------------------------------------------- 结算模式
def settle(args):
    if not args.baseline_file or not args.improved_file:
        raise NotMeasurable('必须同时提供 --baseline-file 与 --improved-file（不同时点/不同版本的两组结果）')

    p1, p2 = Path(args.baseline_file).resolve(), Path(args.improved_file).resolve()
    if os.path.normcase(str(p1)) == os.path.normcase(str(p2)):
        raise NotMeasurable('baseline 与 improved 是同一个文件——不是两次独立运行，拒绝结算')

    base_idx = index_by_task(load_records(p1), args.score_field, args.score_mode, 'baseline')
    imp_idx = index_by_task(load_records(p2), args.score_field, args.score_mode, 'improved')

    # OOD 任务：显式参数 + 记录里的 ood=true
    ood_ids = set(args.ood_task or [])
    for idx in (base_idx, imp_idx):
        for tid, (_, rec) in idx.items():
            if rec.get('ood') is True:
                ood_ids.add(tid)

    pairs, skipped, confounds = build_pairs(base_idx, imp_idx, ood_ids)
    if len(pairs) < MIN_PAIRS:
        raise NotMeasurable(f'有效配对 {len(pairs)} < {MIN_PAIRS}'
                            + (f'（另有 {len(skipped)} 个 baseline=0 的任务被跳过）' if skipped else ''))
    if not ood_ids or not any(p['ood'] for p in pairs):
        raise NotMeasurable('未指定有效的 OOD 任务（--ood-task 或记录 ood=true）——'
                            'KR2 要求 OOD 非负，缺 OOD 子集即 N/M')

    ood_ids = {t for t in ood_ids if any(p['task'] == t for p in pairs)}
    gains = [p['gain'] for p in pairs]
    if args.method == 'bootstrap':
        if args.bootstrap_n < 100:
            raise NotMeasurable('--bootstrap-n 至少 100')
        lo, hi, meta = ci_bootstrap(gains, args.bootstrap_n, args.bootstrap_seed)
    else:
        lo, hi, meta = ci_t(gains)

    lines = as_evidence_lines(pairs)
    verdict = verify_kr2_logic(lines)
    ci_ok = lo > 0  # CI 不跨零
    final = 'PASS' if verdict[0] == 'PASS' and ci_ok else 'FAIL'
    report('真实运行结果结算' + ('（dry-run 不落盘）' if args.dry_run else ''),
           pairs, lines, lo, hi, meta, ood_ids, skipped, confounds,
           (final, verdict[1] + ('; CI 下界 >0' if ci_ok else '; CI 跨零')))

    if not args.dry_run:
        HOLDOUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = HOLDOUT.with_suffix('.jsonl.tmp')
        with tmp.open('w', encoding='utf-8') as f:
            for row in lines:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        os.replace(str(tmp), str(HOLDOUT))
        print(f'\n  已写入正式证据: {HOLDOUT} ({len(lines)} 行 paired_run)')
    else:
        print('\n  dry-run: 不写正式文件（正式证据只来自真实运行）')
    return 0 if final == 'PASS' else 1


# ---------------------------------------------------------------- probe 模式
def probe():
    """合成数据数学自证：只打印，绝不写正式文件。"""
    print('!' * 66)
    print('  PROBE / SYNTHETIC DATA —— 合成数据，仅验证数学正确性')
    print('  不写正式证据文件，不作 KR2 验收，不得据此声称经验改进。')
    print('!' * 66)

    # 基线/改进分数（人工构造，gain 可手算）
    base_scores = [1.00, 0.50, 0.80, 0.40, 0.50, 0.50, 0.50, 1.00, 0.50, 0.25]
    imp_scores = [1.12, 0.575, 0.88, 0.44, 0.55, 0.55, 0.55, 1.10, 0.50, 0.30]
    expected_gains = [0.12, 0.15, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.0, 0.20]

    pairs = []
    for i, (b, imp) in enumerate(zip(base_scores, imp_scores)):
        pairs.append({'task': f'P{i + 1}', 'baseline': b, 'improved': imp,
                      'gain': (imp - b) / b, 'ood': i in (0, 9)})
    gains = [p['gain'] for p in pairs]

    # 自检 1：gain 逐项与手算值一致
    assert len(gains) == len(expected_gains), 'pair 数量不对'
    for i, (g, e) in enumerate(zip(gains, expected_gains)):
        assert abs(g - e) < 1e-12, f'gain[{i}]={g} != 手算 {e}'
    print(f'  [OK] gain 逐项手算一致: {[round(g, 4) for g in gains]}')

    # 自检 2：mean 与手算一致
    m = mean(gains)
    assert abs(m - 0.107) < 1e-12, f'mean={m} != 0.107'
    print(f'  [OK] mean(gain) = {m:.6f} = 0.107（手算）')

    # 自检 3：t 区间包含 mean 且半宽为正
    lo, hi, meta = ci_t(gains)
    assert lo < m < hi and hi - lo > 0, 't 区间异常'
    print(f'  [OK] paired-t 95%CI = [{lo:.6f}, {hi:.6f}] '
          f'(df={meta["df"]}, t={meta["t_crit_0.975"]}, s={meta["sd"]:.6f})')

    # 自检 4：bootstrap 区间包含 mean（固定 seed 可复现）
    blo, bhi, bmeta = ci_bootstrap(gains, 10000, 42)
    assert blo <= m <= bhi, 'bootstrap 区间未包含 mean'
    blo2, bhi2, _ = ci_bootstrap(gains, 10000, 42)
    assert (blo, bhi) == (blo2, bhi2), 'bootstrap 固定 seed 不可复现'
    print(f'  [OK] bootstrap 95%CI = [{blo:.6f}, {bhi:.6f}] '
          f'(10000 次, seed=42, 可复现)')

    # 自检 5：OOD 子集映射与手算一致（非 OOD -> 0.0）
    lines = as_evidence_lines(pairs)
    assert len(lines) == 10
    for p, line in zip(pairs, lines):
        want = p['gain'] if p['ood'] else 0.0
        assert line['type'] == 'paired_run' and abs(line['ood_gain'] - want) < 1e-12
    ood_vals = [p['gain'] for p in pairs if p['ood']]
    assert abs(mean(ood_vals) - 0.16) < 1e-12, f'OOD mean={mean(ood_vals)} != 0.16'
    print(f'  [OK] OOD 子集 mean = {mean(ood_vals):.6f} = 0.16（手算），非 OOD 记 0.0')

    # 自检 6：完整套用 goal_verify 判定逻辑（含 PASS/FAIL/N-M 三态）
    st, why = verify_kr2_logic(lines)
    assert st == 'PASS', f'10 对 mean=0.107 应判 PASS，实际 {st}'
    st7, _ = verify_kr2_logic(lines[:7])
    assert st7 == 'NOT_MEASURABLE', '少于 8 对应判 N/M'
    st_fail, _ = verify_kr2_logic([{'gain': 0.05, 'ood_gain': 0.0} for _ in range(10)])
    assert st_fail == 'FAIL', 'mean<=0.10 应判 FAIL'
    st_ood, _ = verify_kr2_logic([{'gain': 0.20, 'ood_gain': -0.01} for _ in range(10)])
    assert st_ood == 'FAIL', 'OOD 为负应判 FAIL'
    print(f'  [OK] goal_verify 三态自检: 10对=>PASS, 7对=>N/M, mean<=0.1=>FAIL, OOD负=>FAIL')

    report('PROBE 合成数据自检（非真实证据）', pairs, lines, lo, hi, meta,
           {'P1', 'P10'}, [], [], (st, why))
    print(f'  正式证据路径: {HOLDOUT}')
    print('  probe 不写、不改、不删正式证据文件。')
    print('  真实运行仍缺：两组不同时点/版本的基线/改进结果文件（见脚本末尾报告）。')
    return 0


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(
        description='hold-out 配对对照结算器（KR2 证据生成器）；缺真实输入即 N/M，绝不编造 gain/CI。',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--baseline-file', help='基线组运行结果文件（不同时点/版本）')
    ap.add_argument('--improved-file', help='改进组运行结果文件（不得与 baseline 同一文件）')
    ap.add_argument('--ood-task', action='append', default=[],
                    help='OOD 任务的 task_id，可重复；记录里 ood=true 也可')
    ap.add_argument('--score-field', help='显式数值分数字段名（如 score/pass_rate）')
    ap.add_argument('--score-mode', choices=['auto', 'ok', 'profile'], default='auto',
                    help='无显式分数时的派生规则：profile=OK维度占比, ok=1/0；默认 auto')
    ap.add_argument('--method', choices=['t', 'bootstrap'], default='t',
                    help='95%%CI 方法：t=配对t分布(默认), bootstrap=有放回重采样')
    ap.add_argument('--bootstrap-n', type=int, default=10000, help='bootstrap 重采样次数（默认 10000）')
    ap.add_argument('--bootstrap-seed', type=int, default=0, help='bootstrap 随机种子（默认 0）')
    ap.add_argument('--probe', action='store_true', help='合成数据数学自证，不写正式文件')
    ap.add_argument('--dry-run', action='store_true', help='用真实输入完整结算但不写正式文件')
    args = ap.parse_args()

    try:
        if args.probe:
            return probe()
        return settle(args)
    except NotMeasurable as e:
        print(f'\n[N/M] {e}')
        print('N/M 不等于 FAIL，也不等于 PASS；不写任何正式证据文件。')
        return 2


if __name__ == '__main__':
    sys.exit(main())
