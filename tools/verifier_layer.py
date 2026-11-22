# -*- coding: utf-8 -*-
"""verifier_layer —— 验证层去自审：成对换位 + 独立 rubric + 判断下沉（S21，零 LLM）

依据：CAPABILITY_LADDER.yaml 的 S21 卡「验证层去自审（质量压倒多样性）」
- what: Critic/Planner 不再 35B 自审；必须 LLM judge 时**成对交换顺序 + 独立 rubric
        + 人工抽检**；能断言的判断下沉到 Python 规则/测试/哈希。
- advice: 先做"成对换位"判据，零成本可立刻降自偏好。
- why: Self-MoA(arXiv:2502.00674) 最强采样优于混合 +6.6；JudgeBench(arXiv:2410.12784)
       GPT-4o 客观判断仅 50.9%≈抛硬币——单序判断不可信，必须双向验证。

本工具把"判断"下沉为确定性统计（不调用任何 LLM）：
1. 加载 rubric：默认从运行版 bench/rubrics/（真实路径 D:/Brain/workspace/bench/rubrics），
   并与权威源 config/rubrics/ 合并；同名 rubric 以**运行版为准**（三副本坑：权威 publish
   与运行 workspace 可能不同步，工具按运行版实际读取，绝不因 publish 找不到就造假的）。
   环境变量 RUBRICS_DIR / BENCH_DIR / CONFIG_RUBRICS_DIR 可覆盖三个位置。
2. 成对交换一致性：每条判定记录含"A 在前(forward)"与"交换后(swapped)"两次结果；
   若 winner 翻转 → 记为位置偏差(position bias)。有 score_a/score_b 时**确定性地由分数
   重判 winner**（判断下沉），不盲信 judge 的语义标签。
3. 独立 rubric 一致性：forward_rubric ≠ swapped_rubric 才算独立证据；rubric_consistency
   统计这些独立对的一致率。同 rubric 的对单独统计，不计入独立证据。
4. 比例区间用 Wilson 95% CI（小样本优于 Wald；项目 scientific_measurement 惯例）。

输入数据契约（--pairs PATH，JSON list 或 {"pairs":[...]}）：
  {
    "id": "p1",
    "rubric": "critic_v2",            # 默认 rubric（两序都用它时用）
    "forward_rubric": "critic_v2",    # 可选，覆盖 forward 的 rubric
    "swapped_rubric": "critic_v1",    # 可选，覆盖 swapped 的 rubric；与 forward 不同=独立
    "forward": {"winner": "A", "score_a": 0.8, "score_b": 0.6},  # A 在前
    "swapped": {"winner": "A", "score_a": 0.8, "score_b": 0.6}   # 交换后，winner 用原始 A/B 标签
  }
  winner ∈ {A, B, TIE}；缺 winner 但有 score_a/score_b 时确定性重判。

用法:
  python tools/verifier_layer.py --probe                 # 合成自证（不写正式证据）
  python tools/verifier_layer.py --pairs PATH            # 真实成对判定日志
  python tools/verifier_layer.py --pairs PATH --json     # 结构化输出
  python tools/verifier_layer.py --json                  # 无数据 → N/M，不造数

约定：退出码 0 = 工具正常执行；门禁结论看输出里的 verdict / gate_pass。
      verdict='N/M' 表示证据不足，按本项目 noise_floor 惯例不判过、不造数。
"""
import argparse
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
# 真实运行版 rubric 路径（team-lead 2026-11-22 明确：权威 publish 与运行 workspace 不同步，
# 默认指向运行版；publish/config/rubrics 作为权威副本合并，同名以运行版为准）。
RUBRICS_DIR = Path(os.environ.get('RUBRICS_DIR') or (Path(BENCH_DIR) / 'rubrics'))
CONFIG_RUBRICS_DIR = Path(os.environ.get('CONFIG_RUBRICS_DIR') or (ROOT / 'config' / 'rubrics'))

# 门禁阈值（CLI 可覆盖；依据见模块 docstring，均为经验起点，非金标准）
MAX_POSITION_BIAS = 0.10       # 翻转率 >10% → 位置偏差不可接受
MIN_RUBRIC_CONSISTENCY = 0.60  # 独立 rubric 一致率 <60% → 判断不稳
Z = 1.96                       # Wilson 95%

