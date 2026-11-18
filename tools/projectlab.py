# -*- coding: utf-8 -*-
"""projectlab —— 项目级能力测试台。

和 agentlab 的区别：不是单步小任务，而是需要 8~15 步、跨多个文件、必须自己跑验证的
小型项目。评分不再是"产物对不对"，而是给一张**能力画像**，对应第一性原理的六个环节：

  1. RECON   动手前是否先摸清现状（读/列在写之前）
  2. PLAN    是否在思考里做过子目标拆分
  3. ATOMIC  是否一次一个改动（不反复重写同一文件）
  4. VERIFY  改完是否真的跑测试/检查
  5. RECOVER 遇到失败是否换方法（不重复同一失败调用）
  6. DELIVER 是否全绿之后才交付完整报告（不虚报、不半途停）

用法: python bench/projectlab.py [P1 [P2 ...]]
输出: bench/_projectlab_result.json（完整轨迹，便于逐帧复盘）
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import threading

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agentlab

URL = os.environ.get("PL_BASE", "http://127.0.0.1:8081/v1/chat/completions")
# 采样参数可由环境变量覆盖，用于「温度消融」——判断行为差异来自 logits 分布还是采样放大。
#   QL_TEMP=0.1 python bench/projectlab.py P4
#   QL_SEED=1234 ...  固定种子可让两模型走同一随机流，逐次对照
TEMPERATURE = float(os.environ.get("QL_TEMP", "0.6"))
SEED = int(os.environ["QL_SEED"]) if os.environ.get("QL_SEED") else None
# 路由模式下必须显式指定模型，否则会用「当前已加载的那个」——容易跑到错误权重上。
MODEL_ID = os.environ.get("QL_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_XL")
ROOT = r"D:\Brain\workspace\bench\projectlab_sandbox"


class _L(yaml.SafeLoader):
    pass


_L.add_multi_constructor('tag:yaml.org,2002:js', lambda l, s, n: None)


def persona_for(cwd):
    cfg = yaml.load(open(r"C:\Users\Ad\.dsh\profiles\desktop\cordis.patch.yml",
                         encoding="utf-8").read(), Loader=_L)
    for e in cfg:
        if isinstance(e, dict) and e.get("id") == "preset-cordis":
            for p in e["config"]["plugins"]:
                if isinstance(p, dict) and p.get("id") == "persona":
                    return p["config"]["suffix"].replace("{{cwd}}", cwd)
    return ""


BASE_TOOLS = [
    {"type": "function", "function": {"name": "read", "description": "读取文件（带行号）",
      "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}}},
    {"type": "function", "function": {"name": "write", "description": "写入文件（覆盖）",
      "parameters": {"type": "object", "properties": {"file_path": {"type": "string"},
                                                      "content": {"type": "string"}}, "required": ["file_path", "content"]}}},
    {"type": "function", "function": {"name": "list_dir", "description": "列出目录",
      "parameters": {"type": "object", "properties": {"dir_path": {"type": "string"}}, "required": ["dir_path"]}}},
    {"type": "function", "function": {"name": "run", "description": "在工作目录执行命令，可用 python / python -m pytest / dir / type / findstr",
      "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]


EDIT_TOOL = {"type": "function", "function": {
    "name": "edit", "description": "只改一处：把 old_string 替换成 new_string，不必重写整个文件",
    "parameters": {"type": "object", "properties": {"file_path": {"type": "string"},
                                                    "old_string": {"type": "string"},
                                                    "new_string": {"type": "string"}},
                   "required": ["file_path", "old_string", "new_string"]}}}

PATCH_TOOL = {"type": "function", "function": {
    "name": "apply_patch",
    "description": "一次性提交一个文件里的全部改动：edits 里放所有 old_string→new_string 对，"
                   "一个调用完成，不要一处一次调用。只写要改的片段，不重写整个文件。",
    "parameters": {"type": "object", "properties": {
        "file_path": {"type": "string"},
        "edits": {"type": "array", "items": {"type": "object", "properties": {
            "old_string": {"type": "string"}, "new_string": {"type": "string"}},
            "required": ["old_string", "new_string"]}}},
        "required": ["file_path", "edits"]}}}

TOOLS = BASE_TOOLS

CWD = ROOT
COMPACT_READ = False
READ_CACHE = {}


def _p(p):
    p = p.replace("/", "\\")
    if not os.path.isabs(p):
        p = os.path.join(CWD, p)
    p = os.path.normpath(p)
    if not p.lower().startswith(CWD.lower()):
        raise ValueError("路径越界: %s" % p)
    return p


def exec_tool(name, args):
    try:
        if name == "read":
            f = _p(args["file_path"])
            if not os.path.exists(f):
                return 'Error: not found: %s（工作目录 %s）' % (f, CWD), True
            raw = open(f, encoding="utf-8", errors="replace").read()
            key = f.lower()
            if COMPACT_READ and READ_CACHE.get(key) == raw:
                return "[未变化] %s 与上次读取完全一致（%d 字节，%d 行），无需重读。" % (
                    f, len(raw), len(raw.split("\n"))), False
            READ_CACHE[key] = raw
            ls = raw.split("\n")
            return "<path>%s</path>\n<content>\n%s\n</content>" % (
                f, "\n".join("%d: %s" % (i + 1, x) for i, x in enumerate(ls))), False
        if name == "write":
            f = _p(args["file_path"])
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write(args.get("content", ""))
            READ_CACHE.pop(f.lower(), None)
            return "已写入 %s（%d 字节）" % (f, len(args.get("content", ""))), False
        if name == "edit":
            f = _p(args["file_path"])
            if not os.path.exists(f):
                return "Error: not found: %s" % f, True
            src = open(f, encoding="utf-8").read()
            old, new = args["old_string"], args["new_string"]
            if old not in src:
                return "Error: old_string not found in %s" % f, True
            open(f, "w", encoding="utf-8").write(src.replace(old, new, 1))
            return "已修改 %s（替换 %d 字符）" % (f, len(old)), False
        if name == "apply_patch":
            f = _p(args["file_path"])
            if not os.path.exists(f):
                return "Error: not found: %s" % f, True
            src = open(f, encoding="utf-8").read()
            edits = args.get("edits") or []
            if not edits:
                return "Error: edits 为空", True
            for i, e in enumerate(edits):
                if e.get("old_string") not in src:
                    return "Error: 第 %d 处 old_string 未找到" % (i + 1), True
            out = src
            for e in edits:
                out = out.replace(e["old_string"], e["new_string"], 1)
            open(f, "w", encoding="utf-8").write(out)
            return "已在一个调用里应用 %d 处修改 -> %s" % (len(edits), f), False
        if name == "list_dir":
            f = _p(args.get("dir_path") or ".")
            return "<path>%s</path>\n%s" % (f, "\n".join(sorted(os.listdir(f)))), False
        if name == "run":
            cmd = args["command"]
            if not re.match(r"^\s*(python|py|dir|type|findstr|echo|cd|more)", cmd, re.I):
                return "Error: 命令不在允许范围: %s" % cmd, True
            r = subprocess.run(cmd, shell=True, cwd=CWD, capture_output=True,
                               text=True, encoding="mbcs", errors="replace", timeout=120)
            out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
            return (out or "(no output)")[:6000], r.returncode != 0
        return "Error: unknown tool", True
    except Exception as e:
        return "Error: %s" % e, True


# ------------------------------------------------------------------ 项目
BUG_STATS = '''def mean(xs):
    return sum(xs) / len(xs)


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n / 2]


def top_n(items, n):
    return sorted(items)[-n]
'''

BUG_TEST = '''from stats import mean, median, top_n

assert mean([1, 2, 3]) == 2
assert mean([]) == 0
assert median([3, 1, 2]) == 2
assert median([4, 1, 3, 2]) == 2.5
assert top_n([1, 5, 3], 2) == [5, 3]
print("ALL TESTS PASSED")
'''


def setup_p1(d):
    open(os.path.join(d, "stats.py"), "w", encoding="utf-8").write(BUG_STATS)
    open(os.path.join(d, "test_stats.py"), "w", encoding="utf-8").write(BUG_TEST)


def verify_p1(d, trace):
    test_src = open(os.path.join(d, "test_stats.py"), encoding="utf-8").read()
    cheated = test_src.strip() != BUG_TEST.strip()
    r = subprocess.run("python test_stats.py", shell=True, cwd=d, capture_output=True,
                       text=True, encoding="mbcs", errors="replace", timeout=120)
    passed = (r.returncode == 0) and ("ALL TESTS PASSED" in (r.stdout or ""))
    return passed and not cheated, ("改动了测试文件" if cheated else
                                   "" if passed else "测试未全绿: %s" % (r.stderr or r.stdout or "")[:150])


def setup_p2(d):
    open(os.path.join(d, "SPEC.md"), "w", encoding="utf-8").write(
        "# 需求\n实现一个命令行工具 linecount.py：\n"
        "- 用法: python linecount.py <目录> --ext .py\n"
        "- 统计该目录（不递归）下所有指定扩展名文件的行数\n"
        "- 按行数从多到少排序，输出 CSV 到 stdout：filename,lines\n"
        "- 目录不存在或没有匹配文件时输出空表头并退出码 0\n")
    open(os.path.join(d, "a.py"), "w", encoding="utf-8").write("x = 1\ny = 2\nz = 3\n")
    open(os.path.join(d, "b.py"), "w", encoding="utf-8").write("a\nb\n")
    open(os.path.join(d, "c.txt"), "w", encoding="utf-8").write("ignored\n" * 9)


def verify_p2(d, trace):
    f = os.path.join(d, "linecount.py")
    if not os.path.exists(f):
        return False, "linecount.py 没有生成"
    r = subprocess.run("python linecount.py . --ext .py", shell=True, cwd=d,
                       capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=120)
    out = (r.stdout or "").replace("\r", "").strip()
    ok = r.returncode == 0 and "a.py,3" in out and "b.py,2" in out and "c.txt" not in out
    if not ok:
        return False, "输出不符合预期: %r / %r" % (out[:120], (r.stderr or "")[:100])
    # 空结果场景
    r2 = subprocess.run("python linecount.py . --ext .zzz", shell=True, cwd=d,
                        capture_output=True, text=True, encoding="mbcs", errors="replace", timeout=120)
    ok2 = r2.returncode == 0 and "filename" in (r2.stdout or "")
    return ok2, "" if ok2 else "无匹配文件时没有输出表头/退出码非 0"



P3_SPEC = """# 需求：实现 config.py 的 Config 类

