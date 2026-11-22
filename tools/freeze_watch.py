# -*- coding: utf-8 -*-
"""卡死看门狗：检测 llama-server 冻死并重启 dsh（R7 元治理锁/可靠性）。"""
import json, urllib.request, urllib.parse, subprocess, time, sys, os, datetime

SLOTS = "http://127.0.0.1:8081/slots"
MODELS = "http://127.0.0.1:8081/v1/models"
HERE  = os.path.dirname(os.path.abspath(__file__))
LOG   = os.path.join(HERE, "freeze_watch.log")

POLL      = int(os.environ.get("FW_POLL", "8"))          # 轮询间隔秒
STUCK_SEC = int(os.environ.get("FW_STUCK_SEC", "120"))   # 无进展多久判"疑似卡死"
POWER_LOW = float(os.environ.get("FW_POWER_LOW", "30"))  # 冻结签名：功耗低于此值(W)
RESTART   = "--restart-dsh" in sys.argv                 # 检出冻结后是否触发 RestartDsh 自动恢复
VERBOSE   = "--verbose" in sys.argv
COOLDOWN  = 300

def slog(m):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {m}"
    try:
        with open(LOG, "a", encoding="utf-8") as f: f.write(line + "\n")
    except Exception: pass
    try:
        print(line, flush=True)
    except Exception: pass

def loaded_model():
    """路由模式（2026-11-11 起生产用）下，/slots 必须带 ?model=<id>。
    ⚠ 且只能查【当前已加载】的那个：对未加载的 id 发请求会触发 router 换模型，
    看门狗每 8 秒换一次模型会直接把服务拖死。所以先问 /v1/models 拿 loaded 的那个。
    单模型模式没有 status 字段，这里返回 None，回退到原来的无参 /slots。"""
    try:
        with urllib.request.urlopen(MODELS, timeout=5) as r:
            d = json.loads(r.read().decode())
        for m in d.get("data", []):
            if (m.get("status") or {}).get("value") == "loaded":
                return m.get("id")
        return ""   # 路由模式但当前没有已加载模型 → 视为空闲
    except Exception:
        return None  # 老版本/单模型：走无参路径


def get_slot():
    model = loaded_model()
    if model == "":
        return None
    url = SLOTS + ("?model=" + urllib.parse.quote(model) if model else "")
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            d = json.loads(r.read().decode())
        return d[0] if isinstance(d, list) and d else d
    except Exception:
        return None

NOWIN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

def gpu():
    try:
        o = subprocess.run(["nvidia-smi","--query-gpu=power.draw,utilization.gpu","--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=5, creationflags=NOWIN).stdout.strip()
        p = [x.strip() for x in o.split(",")]
        return float(p[0]), float(p[1])
    except Exception:
        return None, None

def restart_dsh():
    slog("[ACTION] 触发 RestartDsh 计划任务（重启 dsh+llama-server 恢复）")
    subprocess.run(["schtasks","/Run","/TN","RestartDsh"], capture_output=True, creationflags=NOWIN)

last = None; stuck_since = None; last_restart = 0.0
slog(f"[start] poll={POLL}s stuck_th={STUCK_SEC}s powerLow={POWER_LOW}W restart={RESTART}")
while True:
    s = get_slot()
    if not s:
        time.sleep(POLL); continue
    proc  = bool(s.get("is_processing"))
    pproc = s.get("n_prompt_tokens_processed", 0) or 0
    nt    = s.get("next_token")
    dec   = 0
    if isinstance(nt, list) and nt and isinstance(nt[0], dict):
        dec = nt[0].get("n_decoded", 0) or 0
    prog = (pproc, dec)

    if not proc:
        if VERBOSE and last is not None: slog(f"[idle] 上请求已结束")
        last = None; stuck_since = None
        time.sleep(POLL); continue

    if last is None or prog != last:
        if VERBOSE: slog(f"[progress] prompt_proc={pproc} decoded={dec} (推进中=正常)")
        last = prog; stuck_since = None
    else:
        if stuck_since is None: stuck_since = time.time()
        stuck_for = time.time() - stuck_since
        if stuck_for >= STUCK_SEC:
            pw, ut = gpu()
            if pw is not None and pw < POWER_LOW:
                if time.time() - last_restart > COOLDOWN:
                    slog(f"[FROZEN] 无进展 {int(stuck_for)}s + 功耗 {pw:.1f}W(util {ut}%) prompt_proc={pproc} decoded={dec} → 真冻死")
                    if RESTART: restart_dsh(); last_restart = time.time()
                    stuck_since = None
            else:
                if VERBOSE: slog(f"[slow] 无进展 {int(stuck_for)}s 但功耗 {pw}W 正常 → 慢但未冻，不打断")
    time.sleep(POLL)