VERDICT_TOKENS = {
    'A': 'A', 'B': 'B',
    'TIE': 'TIE', 'T': 'TIE', '0': 'TIE', 'EQUAL': 'TIE', 'DRAW': 'TIE',
}


# ---------------------------------------------------------------------------
# 纯函数：可单测，不读写正式产物
# ---------------------------------------------------------------------------

def load_rubric_dir(path):
    """读一个 rubric 目录的 *.json → {stem: obj}；缺失/非法文件跳过，不造数。"""
    out = {}
    try:
        files = sorted(Path(path).glob('*.json'))
    except OSError:
        return out
    for p in files:
        try:
            obj = json.loads(p.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(obj, dict):
            out[p.stem] = obj
    return out


def load_rubrics(rubrics_dir=None, config_dir=None):
    """合并 config/rubrics 与 bench/rubrics；同名以运行版(rubrics_dir)为准。

    返回 {stem: obj}——与 tools/test_verifier_layer.py 的调用契约一致。
    需要来源审计信息时用 load_rubrics_meta()。
    """
    merged, _ = load_rubrics_meta(rubrics_dir, config_dir)
    return merged


def load_rubrics_meta(rubrics_dir=None, config_dir=None):
    """返回 (merged_dict, meta)；meta 记录两目录各加载了哪些，便于审计来源。"""
    cfg = load_rubric_dir(config_dir or CONFIG_RUBRICS_DIR)
    run = load_rubric_dir(rubrics_dir or RUBRICS_DIR)
    merged = dict(cfg)
    merged.update(run)  # 运行版覆盖权威副本（三副本坑：以实际读取的运行版为准）
    meta = {
        'runtime_dir': str(rubrics_dir or RUBRICS_DIR),
        'config_dir': str(config_dir or CONFIG_RUBRICS_DIR),
        'runtime_files': sorted(run),
        'config_files': sorted(cfg),
        'overridden': sorted(set(cfg) & set(run)),  # 同名被运行版覆盖者
        'loaded': sorted(merged),
    }
    return merged, meta


def normalize_verdict(raw, score_a=None, score_b=None):
    """规整 winner：优先语义标签；缺失则由分数确定性重判（判断下沉）。

    返回 'A'/'B'/'TIE'，无法判定 → None。
    """
    if isinstance(raw, dict):
        raw = (raw.get('winner') or raw.get('verdict') or raw.get('preferred'))
    if raw is not None:
        token = str(raw).strip().upper()
        if token in VERDICT_TOKENS:
            return VERDICT_TOKENS[token]
    # 语义标签缺失/非法 → 用分数确定性重判，不盲信 judge 标签
    if score_a is not None and score_b is not None:
        try:
            a, b = float(score_a), float(score_b)
        except (TypeError, ValueError):
            return None
        if math.isnan(a) or math.isnan(b):
            return None
        if abs(a - b) < 1e-9:
            return 'TIE'
        return 'A' if a > b else 'B'
    return None


def score_candidate(raw=None, score_a=None, score_b=None):
    """确定性打分（判断下沉）：一条判定 → {winner, margin, source}。

    winner 优先取语义标签；缺失/非法时由 score_a/score_b 确定性重判；
    margin=|a-b| 为判定强度（无分数 → None）；无法判定 → winner=None。
    """
    winner = normalize_verdict(raw, score_a, score_b)
    margin = None
    if score_a is not None and score_b is not None:
        try:
            margin = round(abs(float(score_a) - float(score_b)), 4)
        except (TypeError, ValueError):
            margin = None
    label = (raw.get('winner') or raw.get('verdict')) if isinstance(raw, dict) else raw
    labeled = label is not None and str(label).strip().upper() in VERDICT_TOKENS
    source = 'label' if labeled else ('score' if (winner and margin is not None) else None)
    return {'winner': winner, 'margin': margin, 'source': source}


def normalize_pair(row):
    """规整一条成对判定；非法 → None。winner 用原始候选 A/B 标签表示。"""
    if not isinstance(row, dict):
        return None
    fwd = row.get('forward') if isinstance(row.get('forward'), dict) else {}
    swp = row.get('swapped') if isinstance(row.get('swapped'), dict) else {}
    base = row.get('rubric')
    fwd_r = row.get('forward_rubric') or base or fwd.get('rubric')
    swp_r = row.get('swapped_rubric') or row.get('rubric_swapped') or base or swp.get('rubric')
    fwd_s = score_candidate(row.get('forward'), fwd.get('score_a'), fwd.get('score_b'))
    swp_s = score_candidate(row.get('swapped'), swp.get('score_a'), swp.get('score_b'))
    return {
        'id': row.get('id') or row.get('pair') or '?',
        'forward': fwd_s['winner'],
        'swapped': swp_s['winner'],
        'forward_margin': fwd_s['margin'],
        'swapped_margin': swp_s['margin'],
        'forward_rubric': fwd_r,
        'swapped_rubric': swp_r,
        'independent_rubric': bool(fwd_r and swp_r and fwd_r != swp_r),
    }


def wilson_ci(k, n, z=Z):
    """Wilson score 置信区间；n<=0 → None。"""
    if not n or n <= 0:
        return None
    p = k / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, center - half), 4), round(min(1.0, center + half), 4)]


