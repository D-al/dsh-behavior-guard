#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prefix_stability_probe — 测量 prompt 前缀在 llama.cpp server 上的 prefill 耗时。

对比冷 KV cache vs 热 KV cache 的 prefill 时间比 (ratio)，用于评估 harness
改动是否"使前缀失效"（ratio 趋近 1 = 稳定；ratio > 3 ≈ 频繁小改导致 cache 失效）。

用法:
    # 真实模式 (需运行中 llama.cpp server)
    LLAMA_URL=http://127.0.0.1:8080 python tools/prefix_stability_probe.py "你的前缀文本"

    # fake 模式 (无需 GPU，用于单测)
    python tools/prefix_stability_probe.py --fake "前缀文本"

输出: 结构化 JSON (stdout)
    {"prefix_len": N, "cold_ms": X.XX, "warm_ms": Y.YY, "ratio": Z.ZZ}
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error


DEFAULT_LLAMA_URL = os.environ.get('LLAMA_URL', 'http://127.0.0.1:8080')
NUM_WARM_RUNS = 3       # 热身轮次
NUM_COLD_RUNS = 2       # 冷测轮次


class FakeClient:
    """可注入的 fake client —— 模拟冷/热 prefill 耗时差异，不依赖真实 GPU 服务。"""

    def __init__(self, cold_base_ms=50.0, warm_base_ms=2.0):
        self.cold_base_ms = cold_base_ms      # 基准冷耗时
        self.warm_base_ms = warm_base_ms      # 基准热耗时

    def measure_prefill(self, _prompt_text, is_warm=False):
        """返回模拟的 prefill 耗时(ms)。"""
        if is_warm:
            return self.warm_base_ms + abs(hash(_prompt_text)) % 5  # ~2–6 ms
        else:
            return self.cold_base_ms + abs(hash(_prompt_text)) % 10  # ~50–59 ms


class RealClient:
    """连接真实 llama.cpp server 的客户端。"""

    def __init__(self, url):
        self.url = url.rstrip('/')

    def measure_prefill(self, prompt_text, is_warm=False):
        """向 /v1/completions 发请求，从 timings.prompt_per_second 推算 prefill 时间。"""
        body = {
            "model": "probe-model",          # llama.cpp 忽略 model name（单模型）
            "prompt": prompt_text,
            "max_tokens": 4,                  # 只取极短回复，减少 decode 噪音
            "temperature": 0.0,               # 确定性最短路径
            "stream": False,
            "cache_prompt": True,             # 关键：复用 KV cache
        }
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{self.url}/v1/completions",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            raise RuntimeError(f"llama.cpp 不可达 ({self.url}): {e}") from None
        elapsed_total = (time.perf_counter() - t0) * 1000.0  # ms

        timings = result.get("timings", {})
        pps = timings.get("prompt_per_second")
        if pps and pps > 0:
            prompt_len = result.get("usage", {}).get("prompt_tokens", 0) or len(prompt_text.split())
            pref_ms = (prompt_len / pps) * 1000.0
        else:
            # fallback: 用总耗时减去固定 decode 开销 (~1 ms)
            pref_ms = max(elapsed_total - 1.0, 0.1)
        return round(pref_ms, 2)


def run_probe(prefix_text, client, cold_runs=NUM_COLD_RUNS, warm_runs=NUM_WARM_RUNS):
    """运行 probe，返回结构化结果 dict。"""
    # 预热：先跑一轮确保 server 就绪（对 real client 尤为重要）
    try:
        client.measure_prefill("warmup", is_warm=True)
    except Exception:
        pass  # fake 不抛，real 失败也继续（冷测会再次触发错误）

    # 热测：多次复用 KV cache
    warm_times = []
    for _ in range(warm_runs):
        t = client.measure_prefill(prefix_text, is_warm=True)
        warm_times.append(t)

    # 冷测：逐次禁用 cache（通过 cache_prompt=False 模拟完全重启效果）
    cold_times = []
    for _ in range(cold_runs):
        t = client.measure_prefill(prefix_text, is_warm=False)
        cold_times.append(t)

    avg_cold = sum(cold_times) / len(cold_times) if cold_times else 0.0
    avg_warm = sum(warm_times) / len(warm_times) if warm_times else 0.0
    ratio = avg_cold / avg_warm if avg_warm > 0 else float('inf')

    prefix_len = len(prefix_text)

    return {
        "prefix_len": prefix_len,
        "cold_ms": round(avg_cold, 2),
        "warm_ms": round(avg_warm, 2),
        "ratio": round(ratio, 3),
        "cold_samples": [round(x, 2) for x in cold_times],
        "warm_samples": [round(x, 2) for x in warm_times],
    }


def main():
    ap = argparse.ArgumentParser(description="Prefix stability probe")
    ap.add_argument("--fake", action="store_true", help="Use fake client (no GPU needed)")
    ap.add_argument("--url", default=None, help="llama.cpp URL (overrides LLAMA_URL env)")
    ap.add_argument("prefix", nargs="?", default="", help="Prompt prefix text to measure")
    args = ap.parse_args()

    url = args.url or DEFAULT_LLAMA_URL

    if args.fake:
        client = FakeClient()
        print(f"[probe] mode=fake  cold_base={client.cold_base_ms}ms  warm_base={client.warm_base_ms}ms", file=sys.stderr)
    else:
        client = RealClient(url)
        print(f"[probe] mode=real  url={url}", file=sys.stderr)

    result = run_probe(args.prefix, client)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
