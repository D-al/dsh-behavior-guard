# -*- coding: utf-8 -*-
"""35B agent 错误类型分类器 + 基线 / 新类型检测（v1.0）

设计原则：
1. 根因优先：root(3) > behavior(2) > surface(1)；表面型（tool_failure）被根因型压制。
2. 互斥/主次：显式 suppresses 规则 + 最多保留 3 个类型（1 primary + <=2 secondary）。
3. 可复现：基线只来自 85 组 v2 去重数据（off27/on28/inject-on30），含频次/首次出现/分组分布。

用法：
  python error_taxonomy.py --build-baseline
  python error_taxonomy.py --check <sid>          # sid 可全名或 8 位前缀
  python error_taxonomy.py --report               # 打印基线报告（分组分布 / 稀有类型）
  python error_taxonomy.py --self-test            # 内置规则自检
"""
from __future__ import annotations
import argparse
import collections
import datetime as _dt
import glob
import json
import os
import re
import subprocess
import sys

BENCH = r"D:/Brain/workspace/bench"
TRACE = BENCH + "/_trace.jsonl"
REFLECTION = BENCH + "/_ab_reflection_result.json"
BASELINE = BENCH + "/_error_baseline.json"
SESSIONS_ROOT = r"D:/Brain/dsh-data/sessions"
DUMP_JS = r"D:/tmp/dsh-investigate/dump_session.mjs"

TIER = {"root": 3, "behavior": 2, "surface": 1}
SEV = {"high": 3, "mid": 2, "low": 1}

# ---------------------------------------------------------------- 上下文

class Ctx:
    """归类所需的归一化视图：trace 行 + 会话文本。"""

    def __init__(self, rows, text):
        self.rows = list(rows or [])
        self.text = text or ""
        self.counts = collections.Counter(str(r.get("kind") or "") for r in self.rows)
        self.codes = collections.Counter(
            str(r.get("code") or "") for r in self.rows if r.get("code")
        )
        self.tool_names = collections.Counter(
            str(r.get("name") or "") for r in self.rows
            if r.get("kind") == "tool_call" and r.get("name")
        )

    def k(self, kind):
        return self.counts.get(kind, 0)

    def flag(self, kind, field, truthy=True):
        n = 0
        for r in self.rows:
            if r.get("kind") == kind and bool(r.get(field)) == truthy:
                n += 1
        return n

    def field(self, kind, key, default=0):
        vals = [r.get(key, default) for r in self.rows if r.get("kind") == kind]
        return max(vals) if vals else default

    def re_n(self, pattern, flags=0):
        return len(re.findall(pattern, self.text, flags))


# ---------------------------------------------------------------- 检测规则
# 每条规则返回 (命中?, 证据片段以 ';' 分隔)。证据用于报告可追溯。

def _inj_interrupt(c):
    ev = []
    esc = c.flag("d1_probe_guard", "escalated")
    if esc:
        ev.append("d1_probe_guard:escalatedx%d" % esc)
    if c.k("ask_user_question") or c.tool_names.get("ask_user_question", 0):
        ev.append("ask_user_question")
    if c.re_n(r"本来(可以|就)?(直接)?(结束|完成)|明明(已经)?(完成|写完|改好)|"
              r"(多余|不必要).{0,8}(指令|提醒)|(还|仍|被迫).{0,10}(按|遵守).{0,6}(流程|要求)|"
              r"其实.{0,10}已经.{0,8}(完成|够了)"):
        ev.append("text:plan-interrupted")
    if c.k("state_board_inject") >= 2 and c.k("control_turn") >= 1:
        ev.append("state_board_inject>=2+control_turn")
    ok = bool(esc and (len(ev) >= 2)) or (len(ev) >= 2 and "text:plan-interrupted" in ev)
    return ok, ";".join(ev)


def _fake_verify(c):
    ev = []
    if c.k("edit_is_verify"):
        ev.append("edit_is_verify")
    if c.re_n(r"自签|验证报告|没有(可用)?的?verify_agent|没看到(可用)?的?脚本|"
              r"不用(再)?验证|已经验证过(了)?|"
              r"(没|未).{0,6}验证.{0,10}(就|直接).{0,6}(结束|完成|告诉用户)"):
        ev.append("text:self-signed-verify")
    # 反复声称"确认改动生效"却没有任何 edit/write 调用 = 假验证循环
    if c.k("verify_on_stop") and c.k("tool_call") <= c.k("verify_on_stop"):
        ev.append("verify_on_stop-without-tool")
    return bool(ev), ";".join(ev)