def _rate(flips, total):
    return round(flips / total, 4) if total else None


def analyze(pairs, rubrics=None):
    """成对交换 + 独立 rubric 的确定性统计。

    pairs: 原始行列表（list[dict]）；rubrics: 已加载 rubric（用于校验引用是否存在）。
    返回统计 dict（纯数据，不含 verdict）。
    """
    norm = [p for p in (normalize_pair(r) for r in (pairs or [])) if p]
    known = set((rubrics or {}).keys())

    judged = [p for p in norm if p['forward'] and p['swapped']]
    flips = [p for p in judged if p['forward'] != p['swapped']]  # 含 TIE 与非 TIE 翻转
    decisive = [p for p in judged if p['forward'] != 'TIE' and p['swapped'] != 'TIE']
    decisive_flips = [p for p in decisive if p['forward'] != p['swapped']]

    indep = [p for p in judged if p['independent_rubric']]
    indep_agree = [p for p in indep if p['forward'] == p['swapped']]
    same_rubric = [p for p in judged if not p['independent_rubric']]

    unknown_rubric = sorted({
        r for p in norm for r in (p['forward_rubric'], p['swapped_rubric'])
        if r and known and r not in known
    })

    n_j = len(judged)
    n_d = len(decisive)
    n_i = len(indep)
    return {
        'n_input': len(norm),
        'n_judged': n_j,
        'n_missing': len(norm) - n_j,
        'n_decisive': n_d,
        'n_independent_rubric': n_i,
        'n_same_rubric': len(same_rubric),
        'flips': len(flips),
        'decisive_flips': len(decisive_flips),
        'indep_agreements': len(indep_agree),
        'position_bias_rate': _rate(len(flips), n_j),
        'decisive_flip_rate': _rate(len(decisive_flips), n_d),
        'rubric_consistency_rate': _rate(len(indep_agree), n_i),
        'position_bias_ci': wilson_ci(len(flips), n_j),
        'decisive_flip_ci': wilson_ci(len(decisive_flips), n_d),
        'rubric_consistency_ci': wilson_ci(len(indep_agree), n_i),
        'unknown_rubric_refs': unknown_rubric,
        'rubric_catalog': sorted(known),
    }


