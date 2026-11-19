# -*- coding: utf-8 -*-
"""S1-P2 最小闭环协议：读 evidence bundle → 35B 作 proposer 产候选 → acceptance gate 判定。
本脚本只产 patch 到隔离目录，绝不自动部署（ADR-0015/0018）。
用法:
  D:/Python/python.exe bench/self_harness_proposer.py --dry-run   # 只构造 prompt，不调 LLM
  D:/Python/python.exe bench/self_harness_proposer.py             # 调 8081 产候选
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, r'D:\Brain\publish\dsh-behavior-guard\tools')
from self_harness_gate import accept, surface_check, load_surfaces

BENCH_DIR = os.environ.get('BENCH_DIR') or r'D:\Brain\workspace\bench'
BUNDLE = str(Path(BENCH_DIR) / '_evidence_bundle.json')
OUTDIR = str(Path(BENCH_DIR) / '_self_harness_candidates')
URL = 'http://127.0.0.1:8081/v1/chat/completions'
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'

PROPOSER_SYSTEM = """你是 harness 自改进提案器（proposer）。只拿到弱点证据，不能改模型权重。
规则：
1. 只从白名单 surface 中选一个做最小改动。
2. 输出严格 JSON，允许 decline（证据不足时明确 decline）。
3. 禁止改安全面（权限/L0-L3/verify闸门/GWT/FEP/AGENTS.md）。
4. 一次只提一个候选，并说明它对应哪个失败签名。
输出格式：
{"surface":"<白名单id>","action":"patch|decline","change":"<具体改法，一句话>","rationale":"<对应哪个失败签名>","patch":"<结构化替换，必须是 JSON 字符串>"}
只输出 JSON，不要解释文字。"""


def build_prompt(bundle):
    surfaces = load_surfaces()['editable']
    top = bundle.get('top_actionable', [])[:3]
    protected = bundle.get('protected', {}).get('count', 0)
    return (
        PROPOSER_SYSTEM + '\n\n【可编辑 surface 白名单】\n' +
        '\n'.join(f"- {s['id']} ({s['kind']}): {s['target']}" for s in surfaces) +
        '\n\n【本轮失败签名（按 support×actionability 排序）】\n' +
        '\n'.join(f"- {s['terminal_cause']}: support={s['support']}, mechanism={s['agent_mechanism']}, criticality={s['criticality']}"
                  for s in top) +
        f'\n\n【受保护行为】{protected} 条 recovered_friction，禁止改动会破坏它们的机制。\n' +
        '请提出一个最小候选，或 decline。只输出 JSON。'
    )


def call_llm(prompt):
    body = json.dumps({
        'model': MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        # thinking 模型会把 token 花在 reasoning_content（S5-②/S7 同款坑）：
        # 600 太小导致 content 空 → 提到 1200 并在下方做 reasoning 兜底。
        'max_tokens': 1200, 'temperature': 0.7,
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read().decode())
    msg = d['choices'][0]['message']
    out = msg.get('content') or ''
    if not out:
        out = msg.get('reasoning_content') or ''  # S5-② 同款兜底
    i, j = out.find('{'), out.rfind('}')
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(out[i:j + 1])
    except Exception:
        return None  # 解析失败按设计视为 decline，不崩脚本


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    try:
        bundle = json.load(open(BUNDLE, encoding='utf-8'))
    except Exception as e:
        print(f'evidence bundle 不可读（{e}）— 先跑 weakness_miner.py 生成')
        return
    prompt = build_prompt(bundle)
    if a.dry_run:
        print(prompt)
        return
    cand = call_llm(prompt)
    if not cand:
        print('proposer 返回空/不可解析 JSON → 视为 decline')
        return
    sid = cand.get('surface', '')
    # 面校验覆盖 change + patch 两处（原只校验 change，结构化替换 patch 是真正的写回内容）
    chk = surface_check(sid, [cand.get('change', ''), cand.get('patch', '')])
    result = {
        'proposer_output': cand,
        'surface_check': chk,
        'gate': {'decision': 'no-op', 'reason': 'evaluation not run in this protocol script'},
        'note': '本脚本只产候选与面校验；双 split 评测需接 self_harness_eval.py（P3 后才常态化）。',
    }
    os.makedirs(OUTDIR, exist_ok=True)
    # uuid 命名，避免 candidate-N 的 TOCTOU 竞态与目录污染导致的跳号
    from uuid import uuid4
    p = os.path.join(OUTDIR, f"candidate-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}.json")
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1200])
    print(f'written: {p}')


if __name__ == '__main__':
    main()
