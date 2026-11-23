# -*- coding: utf-8 -*-
"""KV cache q4_0 vs q8_0 对长上下文质量的影响。
任务：needle-in-haystack（在不同深度插入唯一事实，问出来），检测 DeltaNet 状态漂移。
同时测能否启动 + 显存 + 速度。
"""
import subprocess, time, urllib.request, json, statistics, random, re
from pathlib import Path

LOG = Path('D:/Brain/_cleanup_20261118/kv_cache.log')
def log(m):
    line = f'{time.strftime("%H:%M:%S")} {m}'
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(line + '\n')

EXE = 'D:/llama.cpp/build/bin/llama-server.exe'
PRESET = 'D:/Brain/_cleanup_20261118/preset_A_40_1350.ini'
PORT = 8081
MODEL = 'Qwen3.6-35B-A3B-UD-Q4_K_XL'
_SENTS = [
    "混合专家模型每 token 只激活少数专家，其余权重留在主机内存，解码瓶颈主要在内存带宽和延迟上。",
    "数据按时间顺序逐条记录，每条都包含日期、地点和一类物资编号，便于后续按编号检索与核对。",
    "项目组每周汇总一次进展，把新到达的样本归档到对应城市的分目录，并更新索引表。",
    "演示文稿第三页说明了量化方法：不同张量可以采用不同精度，以在质量和体积之间取得平衡。",
    "运维手册提醒，缓存命中率下降时应先检查路由分布，再考虑扩大缓存容量或调整淘汰策略。",
    "会议纪要里提到，上周完成了引擎升级，新增了对专家卸载场景的若干优化，需要在生产环境复测。",
]
FILLER = ("\n".join(_SENTS)) * 160

# needle：一个独特的编号+地点+颜色，插在不同深度
NEEDLES = [
    ("A7K3-91", "杭州", "青绿色"),
    ("B4M8-27", "成都", "琥珀色"),
    ("C9P2-63", "西安", "深蓝色"),
    ("D2N6-48", "武汉", "金黄色"),
    ("E5R1-74", "南京", "紫罗兰"),
]

def make_prompt(needle, pos_ratio, total_chars=48000):
    code, city, color = needle
    fact = f"【重要记录】编号 {code} 对应的是 {city} 的{color}纪念品，请记住这个对应关系。"
    target = int(total_chars * pos_ratio)
    pre = FILLER[:target]
    post = FILLER[total_chars:]
    return pre + "\n\n" + fact + "\n\n" + post, code, city, color

def wait_health(seconds=300):
    for i in range(seconds):
        try:
            if urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health', timeout=2).status == 200:
                return i + 1
        except Exception: pass
        time.sleep(1)
    return None

def ask(prompt, expect):
    code, city, color = expect
    q = f"\n\n请回答：编号 {code} 对应的是哪个城市的什么颜色纪念品？只回答城市和颜色。"
    body = {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt + q}],
            'temperature': 0.1, 'max_tokens': 1024, 'stream': False}
    req = urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions',
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    msg = r['choices'][0]['message']
    text = msg.get('content') or ''
    ok = (city in text) and (color in text or color.replace('色','') in text)
    return ok, text.strip()[:120], r.get('usage', {})

for label, vtype in [('kv_q4', 'q4_0'), ('kv_q8', 'q8_0')]:
    log(f'=== CELL {label} V={vtype} ===')
    subprocess.run(['taskkill', '/F', '/IM', 'llama-server.exe'], capture_output=True)
    time.sleep(3)
    args = [EXE, '--models-preset', PRESET, '--models-max', '1', '--models-memory-margin', '450',
            '-c', '98304', '-np', '1', '-fa', 'on', '--cache-type-k', 'q8_0', '--cache-type-v', vtype,
            '-t', '6', '-b', '4096', '-ub', '2048', '-lm', 'none',
            '--moe-cache-cpu-share', '1.0', '--port', str(PORT), '--host', '127.0.0.1', '-lv', '4',
            '--spec-type', 'draft-mtp', '--spec-draft-n-max', '5', '--spec-draft-p-min', '0.8',
            '--ctx-checkpoints', '2', '--cache-ram', '0']
    logf = open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', 'w')
    p = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    sec = wait_health()
    log(f'health={sec}s' if sec else 'TIMEOUT')
    if not sec:
        logf.flush()
        for l in open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', errors='replace'):
            if 'error' in l.lower() or 'out of memory' in l.lower():
                log('ERR ' + l.strip()[:180])
        p.kill(); logf.close(); continue
    # 触发加载
    try:
        body = {'model': MODEL, 'prompt': '你好', 'n_predict': 8, 'ignore_eos': True, 'stream': False}
        urllib.request.urlopen(urllib.request.Request(
            f'http://127.0.0.1:{PORT}/completion', data=json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'}), timeout=1200).read()
    except Exception as e:
        log(f'LOAD ERR {e}'); p.kill(); logf.close(); continue
    smi = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader'],
                         capture_output=True, text=True)
    log(f'VRAM_USED {smi.stdout.strip()}')
    logf.flush()
    for l in open(f'D:/Brain/_cleanup_20261118/{label}_srv.log', errors='replace'):
        if 'KV buffer size' in l or 'MoE cache size' in l:
            log('CFG ' + l.strip()[:180])
    # 5 个 needle，不同深度
    ok_n = 0
    for i, needle in enumerate(NEEDLES):
        pos = 0.1 + 0.2 * i  # 0.1, 0.3, 0.5, 0.7, 0.9
        prompt, code, city, color = make_prompt(needle, pos)
        try:
            ok, text, tm = ask(prompt, (code, city, color))
        except Exception as e:
            ok, text, tm = False, f'ERR {type(e).__name__}', {}
        ok_n += ok
        log(f'{label:7} needle@{pos:.1f} {"PASS" if ok else "FAIL"} | {text}')
    log(f'{label:7} NEEDLE {ok_n}/{len(NEEDLES)}')
    p.terminate()
    try: p.wait(timeout=30)
    except Exception: p.kill()
    logf.close()
    time.sleep(3)
log('=== KV CACHE DONE ===')
