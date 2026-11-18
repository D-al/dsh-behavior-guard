#!/usr/bin/env python3
"""GPU 引擎争抢守护：检测 3D 抢占导致 Copy 饿死，主动降帧保住推理。

背景：单 GPU(无核显) + WDDM 多引擎共享。前台 Electron 窗口(dsh/WorkBuddy)
的 3D 合成被 DWM 高优先级调度，抢占显存带宽与 Copy 引擎；
llama.cpp 的 MoE 专家换入依赖 Copy → Copy 掉 0 → 推理停滞。
聚合 util% 会误导（空闲 3D 也能 100%），必须按 pid + engtype 读分引擎计数器。

三级动作（从轻到重，都保持窗口在屏幕上，只在必要时遮住/最小化）：
  L1 eco    ：对抢 3D 的 pid 设 EcoQoS(效率模式)——窗口仍可见，Chromium 自动降帧
  L2 cloak  ：预留（DWM cloak，需注入，本脚本不实现）
  L3 minimize：SW_MINIMIZE 该窗口——最有效但打断交互，作为兜底

推理结束(is_processing=false)后自动撤销 EcoQoS / 还原窗口。
所有动作写 JSONL 审计日志，带冷却避免抖动。

用法：
  python gpu_engine_guard.py --dry-run          # 只检测记录，不动作（先跑这个看误报）
  python gpu_engine_guard.py --apply            # 启用 L1+L3 动作
  python gpu_engine_guard.py --apply --no-eco   # 只用最小化（EcoQoS 出问题时）
  python gpu_engine_guard.py --selftest         # 自检：计数器读取 + EcoQoS API + 判据逻辑
"""
import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
import datetime
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "_gpu_guard.jsonl")
NOWIN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

SLOTS = "http://127.0.0.1:8081/slots"
MODELS = "http://127.0.0.1:8081/v1/models"

# 判据默认阈值（可被环境变量覆盖）
POLL = float(os.environ.get("GG_POLL", "1.5"))          # 采样间隔秒
HIGH_3D = float(os.environ.get("GG_HIGH_3D", "85"))     # 3D 引擎占用超过此值算"抢"
LOW_COPY = float(os.environ.get("GG_LOW_COPY", "2"))    # Copy 引擎低于此值算"饿死"
SUSTAIN = int(os.environ.get("GG_SUSTAIN", "3"))         # 连续 N 次命中才动作
COOLDOWN = float(os.environ.get("GG_COOLDOWN", "20"))    # 两次动作最小间隔秒
MIN_IDLE = int(os.environ.get("GG_MIN_IDLE", "2"))       # 推理空闲 N 次后撤销动作

# 免打扰 pid：dwm(4)、系统进程——它们 3D 高但不该被降帧
SKIP_PIDS = {4, 0}
# 只对这些进程名做动作（None=所有非系统进程）
TARGET_NAMES = {"workbuddy.exe", "deepseek harness.exe", "code.exe", "msedge.exe", "chrome.exe"}


def log(ev, **kw):
    rec = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "ev": ev, **kw}
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        print(json.dumps(rec, ensure_ascii=False), flush=True)
    except Exception:
        pass


# ── GPU 分引擎采样 ────────────────────────────────────────────
PS_ENGINE = (
    "(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction SilentlyContinue).CounterSamples | "
    "ForEach-Object { $p=0; $e='?'; "
    "if($_.Path -match 'pid_(\\d+)'){$p=[int]$matches[1]}; "
    "if($_.Path -match 'engtype_(\\w+)'){$e=$matches[1]}; "
    "\"$p|$e|$([math]::Round($_.CookedValue,1))\" }"
)


def sample_engines():
    """返回 {pid: {'3d':%, 'copy':%, 'cuda':%, ...}}，只保留非零项。"""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", PS_ENGINE],
                           capture_output=True, text=True, timeout=10, creationflags=NOWIN)
    except Exception as e:
        log("engine_sample_err", err=str(e)[:120])
        return {}
    out = {}
    for line in r.stdout.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3:
            continue
        try:
            pid, et, val = int(parts[0]), parts[1], float(parts[2])
        except ValueError:
            continue
        if pid in SKIP_PIDS or val <= 0:
            continue
        out.setdefault(pid, {})[et] = out.setdefault(pid, {}).get(et, 0.0) + val
    return out