def build_report(pairs, rubrics=None, rubric_meta=None,
                 max_bias=MAX_POSITION_BIAS, min_cons=MIN_RUBRIC_CONSISTENCY):
    """组装结构化报告；无数据 → N/M，不造数。"""
    st = analyze(pairs, rubrics)
    reasons = []
    if st['n_judged'] == 0:
        reasons.append('无有效成对判定（forward/swapped 双全）')
    if st['n_decisive'] == 0 and st['n_judged'] > 0:
        reasons.append('全部为 TIE，无可判定的胜负对')
    if st['unknown_rubric_refs']:
        reasons.append('引用未加载 rubric: ' + ','.join(st['unknown_rubric_refs']))

    no_indep = st['n_judged'] > 0 and st['n_independent_rubric'] == 0
    rate = st['position_bias_rate']
    cons = st['rubric_consistency_rate']
    insufficient = bool(reasons)
    if insufficient:
        verdict = 'N/M'
        why = '；'.join(reasons) + '——不造数，按 noise_floor 惯例不判过'
    else:
        bad_bias = rate is not None and rate > max_bias
        bad_cons = cons is not None and cons < min_cons
        if bad_bias or bad_cons:
            # 明确的失败优先于"证据不足"：位置偏差/不一致一旦可判就不被无独立 rubric 掩盖
            verdict = 'FAIL'
            parts = []
            if bad_bias:
                parts.append(f'翻转率 {rate:.3f}>{max_bias}')
            if bad_cons:
                parts.append(f'独立 rubric 一致率 {cons:.3f}<{min_cons}')
            why = '；'.join(parts)
        elif no_indep:
            # 位置偏差可判但独立 rubric 要求未满足：不宣称全面 PASS，也不造数
            verdict = 'N/M'
            why = (f'翻转率 {rate:.3f}≤{max_bias}，但无独立 rubric 对'
                   '（forward/swapped 同 rubric）——一致率 N/M，不宣称全面通过')
        else:
            verdict = 'PASS'
            why = (f'翻转率 {rate:.3f}≤{max_bias}，'
                   f'独立 rubric 一致率 {cons:.3f}≥{min_cons}')

    return {
        'tool': 'verifier_layer',
        'verdict': verdict,
        'insufficient': insufficient,
        'gate_pass': (not insufficient) and verdict == 'PASS',
        'why': why,
        'thresholds': {'max_position_bias': max_bias, 'min_rubric_consistency': min_cons},
        'stats': st,
        'position_bias': {
            'rate': rate,
            'ci95': st['position_bias_ci'],
            'flips': st['flips'], 'n': st['n_judged'],
            'decisive_rate': st['decisive_flip_rate'],
            'decisive_ci95': st['decisive_flip_ci'],
        },
        'rubric_consistency': {
            'rate': cons,
            'ci95': st['rubric_consistency_ci'],
            'agreements': st['indep_agreements'], 'n': st['n_independent_rubric'],
            'same_rubric_pairs': st['n_same_rubric'],
        },
        'ci': {
            'method': 'Wilson score 95%',
            'z': Z,
            'position_bias': st['position_bias_ci'],
            'rubric_consistency': st['rubric_consistency_ci'],
        },
        'rubrics': rubric_meta or {},
        'math_basis': (
            'position_bias=交换前后 winner 翻转比；decisive_flip 排除 TIE；'
            'rubric_consistency=独立 rubric(forward≠swapped)对的一致比；'
            'winner 可由 score_a/score_b 确定性重判（判断下沉）；'
            '区间用 Wilson 95%（小样本优于 Wald）；无双向判定/无独立 rubric/引用未加载 rubric → N/M。'
        ),
    }


def pairwise_swap_check(pairs, rubrics=None, meta=None,
                        max_bias=MAX_POSITION_BIAS, min_cons=MIN_RUBRIC_CONSISTENCY):
    """S21 核心公开入口：成对交换顺序一致性检查（确定性、零 LLM）。

    与 build_report 同源实现；保留此具名入口供显式引用——
    ROADMAP_GRAPH.md 中 S21 的 verify 要求 def pairwise_swap_check|def score_candidate。
    """
    return build_report(pairs, rubrics, meta, max_bias=max_bias, min_cons=min_cons)


def render_text(rep):
    """人类可读报告。"""
    st = rep['stats']
    lines = [
        f'验证层去自审（S21）：{rep["verdict"]}',
        f'  输入 {st["n_input"]}，双向判定 {st["n_judged"]}（缺向 {st["n_missing"]}），'
        f'独立 rubric 对 {st["n_independent_rubric"]}',
        f'  {rep["why"]}',
    ]
    pb = rep['position_bias']
    rc = rep['rubric_consistency']
    fmt = lambda v, f='{:.3f}': 'N/M' if v is None else f.format(v)
    lines.append(f'  position_bias = {fmt(pb["rate"])} '
                 f'(flips {pb["flips"]}/{pb["n"]}, CI95 {pb["ci95"]})')
    lines.append(f'  decisive_flip = {fmt(pb["decisive_rate"])} '
                 f'(CI95 {pb["decisive_ci95"]})')
    lines.append(f'  rubric_consistency = {fmt(rc["rate"])} '
                 f'(agree {rc["agreements"]}/{rc["n"]}, CI95 {rc["ci95"]})')
    lines.append(f'  rubric 来源：运行版 {st["rubric_catalog"]}'
                 f'（覆盖权威副本 {rep["rubrics"].get("overridden", [])}）')
    lines.append('')
    lines.append('数学依据：' + rep['math_basis'])
    lines.append('注：退出码 0 仅表示工具正常执行；门禁结论看 verdict / gate_pass。')
    return '\n'.join(lines)


