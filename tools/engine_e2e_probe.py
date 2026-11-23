# -*- coding: utf-8 -*-
"""端到端引擎 A/B 探针（2026-11-23）

背景：裸 decode t/s 是误导性指标（已证伪 cpu-share=1.0：decode +37% 但端到端慢 2.4×）。
本脚本模拟 harness 真实模式：多轮对话，每轮有增量 prefill + 生成，测**总墙钟**。

用法: python tools/engine_e2e_probe.py <port> <label> <runs> <warm>
  port   : 引擎端口（8081）
  label  : 结果标签（如 b12244 / master）
  runs   : 正式次数（用户要求充分，>=5）
  warm   : warmup 次数（>=2，moe-cache 需按需增长）

输出 JSON 到 tools/_e2e_<label>.json，含每次墙钟、prefill/decode t/s、显存。
"""
import json, urllib.request, subprocess, sys, time, statistics
from pathlib import Path

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
LABEL = sys.argv[2] if len(sys.argv) > 2 else 'test'
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
WARM = int(sys.argv[4]) if len(sys.argv) > 4 else 2
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
URL = f'http://127.0.0.1:{PORT}/v1/completions'

# 模拟 harness：首轮 20K 上下文，后续每轮追加 1K 增量（对应注入/工具结果）
FILLER = ("混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，"
          "预填充瓶颈在 GPU 矩阵乘；显存里缓存热点专家可以显著提升解码吞吐。" * 40)
def make_prompt(chars):
    return (FILLER * (chars // len(FILLER) + 1))[:chars] + "\n\n请用三句话总结。"

def one_run(tag):
    """一次端到端：4 轮对话，20K + 1K×3 增量，每轮生成 96 tokens"""
    t_start = time.perf_counter()
    rows = []
    ctx = make_prompt(20000)
    for step in range(4):
        if step > 0:
            ctx += '\n\n' + make_prompt(1000)
        body = {'model': MODEL, 'prompt': ctx, 'max_tokens': 96, 'min_tokens': 96,
                'temperature': 0.7, 'top_p': 0.95, 'stream': False, 'cache_prompt': True}
        req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        dt = time.perf_counter() - t0
        tm = r.get('timings', {})
        rows.append({'step': step, 'wall_s': round(dt, 3),
                     'prompt_tokens': r['usage']['prompt_tokens'],
                     'prefill_tps': round(tm.get('prompt_per_second', 0), 1),
                     'decode_tps': round(tm.get('predicted_per_second', 0), 2),
                     'out_tokens': r['usage']['completion_tokens']})
    total = time.perf_counter() - t_start
    vr = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,power.draw',
                         '--format=csv,noheader'], capture_output=True, text=True).stdout.strip()
    print(f'{LABEL:12} {tag:8} total={total:6.2f}s | ' +
          ' | '.join(f's{r["step"]}:{r["wall_s"]:.1f}s/{r["out_tokens"]}tok/{r["decode_tps"]:.1f}t' for r in rows) +
          f' | {vr}', flush=True)
    return {'total_wall_s': round(total, 3), 'steps': rows, 'vram': vr}

results = []
for k in range(-WARM, RUNS):
    results.append(one_run('warmup' if k < 0 else f'run{k}'))

formal = results[WARM:]
totals = [r['total_wall_s'] for r in formal]
out = {'label': LABEL, 'runs': RUNS, 'warm': WARM,
       'totals': totals, 'median_s': round(statistics.median(totals), 3),
       'mean_s': round(statistics.mean(totals), 3),
       'stdev_s': round(statistics.stdev(totals), 3) if len(totals) > 1 else 0,
       'all': results}
p = Path(f'D:/Brain/_cleanup_20261118/e2e_{LABEL}.json')
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'\n=== {LABEL}: median={out["median_s"]}s mean={out["mean_s"]}s stdev={out["stdev_s"]}s ===')