def _verify_narration_loop(c):
    """反复声称'确认改动生效'却没有任何写入——空想验证，与自签验证区分。"""
    n = c.re_n(r"确认.{0,12}(改动|修改|生效)")
    if n >= 2 and (c.tool_names.get("edit", 0) + c.tool_names.get("write", 0)) == 0:
        return True, "text:verify-narration-loop-x%d(no-edit/write)" % n
    return False, ""


def _verify_no_channel(c):
    ev = []
    if c.re_n(r"没有.{0,6}(检查器|校验器)|无.{0,6}(检查器|校验器)|"
              r"没有.{0,10}(脚本|工具).{0,10}(验证|检查)|没看到.{0,10}(脚本|工具)|"
              r"(VBS|vbs).{0,12}(无|没有).{0,6}(检查|验证)"):
        ev.append("text:no-verify-channel")
    if c.k("verify_on_stop") and c.k("tool_failure"):
        ev.append("verify_on_stop+tool_failure")
    return bool(ev), ";".join(ev)


def _doing_right_blocked(c):
    ev = []
    if c.k("zero_write_claim") and (c.k("safety_gate_block") or c.k("step_hard_stop")):
        ev.append("zero_write_claim+gate/stop")
    if c.flag("fep_cycle", "verified") and (c.k("verify_on_stop") or c.k("step_hard_stop")):
        ev.append("fep_verified+verify_on_stop/stop")
    if c.re_n(r"明明.{0,12}(改|写|验证)|(已|已经).{0,8}在.{0,4}第.{0,4}(轮|步).{0,8}(改|写)|"
              r"为什么.{0,10}(说|判|认为).{0,8}(没|无|零)|(改|写).{0,10}了.{0,10}却.{0,8}(被拦|不算)"):
        ev.append("text:did-right-but-blocked")
    return bool(ev), ";".join(ev)


def _recall_blind(c):
    ev = []
    if c.re_n(r"(compaction|压缩|摘要).{0,16}(丢|看不到|没(有)?|缺)|"
              r"看不到.{0,8}(历史|之前)|之前.{0,12}(改|写).{0,12}但.{0,8}(没|不)|"
              r"记不(清|得)|历史.{0,8}(看不到|找不到)"):
        ev.append("text:recall-blind")
    if c.k("archive_dedup") and c.k("tool_failure") >= 1:
        ev.append("archive_dedup+tool_failure")
    return bool(ev), ";".join(ev)


def _tool_detour(c):
    ev = []
    if c.re_n(r"绕开|绕过|不用.{0,6}shell|直接.{0,8}write.{0,6}(工具|创建)|"
              r"编码问题|被.{0,8}(逼|迫).{0,8}(换|用)|换.{0,8}工具.{0,8}(创建|写)"):
        ev.append("text:tool-detour")
    if c.k("shell_write_counted") and c.tool_names.get("write", 0):
        ev.append("shell_write_counted+write")
    if c.tool_names.get("pwsh", 0) >= 5 and c.k("tool_failure") >= 2:
        ev.append("pwsh>=5+fail>=2")
    return bool(ev), ";".join(ev)


def _hard_stop_loop(c):
    ev = []
    stops = c.k("step_hard_stop")
    warns = c.k("step_hard_warn")
    if stops:
        ev.append("step_hard_stopx%d(streak<=%d)" % (stops, c.field("step_hard_stop", "streak")))
    if warns >= 2:
        ev.append("step_hard_warnx%d" % warns)
    return bool(ev), ";".join(ev)


def _repeat_write_spin(c):
    ev = []
    if c.k("semantic_check_fail"):
        ev.append("semantic_check_failx%d" % c.k("semantic_check_fail"))
    return bool(ev), ";".join(ev)


