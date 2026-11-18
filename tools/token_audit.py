# -*- coding: utf-8 -*-
"""token 审计：把每一步生成的内容按用途拆开，精确算冗余占比。

分类：
  ARTIFACT  工件 —— write/edit 的 content 参数（任务的固有信息）
  THINK     思考 —— 其中再细分为 DRAFT（在思考里打完整草稿）、
                    RESTATE（复述问题/历史）、DECISION（真正的决策）
  REPLY     正文
  OLDSTR    old_string（复述已有的原文）
  OTHER     其它工具参数
"""
import json
import os
import re
import sys
import urllib.request

URL = "http://127.0.0.1:8081/tokenize"
MODEL = os.environ.get("QL_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_XL")


def ntok(s):
    if not s:
        return 0
    req = urllib.request.Request(URL, data=json.dumps({"model": MODEL, "content": s}).encode(),
                                 headers={"Content-Type": "application/json"})
    return len(json.loads(urllib.request.urlopen(req, timeout=60).read())["tokens"])


def classify_think(t):
    if not t:
        return "DECISION", 0, 0
    draft_hit = ("```" in t or len(re.findall(r"^\s*(def |class |import |from |with open|return |if |for )",
                                              t, re.M)) >= 3)
    return ("DRAFT" if draft_hit else "DECISION",
            1 if re.search(r"(用户(要求|问|说|让)|任务(要求|是)|根据截图|当前问题)", t[:120]) else 0,
            1 if re.search(r"(让我确认|输出准备|接下来我应该|准备回答|再检查一遍|首先，我需要理解)", t) else 0)


def audit(result_path):
    rows = json.load(open(result_path, encoding="utf-8"))
    for r in rows:
        print("\n===== %s | %d 步 | 总生成 %d tok =====" % (
            r["project"], r["steps"], sum(x.get("n_gen", 0) for x in r["trace"])))
        tot = dict(ARTIFACT=0, OLDSTR=0, THINK=0, REPLY=0, OTHER=0)
        think_kind = dict(DRAFT=0, DECISION=0)
        flags = dict(RESTATE=0, RITUAL=0)
        for s, think in zip(r["trace"], r.get("thinks", [{}] * len(r["trace"]))):
            th = think if isinstance(think, str) else (think.get("text", "") if isinstance(think, dict) else "")
            body = s.get("body", "")
            nt = ntok(th)
            tot["THINK"] += nt
            tot["REPLY"] += ntok(body)
            kind, restate, ritual = classify_think(th)
            think_kind[kind] += nt
            flags["RESTATE"] += restate
            flags["RITUAL"] += ritual
            for name, args in s.get("calls", []):
                if name in ("write", "edit"):
                    tot["ARTIFACT"] += ntok(args.get("content") or args.get("new_string") or "")
                    tot["OLDSTR"] += ntok(args.get("old_string") or "")
                    rest = {k: v for k, v in args.items()
                            if k not in ("content", "new_string", "old_string")}
                    tot["OTHER"] += ntok(json.dumps(rest, ensure_ascii=False))
                elif name == "apply_patch":
                    for e in args.get("edits", []):
                        tot["ARTIFACT"] += ntok(e.get("new_string") or "")
                        tot["OLDSTR"] += ntok(e.get("old_string") or "")
                    tot["OTHER"] += ntok(args.get("file_path") or "")
                else:
                    tot["OTHER"] += ntok(json.dumps(args, ensure_ascii=False))
        s = sum(tot.values())
        for k, v in tot.items():
            print("  %-9s %5d tok  %5.1f%%" % (k, v, 100 * v / max(s, 1)))
        print("  思考细分: 草稿 %d tok / 决策 %d tok" % (think_kind["DRAFT"], think_kind["DECISION"]))
        print("  复述开头 %d 步, 仪式化收尾 %d 步" % (flags["RESTATE"], flags["RITUAL"]))
        print("  —— 按内容合计 %d tok（与 usage 有少量格式 token 差）" % s)


if __name__ == "__main__":
    audit(sys.argv[1] if len(sys.argv) > 1 else
          os.path.join(os.path.dirname(__file__), "_projectlab_result.json"))
