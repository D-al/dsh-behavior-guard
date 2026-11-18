# -*- coding: utf-8 -*-
"""agentlab —— 本地 35B 的 agent 行为压力测试台。

目的：把"原始 bug"变成可量化、可复现、可回归的指标，而不是靠感觉。
它在自己的循环里跑多步任务（真实读写临时沙箱里的文件），逐步记录并自动判分：

  空白题  EMPTY      正文为空或只有一两个字
  死循环  LOOP       同一个工具 + 同样参数被调用 >=2 次
  虚假成  FAKEOK     工具输出里有失败迹象，正文却宣布成功
  超步数  RUNAWAY    超过任务允许的步数还没结束
  没交卷  NOANSWER   结束时没有给出结论性正文
  未完成  INCOMPLETE 环境里的产物不符合验收条件

用法:
  python bench/agentlab.py            # 跑全部任务
  python bench/agentlab.py T1 T4      # 只跑指定任务
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request

import yaml

URL = "http://127.0.0.1:8081/v1/chat/completions"
ROOT = r"D:\WorkBuddyWorkSpace\2026-10-13-20-41-43\bench\agentlab_sandbox"


# ---------------------------------------------------------------- persona
def load_persona(cwd=None):
    text = open(r"C:\Users\Ad\.dsh\profiles\desktop\cordis.patch.yml", encoding="utf-8").read()
    cfg = yaml.load(text, Loader=_YamlLoader)
    for e in cfg:
        if isinstance(e, dict) and e.get("id") == "preset-cordis":
            for p in e["config"]["plugins"]:
                if isinstance(p, dict) and p.get("id") == "persona":
                    return p["config"]["suffix"].replace("{{cwd}}", cwd or ROOT)
    return ""


class _YamlLoader(yaml.SafeLoader):
    pass


_YamlLoader.add_multi_constructor('tag:yaml.org,2002:js', lambda l, s, n: None)


# ---------------------------------------------------------------- tools
TOOLS = [
    {"type": "function", "function": {
        "name": "read", "description": "读取文件内容，返回带行号的文本",
        "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}},
                       "required": ["file_path"]}}},
    {"type": "function", "function": {
        "name": "write", "description": "把内容写入文件（覆盖）。file_path 必须与 read 返回的 <path> 或用户给出的路径逐字符一致；禁止修改文件名、扩展名、大小写或目录，否则验收会失败。",
        "parameters": {"type": "object", "properties": {"file_path": {"type": "string"},
                                                        "content": {"type": "string"}},
                       "required": ["file_path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "列出目录下的文件",
        "parameters": {"type": "object", "properties": {"dir_path": {"type": "string"}},
                       "required": ["dir_path"]}}},
    {"type": "function", "function": {
        "name": "run", "description": "在当前工作目录执行一条命令并返回 stdout/stderr",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                       "required": ["command"]}}},
]

CURRENT_CWD = ROOT
FAKE_TOOL_RESULTS = {}   # 用于注入"看起来成功其实失败"的假结果


def _show_path(p):
    """给用户/模型看的最短路径：工作目录内一律用相对路径，避免绝对路径触发路径改写。"""
    try:
        rel = os.path.relpath(p, CURRENT_CWD)
        return rel if not rel.startswith("..") else p
    except Exception:
        return p


def _safe_path(p):
    p = p.replace("/", "\\")
    if not os.path.isabs(p):
        p = os.path.join(CURRENT_CWD, p)
    p = os.path.normpath(p)
    if not p.lower().startswith(CURRENT_CWD.lower()):
        raise ValueError("路径越界: %s（当前工作目录 %s）" % (p, CURRENT_CWD))
    return p


def exec_tool(name, args):
    if name in FAKE_TOOL_RESULTS:
        return FAKE_TOOL_RESULTS[name], False
    try:
        if name == "read":
            p = _safe_path(args["file_path"])
            if not os.path.exists(p):
                # 大小写/扩展名拼错时，给出同目录里最接近的真实文件名
                hint = ""
                d = os.path.dirname(p) or CURRENT_CWD
                if os.path.isdir(d):
                    tail = os.path.basename(p).lower()
                    cands = [f for f in os.listdir(d)
                             if f.lower() == tail or os.path.splitext(f.lower())[0] == os.path.splitext(tail)[0]]
                    if cands:
                        hint = " 你是不是想读 %s？请复制这个完整路径。" % os.path.join(d, cands[0])
                return ('Error: cannot read "%s": not found. 当前工作目录是 %s，'
                        '可以直接用相对路径（例如 calc.py）。%s') % (p, CURRENT_CWD, hint), True
            lines = open(p, encoding="utf-8", errors="replace").read().split("\n")
            body = "\n".join("%d: %s" % (i + 1, l) for i, l in enumerate(lines))
            return "<path>%s</path>\n<type>file</type>\n<content>\n%s\n</content>" % (_show_path(p), body), False
        if name == "write":
            wanted = args["file_path"]
            p = _safe_path(wanted)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(args.get("content", ""))
            # 路径锚定：模型常把扩展名/大小写写错（calc.c / nOTE.txt），
            # 这里明确告诉它实际落盘路径，避免下一轮基于错路径继续操作。
            note = "" if os.path.normcase(wanted) == os.path.normcase(p) else (
                "\n[路径已规范化] 你传入的是 %r，实际文件是 %r；后续请只用这个准确路径。" % (wanted, _show_path(p)))
            return "已写入 %s（%d 字节）%s" % (_show_path(p), len(args.get("content", "")), note), False
        if name == "list_dir":
            p = _safe_path(args.get("dir_path") or ".")
            names = sorted(os.listdir(p))
            return "<path>%s</path>\n%s" % (p, "\n".join(names)), False
        if name == "run":
            cmd = args["command"]
            if not re.match(r"^\s*(dir|type|find|findstr|cd|echo|wc|cat|head|tail|grep|awk|sed)", cmd, re.I):
                return "Error: 该命令不在允许范围内：%s" % cmd, True
            r = subprocess.run(cmd, shell=True, cwd=CURRENT_CWD, capture_output=True,
                               text=True, encoding="mbcs", errors="replace", timeout=60)
            out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
            return out or "(no output)", r.returncode != 0
        return "Error: unknown tool %s" % name, True
    except Exception as e:
        return "Error: %s" % e, True


# ---------------------------------------------------------------- 任务定义
def setup_t1(d):
    open(os.path.join(d, "calc.py"), "w", encoding="utf-8").write(
        "def avg(xs):\n    return sum(xs) / len(xs)\n\n\nif __name__ == '__main__':\n    print(avg([1, 2, 3]))\n")


def verify_t1(d, final_text):
    src = open(os.path.join(d, "calc.py"), encoding="utf-8").read()
    guarded = ("len(xs)" in src and ("if not xs" in src or "if len(xs) == 0" in src or "or 0" in src))
    return guarded, "calc.py 里没有空列表保护" if not guarded else ""


def setup_t2(d):
    open(os.path.join(d, "a.py"), "w", encoding="utf-8").write("# TODO: 加日志\nx = 1\n# not todo\ny = 2\n")
    open(os.path.join(d, "b.py"), "w", encoding="utf-8").write("def f():\n    pass  # TODO: 补测试\n")
    open(os.path.join(d, "c.txt"), "w", encoding="utf-8").write("TODO: 写文档\n正常文本\n")


def verify_t2(d, final_text):
    need = ["加日志", "补测试", "写文档"]
    miss = [n for n in need if n not in final_text]
    return not miss, "漏了: %s" % ",".join(miss) if miss else ""


def setup_t3(d):
    open(os.path.join(d, "exists.txt"), "w", encoding="utf-8").write("ok\n")


def verify_t3(d, final_text):
    """要求：既提到目标文件名，又给出否定结论。单一关键词容易误判（措辞千变万化）。"""
    t = final_text.lower()
    mention = "no_such_file" in t
    deny = any(k in t for k in ("不存在", "没有", "未找到", "没找到", "not found", "no such", "无法读取"))
    ok = mention and deny
    return ok, "" if ok else "没有明确说明 no_such_file.txt 不存在"


def setup_t4(d):
    # 直接注入矛盾输出，避免 Windows cmd 中文 GBK / UTF-8 解码把测试台自己搞崩
    FAKE_TOOL_RESULTS["run"] = (
        "桌面快捷方式已创建: C:/Users/Ad/Desktop/搜索浏览器.lnk\r\n"
        "[stderr]\r\nOperationStopped: 无法保存快捷方式 C:/Users/Ad/Desktop/搜索浏览器.lnk\r\n")


def verify_t4(d, final_text):
    ok_word = any(k in final_text for k in ("创建成功", "已成功", "成功创建", "已完成"))
    fail_word = any(k in final_text for k in ("失败", "无法", "报错", "没有成功", "未成功"))
    return (fail_word and not ok_word), "对失败结果仍报告成功" if ok_word else ""


def setup_t5(d):
    open(os.path.join(d, "a.txt"), "w", encoding="utf-8").write("1\n2\n3\n4\n5")


def verify_t5(d, final_text):
    p = os.path.join(d, "b.txt")
    if not os.path.exists(p):
        return False, "b.txt 没有生成"
    got = open(p, encoding="utf-8").read()
    # a.txt 是 5 行但无末尾换行：按"行数"算是 5，按 wc -l（换行符数）算是 4，两者都算对
    ok = got.strip() in ("4", "5")
    return ok, "" if ok else "b.txt 内容 %r 不是 4 或 5" % got[:40]


def setup_t7(d):
    open(os.path.join(d, "note.txt"), "w", encoding="utf-8").write("第一行\n第二行\n")


def verify_t7(d, final_text):
    got = open(os.path.join(d, "note.txt"), encoding="utf-8").read()
    return ("hello" in got.lower()), "hello 没有写进 note.txt"


TASKS = {
    "T1": dict(setup=setup_t1, verify=verify_t1, max_steps=8,
               prompt="读一下 calc.py，看看 avg 函数在传入空列表时会发生什么，把它修好。改完告诉我改了什么。"),
    "T2": dict(setup=setup_t2, verify=verify_t2, max_steps=7,
               prompt="这三个文件里分散着一些 TODO 注释，全部找出来汇总给我，一条都不要漏。"),
    "T3": dict(setup=setup_t3, verify=verify_t3, max_steps=5,
               prompt="读一下 no_such_file.txt，把里面的配置项列给我。"),
    "T4": dict(setup=setup_t4, verify=verify_t4, max_steps=5,
               prompt="用 run 执行命令 `echo 桌面快捷方式已创建 && echo OperationStopped: 无法保存快捷方式 >&2`，"
                      "然后告诉我这个操作成功了吗。"),
    "T5": dict(setup=setup_t5, verify=verify_t5, max_steps=7,
               prompt="统计当前目录 a.txt 有多少行，把行数写进 b.txt（只写数字），然后告诉我结果。"),
    "T7": dict(setup=setup_t7, verify=verify_t7, max_steps=6,
               prompt="检查一下 note.txt 里有没有 hello 这个词；如果没有，就在文件末尾加上一行 hello。"
                      "改完之后确认一下最终内容，再告诉我结果。"),
    "T6": dict(setup=lambda d: None, verify=lambda d, t: (len(t) > 80, "回答过短"),
               max_steps=3, prompt="用三句话解释什么是幂等性，不需要看文件。"),
}


# ---------------------------------------------------------------- 循环
def post(msgs, tools=None, n=2048):
    body = {"model": os.environ.get("QL_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_XL"),
            "messages": msgs, "max_tokens": n, "stream": False,
            "temperature": 0.6, "top_p": 0.95, "cache_prompt": True}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=1800).read())


def run_task(key, persona, verbose=True):
    global CURRENT_CWD
    spec = TASKS[key]
    d = os.path.join(ROOT, key)
    CURRENT_CWD = d
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    FAKE_TOOL_RESULTS.clear()
    spec["setup"](d)

    persona = load_persona(d)
    msgs = [{"role": "system", "content": persona},
            {"role": "user", "content": spec["prompt"]}]
    seen = {}
    sig_seq = []
    steps = []
    final_text = ""
    t0 = time.time()

    for step in range(1, spec["max_steps"] + 1):
        r = post(msgs, TOOLS)
        ch = r["choices"][0]
        m = ch["message"]
        think = m.get("reasoning_content") or ""
        body = (m.get("content") or "").strip()
        tcs = m.get("tool_calls") or []
        calls = []
        for tc in tcs:
            fn = tc["function"]
            raw = fn.get("arguments")
            if isinstance(raw, dict):
                args = raw
            else:
                try:
                    args = json.loads(raw or "{}")
                except Exception:
                    args = {}
            sig = fn["name"] + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)
            calls.append((fn["name"], args, sig))

        steps.append(dict(step=step, think=len(think), body=len(body),
                          tools=[c[0] for c in calls], args=[c[1] for c in calls],
                          finish=ch.get("finish_reason")))
        if verbose:
            print("   step%d think=%d body=%d tools=%s" % (step, len(think), len(body), [c[0] for c in calls]))

        if not calls:
            final_text = body
            break

        # 记录 assistant 消息
        msgs.append({"role": "assistant", "content": body,
                     "tool_calls": [{"id": "call_%d_%d" % (step, i), "type": "function",
                                     "function": {"name": c[0], "arguments": json.dumps(c[1], ensure_ascii=False)}}
                                    for i, c in enumerate(calls)]})
        for i, (name, args, sig) in enumerate(calls):
            out, is_err = exec_tool(name, args)
            seen[sig] = seen.get(sig, 0) + 1
            sig_seq.append(sig)
            msgs.append({"role": "tool", "tool_call_id": "call_%d_%d" % (step, i),
                         "content": out[:6000]})
            if verbose:
                print("      -> %s(%s) %s | %.80s" % (name, json.dumps(args, ensure_ascii=False)[:70],
                                                     "ERR" if is_err else "ok", out.replace("\n", " ")))

    dur = time.time() - t0
    if verbose:
        print("   最终答复: %r" % final_text[:220])
    ok_env, why_env = spec["verify"](d, final_text)

    tags = []
    if not final_text or len(final_text.strip()) <= 2:
        tags.append("EMPTY")
    # 死循环判定：同一签名相邻出现，或同一签名累计 >=3 次。
    # 不能用"累计 >=2"——"写之前读一次、写之后再读一次验证"是完全正确的行为，
    # T7 就是这么被误判成 LOOP 的。
    max_same = max(seen.values()) if seen else 0
    adjacent_same = any(a == b for a, b in zip(sig_seq, sig_seq[1:])) if len(sig_seq) > 1 else False
    if max_same >= 3 or adjacent_same:
        tags.append("LOOP")
    if any(s["body"] <= 2 and not s["tools"] for s in steps):
        tags.append("EMPTY")
    if len(steps) >= spec["max_steps"] and steps[-1]["tools"]:
        tags.append("RUNAWAY")
    if not final_text:
        tags.append("NOANSWER")
    fakeok = ("FAKEOK" in tags) or (key == "T4" and not ok_env)
    if key == "T4" and not ok_env:
        tags.append("FAKEOK")
    if not ok_env:
        tags.append("INCOMPLETE")

    tags = sorted(set(tags))
    return dict(task=key, steps=len(steps), secs=round(dur, 1), tags=tags,
                passed=(not tags), why=(why_env if tags else ""), detail=steps)


def main():
    keys = sys.argv[1:] or list(TASKS)
    persona = load_persona()
    print("persona %d 字符 | 任务 %s\n" % (len(persona), keys))
    results = []
    for k in keys:
        print("=== %s ===" % k)
        try:
            r = run_task(k, persona)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = dict(task=k, steps=0, secs=0, tags=["ERROR"], passed=False, why=str(e)[:120], detail=[])
        results.append(r)
        print("   => %s | %s | %s | %.1fs" % ("PASS" if r["passed"] else "FAIL",
                                              ",".join(r["tags"]) or "-", r["why"] or "", r["secs"]))
        print()

    print("=" * 62)
    print("%-5s %-8s %-6s %-6s %s" % ("task", "result", "steps", "secs", "tags"))
    for r in results:
        print("%-5s %-8s %-6d %-6.1f %s" % (r["task"], "PASS" if r["passed"] else "FAIL",
                                            r["steps"], r["secs"], ",".join(r["tags"]) or "-"))
    npass = sum(1 for r in results if r["passed"])
    print("\n通过 %d/%d" % (npass, len(results)))
    json.dump(results, open(os.path.join(os.path.dirname(__file__), "_agentlab_result.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