def _probe_loop(c):
    ev = []
    if c.field("d1_probe_guard", "count") >= 3:
        ev.append("d1_probe_guard.count=%d" % c.field("d1_probe_guard", "count"))
    if c.field("read_denied", "reads") >= 3:
        ev.append("read_denied.reads=%d" % c.field("read_denied", "reads"))
    if c.field("pattern_lock", "repetition", 0.0) >= 0.8:
        ev.append("pattern_lock.repetition=%.2f" % c.field("pattern_lock", "repetition", 0.0))
    if c.k("review_verdict") >= 2:
        ev.append("review_verdictx%d" % c.k("review_verdict"))
    return bool(ev), ";".join(ev)


def _intent_drift(c):
    ev = []
    if c.flag("intent_drift", "drifted"):
        ev.append("intent_drift:drifted=true")
    if c.re_n(r"跑题|偏离.{0,6}(目标|任务)|忘(了|记).{0,6}(任务|目标)"):
        ev.append("text:intent-drift")
    return bool(ev), ";".join(ev)


def _forced_help(c):
    ev = []
    if c.flag("d1_probe_guard", "escalated") and (
            c.k("ask_user_question") or c.tool_names.get("ask_user_question", 0)):
        ev.append("escalated+ask_user_question")
    if c.re_n(r"只能(去)?问用户|被迫.{0,8}(求助|问)|不(知道|确定).{0,8}(该|去).{0,6}问"):
        ev.append("text:forced-help")
    return bool(ev), ";".join(ev)


def _side_effect_damage(c):
    ev = []
    if c.re_n(r"修坏|重复.{0,8}bundle|dispose|空白|白屏|删错|覆盖.{0,8}(坏|错)|"
              r"(写|改).{0,8}(坏|错).{0,8}(文件|配置)"):
        ev.append("text:side-effect-damage")
    return bool(ev), ";".join(ev)


def _edit_anchor(c):
    n = c.codes.get("FS_EDIT_NOT_FOUND", 0)
    return n > 0, "tool_failure:FS_EDIT_NOT_FOUNDx%d" % n if n else ""


def _tool_failure_unhealed(c):
    fails, heals = c.k("tool_failure"), c.k("tool_failure_heal")
    n = fails - heals
    return n > 0, "tool_failure%d-heal%d=unhealed%d" % (fails, heals, n) if n > 0 else ""


# code, 中文, tier, severity, detector, suppresses, 来源
RULES = [
    dict(code="INJ_INTERRUPT", zh="注入打断原计划", tier="root", severity="high", fn=_inj_interrupt,
         suppress=["PROBE_LOOP", "FORCED_HELP"], source="CAPABILITY_MISMATCH_AUDIT_20261127 §1.5"),
    dict(code="FAKE_VERIFY", zh="假验证/自签验证", tier="root", severity="high", fn=_fake_verify,
         suppress=["VERIFY_NO_CHANNEL", "HARD_STOP_LOOP"], source="CAPABILITY_MISMATCH_AUDIT §1.2 / MISTAKE_BOOK（CRITIC 外部锚定）"),
    dict(code="VERIFY_NARRATION_LOOP", zh="空想验证循环（反复声称确认改动但无写入）", tier="behavior", severity="mid",
         fn=_verify_narration_loop, suppress=[], source="本次 85 组基线实证（AB 任务中高频出现）"),
    dict(code="VERIFY_NO_CHANNEL", zh="想验证但没通道", tier="root", severity="mid", fn=_verify_no_channel,
         suppress=["FAKE_VERIFY"], source="CAPABILITY_MISMATCH_AUDIT §1.2"),
    dict(code="DOING_RIGHT_BLOCKED", zh="做对了却被拦", tier="root", severity="high", fn=_doing_right_blocked,
         suppress=["HARD_STOP_LOOP", "TOOL_FAILURE_UNHEALED"], source="CAPABILITY_MISMATCH_AUDIT §1.1"),
    dict(code="RECALL_BLIND", zh="回忆盲区/看不到历史", tier="root", severity="mid", fn=_recall_blind,
         suppress=[], source="CAPABILITY_MISMATCH_AUDIT §1.3 / REFLECTION_RECALL_GAP"),
    dict(code="TOOL_DETOUR", zh="工具绕路/工具面逼出绕路", tier="root", severity="mid", fn=_tool_detour,
         suppress=["EDIT_ANCHOR_MISMATCH"], source="CAPABILITY_MISMATCH_AUDIT §1.4"),
    dict(code="HARD_STOP_LOOP", zh="无效循环硬停", tier="behavior", severity="high", fn=_hard_stop_loop,
         suppress=[], source="AB_JUDGEMENT_FINAL_20261127（主判据） / 已证伪清单"),
    dict(code="REPEAT_WRITE_SPIN", zh="重复写入空转", tier="behavior", severity="mid", fn=_repeat_write_spin,
         suppress=[], source="AGENT_BRIEF 铁律 / semantic_check_fail（连续写入完全相同）"),
    dict(code="PROBE_LOOP", zh="重复探测回圈", tier="behavior", severity="mid", fn=_probe_loop,
         suppress=[], source="CAPABILITY_MISMATCH_AUDIT §1.5 / d1_probe_guard / read_denied"),
    dict(code="INTENT_DRIFT", zh="意图漂移", tier="behavior", severity="mid", fn=_intent_drift,
         suppress=[], source="intent_drift trace / GOAL_STATEMENT_EVOLUTION"),
    dict(code="FORCED_HELP", zh="被迫向用户求助", tier="behavior", severity="mid", fn=_forced_help,
         suppress=[], source="CAPABILITY_MISMATCH_AUDIT §1.5（a91afe6d L440→ask_user_question）"),
    dict(code="SIDE_EFFECT_DAMAGE", zh="副作用破坏", tier="behavior", severity="high", fn=_side_effect_damage,
         suppress=[], source="POSTMORTEM_PLUGIN_REPAIR / SESSION_SELF_STOP / BLANK_UI"),
    dict(code="EDIT_ANCHOR_MISMATCH", zh="edit 锚点失配", tier="surface", severity="low", fn=_edit_anchor,
         suppress=["TOOL_FAILURE_UNHEALED"], source="AGENT_BRIEF 优先级 / MISTAKE_BOOK C-001"),
    dict(code="TOOL_FAILURE_UNHEALED", zh="工具失败未自愈", tier="surface", severity="mid", fn=_tool_failure_unhealed,
         suppress=[], source="tool_failure / tool_failure_heal trace kind"),
]
RULE_BY_CODE = {r["code"]: r for r in RULES}


