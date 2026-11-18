# -*- coding: utf-8 -*-
"""速度探针：用 /v1/completions（不走 chat 模板，token 数可控）测 prefill / decode。

用法: python bench/speed_probe.py [档位] [重复次数]
档位: 2k | 20k | 60k | all（默认 all）
输出: prompt_tok / prefill t/s / decode t/s / 显存余量 / 进程 RSS 无关
"""
import json, urllib.request, subprocess, sys, time

LEVELS = {"2k": 2000, "20k": 20000, "60k": 60000}
FILLER = ("混合专家模型每 token 只激活少数专家，其余权重留在内存；解码瓶颈在内存延迟，"
          "预填充瓶颈在 GPU 矩阵乘；显存里缓存热点专家可以显著提升解码吞吐。" * 40)

def build_prompt(target_chars):
    return (FILLER * (target_chars // len(FILLER) + 1))[:target_chars] + "\n\n请用三句话总结。"

def vram():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,power.draw,clocks.sm",
                          "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    return out

def run(name, chars, runs, warm=0):
    for k in range(-warm, runs):
        tag = "warmup" if k < 0 else "run%d" % k
        body = {"model": "Qwen3.6-35B-A3B-UD-Q4_K_XL", "prompt": build_prompt(chars),
                "max_tokens": 256, "temperature": 0.6, "top_p": 0.95,
                "stream": False, "cache_prompt": False}
        req = urllib.request.Request("http://127.0.0.1:8081/v1/completions",
                                     data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        t0 = time.time()
        r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        dt = time.time() - t0
        t = r.get("timings", {})
        print("%-4s %-6s prompt=%d prefill=%6.0f t/s decode=%5.2f t/s out=%d total=%5.1fs | %s"
              % (name, tag, r["usage"]["prompt_tokens"], t.get("prompt_per_second", 0),
                 t.get("predicted_per_second", 0), r["usage"]["completion_tokens"], dt, vram()), flush=True)

if __name__ == "__main__":
    levels = sys.argv[1] if len(sys.argv) > 1 else "all"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    warm = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    todo = list(LEVELS.items()) if levels == "all" else [(levels, LEVELS[levels])]
    for name, chars in todo:
        run(name, chars, runs, warm)
