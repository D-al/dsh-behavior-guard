# -*- coding: utf-8 -*-
"""35B A/B 判优的严格统计检验（可随数据增长重复运行）。

主指标 tool_calls/session：Shapiro-Wilk 正态性 -> Welch t / Mann-Whitney U（两者均报）；
效应量 Cohen's d + rank-biserial + Bootstrap 95% CI；二项指标 Fisher exact + OR CI；
三组两两比较 Holm-Bonferroni；p>0.05 时 TOST 等效（边界 ±1 tool_call）；
判定：判优 / 等效 / 不确定（附需补样本量，power=0.95，用当前 observed 方差）。

用法: python ab_significance.py [输入JSON] [输出JSON]
"""
import json, math, sys
import numpy as np
from scipy import stats

SRC = r'D:/Brain/workspace/bench/_ab_reflection_result.json'
OUT = r'D:/Brain/workspace/bench/_ab_significance_result.json'
ALPHA, POWER, BOUND, BOOT = 0.05, 0.95, 1.0, 10000
GROUPS = ('off', 'on', 'inject-on')
PAIRS = (('off', 'on'), ('off', 'inject-on'), ('on', 'inject-on'))


def r(x, n=4):
    """保留小数；None/NaN 原样返回，保证 JSON 合法。"""
    if x is None:
        return None
    x = float(x)
    return round(x, n) if math.isfinite(x) else None


def series(rows, g, k):
    return np.array([float(x.get(k, 0)) for x in rows if x.get('group') == g])