def totals(engines):
    """聚合所有非系统进程的 3d / copy / cuda。"""
    t = {"3d": 0.0, "copy": 0.0, "cuda": 0.0}
    for pid, m in engines.items():
        for k in t:
            t[k] += m.get(k, 0.0)
    return t


# ── 推理状态 ──────────────────────────────────────────────────
def loaded_model():
    import urllib.request
    try:
        with urllib.request.urlopen(MODELS, timeout=4) as r:
            d = json.loads(r.read().decode())
        for m in d.get("data", []):
            if (m.get("status") or {}).get("value") == "loaded":
                return m.get("id")
        return ""
    except Exception:
        return None


def is_processing():
    import urllib.request, urllib.parse
    model = loaded_model()
    if model == "":
        return False
    url = SLOTS + ("?model=" + urllib.parse.quote(model) if model else "")
    try:
        with urllib.request.urlopen(url, timeout=4) as r:
            d = json.loads(r.read().decode())
        s = d[0] if isinstance(d, list) and d else d
        return bool(s.get("is_processing")) if s else False
    except Exception:
        return False


# ── pid → 进程名 ──────────────────────────────────────────────
def pid_name(pid):
    ps = f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue).ProcessName"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, text=True, timeout=8, creationflags=NOWIN)
        return r.stdout.strip().splitlines()[0].lower() if r.stdout.strip() else ""
    except Exception:
        return ""


# ── EcoQoS（效率模式）——窗口保持可见但降帧 ──────────────────
class PPT_STATE(ctypes.Structure):
    _fields_ = [("Version", wintypes.DWORD), ("ControlMask", wintypes.DWORD), ("StateMask", wintypes.DWORD)]


def _k32():
    k = ctypes.windll.kernel32
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.SetProcessInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(PPT_STATE), wintypes.DWORD]
    k.SetProcessInformation.restype = wintypes.BOOL
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    return k


def eco_qos(pid, on):
    """ProcessPowerThrottling=4, EXECUTION_SPEED=1。返回 (ok, err)。"""
    try:
        k = _k32()
        h = k.OpenProcess(0x0300, False, pid)  # QUERY_LIMITED | SET_LIMITED
        if not h:
            return False, ctypes.get_last_error()
        s = PPT_STATE(1, 1, 1 if on else 0)
        ok = bool(k.SetProcessInformation(h, 4, ctypes.byref(s), ctypes.sizeof(s)))
        err = 0 if ok else ctypes.get_last_error()
        k.CloseHandle(h)
        return ok, err
    except Exception as e:
        return False, str(e)[:80]


# ── 窗口最小化 / 还原 ────────────────────────────────────────
u = ctypes.windll.user32 if os.name == "nt" else None
SW_MINIMIZE, SW_RESTORE = 6, 9


def windows_of_pid(pid):
    if not u:
        return []
    EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    u.EnumWindows.argtypes = [EnumProc, wintypes.LPARAM]
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    found = []

    def visit(hwnd, _):
        if not u.IsWindowVisible(hwnd):
            return True
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            found.append(hwnd)
        return True

    u.EnumWindows(EnumProc(visit), 0)
    return found


def show_windows(pid, cmd):
    if not u:
        return 0
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    n = 0
    for hwnd in windows_of_pid(pid):
        u.ShowWindow(hwnd, cmd)
        n += 1
    return n


# ── 判据（纯函数，可单测）────────────────────────────────────
def should_act(t, processing, high_3d=HIGH_3D, low_copy=LOW_COPY):
    """引擎争抢签名：推理中 + 3D 高 + Copy 饿死。"""
    return bool(processing and t["3d"] >= high_3d and t["copy"] <= low_copy)


