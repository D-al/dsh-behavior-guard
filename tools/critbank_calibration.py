# -*- coding: utf-8 -*-
"""critbank_calibration —— CritBank 校准门禁（CEB 路线，S19，零 LLM）

依据：docs/ROUTE_POSITION_AND_EVOLUTION_20261121.md 的 CEB(arXiv:2607.12397)
- 复合键 (task, state, action) 与本项目 Task/State/Action 同构；
- 每条加 ŷ（hindsight productive 伪标签）+ χ（当初一致性标志）；
- 按 B⁺/B⁻ 正负对照检索，冻结 critic 执行前给 confidence，低置信转人工/重规划。

无金标准时的**代理与数学依据**（必须显式声明，勿当成真值）：
- 本机没有 logprobs（audit_calibrate.py 标注的 🔴R3），也没有逐次 hindsight V=5 投票日志。
- 可用证据只有 crit_decay.py 的侧表 _critbank_state.json：每条 {helpful, harmful} 计数。
  设单次注入"事后 productive"为 Bernoulli(p)，h/a 是 n=h+a 次独立观测：
  * ŷ = h/n —— p 的 MLE（plug-in 估计），作为"预测置信"的经验代理；
  * χ_score = 2ŷ-1 = (h-a)/n —— 方向一致性强度 ∈[-1,1]；χ = sign(h-a) ∈{+1,0,-1}；
  * confidence = |2ŷ-1| —— 交给冻结 critic 的置信度代理（|·| 只取强度、不含方向）；
  * brier_const = ŷ(1-ŷ) —— 常值预测器 ŷ 的期望 Brier（下界），0.25 为随机基线。
- B⁺/B⁻ 分组：逐次日志存在时用 productive 标签；否则用聚合代理 χ>0 / χ<0（χ=0 中性排除）。
  ⚠ 聚合模式下 AUC 检验的是"bank 群体中置信强度是否与方向一致"，是回顾性一致性检查，
    不是独立前瞻预测（前瞻校准需逐次 productive 标签，当前缺 → N/M，不造数）。
- 若提供逐次日志 [{id, confidence, productive}]，则 Brier/ECE/AUC/χ 差异均为真实非循环指标。

用法:
  python tools/critbank_calibration.py                 # 人类可读报告
  python tools/critbank_calibration.py --json          # 结构化报告（含每条 score / 阈值判定）
  python tools/critbank_calibration.py --json --hits PATH  # 用逐次命中日志算真校准指标
  # 环境变量：BENCH_DIR（侧表目录）、CRITBANK_BANK / CRITBANK_STATE（路径覆盖）

约定：进程退出码 0 = 工具正常执行；门禁结论看输出里的 verdict / gate_pass。
      verdict='N/M' 表示证据不足，按本项目 noise_floor() 惯例不判过、不造数。
"""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
BANK_DEFAULT = ROOT / 'config' / 'critbank.json'
STATE_DEFAULT = Path(BENCH_DIR) / '_critbank_state.json'

# 门禁阈值（可由 CLI 覆盖；依据见模块 docstring）
MIN_EVIDENTRIES = 2      # 至少 2 条有 hindsight 证据的条目
MIN_AUC = 0.60           # B⁺/B⁻ 区分度（随机=0.5）
MIN_CONFIDENCE = 0.20    # 单条 confidence 低于此值 → 转人工/重规划

MATH_BASIS = (
    '无 logprobs/无 V=5 hindsight 投票日志，故用 crit_decay 侧表 helpful/harmful 做代理：'
    'ŷ=h/(h+a) 为 Bernoulli(p) 的 MLE；χ_score=2ŷ-1=(h-a)/n，χ=sign(h-a)；'
    'confidence=|2ŷ-1|；brier_const=ŷ(1-ŷ)（常值预测器下界，0.25 为随机基线）。'
    'B⁺/B⁻ 由 χ>0/χ<0（聚合代理）或 productive 标签（逐次日志）划分。'
    '聚合模式 AUC 为回顾性一致性检查，前瞻校准须逐次标签（缺则 N/M，不造数）。'
)


# ---------------------------------------------------------------------------
# 纯函数：可单测，不读写任何正式产物
# ---------------------------------------------------------------------------

def load_bank(path=None):
    """读 config/critbank.json（9 条）；文件缺失/非法 → []，不造数。"""
    p = Path(path) if path else BANK_DEFAULT
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return obj if isinstance(obj, list) else []


def load_state(path=None):
    """读 _critbank_state.json（crit_decay.py 的侧表）；缺失/非法 → {}。"""
    p = Path(path) if path else STATE_DEFAULT
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return obj if isinstance(obj, dict) else {}


def load_hits(path=None):
    """读逐次命中日志 [{id, confidence, productive}]；缺失 → []。"""
    if not path:
        return []
    try:
        obj = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    if isinstance(obj, dict):
        obj = obj.get('hits', [])
    if not isinstance(obj, list):
        return []
    out = []
    for h in obj:
        if not isinstance(h, dict):
            continue
        try:
            c = float(h['confidence'])
            y = bool(h['productive'])
        except (KeyError, TypeError, ValueError):
            continue
        out.append({'id': h.get('id'), 'confidence': c, 'productive': y})
    return out