# ---------------------------------------------------------------- 核心 API

def classify_session(sid, trace_rows, session_text) -> list:
    """返回会话命中的错误类型列表（已做主次互斥与数量裁剪）。

    每项: {code, zh, tier, severity, evidence, confidence, role, source}
    """
    c = Ctx(trace_rows, session_text)
    hits = []
    for r in RULES:
        ok, ev = r["fn"](c)
        if not ok:
            continue
        n_ev = len([x for x in ev.split(";") if x])
        hits.append(dict(
            code=r["code"], zh=r["zh"], tier=r["tier"], severity=r["severity"],
            evidence=ev, confidence=round(min(1.0, 0.6 + 0.12 * (n_ev - 1)), 2),
            role="secondary", source=r["source"],
        ))
    have = {h["code"] for h in hits}
    drop = set()
    for h in hits:
        for s in RULE_BY_CODE[h["code"]]["suppress"]:
            if s in have:
                drop.add(s)
    hits = [h for h in hits if h["code"] not in drop]
    hits.sort(key=lambda h: (-TIER[h["tier"]], -SEV[h["severity"]], -h["confidence"]))
    keep = hits[:1]
    for h in hits[1:]:
        if len(keep) >= 3:
            break
        if h["tier"] != "surface":
            keep.append(h)
        elif len(keep) < 2 and not any(k["tier"] == "surface" for k in keep):
            keep.append(h)
    for i, h in enumerate(keep):
        h["role"] = "primary" if i == 0 else "secondary"
    return keep


def _short(sid):
    sid = str(sid or "")
    parts = sid.split("-")
    return parts[1][:8] if sid.startswith("session-") and len(parts) > 1 else sid[:8]


def _load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def load_trace():
    by_sid = collections.defaultdict(list)
    for r in _load_jsonl(TRACE):
        by_sid[_short(r.get("sid"))].append(r)
    return by_sid


def load_v2():
    """85 组去重 v2 数据。"""
    records = json.load(open(REFLECTION, encoding="utf-8"))
    seen, out = set(), []
    for x in records:
        sid = x.get("sid", "")
        if sid in seen:
            continue
        seen.add(sid)
        if x.get("batch") == "v2":
            out.append(x)
    return out