def pick_culprit(engines):
    """选 3D 占用最高、且属于目标进程名的 pid。"""
    cands = [(m.get("3d", 0.0), pid) for pid, m in engines.items()]
    cands.sort(reverse=True)
    for val, pid in cands:
        if val < HIGH_3D:
            continue
        name = pid_name(pid)
        if not TARGET_NAMES or name in TARGET_NAMES:
            return pid, name, val
    return None, None, 0.0


# ── 主循环 ────────────────────────────────────────────────────
def run(args):
    state = {"hits": 0, "active_pid": None, "action": None, "last_action": 0.0, "idle": 0}
    log("start", dry_run=args.dry_run, eco=not args.no_eco, poll=POLL,
        high_3d=HIGH_3D, low_copy=LOW_COPY, sustain=SUSTAIN)
    while True:
        try:
            eng = sample_engines()
            t = totals(eng)
            proc = is_processing()
            hit = should_act(t, proc)
            if args.verbose and (hit or proc):
                log("sample", proc=proc, **{k: round(v, 1) for k, v in t.items()}, hit=hit)

            if hit:
                state["hits"] += 1
                state["idle"] = 0
                if state["hits"] >= SUSTAIN:
                    now = time.time()
                    if state["active_pid"] is None and now - state["last_action"] >= COOLDOWN:
                        pid, name, val = pick_culprit(eng)
                        if pid:
                            action = None
                            if not args.dry_run and not args.no_eco:
                                ok, err = eco_qos(pid, True)
                                if ok:
                                    action = "eco_on"
                                else:
                                    log("eco_fail", pid=pid, err=str(err)[:80])
                            if not args.dry_run and action is None:
                                n = show_windows(pid, SW_MINIMIZE)
                                action = f"minimize({n})"
                            if args.dry_run:
                                action = "DRY_RUN"
                            state.update(active_pid=pid, action=action, last_action=now)
                            log("ACTION", pid=pid, name=name, eng3d=round(val, 1), copy=round(t["copy"], 1), action=action)
            else:
                state["hits"] = 0
                if state["active_pid"] is not None and not proc:
                    state["idle"] += 1
                    if state["idle"] >= MIN_IDLE:
                        pid = state["active_pid"]
                        if not args.dry_run:
                            if "eco_on" in str(state["action"]):
                                eco_qos(pid, False)
                            elif "minimize" in str(state["action"]):
                                show_windows(pid, SW_RESTORE)
                        log("RECOVER", pid=pid, action=state["action"])
                        state.update(active_pid=None, action=None, idle=0)
            time.sleep(POLL)
        except KeyboardInterrupt:
            log("stop")
            break
        except Exception as e:
            log("loop_err", err=str(e)[:160])
            time.sleep(POLL)


def selftest():
    print("== gpu_engine_guard selftest ==")
    eng = sample_engines()
    t = totals(eng)
    print(f"[1] engine sample: {len(eng)} nonzero pids, totals={t}")
    print(f"    {'OK' if len(eng) > 0 else 'WARN'} (empty is ok when idle)")
    print(f"[2] should_act(3d=95,copy=0,processing=True) = {should_act({'3d':95,'copy':0,'cuda':30}, True)}  (expect True)")
    print(f"    should_act(3d=95,copy=0,processing=False) = {should_act({'3d':95,'copy':0,'cuda':30}, False)}  (expect False)")
    print(f"    should_act(3d=60,copy=5,processing=True)  = {should_act({'3d':60,'copy':5,'cuda':30}, True)}  (expect False)")
    ok, err = eco_qos(os.getpid(), True)
    print(f"[3] EcoQoS API on self pid={os.getpid()}: ok={ok} err={err}  (expect True)")
    if ok:
        ok2, _ = eco_qos(os.getpid(), False)
        print(f"    EcoQoS off: ok={ok2}  (expect True)")
    print("selftest done")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="只检测记录，不动作（默认推荐先跑）")
    g.add_argument("--apply", action="store_true", help="启用降帧动作")
    ap.add_argument("--no-eco", action="store_true", help="禁用 EcoQoS，只用最小化")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
    else:
        run(args)


if __name__ == "__main__":
    main()