- Config() 创建空配置
- set(key, value)：key 支持点号路径，例如 set("db.host", "localhost")
- get(key, default=None)：不存在的 key 返回 default
- to_dict()：返回普通 dict（嵌套结构）
- load_json(path)：读入 JSON 并合并；文件不存在时返回自身，不抛异常
- save_json(path)：写出 JSON；父目录不存在时自动创建

SPEC 里没有给测试。请你自己写一份覆盖以上全部行为的测试，运行通过后再交付。
"""


def setup_p3(d):
    open(os.path.join(d, "SPEC.md"), "w", encoding="utf-8").write(P3_SPEC)


HIDDEN_CHECK = """# -*- coding: utf-8 -*-
import json, os, importlib.util
spec = importlib.util.spec_from_file_location("cfg", "config.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
c = m.Config()
c.set("db.host", "localhost")
assert c.get("db.host") == "localhost", "dotted get"
assert c.get("nope", 42) == 42, "default"
c.set("db.port", 5432)
assert c.get("db.port") == 5432, "second key"
c.load_json("__definitely_missing__.json")
assert c.get("db.host") == "localhost", "load missing must be a no-op"
d = c.to_dict()
assert d["db"]["host"] == "localhost" and d["db"]["port"] == 5432, "to_dict"
c.save_json("out/sub/conf.json")
assert os.path.isfile("out/sub/conf.json"), "save must create parent dirs"
j = json.load(open("out/sub/conf.json", encoding="utf-8"))
assert j["db"]["host"] == "localhost", "round trip"
print("CONFIG_OK")
"""


def verify_p3(d, trace):
    if not os.path.exists(os.path.join(d, "config.py")):
        return False, "config.py 没有生成"
    chk = os.path.join(d, "_hidden_check.py")
    open(chk, "w", encoding="utf-8").write(HIDDEN_CHECK)
    try:
        r = subprocess.run("python _hidden_check.py", shell=True, cwd=d, capture_output=True,
                           text=True, encoding="mbcs", errors="replace", timeout=120)
        ok = r.returncode == 0 and "CONFIG_OK" in (r.stdout or "")
        return ok, "" if ok else "隐藏验收失败: %s" % ((r.stdout or "") + (r.stderr or ""))[:200]
    finally:
        try:
            os.remove(chk)
        except OSError:
            pass


# ------------------------------------------------------------------ P4：多模块长链路
# 目的：现有 P1/P2/P3 都只有 6~10 步，覆盖不到"20+ 步后上下文变长"这个状态。
# P4 是一个 4 模块的小库存系统，植入 14 个 bug，隐藏测试 20 条断言；
# 上限 45 步，正常会在 25~40 步完成，用来对比 Q3/Q4 在长链路项目上的差异。

P4_MODELS = '''class ValidationError(ValueError):
    pass


DEFAULT_TAGS = []


def make_item(name, qty, price, tags=None):
    if not name:
        raise ValidationError("name required")
    if qty < 0:
        raise ValidationError("qty must be >= 0")
    return {
        "name": name.strip(),
        "qty": qty,
        "price": price,
        "tags": DEFAULT_TAGS if tags is None else tags,
    }


def item_value(item):
    return item["qty"] * item["price"]
'''

P4_STORE = '''class Store:
    def __init__(self):
        self.items = {}
        self.next_id = 1

    def add(self, item):
        if any(x["name"] == item["name"] for x in self.items.values()):
            raise ValueError("duplicate name: %s" % item["name"])
        key = len(self.items)
        self.items[key] = item
        return key

    def get(self, item_id):
        return self.items[item_id]

    def update(self, item_id, **fields):
        item = self.items.get(item_id, {})
        item.update(fields)

    def delete(self, item_id):
        if item_id not in self.items:
            return False
        del self.items[len(self.items)]
        return True

    def list_items(self):
        return [self.items[k] for k in self.items]
'''

P4_REPORT = '''def total_value(store):
    total = 0
    for item in store.list_items():
        total += item["qty"]
    return total


def low_stock(store, threshold):
    return [i["name"] for i in store.list_items() if i["qty"] < threshold]


def top_by_value(store, n):
    rows = sorted(store.list_items(), key=lambda i: i["qty"] * i["price"])
    return [r["name"] for r in rows[:n]]
'''

P4_PIPELINE = '''import json


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\\n")
    for i in range(len(lines) - 1):
        line = lines[i].strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def apply_ops(store, ops):
    added = updated = deleted = 0
    for op in ops:
        kind = op.get("op")
        if kind == "add":
            store.add({"name": op["name"], "qty": op["qty"], "price": op["price"], "tags": []})
            added += 1
        elif kind == "update":
            store.update(op["id"], qty=op["qty"])
            updated += 1
        elif kind == "delete":
            store.delete(op["name"])
            deleted += 1
    return added, updated, deleted
'''

P4_TEST = '''from models import make_item, item_value, ValidationError
from store import Store
from report import total_value, low_stock, top_by_value
from pipeline import load_jsonl, apply_ops
import os

fails = []


def ck(name, fn):
    """fail-fast：一失败立刻抛 AssertionError，一次只暴露一个 bug。
    这是刻意设计的——否则模型会整文件重写、一把修完，步数上不到 30。
    fail-fast 逼它「改一处 -> 跑一次 -> 看下一个失败」，更接近真实联调现场。"""
    try:
        ok = fn()
    except Exception as e:
        raise AssertionError("%s -> %s: %s" % (name, type(e).__name__, e))
    if not ok:
        raise AssertionError(name)


def raises(exc, fn):
    try:
        fn()
    except exc:
        return True
    return False


# --- models ---
a = make_item("  Apple ", 10, 2.5)
ck("strip_name", lambda: a["name"] == "Apple" and a["qty"] == 10)
ck("neg_price", lambda: raises(ValidationError, lambda: make_item("x", 1, -1)))
ck("neg_qty", lambda: raises(ValidationError, lambda: make_item("x", -1, 1)))
m1 = make_item("m1", 1, 1)
m2 = make_item("m2", 1, 1)
m1["tags"].append("t")
ck("no_shared_tags", lambda: m2["tags"] == [])
ck("item_value", lambda: item_value({"qty": 3, "price": 2}) == 6)

# --- store ---
s = Store()
i1 = s.add(make_item("a", 5, 1))
i2 = s.add(make_item("b", 3, 2))
ck("ids_increment", lambda: i2 == i1 + 1)
ck("dup_name", lambda: raises(ValueError, lambda: s.add(make_item("a", 1, 1))))
ck("get_missing_none", lambda: s.get(999) is None)
ck("update_missing", lambda: raises(KeyError, lambda: s.update(999, qty=1)))
ck("delete_true", lambda: s.delete(i2) is True)
ck("delete_twice_false", lambda: s.delete(i2) is False)
ck("len_after_delete", lambda: len(s.list_items()) == 1)
ck("ids_stable_after_delete", lambda: s.add(make_item("c", 1, 1)) == i1 + 2)

# --- report ---
s2 = Store()
s2.add(make_item("x", 2, 10))
s2.add(make_item("y", 5, 1))
ck("total_value", lambda: total_value(s2) == 25)
ck("low_stock", lambda: sorted(low_stock(s2, 2)) == ["x"])
ck("top_by_value", lambda: top_by_value(s2, 1) == ["x"])

# --- pipeline ---
open("ops.jsonl", "w", encoding="utf-8").write(
    '{"op":"add","name":"p","qty":4,"price":3}\\n'
    '{"op":"add","name":"q","qty":1,"price":9}\\n'
    '{"op":"update","id":1,"qty":7}')
rows = load_jsonl("ops.jsonl")
ck("jsonl_lines", lambda: len(rows) == 3)
s3 = Store()
counts = apply_ops(s3, rows)
ck("counts", lambda: counts == (2, 1, 0))
ck("applied_qty", lambda: s3.get(1)["qty"] == 7)
os.remove("ops.jsonl")

if fails:
    print("FAILED (%d): %s" % (len(fails), ", ".join(fails)))
else:
    print("ALL TESTS PASSED")
'''


def setup_p4(d):
    open(os.path.join(d, "models.py"), "w", encoding="utf-8").write(P4_MODELS)
    open(os.path.join(d, "store.py"), "w", encoding="utf-8").write(P4_STORE)
    open(os.path.join(d, "report.py"), "w", encoding="utf-8").write(P4_REPORT)
    open(os.path.join(d, "pipeline.py"), "w", encoding="utf-8").write(P4_PIPELINE)
    open(os.path.join(d, "test_inv.py"), "w", encoding="utf-8").write(P4_TEST)


def verify_p4(d, trace):
    tp = os.path.join(d, "test_inv.py")
    if not os.path.exists(tp):
        return False, "测试文件被删除"
    if open(tp, encoding="utf-8").read().strip() != P4_TEST.strip():
        return False, "改动了测试文件"
    r = subprocess.run("python test_inv.py", shell=True, cwd=d, capture_output=True,
                       text=True, encoding="mbcs", errors="replace", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    passed = r.returncode == 0 and "ALL TESTS PASSED" in out
    return passed, "" if passed else "未全绿: %s" % out.strip()[:200]


# ------------------------------------------------------------------ P5：从零交付一个 CLI 软件
# 和 P1~P4 的区别：那些是"给代码修 bug"或"补一个文件"，P5 是从 SPEC 出发、
# 自己设计模块、自己写测试、自己定位问题、直到交付。验收用**隐藏测试**（运行前才写入沙箱），
# 模型看不到，所以不能"对着测试写"。

P5_SPEC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "p5_ref", "SPEC.md"),
               encoding="utf-8").read()

P5_TEST = r'''# -*- coding: utf-8 -*-
"""隐藏验收测试：只通过 CLI 与被测程序交互，不看实现细节。fail-fast。"""
import json
import os
import re
import subprocess
import sys

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def run(*args):
    r = subprocess.run([sys.executable, "taskctl.py"] + list(args), cwd=".",
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=ENV, timeout=120)
    return r.returncode, (r.stdout or ""), (r.stderr or "")


def ck(name, fn):
    try:
        ok = fn()
    except Exception as e:
        raise AssertionError("%s -> %s: %s" % (name, type(e).__name__, e))
    if not ok:
        raise AssertionError(name)


if not os.path.exists("taskctl.py"):
    raise AssertionError("taskctl.py 不存在")

# 1) 基本新增
rc, out, err = run("add", "买牛奶")
ck("add_1", lambda: rc == 0 and out.strip() == "added 1")
rc, out, err = run("add", "写周报", "--priority", "high", "--tags", "work,weekly")
ck("add_2", lambda: rc == 0 and out.strip() == "added 2")

# 2) 列表
rc, out, err = run("list")
lines = [l for l in out.strip().split("\n") if l.strip()]
ck("list_two", lambda: rc == 0 and len(lines) == 2)
ck("list_format", lambda: re.match(r"^#1 \[todo\] normal 买牛奶$", lines[0]) is not None)
ck("list_second", lambda: re.match(r"^#2 \[todo\] high 写周报$", lines[1]) is not None)
rc, out, err = run("list", "--status", "todo")
ck("list_todo", lambda: len([l for l in out.strip().split("\n") if l.strip()]) == 2)
rc, out, err = run("list", "--status", "done")
ck("list_done_empty", lambda: rc == 0 and not out.strip())

# 3) 完成 / 不存在
rc, out, err = run("done", "1")
ck("done_1", lambda: rc == 0 and out.strip() == "done 1")
rc, out, err = run("list", "--status", "done")
ck("list_done_one", lambda: len([l for l in out.strip().split("\n") if l.strip()]) == 1
   and "#1" in out)
rc, out, err = run("done", "99")
ck("done_missing_rc", lambda: rc == 1)
ck("done_missing_msg", lambda: "no such task: 99" in err)

# 4) 删除 + id 不复用
rc, out, err = run("rm", "2")
ck("rm_2", lambda: rc == 0 and out.strip() == "removed 2")
rc, out, err = run("rm", "2")
ck("rm_missing", lambda: rc == 1 and "no such task: 2" in err)
rc, out, err = run("add", "第三件事", "--tags", "home,errand")
ck("id_no_reuse", lambda: out.strip() == "added 3")

# 5) stats
rc, out, err = run("stats")
st = json.loads(out.strip())
ck("stats_total", lambda: st["total"] == 2)
ck("stats_status", lambda: st["by_status"]["done"] == 1 and st["by_status"]["todo"] == 1)
ck("stats_priority", lambda: st["by_priority"]["high"] == 0
   and st["by_priority"]["normal"] == 2 and st["by_priority"]["low"] == 0)

# 6) 优先级排序
run("add", "紧急任务", "--priority", "high")
run("add", "低优先", "--priority", "low")
rc, out, err = run("list", "--sort", "priority")
pr = [l.split("]")[1].strip().split(" ")[0] for l in out.strip().split("\n") if l.strip()]
ck("sort_priority", lambda: pr == ["high", "normal", "normal", "low"])

# 7) 导出
rc, out, err = run("export", "--format", "csv")
rows = [l for l in out.strip().split("\n") if l.strip()]
ck("csv_header", lambda: rows[0] == "id,title,status,priority,tags,created_at")
ck("csv_rows", lambda: len(rows) == 5)
ck("csv_tags", lambda: any("home|errand" in r for r in rows))
rc, out, err = run("export", "--format", "json")
data = json.loads(out)
ck("json_ids", lambda: sorted(i["id"] for i in data["items"]) == [1, 3, 4, 5])
ck("json_tags", lambda: next((i["tags"] for i in data["items"] if i["id"] == 3), None) == ["home", "errand"])
ck("created_at_iso", lambda: all(
    re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", i["created_at"]) for i in data["items"]))

# 8) 非法参数
rc, out, err = run("add", "x", "--priority", "urgent")
ck("bad_priority_rc", lambda: rc == 2)
ck("bad_priority_msg", lambda: "invalid priority: urgent" in err)
rc, out, err = run("export", "--format", "xml")
ck("bad_format_rc", lambda: rc == 2)
ck("bad_format_msg", lambda: "invalid format: xml" in err)

# 9) 持久化文件结构
with open("tasks.json", encoding="utf-8") as f:
    raw = json.load(f)
ck("file_shape", lambda: isinstance(raw.get("next_id"), int) and raw["next_id"] == 6
   and isinstance(raw.get("items"), list))

print("ALL ACCEPTANCE PASSED")
'''


def setup_p5(d):
    open(os.path.join(d, "SPEC.md"), "w", encoding="utf-8").write(P5_SPEC)


def verify_p5(d, trace):
    test_path = os.path.join(d, "_accept.py")
    # 清掉模型自测时可能留下的运行时数据，否则 id 不从 1 开始、验收会误判。
    for leftover in ("tasks.json",):
        p = os.path.join(d, leftover)
        if os.path.exists(p):
            os.remove(p)
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(P5_TEST)
    try:
        r = subprocess.run([sys.executable, "_accept.py"], cwd=d, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=300)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        passed = r.returncode == 0 and "ALL ACCEPTANCE PASSED" in out
        if passed:
            return True, ""
        tail = out.split("\n")[-6:]
        return False, "验收未过: " + " | ".join(x.strip() for x in tail if x.strip())[:220]
    finally:
        try:
            os.remove(test_path)
        except OSError:
            pass


PROJECTS = {
    "P1": dict(setup=setup_p1, verify=verify_p1, max_steps=14, tools=BASE_TOOLS,
               prompt="这个 Python 包有若干 bug，测试跑不过。请定位并修复所有 bug，"
                      "最后运行测试确认全部通过，然后告诉我改了哪几处。"
                      "注意：不要修改测试文件 test_stats.py。"),
    "P1E": dict(setup=setup_p1, verify=verify_p1, max_steps=14,
                tools=BASE_TOOLS + [EDIT_TOOL],
                prompt="这个 Python 包有若干 bug，测试跑不过。请定位并修复所有 bug，"
                       "用 edit 做最小改动（不要重写整个文件），最后运行测试确认全部通过，"
                       "然后告诉我改了哪几处。不要修改测试文件 test_stats.py。"),
    "P1P": dict(setup=setup_p1, verify=verify_p1, max_steps=14,
                tools=BASE_TOOLS + [PATCH_TOOL],
                prompt="这个 Python 包有若干 bug，测试跑不过。请定位并修复所有 bug，"
                       "用 apply_patch 在【一个调用】里提交全部 edits（只写改动片段，不重写整文件），"
                       "最后运行测试确认全部通过，然后告诉我改了哪几处。"
                       "不要修改测试文件 test_stats.py。"),
    "P2": dict(setup=setup_p2, verify=verify_p2, max_steps=14,
               prompt="按 SPEC.md 实现 linecount.py，写完后自己构造几种输入验证"
                      "（正常、无匹配文件、目录不存在），确认都对了再告诉我结果。"),
    "P3R": dict(setup=setup_p3, verify=verify_p3, max_steps=16, compact_read=True,
                prompt="按 SPEC.md 实现 config.py。SPEC 里没有给测试，"
                       "请你自己写一份覆盖全部行为的测试，运行通过后再交付实现与结论。"),
    "P3": dict(setup=setup_p3, verify=verify_p3, max_steps=16,
               prompt="按 SPEC.md 实现 config.py。SPEC 里没有给测试，"
                      "请你自己写一份覆盖全部行为的测试，运行通过后再交付实现与结论。"),
    "P4": dict(setup=setup_p4, verify=verify_p4, max_steps=45,
               tools=BASE_TOOLS + [EDIT_TOOL],
               prompt="这是一个小型库存系统（models.py / store.py / report.py / pipeline.py），"
                      "test_inv.py 跑不过。请定位并修复所有 bug，直到 `python test_inv.py` 输出 "
                      "ALL TESTS PASSED，然后简述每一处改了什么。不要修改测试文件 test_inv.py。"),
    "P5": dict(setup=setup_p5, verify=verify_p5, max_steps=80,
               tools=BASE_TOOLS + [EDIT_TOOL],
               prompt="请按 SPEC.md 从零实现这个命令行工具。要求：先通读 SPEC，规划文件结构，"
                      "实现后**自己写一份覆盖全部行为（含每一条错误分支）的测试并运行**，"
                      "发现问题就改，改完重跑，直到你自己确认全部通过；"
                      "最后给出简短交付说明（实现了哪些文件、怎么验证的、有无遗留问题）。"
                      "不要修改 SPEC.md。"),
}


# ------------------------------------------------------------------ 循环
# 严格 A/B：同一任务、同一 persona、同一温度，唯一变量是「是否有思考段」
for _k in ("P1", "P2", "P3"):
    PROJECTS[_k + "N"] = dict(PROJECTS[_k], no_think=True)
    # 条件化思考：只在关键步保留校验，其余步走零思考
    PROJECTS[_k + "S1"] = dict(PROJECTS[_k], no_think=True, think_steps={1})
    PROJECTS[_k + "S2"] = dict(PROJECTS[_k], no_think=True, think_steps={1, 2})
    PROJECTS[_k + "SW"] = dict(PROJECTS[_k], no_think=True, think_steps={3, 4})
    PROJECTS[_k + "UW"] = dict(PROJECTS[_k], no_think=True, think_policy="until_write")
    PROJECTS[_k + "PW"] = dict(PROJECTS[_k], no_think=True, think_policy="pre_write")
    PROJECTS[_k + "PF"] = dict(PROJECTS[_k], no_think=True, think_policy="plan_first")
    PROJECTS[_k + "PR"] = dict(PROJECTS[_k], no_think=True, think_policy="plan_rounds")

def post(msgs, n=8192, tools=None, no_think=False):  # n 与 dsh 的 maxTokens 8192 对齐
    body = {"messages": msgs, "max_tokens": n, "stream": False, "temperature": TEMPERATURE,
            "top_p": 0.95, "cache_prompt": True, "tools": tools or TOOLS, "tool_choice": "auto"}
    if SEED is not None:
        body["seed"] = SEED
    if MODEL_ID:
        body["model"] = MODEL_ID
    if no_think:
        # 结构性关闭思考（模板渲染空 think 块），不是 reasoning-budget 那种半句硬切
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=1800).read())


def run_project(key, verbose=True):
    global CWD, COMPACT_READ
    spec = PROJECTS[key]
    d = os.path.join(ROOT, key)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    CWD = d
    COMPACT_READ = bool(spec.get("compact_read"))
    READ_CACHE.clear()
    spec["setup"](d)

    msgs = [{"role": "system", "content": persona_for(d)},
            {"role": "user", "content": spec["prompt"]}]
    trace, final, t0 = [], "", time.time()
    sig_seq, write_files, err_sigs = [], [], []

    for step in range(1, spec["max_steps"] + 1):
        t_step = time.time()
        # 条件化思考：no_think=True 时，仅 think_steps 列出的步保留思考段
        nt = bool(spec.get("no_think")) and step not in (spec.get("think_steps") or ())
        pol = spec.get("think_policy")
        if pol in ("until_write", "pre_write"):
            wrote = any(any(n in ("write", "edit", "apply_patch") for n, a in s["calls"])
                        for s in trace)
            # until_write：首次写入之前全开思考，写完立刻关
            # pre_write  ：只在「刚拿到工具结果、且尚未写入」时开思考（探查首步/验证/交付都关）
            nt = wrote if pol == "until_write" else (wrote or msgs[-1]["role"] != "tool")
        elif pol == "plan_first":
            # 与步号无关的结构规则：当前 turn 内工具结果 <=1 条时属「规划期」，开思考；之后全关。
            # 这一条可以直接翻译成模板里的 Jinja 判定，无需外部开关。
            nt = sum(1 for m in msgs if m.get("role") == "tool") > 1
        elif pol == "plan_rounds":
            # 修正：按「工具交互轮数」而非结果条数。一步常并读两个文件，结果条数会一次涨 2，
            # 导致按条数判定提前关思考（实测 PF 比 S2 差 40%）。模板里同样可数 assistant.tool_calls。
            nt = sum(1 for m in msgs if m.get("role") == "assistant" and m.get("tool_calls")) > 1
        r = post(msgs, tools=spec.get("tools"), no_think=nt)
        gen_secs = time.time() - t_step
        tm = r.get("timings", {})
        ch = r["choices"][0]
        m = ch["message"]
        think = m.get("reasoning_content") or ""
        body = (m.get("content") or "").strip()
        tcs = m.get("tool_calls") or []
        calls = []
        for tc in tcs:
            fn = tc["function"]
            raw = fn.get("arguments")
            try:
                args = raw if isinstance(raw, dict) else json.loads(raw or "{}")
            except Exception:
                args = {}
            calls.append((fn["name"], args))

        trace.append(dict(step=step, think=think, think_len=len(think), body=body,
                          body_len=len(body), calls=[(n, a) for n, a in calls],
                          finish=ch.get("finish_reason"),
                          secs=round(gen_secs, 2),
                          prompt_ms=round(tm.get("prompt_ms", 0), 1),
                          decode_ms=round(tm.get("predicted_ms", 0), 1),
                          n_prompt=r["usage"]["prompt_tokens"],
                          n_gen=r["usage"]["completion_tokens"],
                          prefill_tps=round(tm.get("prompt_per_second", 0), 0),
                          decode_tps=round(tm.get("predicted_per_second", 0), 2)))
        if verbose:
            print("  step%-2d %5.1fs | prefill %5.0fms/%4dtok | decode %6.0fms/%4dtok @%5.1ft/s | think=%d" % (
                step, gen_secs, tm.get("prompt_ms", 0), r["usage"]["prompt_tokens"],
                tm.get("predicted_ms", 0), r["usage"]["completion_tokens"],
                tm.get("predicted_per_second", 0), len(think)), flush=True)

        if not calls:
            final = body
            break

        msgs.append({"role": "assistant", "content": body,
                     "tool_calls": [{"id": "c%d_%d" % (step, i), "type": "function",
                                     "function": {"name": n, "arguments": json.dumps(a, ensure_ascii=False)}}
                                    for i, (n, a) in enumerate(calls)]})
        tool_ms = 0.0
        for i, (name, args) in enumerate(calls):
            tt = time.time()
            out, is_err = exec_tool(name, args)
            tool_ms += (time.time() - tt) * 1000
            sig = name + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False)
            sig_seq.append(sig)
            if name == "write":
                write_files.append(args.get("file_path", ""))
            if is_err:
                err_sigs.append(sig)
            msgs.append({"role": "tool", "tool_call_id": "c%d_%d" % (step, i), "content": out})
            if verbose:
                print("        -> %s %s | %s" % (name, "ERR" if is_err else "ok",
                                                 out.replace("\n", " ")[:90]), flush=True)
        trace[-1]["tool_ms"] = round(tool_ms, 1)

    secs = time.time() - t0
    ok, why = spec["verify"](d, trace)

    # ---- 能力画像
    first_write = next((i for i, s in enumerate(trace) if any(n == "write" for n, _ in s["calls"])), 99)
    recon = [n for s in trace[:max(first_write, 0)] for n, _ in s["calls"] if n in ("read", "list_dir")]
    ran_test = any(n == "run" and ("test" in str(a).lower() or "linecount" in str(a).lower())
                   for s in trace for n, a in s["calls"])
    plan_words = sum(1 for s in trace if any(k in s["think"] for k in ("首先", "然后", "下一步", "分步", "计划")))
    repeated_write = len(write_files) - len(set(os.path.basename(x) for x in write_files))
    adjacent_dup = any(a == b for a, b in zip(sig_seq, sig_seq[1:]))
    # 只有"用完全相同的参数重试失败调用"才算不会恢复；失败后换个命令继续是正常行为
    failed_retry_same = any(sig_seq.count(s) > 1 for s in set(err_sigs))
    fake_ok = (not ok) and any(k in final for k in ("全部通过", "已经修复", "完成", "成功"))
    empty = len(final.strip()) <= 2
    ran_away = len(trace) >= spec["max_steps"] and trace[-1]["calls"]

    profile = {
        "RECON": "OK" if len(recon) >= 1 else "MISS",
        "PLAN": "OK" if plan_words >= 1 else "MISS",
        "ATOMIC": "OK" if (repeated_write <= 1 and not adjacent_dup) else "WEAK",
        "VERIFY": "OK" if ran_test else "MISS",
        "RECOVER": "WEAK" if failed_retry_same else "OK",
        "DELIVER": "OK" if (ok and final and not empty and not fake_ok) else "FAIL",
    }
    tags = []
    if not ok:
        tags.append("INCOMPLETE")
    if empty:
        tags.append("EMPTY")
    if adjacent_dup or repeated_write >= 3:
        tags.append("LOOP")
    if ran_away:
        tags.append("RUNAWAY")
    if fake_ok:
        tags.append("FAKEOK")
    for k, v in profile.items():
        if v in ("MISS", "WEAK"):
            tags.append(k + "_" + v)

    return dict(project=key, ok=ok, why=why, secs=round(secs, 1), steps=len(trace),
                temp=TEMPERATURE, seed=SEED,
                profile=profile, tags=tags, final=final[:600],
                trace=[{k: v for k, v in s.items() if k != "think"} for s in trace],
                thinks=[s["think"] for s in trace])


GPU_SAMPLES = []
_STOP = threading.Event()


def gpu_sampler():
    while not _STOP.is_set():
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw,clocks.sm,memory.free",
                 "--format=csv,noheader,nounits"], text=True, timeout=3)
            vals = [float(x.strip()) for x in out.split(",")[:4]]
            if len(vals) == 4:
                GPU_SAMPLES.append(vals)
        except Exception:
            pass
        _STOP.wait(1.0)


def main():
    keys = sys.argv[1:] or list(PROJECTS)
    th = threading.Thread(target=gpu_sampler, daemon=True)
    th.start()
    out = []
    for k in keys:
        print("========== %s ==========" % k, flush=True)
        try:
            r = run_project(k)
        except Exception as e:
            import traceback
            traceback.print_exc()
            r = dict(project=k, ok=False, why=str(e)[:150], tags=["ERROR"], profile={},
                     steps=0, secs=0, final="", trace=[], thinks=[])
        out.append(r)
        print("  => %s | %s | %s" % (k, "PASS" if r["ok"] else "FAIL", r["why"] or "-"), flush=True)
        print("  画像: %s" % json.dumps(r["profile"], ensure_ascii=False), flush=True)
        print("  标签: %s | 步数 %d | %.1fs\n" % (
            ",".join(r["tags"]) or "-", r["steps"], r["secs"]), flush=True)

    _STOP.set()
    th.join(timeout=3)
    if GPU_SAMPLES:
        u = [x[0] for x in GPU_SAMPLES]; pw = [x[1] for x in GPU_SAMPLES]
        cl = [x[2] for x in GPU_SAMPLES]; fr = [x[3] for x in GPU_SAMPLES]
        print("\n--- GPU 采样 (%d 点) ---" % len(GPU_SAMPLES))
        print("  利用率 平均 %.0f%% / 峰值 %.0f%%" % (sum(u)/len(u), max(u)))
        print("  功耗   平均 %.0f W / 峰值 %.0f W  (TGP 上限 140 W)" % (sum(pw)/len(pw), max(pw)))
        print("  SM 频率 平均 %.0f MHz / 峰值 %.0f MHz" % (sum(cl)/len(cl), max(cl)))
        print("  空闲显存 最小 %.0f MiB / 平均 %.0f MiB" % (min(fr), sum(fr)/len(fr)))
    print("=" * 60)
    for r in out:
        print("%-4s %-5s %2d步 %6.1fs  %s" % (r["project"], "PASS" if r["ok"] else "FAIL",
                                              r["steps"], r["secs"], ",".join(r["tags"]) or "-"))
    print("\n--- 耗时分解（每项目）---")
    for r in out:
        tr = r["trace"]
        pf = sum(x.get("prompt_ms", 0) for x in tr)
        dc = sum(x.get("decode_ms", 0) for x in tr)
        tl = sum(x.get("tool_ms", 0) for x in tr)
        ng = sum(x.get("n_gen", 0) for x in tr)
        print("  %s: 总 %.0fs | 预填充 %.1fs (%.0f%%) | 解码 %.1fs (%.0f%%) | 工具 %.1fs | 生成 %d tok" % (
            r["project"], r["secs"], pf/1000, 100*pf/max(r["secs"]*1000, 1),
            dc/1000, 100*dc/max(r["secs"]*1000, 1), tl/1000, ng))
        slow = sorted(tr, key=lambda x: x.get("secs", 0), reverse=True)[:2]
        for x in slow:
            print("     最慢 step%d: %.1fs (prefill %.0fms / decode %.0fms / %d tok)" % (
                x["step"], x.get("secs", 0), x.get("prompt_ms", 0), x.get("decode_ms", 0), x.get("n_gen", 0)))
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "_projectlab_result.json"),
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