def counters(state_row):
    """从状态行取 (helpful, harmful)，负数按 0、非数按 0。"""
    row = state_row if isinstance(state_row, dict) else {}
    try:
        h = max(0, int(row.get('helpful') or 0))
    except (TypeError, ValueError):
        h = 0
    try:
        a = max(0, int(row.get('harmful') or 0))
    except (TypeError, ValueError):
        a = 0
    return h, a


def proxy_from_counters(helpful, harmful):
    """ŷ/χ 聚合代理；h+a==0 → None（N/M，不造数）。"""
    n = helpful + harmful
    if n <= 0:
        return None
    y_hat = helpful / n
    chi_score = 2 * y_hat - 1.0
    chi = 1 if chi_score > 0 else (-1 if chi_score < 0 else 0)
    return {
        'n': n, 'helpful': helpful, 'harmful': harmful,
        'y_hat': round(y_hat, 4),
        'chi': chi, 'chi_score': round(chi_score, 4),
        'confidence': round(abs(chi_score), 4),
        'brier_const': round(y_hat * (1.0 - y_hat), 4),
    }


def _pairs(pairs):
    """规整 [(confidence, productive_bool)]；非法输入丢弃。"""
    out = []
    for item in pairs or []:
        try:
            p, y = item[0], bool(item[1])
            p = float(p)
        except (TypeError, ValueError, IndexError):
            continue
        if 0.0 <= p <= 1.0:
            out.append((p, y))
    return out


def brier_score(pairs):
    """Brier = mean((p-y)^2)，p∈[0,1], y∈{0,1}；无样本 → None。"""
    vals = _pairs(pairs)
    if not vals:
        return None
    return sum((p - (1 if y else 0)) ** 2 for p, y in vals) / len(vals)


def ece(pairs, bins=10):
    """ECE = Σ_b (|B_b|/N)·|mean(p_b) - mean(y_b)|；等宽分箱，无样本 → None。"""
    vals = _pairs(pairs)
    if not vals:
        return None
    groups = defaultdict(list)
    for p, y in vals:
        b = min(int(p * bins), bins - 1)  # p==1 落入末箱
        groups[b].append((p, 1 if y else 0))
    n = len(vals)
    total = 0.0
    for g in groups.values():
        mp = sum(p for p, _ in g) / len(g)
        my = sum(y for _, y in g) / len(g)
        total += (len(g) / n) * abs(mp - my)
    return total


def auc(pairs):
    """Mann-Whitney U / (n_pos·n_neg) = P(p+>p-) + 0.5·P(tie)；缺任一类 → None（N/M）。"""
    vals = _pairs(pairs)
    pos = [p for p, y in vals if y]
    neg = [p for p, y in vals if not y]
    if not pos or not neg:
        return None
    wins = 0.0
    for a in pos:
        for b in neg:
            wins += 1.0 if a > b else (0.5 if a == b else 0.0)
    return wins / (len(pos) * len(neg))


def chi_discrimination(pairs):
    """χ 区分度 = mean(confidence | B+) - mean(confidence | B-)；缺任一类 → None（N/M）。"""
    vals = _pairs(pairs)
    pos = [p for p, y in vals if y]
    neg = [p for p, y in vals if not y]
    if not pos or not neg:
        return None
    return sum(pos) / len(pos) - sum(neg) / len(neg)


# ---------------------------------------------------------------------------
# 报告组装
# ---------------------------------------------------------------------------

