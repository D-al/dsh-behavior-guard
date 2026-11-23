# -*- coding: utf-8 -*-
"""工具调用判据基准：21 题，覆盖 5 类。用于 MTP on/off 的质量 A/B 判据。
判据：工具名 + 参数（关键字段）是否正确，以及"不该调用时是否乱调"。
对齐 STRATEGY.md R2 判据独立性：工具选择正确率是对 agent 质量的独立 verify，
不能用 decode t/s 或 PPL 替代（两者对 function-calling 决策失明）。
"""
import json

# 模拟 dsh 的工具集（只给关键字段，够模型决策）
TOOLS = [
    {"type": "function", "function": {
        "name": "read", "description": "读取本地文件的完整内容",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string", "description": "绝对路径"}}, "required": ["file_path"]}}},
    {"type": "function", "function": {
        "name": "glob", "description": "按通配符查找文件名，返回匹配的路径列表",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "grep", "description": "在文件内容中搜索正则表达式",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string"}, "path": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "write", "description": "把内容写入文件（覆盖）",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["file_path", "content"]}}},
    {"type": "function", "function": {
        "name": "pwsh", "description": "在 PowerShell 中执行命令",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "web_search", "description": "搜索互联网获取实时信息",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
]

# 每题: id, 类别, 用户问句, 期望工具名(None=不该调用), 期望参数检查(dict 或 None), 说明
CASES = [
    # --- A 单选工具（明确）---
    dict(id="a1", cat="single", q="读一下 D:/proj/config.yaml 里写了什么。", tool="read",
         args={"file_path": "D:/proj/config.yaml"}),
    dict(id="a2", cat="single", q="帮我找一下 D:/data 目录下所有 .csv 文件。", tool="glob",
         args={"pattern": "*.csv"}),
    dict(id="a3", cat="single", q="在 D:/src/main.py 里搜一下 'TODO' 出现的位置。", tool="grep",
         args={"pattern": "TODO"}),
    dict(id="a4", cat="single", q="查一下现在英伟达最新的消费级显卡是什么型号。", tool="web_search", args={}),
    dict(id="a5", cat="single", q="看一下当前目录下有哪些文件。", tool="glob", args={}),

    # --- B 不该调用工具（能用常识/上下文回答）---
    dict(id="b1", cat="negative", q="1 加 1 等于几？", tool=None),
    dict(id="b2", cat="negative", q="请把这句话翻译成英文：今天天气很好。", tool=None),
    dict(id="b3", cat="negative", q="Python 里 list 和 tuple 有什么区别？简单说。", tool=None),

    # --- C 参数精确（容易错）---
    dict(id="c1", cat="params", q="把 'hello world' 写到 D:/tmp/out/a.txt 里。", tool="write",
         args={"file_path": "D:/tmp/out/a.txt", "content": "hello world"}),
    dict(id="c2", cat="params", q="在 D:/logs/2026-11 目录下找所有以 error 开头的 .log 文件。",
         tool="glob", args={"pattern": "error*.log"}),
    dict(id="c3", cat="params", q="执行 pwsh 命令列出 D:/big 下大于 1GB 的文件。", tool="pwsh",
         args={"command": "big"}),
    dict(id="c4", cat="params", q="读 D:/notes/2026/11/23.md。", tool="read",
         args={"file_path": "D:/notes/2026/11/23.md"}),
    dict(id="c5", cat="params", q="在 D:/app/settings.json 里搜 'timeout' 这个配置项。", tool="grep",
         args={"pattern": "timeout"}),

    # --- D 多工具（应选最合适的，或至少是其中之一）---
    dict(id="d1", cat="multi", q="我想知道 D:/proj 下有多少个 .py 文件，每个多大。", tool="pwsh", args={}),
    dict(id="d2", cat="multi", q="把这个项目里所有 TODO 注释找出来汇总。", tool="grep", args={"pattern": "TODO"}),
    dict(id="d3", cat="multi", q="先看看 D:/cfg 目录有什么，再读里面的 default.conf。", tool="glob", args={}),
    dict(id="d4", cat="multi", q="查一下今天 A 股大盘涨跌。", tool="web_search", args={}),

    # --- E 歧义/边界 ---
    dict(id="e1", cat="ambiguous", q="D:/x.txt 有多大？", tool="pwsh", args={}),
    dict(id="e2", cat="ambiguous", q="帮我把 D:/a.txt 备份一份。", tool="pwsh", args={}),
    dict(id="e3", cat="ambiguous", q="D:/data 目录是空的吗？", tool="glob", args={}),
    dict(id="e4", cat="ambiguous", q="这个仓库用什么语言写的？", tool="glob", args={}),
]

def grade(case, resp_msg, finish_reason):
    """返回 (ok, detail)"""
    calls = resp_msg.get("tool_calls") or []
    want = case["tool"]
    if want is None:
        # 不该调用
        if not calls:
            return True, "未调用(正确)"
        return False, f"多调用了 {calls[0]['function']['name']}"
    if not calls:
        return False, "未调用工具"
    name = calls[0]["function"]["name"]
    if name != want:
        return False, f"工具错: 期望 {want} 得到 {name}"
    # 参数检查
    try:
        args = json.loads(calls[0]["function"].get("arguments") or "{}")
    except Exception:
        return False, "参数不是合法 JSON"
    checks = case.get("args") or {}
    for k, expect in checks.items():
        got = str(args.get(k, ""))
        if expect not in got and got not in expect:
            return False, f"参数 {k} 期望含 '{expect}' 得到 '{got[:60]}'"
    return True, "工具+参数正确"