def load_pairs(path):
    """读成对判定日志；缺失/非法 → []，不造数。"""
    if not path:
        return []
    try:
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    if isinstance(obj, dict):
        obj = obj.get('pairs', [])
    return obj if isinstance(obj, list) else []


def probe_payload():
    """合成自证数据：一组稳健对 + 一组位置偏差对 + 一组独立 rubric 不一致对。

    仅证明判据能工作，绝不写正式证据（与 S18 holdout_split --probe 同纪律）。
    """
    stable = [
        {'id': f's{i}', 'forward_rubric': 'critic_v2', 'swapped_rubric': 'critic_v1',
         'forward': {'winner': 'A'}, 'swapped': {'winner': 'A'}}
        for i in range(4)
    ]
    biased = [
        {'id': f'b{i}', 'rubric': 'critic_v2',
         'forward': {'winner': 'A', 'score_a': 0.8, 'score_b': 0.3},
         'swapped': {'winner': 'B', 'score_a': 0.8, 'score_b': 0.3}}
        for i in range(4)
    ]
    indep = [
        {'id': f'i{i}', 'forward_rubric': 'critic_v2', 'swapped_rubric': 'planner_v1',
         'forward': {'winner': 'A'}, 'swapped': {'winner': 'B'}}
        for i in range(4)
    ]
    return stable, biased, indep


def run_probe(max_bias=MAX_POSITION_BIAS, min_cons=MIN_RUBRIC_CONSISTENCY, rubrics=None):
    """三场景自证：稳健→PASS，位置偏差→FAIL，独立 rubric 不一致→FAIL。"""
    stable, biased, indep = probe_payload()
    r1 = build_report(stable, rubrics, max_bias=max_bias, min_cons=min_cons)
    r2 = build_report(biased, rubrics, max_bias=max_bias, min_cons=min_cons)
    r3 = build_report(indep, rubrics, max_bias=max_bias, min_cons=min_cons)
    empty = build_report([], rubrics)
    return {
        'tool': 'verifier_layer', 'mode': 'probe',
        'synthetic_notice': '合成数据仅证明判据可用，绝不写正式证据',
        'cases': {
            'stable': {'verdict': r1['verdict'], 'position_bias': r1['position_bias']['rate']},
            'position_biased': {'verdict': r2['verdict'], 'position_bias': r2['position_bias']['rate']},
            'rubric_inconsistent': {'verdict': r3['verdict'],
                                    'rubric_consistency': r3['rubric_consistency']['rate']},
            'empty': {'verdict': empty['verdict'], 'insufficient': empty['insufficient']},
        },
        'self_check_pass': (
            r1['verdict'] == 'PASS' and r2['verdict'] == 'FAIL'
            and r3['verdict'] == 'FAIL' and empty['verdict'] == 'N/M'
        ),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='验证层去自审（S21，零 LLM，成对换位+独立 rubric）')
    ap.add_argument('--json', action='store_true', help='输出结构化 JSON')
    ap.add_argument('--pairs', help='成对判定日志路径（JSON list 或 {"pairs":[...]}）')
    ap.add_argument('--rubrics-dir', help='覆盖运行版 rubric 目录（默认 RUBRICS_DIR/BENCH_DIR）')
    ap.add_argument('--config-rubrics-dir', help='覆盖权威源 config/rubrics 目录')
    ap.add_argument('--probe', action='store_true', help='合成自证（不写正式证据）')
    ap.add_argument('--max-position-bias', type=float, default=MAX_POSITION_BIAS)
    ap.add_argument('--min-rubric-consistency', type=float, default=MIN_RUBRIC_CONSISTENCY)
    args = ap.parse_args(argv)

    rubrics, meta = load_rubrics_meta(args.rubrics_dir, args.config_rubrics_dir)

    if args.probe:
        out = run_probe(args.max_position_bias, args.min_rubric_consistency, rubrics)
    else:
        out = pairwise_swap_check(
            load_pairs(args.pairs), rubrics, meta,
            max_bias=args.max_position_bias, min_cons=args.min_rubric_consistency,
        )

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.probe:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(render_text(out))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