def build_report(bank, state, hits=None, min_entries=MIN_EVIDENTRIES,
                 min_auc=MIN_AUC, min_conf=MIN_CONFIDENCE):
    """组装结构化校准报告；不写文件，只返回 dict。"""
    entries, agg_pairs = [], []
    for c in bank or []:
        cid = c.get('id', '?') if isinstance(c, dict) else '?'
        h, a = counters(state.get(cid))
        pr = proxy_from_counters(h, a)
        if pr is None:
            entries.append({
                'id': cid, 'tags': c.get('tags', []) if isinstance(c, dict) else [],
                'sufficient': False, 'score': None, 'pass': None,
                'reason': '无 hindsight 证据（helpful+harmful=0）',
            })
            continue
        pr.update({
            'id': cid,
            'tags': c.get('tags', []) if isinstance(c, dict) else [],
            'sufficient': True,
            'score': pr['confidence'],
            'pass': pr['confidence'] >= min_conf,
            'threshold': min_conf,
        })
        entries.append(pr)
        agg_pairs.append((pr['confidence'], pr['chi'] > 0))

    hit_pairs = [(h['confidence'], h['productive']) for h in (hits or [])]
    is_hit_log = bool(hit_pairs)
    pairs = hit_pairs if is_hit_log else agg_pairs

    n_ev = sum(1 for e in entries if e['sufficient'])
    n_pos = sum(1 for _, y in pairs if y)
    n_neg = sum(1 for _, y in pairs if not y)
    auc_v = auc(pairs)
    sep = chi_discrimination(pairs)

    cal = {
        'source': 'hit_log' if is_hit_log else 'aggregate_proxy',
        'B+': n_pos, 'B-': n_neg,
        'auc': round(auc_v, 4) if auc_v is not None else None,
        'chi_discrimination': round(sep, 4) if sep is not None else None,
        'brier': round(brier_score(pairs), 4) if is_hit_log and brier_score(pairs) is not None else None,
        'ece': round(ece(pairs), 4) if is_hit_log and ece(pairs) is not None else None,
        'brier_const_mean': None,
    }
    evidenced = [e for e in entries if e['sufficient']]
    if evidenced:
        cal['brier_const_mean'] = round(
            sum(e['n'] * e['brier_const'] for e in evidenced) /
            sum(e['n'] for e in evidenced), 4)

    reasons = []
    if n_ev < min_entries:
        reasons.append(f'有效条目 {n_ev} < {min_entries}')
    if n_pos == 0 or n_neg == 0:
        reasons.append(f'B+/B- 不双全（B+={n_pos}, B-={n_neg}）')
    if auc_v is None or sep is None:
        reasons.append('区分度不可计算')

    if reasons:
        verdict, insufficient = 'N/M', True
        why = '；'.join(reasons) + '——不造数，按 noise_floor 惯例不判过'
    elif auc_v >= min_auc and sep > 0:
        verdict, insufficient = 'CALIBRATED', False
        why = f'AUC={auc_v:.3f}≥{min_auc}，χ 差异={sep:+.3f}>0'
    else:
        verdict, insufficient = 'UNCALIBRATED', False
        why = f'AUC={auc_v:.3f}<{min_auc} 或 χ 差异={sep:+.3f}≤0'

    return {
        'tool': 'critbank_calibration',
        'n_entries': len(bank or []),
        'n_evidenced': n_ev,
        'thresholds': {'min_entries': min_entries, 'min_auc': min_auc,
                       'min_confidence': min_conf},
        'verdict': verdict,
        'insufficient': insufficient,
        'gate_pass': (not insufficient) and verdict == 'CALIBRATED',
        'why': why,
        'math_basis': MATH_BASIS,
        'calibration': cal,
        'entries': entries,
    }


def render_text(rep):
    """人类可读报告。"""
    lines = [
        f'CritBank 校准门禁：{rep["verdict"]}',
        f'  条目 {rep["n_entries"]}，有 hindsight 证据 {rep["n_evidenced"]}',
        f'  {rep["why"]}',
    ]
    cal = rep['calibration']
    lines.append(f'  证据来源 {cal["source"]} | B+={cal["B+"]} B-={cal["B-"]}')
    lines.append(f'  AUC={cal["auc"] if cal["auc"] is not None else "N/M"}，'
                 f'χ 差异={cal["chi_discrimination"] if cal["chi_discrimination"] is not None else "N/M"}，'
                 f'Brier={cal["brier"] if cal["brier"] is not None else "N/M"}，'
                 f'ECE={cal["ece"] if cal["ece"] is not None else "N/M"}，'
                 f'常值 Brier 下界均值={cal["brier_const_mean"]}')
    lines.append('')
    lines.append(f'{"ID":<8} {"n":>4} {"ŷ":>7} {"χ":>3} {"conf":>7} {"阈值":>6} {"判定":<8}')
    lines.append('-' * 52)
    for e in rep['entries']:
        if not e['sufficient']:
            lines.append(f'{e["id"]:<8} {"-":>4} {"-":>7} {"-":>3} {"-":>7} {"-":>6} {"N/M":<8} 无 hindsight 证据')
        else:
            lines.append(f'{e["id"]:<8} {e["n"]:>4} {e["y_hat"]:>7.3f} {e["chi"]:>3} '
                         f'{e["confidence"]:>7.3f} {e["threshold"]:>6.2f} '
                         f'{"PASS" if e["pass"] else "LOW":<8}')
    lines.append('')
    lines.append('代理说明：' + rep['math_basis'])
    lines.append('注：退出码 0 仅表示工具正常执行；门禁结论看 verdict / gate_pass。')
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description='CritBank 校准门禁（CEB / S19）')
    ap.add_argument('--json', action='store_true', help='输出结构化 JSON')
    ap.add_argument('--bank', help='覆盖 critbank.json 路径')
    ap.add_argument('--state', help='覆盖 _critbank_state.json 路径')
    ap.add_argument('--hits', help='逐次命中日志路径 [{id,confidence,productive}]')
    ap.add_argument('--min-auc', type=float, default=MIN_AUC)
    ap.add_argument('--min-confidence', type=float, default=MIN_CONFIDENCE)
    args = ap.parse_args(argv)

    rep = build_report(
        load_bank(args.bank), load_state(args.state), load_hits(args.hits),
        min_auc=args.min_auc, min_conf=args.min_confidence,
    )
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(render_text(rep))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