_SESSION_CACHE = {}

def session_text_for(sid):
    """从 session.v4.jsonl.zstd 提取 assistant 推理/正文 + harness 注入文本。"""
    key = _short(sid)
    if key in _SESSION_CACHE:
        return _SESSION_CACHE[key]
    full = str(sid)
    uuid = full.replace("session-", "")
    target = None
    for f in glob.glob(SESSIONS_ROOT + "/**/session.v4.jsonl.zstd", recursive=True):
        if uuid[:8] in os.path.basename(os.path.dirname(f)):
            target = f
            break
    text = ""
    if target and os.path.exists(DUMP_JS):
        try:
            raw = subprocess.run(["node", DUMP_JS, target], capture_output=True,
                                 timeout=30).stdout.decode("utf-8", "replace")
            chunks = []
            for line in raw.splitlines():
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                data = d.get("data") or {}
                if d.get("type") == "assistant/message":
                    msg = data.get("message") or {}
                    for part in msg.get("content", []):
                        if isinstance(part, dict) and part.get("type") in ("reasoning", "text"):
                            chunks.append(str(part.get("text") or ""))
                elif d.get("type") == "user/message":
                    src = (data.get("source") or {}).get("kind") or ""
                    if src in ("behavior-guard", "tool-failure-healer", "harness", "system-inject"):
                        for part in data.get("content", []):
                            if isinstance(part, dict) and part.get("type") == "text":
                                chunks.append("[注入]" + str(part.get("text") or ""))
            text = "\n".join(chunks)
        except Exception as e:
            text = ""
    _SESSION_CACHE[key] = text
    return text