def pooled_sd(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    s = ((len(a) - 1) * np.var(a, ddof=1) + (len(b) - 1) * np.var(b, ddof=1)) / (len(a) + len(b) - 2)
    return math.sqrt(s) if s >= 0 else None


def cohens_d(a, b, sp=None):
    sp = pooled_sd(a, b) if sp is None else sp
    if sp is None or sp == 0 or len(a) < 2 or len(b) < 2:
        return None
    return (np.mean(a) - np.mean(b)) / sp


def holm(pvals):
    """Holm-Bonferroni：逐步降级，返回与输入同序的校正 p。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: (pvals[i] is None, pvals[i] if pvals[i] is not None else 1.0))
    adj, prev = [1.0] * m, 0.0
    for rank, i in enumerate(order):
        prev = max(prev, (m - rank) * (pvals[i] if pvals[i] is not None else 1.0))
        adj[i] = min(prev, 1.0)
    return adj


def bootstrap_ci(a, b, B=BOOT, seed=42):
    """Cohen's d 与均值差的 95% percentile bootstrap CI。"""
    rng = np.random.default_rng(seed)
    ds, diffs = [], []
    for _ in range(B):
        aa = rng.choice(a, len(a), replace=True)
        bb = rng.choice(b, len(b), replace=True)
        d = cohens_d(aa, bb)
        if d is not None and math.isfinite(d):
            ds.append(d)
            diffs.append(np.mean(aa) - np.mean(bb))
    if len(ds) < 100:
        return None, None
    return ([r(np.percentile(ds, 2.5)), r(np.percentile(ds, 97.5))],
            [r(np.percentile(diffs, 2.5)), r(np.percentile(diffs, 97.5))])


def binary_test(g1, g2, present):
    """Fisher exact + odds ratio（零格用 Haldane 0.5 校正）+ 95% CI。"""
    a = int(np.sum(g1 == present)); b = len(g1) - a
    c = int(np.sum(g2 == present)); d = len(g2) - c
    table = [[a, b], [c, d]]
    try:
        _, p = stats.fisher_exact(table)
    except Exception:
        p = None
    aa, bb, cc, dd = (a, b, c, d) if min(a, b, c, d) > 0 else (a + 0.5, b + 0.5, c + 0.5, d + 0.5)
    odds = (aa * dd) / (bb * cc)
    se = math.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
    return {"table": table, "p": r(p, 6), "odds_ratio": r(odds),
            "or_ci95": [r(math.exp(math.log(odds) - 1.96 * se)), r(math.exp(math.log(odds) + 1.96 * se))]}


def tost(a, b, delta=BOUND, alpha=ALPHA):
    """双单侧等效检验（TOST）：两单侧 p 均 < alpha 才能宣称等效。"""
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = np.mean(a), np.mean(b)
    v1, v2 = np.var(a, ddof=1) / len(a), np.var(b, ddof=1) / len(b)
    se = math.sqrt(v1 + v2)
    if se == 0:
        return None
    df = (v1 + v2) ** 2 / (v1 ** 2 / (len(a) - 1) + v2 ** 2 / (len(b) - 1))
    diff = ma - mb
    t_low = (diff + delta) / se   # H0: diff <= -delta
    t_high = (diff - delta) / se  # H0: diff >= +delta
    p_low, p_high = stats.t.sf(t_low, df), stats.t.cdf(t_high, df)
    p = max(p_low, p_high)
    return {"bound": delta, "diff": r(diff), "df": r(df, 2),
            "t_low": r(t_low), "p_low": r(p_low, 6), "t_high": r(t_high), "p_high": r(p_high, 6),
            "tost_p": r(p, 6), "equivalent": bool(p < alpha)}


def required_n(a, b, delta=BOUND, alpha=ALPHA, power=POWER):
    """用当前 observed 方差复核 power=0.95 每组所需 n（优势检验 + 等效检验）。"""
    sp = pooled_sd(a, b)
    if sp is None or sp == 0:
        return {"pooled_sd": r(sp), "note": "方差为0或样本不足，无法用方差法估计 n"}
    d = (np.mean(a) - np.mean(b)) / sp
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    n_sup = math.ceil(2 * ((za + zb) / abs(d)) ** 2) if abs(d) > 1e-12 else None
    za1 = stats.norm.ppf(1 - alpha)  # TOST 单侧
    n_eq = math.ceil(2 * sp ** 2 * ((za1 + zb) / delta) ** 2)
    return {"pooled_sd": r(sp), "observed_d": r(d),
            "n_per_group_superiority": n_sup, "n_per_group_equivalence": n_eq,
            "current_n": [len(a), len(b)]}


def main_pair(rows, g1, g2):
    a, b = series(rows, g1, 'tool_calls'), series(rows, g2, 'tool_calls')
    sh = {}
    for g, x in ((g1, a), (g2, b)):
        if len(x) >= 3:
            w, p = stats.shapiro(x)
            sh[g] = {"W": r(w), "p": r(p, 6)}
        else:
            sh[g] = None  # n<3 无法做 Shapiro-Wilk
    normal = all(sh[g] is not None and sh[g]["p"] >= ALPHA for g in (g1, g2))
    primary = "welch_t" if normal else "mannwhitney_u"
    # 两种检验都算，避免选择性报告
    try:
        tt = stats.ttest_ind(a, b, equal_var=False)
        welch = {"t": r(tt.statistic), "p": r(tt.pvalue, 6)}
    except Exception:
        welch = {"t": None, "p": None}
    try:
        mw = stats.mannwhitneyu(a, b, alternative='two-sided')
        U = float(mw.statistic)
        mwu = {"U": r(U), "p": r(mw.pvalue, 6)}
    except Exception:
        U, mwu = None, {"U": None, "p": None}
    rb = 2 * U / (len(a) * len(b)) - 1 if U is not None else None
    ci_d, ci_diff = bootstrap_ci(a, b)
    p_primary = welch["p"] if primary == "welch_t" else mwu["p"]
    t_sign = 1 if (welch["t"] or 0) > 0 else (-1 if (welch["t"] or 0) < 0 else 0)
    rb_sign = 1 if (rb or 0) > 0 else (-1 if (rb or 0) < 0 else 0)
    consistent = t_sign != 0 and t_sign == rb_sign
    return {
        "g1": g1, "g2": g2, "n": [len(a), len(b)],
        "mean": [r(np.mean(a)), r(np.mean(b))], "diff": r(np.mean(a) - np.mean(b)),
        "shapiro": sh, "both_normal": bool(normal), "primary_test": primary,
        "welch": welch, "mannwhitney_u": mwu, "p_primary": p_primary,
        "effect": {"cohens_d": r(cohens_d(a, b)), "rank_biserial": r(rb),
                   "bootstrap_ci_d95": ci_d, "bootstrap_ci_diff95": ci_diff},
        "direction_consistent": bool(consistent),
        "tost": tost(a, b), "n_required": required_n(a, b),
        "binary": {"hard_stop": binary_test(series(rows, g1, 'hard_stop'), series(rows, g2, 'hard_stop'), 1),
                   "completed": binary_test(series(rows, g1, 'completed'), series(rows, g2, 'completed'), True)},
    }


def verdict_of(pair, p_holm):
    """判优 / 等效 / 不确定。p 用 Holm 校正值做决策。"""
    g1, g2, diff = pair["g1"], pair["g2"], pair["diff"]
    winner = g1 if (diff or 0) < 0 else g2  # tool_calls 越少越优
    t, nreq = pair["tost"], pair["n_required"]
    if p_holm is not None and p_holm < ALPHA:
        if pair["direction_consistent"]:
            return {"label": "判优", "winner": winner, "better_direction": "tool_calls 更少",
                    "reason": "校正后显著且两检验方向一致", "p_holm": r(p_holm, 6)}
        return {"label": "不确定", "winner": None, "p_holm": r(p_holm, 6), "n_required": nreq,
                "reason": "显著但 Welch 与 Mann-Whitney 效应方向不一致"}
    if t and t["equivalent"]:
        return {"label": "等效", "winner": None, "p_holm": r(p_holm, 6), "tost_p": t["tost_p"],
                "reason": "p>0.05 但 TOST 通过（均值差落在 ±1 tool_call 内）"}
    return {"label": "不确定", "winner": None, "p_holm": r(p_holm, 6), "n_required": nreq,
            "reason": "不显著且 TOST 未通过，既不能判优也不能宣称等效"}


def build_report(src, rows):
    pairs = [main_pair(rows, g1, g2) for g1, g2 in PAIRS]
    hm = holm([p["p_primary"] for p in pairs])
    hh = holm([p["binary"]["hard_stop"]["p"] for p in pairs])
    hc = holm([p["binary"]["completed"]["p"] for p in pairs])
    for p, pm, ph, pc in zip(pairs, hm, hh, hc):
        p["p_holm"] = r(pm, 6)
        p["binary"]["hard_stop"]["p_holm"] = r(ph, 6)
        p["binary"]["completed"]["p_holm"] = r(pc, 6)
        p["verdict"] = verdict_of(p, pm)
    return {"meta": {"source": src, "alpha": ALPHA, "power": POWER, "equivalence_bound": BOUND,
                     "bootstrap_resamples": BOOT,
                     "groups_n": {g: len(series(rows, g, 'tool_calls')) for g in GROUPS},
                     "note": "p_primary 为主检验原始 p；判定用 Holm 校正后的 p_holm"},
            "pairs": pairs}


def to_text(res):
    L = ["=== A/B 判优严格统计检验 ===",
         f"alpha={ALPHA} power={POWER} 等效边界=±{BOUND} tool_call bootstrap={BOOT}",
         "样本: " + ", ".join(f"{g}={n}" for g, n in res["meta"]["groups_n"].items()),
         "=" * 68]
    for p in res["pairs"]:
        w, m, e, t, n = p["welch"], p["mannwhitney_u"], p["effect"], p["tost"], p["n_required"]
        sh = ", ".join(f"{g}:W={s['W']},p={s['p']}" if s else f"{g}:n<3不可检验"
                       for g, s in p["shapiro"].items())
        L += [f"\n### {p['g1']} vs {p['g2']}  (n={p['n'][0]} vs {p['n'][1]})",
              f"  主指标均值: {p['mean'][0]} vs {p['mean'][1]}  差={p['diff']}",
              f"  Shapiro: {sh}  -> 两者正态={p['both_normal']} 主检验={p['primary_test']}",
              f"  Welch t={w['t']} p={w['p']} | MannWhitney U={m['U']} p={m['p']} [两检验均报]",
              f"  主检验={p['primary_test']} p={p['p_primary']} -> Holm校正 p={p['p_holm']} [判定用校正p]",
              f"  效应量: Cohen d={e['cohens_d']} (95%CI {e['bootstrap_ci_d95']}) "
              f"rank-biserial={e['rank_biserial']} (均值差95%CI {e['bootstrap_ci_diff95']})",
              f"  TOST: {'可宣称等效' if t and t['equivalent'] else '未通过'} "
              f"(p={t['tost_p'] if t else None}, 差={t['diff'] if t else None}) 方向一致={p['direction_consistent']}"]
        for k, lab in (('hard_stop', 'hard_stop有/无'), ('completed', 'completed成功/失败')):
            b = p["binary"][k]
            L.append(f"  Fisher[{lab}]: table={b['table']} OR={b['odds_ratio']} 95%CI={b['or_ci95']} "
                     f"p={b['p']} (Holm p={b['p_holm']})")
        v = p["verdict"]
        L.append(f"  判定: {v['label']}" + (f" 优者={v['winner']}" if v.get('winner') else "")
                 + f"  [{v['reason']}]")
        if n.get("n_per_group_superiority") or n.get("n_per_group_equivalence"):
            L.append(f"  样本复核(power=0.95, 当前方差): d={n.get('observed_d')} "
                     f"判优需 n/组={n.get('n_per_group_superiority')} "
                     f"等效需 n/组={n.get('n_per_group_equivalence')} (当前 {n.get('current_n')})")
    L.append("\n注: 小样本下 Shapiro 检验力低、方差不稳；'不确定' 表示证据不足，需按上面 n 继续采样。")
    return "\n".join(L)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    out = sys.argv[2] if len(sys.argv) > 2 else OUT
    rows = json.load(open(src, encoding='utf-8'))
    res = build_report(src, rows)
    text = to_text(res)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(out.replace('.json', '.txt'), 'w', encoding='utf-8') as f:
        f.write(text + "\n")
    print(text)
    print(f"\n[已写出] {out} 与 {out.replace('.json', '.txt')}")
