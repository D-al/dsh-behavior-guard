#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""工具面审计：统计一次会话里「暴露了多少工具 / 各自被调用多少次 / schema 占多少 token」。
用法: python bench/tool_audit.py [bench/_cur8.jsonl]
"""
import collections
import json
import sys


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "bench/_cur8.jsonl"
    rows = load(path)

    hdr = None
    for r in rows:
        if r.get("type") == "request/header":
            hdr = r["data"].get("header")
            break
    if not hdr or not hdr.get("tools"):
        print("该会话没有记录 tools 定义，无法审计")
        return

    tools = hdr["tools"]
    calls = collections.Counter()
    for r in rows:
        if r.get("type") == "tool/call":
            calls[r["data"].get("name")] += 1

    def size(t):
        d = len(t.get("description") or "")
        p = len(json.dumps(t.get("parameters") or {}, ensure_ascii=False))
        return d, p, d + p

    out = []
    for t in tools:
        name = t.get("name") or "<unnamed>"
        d, p, n = size(t)
        out.append((calls.get(name, 0), name, d, p, n))
    out.sort(reverse=True)

    total = sum(x[4] for x in out)
    zero = [x for x in out if x[0] == 0]
    used = [x for x in out if x[0] > 0]
    total_calls = sum(calls.values())

    print("会话:", path)
    print("暴露工具 %d 个；schema 合计 %d 字符 ≈ %d~%d token"
          % (len(out), total, total // 3, total // 2))
    print("被调用过 %d 个；零调用 %d 个，占 %d 字符 ≈ %d token"
          % (len(used), len(zero), sum(x[4] for x in zero), sum(x[4] for x in zero) // 3))
    if total_calls:
        top5 = sum(x[0] for x in out[:5])
        print("前 5 个工具占调用 %.1f%%（共 %d 次）" % (100 * top5 / total_calls, total_calls))
    print()
    print("%-5s %-30s %7s %8s %8s" % ("调用", "工具名", "描述字", "参数字", "合计字"))
    print("-" * 64)
    for a in out:
        print("%-5d %-30s %7d %8d %8d" % a)
    print()
    print("零调用清单（可考虑按需加载 / 停用）：")
    print("  " + "、".join(x[1] for x in zero))


if __name__ == "__main__":
    main()