def build_baseline(write=True) -> dict:
    """从 85 组 v2 数据构建基线。"""
    v2, trace = load_v2(), load_trace()
    groups = collections.Counter(x.get("group") for x in v2)
    stats = {r["code"]: dict(code=r["code"], zh=r["zh"], tier=r["tier"],
                             severity=r["severity"], count=0, sessions=[],
                             first_seen=None, by_group=collections.Counter(),
                             source=r["source"]) for r in RULES}
    sessions = []
    for x in v2:
        sid = x["sid"]
        rows = trace.get(_short(sid), [])
        text = session_text_for(sid)
        hits = classify_session(sid, rows, text)
        codes = [h["code"] for h in hits]
        sessions.append(dict(sid=sid, group=x.get("group"), primary=codes[0] if codes else None,
                             types=codes, tool_calls=x.get("tool_calls"),
                             hard_stop=x.get("hard_stop"), answer_correct=x.get("answer_correct")))
        for h in hits:
            s = stats[h["code"]]
            s["count"] += 1
            s["sessions"].append(_short(sid))
            s["by_group"][x.get("group")] += 1
            ts = min((str(r.get("ts") or "") for r in rows if r.get("kind")), default="")
            if s["first_seen"] is None or ts < s["first_seen"].get("ts", "9999"):
                s["first_seen"] = dict(sid=_short(sid), ts=ts, group=x.get("group"))
    for s in stats.values():
        s["by_group"] = dict(s["by_group"])
    out = dict(
        version="1.0",
        generated_at=_dt.datetime.now().isoformat(timespec="seconds"),
        description="35B agent 错误类型基线：85 组 v2（off27/on28/inject-on30）",
        taxonomy=[dict(code=r["code"], zh=r["zh"], tier=r["tier"], severity=r["severity"],
                       suppress=r["suppress"], source=r["source"]) for r in RULES],
        groups=dict(groups), types=stats, sessions=sessions,
    )
    if write:
        os.makedirs(BENCH, exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    return out


def load_baseline():
    """从 _error_baseline.json 读取；文件缺失时现场从 85 组重建。"""
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as f:
            return json.load(f)
    return build_baseline(write=False)


def detect_novel(types, baseline=None, mode="narrow") -> list:
    """检测未见过的类型。

    mode='narrow'：基线 0 次（含 taxonomy 未登记类型）；'broad'：基线出现过但 <3 次。
    types 可为 classify_session 返回的 dict 列表，或 code 字符串列表。
    """
    b = baseline or load_baseline()
    stats = b.get("types", {})
    codes = []
    for t in types or []:
        codes.append(t.get("code") if isinstance(t, dict) else str(t))
    if mode == "broad":
        return sorted(c for c in set(codes) if 0 < stats.get(c, {}).get("count", 0) < 3)
    return sorted(c for c in set(codes) if stats.get(c, {}).get("count", 0) == 0)


# ---------------------------------------------------------------- CLI

def _report(b):
    print("基线版本", b.get("version"), "生成于", b.get("generated_at"))
    print("分组", b.get("groups"))
    print("\n%-24s %-22s %5s %6s %6s %6s %s" %
          ("CODE", "中文", "严重度", "总次", "off", "on", "inject-on"))
    rows = sorted(b["types"].values(), key=lambda s: -s["count"])
    for s in rows:
        g = s["by_group"]
        print("%-24s %-22s %5s %6d %6d %6d %6d" %
              (s["code"], s["zh"], s["severity"], s["count"],
               g.get("off", 0), g.get("on", 0), g.get("inject-on", 0)))
    print("\n狭义新类型(基线0次):", sorted(s["code"] for s in rows if s["count"] == 0))
    print("广义新类型(基线<3次):", sorted(s["code"] for s in rows if 0 < s["count"] < 3))


def _self_test():
    cases = [
        ("INJ_INTERRUPT", [dict(kind="d1_probe_guard", escalated=True),
                           dict(kind="tool_call", name="ask_user_question")], ""),
        ("FAKE_VERIFY", [dict(kind="edit_is_verify")], ""),
        ("VERIFY_NARRATION_LOOP", [], "我得先确认刚才那次改动到底生效了没有。\n再确认一下改动生效了没有。"),
        ("DOING_RIGHT_BLOCKED", [dict(kind="zero_write_claim"),
                                 dict(kind="step_hard_stop", streak=9)], ""),
        ("TOOL_DETOUR", [dict(kind="shell_write_counted"),
                         dict(kind="tool_call", name="write")], ""),
        ("RECALL_BLIND", [], "compaction 摘要把 @local 的内容全丢了，看不到之前的历史"),
        ("HARD_STOP_LOOP", [dict(kind="step_hard_stop", streak=12)], ""),
        ("PROBE_LOOP", [dict(kind="pattern_lock", repetition=0.85)], ""),
        ("INTENT_DRIFT", [dict(kind="intent_drift", drifted=True)], ""),
        ("EDIT_ANCHOR_MISMATCH", [dict(kind="tool_failure", code="FS_EDIT_NOT_FOUND")], ""),
        ("TOOL_FAILURE_UNHEALED", [dict(kind="tool_failure"), dict(kind="tool_failure")], ""),
    ]
    ok = 0
    for want, rows, text in cases:
        got = [h["code"] for h in classify_session("test", rows, text)]
        flag = "OK" if want in got else "FAIL"
        ok += flag == "OK"
        print("[%s] want=%s got=%s" % (flag, want, got))
    print("self-test %d/%d" % (ok, len(cases)))
    return 0 if ok == len(cases) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build-baseline", action="store_true", help="重建 _error_baseline.json")
    ap.add_argument("--check", metavar="SID", help="检查单会话（sid 全名或 8 位前缀）")
    ap.add_argument("--report", action="store_true", help="打印基线报告")
    ap.add_argument("--self-test", action="store_true", help="规则自检")
    args = ap.parse_args(argv)
    if args.build_baseline:
        b = build_baseline(write=True)
        print("已写入", BASELINE, "类型数", len(b["types"]), "会话数", len(b["sessions"]))
        _report(b)
        return 0
    if args.check:
        b = load_baseline()
        sid = args.check
        rows = load_trace().get(_short(sid), [])
        text = session_text_for(sid)
        hits = classify_session(sid, rows, text)
        print("SID", sid, "| trace_rows", len(rows), "| text_chars", len(text))
        for h in hits:
            print("  [%s/%s] %s (%s) 置信=%.2f | %s | %s" %
                  (h["role"], h["tier"], h["code"], h["zh"], h["confidence"],
                   h["evidence"], h["source"]))
        print("  狭义新类型:", detect_novel(hits, b, "narrow"))
        print("  广义新类型:", detect_novel(hits, b, "broad"))
        return 0
    if args.report:
        _report(load_baseline())
        return 0
    if args.self_test:
        return _self_test()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
