#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学习闭环 B 段 watcher —— 把 harness 写出的打点变成可回注的沉淀。

背景（2026-11-18 根因）：9 个学习脚本在 bench/ 里但从无调用者，等于死代码。
A 段已在运行版 harness 的 tool_result / crit_hit 处写：
  _pending_learn.jsonl   —— {ts,sid,step,kind:'crit_hit',id:'C-001'}
  _outcome.jsonl         —— {ts,sid,step,tool,target,status,goal,...}
本 watcher 消费它们，跑 crit_decay / crit_revision / skill_draft / trace_timeline /
session_tree / episodic_search，并把"可回注的结论"追加到 _learn_feedback.jsonl，
由 harness 的 pre-step 读取注入下一轮 → 形成 轨迹→沉淀→回注 闭环。

设计纪律：
- 只追加 feedback，绝不改 critbank.json / skills/（G1+G2 人工审批制）
- 增量处理（记住文件 offset），不重复结算
- 全静默失败：任何脚本报错只写日志，不影响主流程
- 心跳写 _learn_watcher.log，方便审计

用法：
  python bench/learn_watcher.py --once     # 跑一轮就退出（测试/计划任务）
  python bench/learn_watcher.py             # 常驻，每 30s 一轮
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

BENCH = os.path.dirname(os.path.abspath(__file__))
PY = r'D:\Python\python.exe'
PENDING = os.path.join(BENCH, '_pending_learn.jsonl')
OUTCOME = os.path.join(BENCH, '_outcome.jsonl')
TRACE = os.path.join(BENCH, '_trace.jsonl')
FEEDBACK = os.path.join(BENCH, '_learn_feedback.jsonl')
STATE = os.path.join(BENCH, '_learn_watcher_state.json')
LOG = os.path.join(BENCH, '_learn_watcher.log')
CRITBANK_STATE = os.path.join(BENCH, '_critbank_state.json')
DRAFTS = os.path.join(BENCH, '_skill_drafts')  # skill_draft.py 产物在根目录（draft-*.md）
REVISIONS = os.path.join(BENCH, '_crit_revisions.json')
INTERVAL = 30          # 心跳：只查 offset，零新数据时几乎零成本
CONSOLIDATE_EVERY = 20 # 巩固层：每 20 轮 ≈ 10 分钟跑一次索引/诊断（社区记忆巩固尺度；原为每轮 30s，过密）

# A0 — test SID blacklist (loaded lazily once)
_TEST_SIDS_CACHE = None


def _load_test_sids():
    """Load test_sids.json; return set() if missing/invalid."""
    global _TEST_SIDS_CACHE
    if _TEST_SIDS_CACHE is not None:
        return _TEST_SIDS_CACHE
    import json as _json
    from pathlib import Path as _Path
    _candidates = [
        str(_Path(__file__).resolve().parent.parent / 'test_sids.json'),
        str(_Path(__file__).resolve().parent / 'test_sids.json'),
        str(_Path(os.environ.get('BENCH_DIR', BENCH)) / 'test_sids.json'),
    ]
    for _p in _candidates:
        try:
            with open(_p, encoding='utf-8') as _f:
                data = _json.load(_f)
                sids = set(data.get('sids', []))
                _TEST_SIDS_CACHE = sids
                return sids
        except Exception:
            continue
    _TEST_SIDS_CACHE = set()
    return _TEST_SIDS_CACHE

SCRIPTS = {
    'crit_decay': [PY, os.path.join(BENCH, 'crit_decay.py')],
    'skill_draft': [PY, os.path.join(BENCH, 'skill_draft.py')],
    'crit_revision': [PY, os.path.join(BENCH, 'crit_revision.py')],
    'trace_timeline': [PY, os.path.join(BENCH, 'trace_timeline.py')],
    'session_tree': [PY, os.path.join(BENCH, 'session_tree.py'), '--build'],
    'episodic_index': [PY, os.path.join(BENCH, 'episodic_search.py'), '--index'],
    'intent_drift': [PY, os.path.join(BENCH, 'intent_drift.py')],
    'mind_state': [PY, os.path.join(BENCH, 'mind_state.py'), '--json'],
    # 地基守护：每10分钟巡检6条地基不变量，零LLM几秒
    'foundation_guard': [PY, 'D:/Brain/publish/dsh-behavior-guard/tools/foundation_guard.py'],
}


def log(msg):
    line = f'{datetime.now().isoformat(timespec="seconds")} {msg}\n'
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line)
    except Exception:
        pass
    print(line.strip())


def load_state():
    try:
        with open(STATE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'pending_offset': 0, 'outcome_offset': 0, 'settled_hits': [], 'last_digest': '', 'runs': 0}


def save_state(s):
    try:
        with open(STATE, 'w', encoding='utf-8') as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def read_new(path, offset):
    """增量读 jsonl，返回 (新行列表, 新 offset)。"""
    if not os.path.exists(path):
        return [], offset
    try:
        with open(path, 'rb') as f:
            f.seek(offset)
            data = f.read()
            new_off = f.tell()
        lines = data.decode('utf-8', errors='replace').split('\n')
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out, new_off
    except Exception:
        return [], offset


def run_script(name, args=None):
    cmd = list(SCRIPTS[name]) + (args or [])
    # 2026-11-19：用 python.exe 调子脚本时，subprocess.run 默认弹 cmd 窗口。
    # 本 watcher 每 30s 跑 mind_state、每 20 轮（≈10min）跑 5 个索引/诊断脚本，
    # 每次都闪一个黑窗口 → 用户看到"每隔一段时间弹几个一闪而过的命令行"。
    # 与 freeze_watch.py 一致，显式 CREATE_NO_WINDOW（Linux 上忽略）。
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           encoding='utf-8', errors='replace', creationflags=flags)
        return r.returncode == 0, (r.stdout or '').strip()
    except Exception as e:
        log(f'[script:{name}] ERROR {e}')
        return False, ''


def append_feedback(sid, text, source):
    """追加一条可回注反馈（harness pre-step 会读）。同 source+text 去重，避免每轮刷屏。"""
    text = str(text)[:500]
    recent = []
    try:
        if os.path.exists(FEEDBACK):
            with open(FEEDBACK, encoding='utf-8') as f:
                recent = [json.loads(x) for x in f if x.strip()]
    except Exception:
        pass
    if any(r.get('source') == source and r.get('text') == text for r in recent):
        return False
    rec = {'ts': datetime.utcnow().isoformat(timespec='milliseconds') + 'Z',
           'sid': sid, 'text': text, 'source': source, 'consumed': False}
    try:
        with open(FEEDBACK, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        log(f'[feedback] sid={sid} source={source}: {text[:80]}')
        return True
    except Exception as e:
        log(f'[feedback] ERROR {e}')
        return False


def settle_crit_hits(state, hits, outcomes, trace_rows):
    """CritBank 命中结算：命中后窗口内又有失败 → harmful，否则 helpful。"""
    # 每个 (sid,id) 只结算一次
    seen = set(tuple(x) for x in state.get('settled_hits', []))
    window = 3
    for h in hits:
        sid, cid, step = h.get('sid', ''), h.get('id', ''), h.get('step', 0)
        if not cid or (sid, cid, step) in seen:
            continue
        # 找命中之后 window 步内同 sid 的失败 outcome
        later_fail = [o for o in outcomes + trace_rows
                      if o.get('sid') == sid and (o.get('step') or 0) > step
                      and (o.get('step') or 0) <= step + window
                      and o.get('status') in ('FAIL', 'UNPRODUCTIVE')]
        flag = '--harmful' if later_fail else '--ok'
        ok, _ = run_script('crit_decay', ['--hit', cid, flag])
        if ok:
            state.setdefault('settled_hits', []).append([sid, cid, step])
            log(f'[settle] {cid} {flag} (sid={sid} step={step} later_fail={len(later_fail)})')
        seen.add((sid, cid, step))


def digest(state, *, deep=False):
    """沉淀：事件驱动层每轮跑（轻）；deep=True 时加跑索引/诊断（每 CONSOLIDATE_EVERY 轮）。

    2026-11-19 频率分层依据：记忆巩固社区惯例是"事件触发 + 周期性离线巩固"，
    原实现每 30s 跑全部 8 个脚本（含会话树/情景索引/意图漂移/心智状态），
    在无新数据时纯属空转（实测心跳日志常见 new_hits=0 new_outcomes=0）。
    """
    # 1) skill 草稿：新草稿 → 提示有可审批技能（不自动入库）
    before = set(os.listdir(DRAFTS)) if os.path.isdir(DRAFTS) else set()
    run_script('skill_draft')
    after = set(os.listdir(DRAFTS)) if os.path.isdir(DRAFTS) else set()
    new = after - before
    for name in sorted(new):
        append_feedback('', f'技能草稿 {name} 已生成（待人工确认后才会入库生效，路径 bench/_skill_drafts/），'
                        '如与当前任务相关可 read 后参考。', 'skill_draft')

    # 2) crit 降级建议
    ok, _ = run_script('crit_revision')
    if ok and os.path.exists(REVISIONS):
        try:
            with open(REVISIONS, encoding='utf-8') as f:
                revs = json.load(f)
            items = revs if isinstance(revs, list) else revs.get('suggestions', [])
            for r in items[:2]:
                append_feedback('', f"教训 {r.get('id')} 命中后仍失败 {r.get('harm_count')} 次，"
                                f"建议降级：{str(r.get('lesson',''))[:80]}", 'crit_revision')
        except Exception:
            pass

    # 3) 失败时间线：滞后过大 → 门控前移提示
    ok, out = run_script('trace_timeline')
    if ok and '滞后中位数' in out:
        line = [x for x in out.split('\n') if '滞后中位数' in x or '→ 建议' in x]
        if line:
            append_feedback('', '失败归因时间线：' + '；'.join(line)[:300], 'trace_timeline')

    if deep:
        consolidate(state)


def consolidate(state):
    """巩固层（每 CONSOLIDATE_EVERY 轮 ≈10 分钟）：索引 + 低频诊断。

    这些脚本扫全部会话根、无新数据时结果不变，原先每 30s 跑属空转。
    """
    run_script('session_tree')
    run_script('episodic_index')

    # 意图漂移：超阈值才回注。
    run_script('intent_drift')
    try:
        with open(os.path.join(BENCH, '_intent_drift.json'), encoding='utf-8') as f:
            drift = json.load(f)
        drifts = drift.get('drifts', [])
        if drifts:
            last = drifts[-1]
            append_feedback('', f"意图漂移：最近指令(seq {last.get('seq')})与初始任务覆盖率 "
                            f"{last.get('coverage')}，最新指令优先：{str(last.get('text',''))[:120]}",
                            'intent_drift')
    except Exception:
        pass
    run_script('mind_state')

    # 地基守护：变更驱动 + 每日兜底（不空转扫盘）
    #   - 指纹变了（推卡/改代码）→ 立即巡检
    #   - 指纹没变 → 距上次巡检≥24h 才跑一次兜底（防环境漂移/外部变化）
    FPCMD = [PY, 'D:/Brain/publish/dsh-behavior-guard/tools/foundation_fingerprint.py']
    fp_changed = subprocess.run(FPCMD + ['--changed'], capture_output=True, timeout=60).returncode == 0
    need_daily = False
    if not fp_changed:
        try:
            import json as _j
            from datetime import datetime as _dt
            _st = _j.loads(open('D:/Brain/workspace/bench/_foundation_fingerprint.json',
                                encoding='utf-8').read())
            _age = (_dt.now() - _dt.fromisoformat(_st['updated'])).total_seconds()
            need_daily = _age >= 86400
        except Exception:
            need_daily = True  # 无基线 → 跑一次建基线
    if not fp_changed and not need_daily:
        log('[FOUNDATION] unchanged & <24h, skip')
    else:
        gok, gout = run_script('foundation_guard')
        if gok:
            # 巡检通过才提交新基线指纹（FAIL 时保留旧指纹，下轮继续告警）
            subprocess.run(FPCMD + ['--commit'], capture_output=True, timeout=60)
            if need_daily:
                log('[FOUNDATION] daily fallback OK')
        else:
            bad_lines = [l for l in gout.splitlines() if '[GUARD] FAIL' in l or '↳ 修复' in l or 'VERDICT' in l]
            append_feedback('', '地基漂移告警：' + ' | '.join(bad_lines[:6]), 'foundation_guard')
            log('[FOUNDATION-DRIFT] ' + ' | '.join(bad_lines[:4]))


def digest_deep_only(state):
    """无新数据时的巩固：只跑离线索引/诊断，不跑依赖新事件的沉淀脚本。"""
    consolidate(state)


def one_round(state):
    hits, state['pending_offset'] = read_new(PENDING, state.get('pending_offset', 0))
    outcomes, state['outcome_offset'] = read_new(OUTCOME, state.get('outcome_offset', 0))
    # A0 filter: load blacklist
    _blacklist = _load_test_sids()
    # trace 全量读（crit_hit 结算需要历史窗口；文件 8MB 轮转前全读成本可接受）
    trace_rows = []
    try:
        with open(TRACE, encoding='utf-8', errors='replace') as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    pass
                sid = r.get('sid', '')
                if _blacklist and (sid in _blacklist or any(sid.startswith(prefix) for prefix in _blacklist)):
                    continue
                trace_rows.append(r)
    except Exception:
        pass

    runs = state.get('runs', 0)
    deep = (runs % CONSOLIDATE_EVERY == 0)
    log(f'[round] new_hits={len(hits)} new_outcomes={len(outcomes)} trace_rows={len(trace_rows)}'
        + (' [deep]' if deep else ''))

    # 事件驱动层：只有新数据才结算 + 跑轻量沉淀脚本（skill_draft / crit_revision / trace_timeline）
    if hits or outcomes:
        settle_crit_hits(state, hits, outcomes, trace_rows)
        digest(state, deep=deep)
    elif deep:
        # 无新数据也要周期性巩固（索引/诊断），但不跑轻量沉淀脚本
        digest_deep_only(state)

    state['last_digest'] = f"{state.get('pending_offset',0)}:{state.get('outcome_offset',0)}"
    state['runs'] = runs + 1
    save_state(state)


def main():
    args = sys.argv[1:]
    once = '--once' in args
    log(f'=== learn_watcher start (once={once}) ===')
    state = load_state()
    while True:
        try:
            one_round(state)
        except Exception as e:
            log(f'[round] FATAL {e}')
        if once:
            break
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
