# -*- coding: utf-8 -*-
"""杠杆C补丁：预算感知调度（按风险信号分配验证密度）。

risk 0=纯读 / 1=有写已验证 / 2=有写未验证或present / 3=错误累积
应用到：控制回合间隔、Critic 上限。默认开，可关做 A/B。
采纳子任务修正：MTP 接受率单步低不算高危（代码类任务常驻 0.55-0.70），
需"连续3步<0.5 且无其他风险信号"才升 risk。
"""
import sys, hashlib, shutil
from pathlib import Path

AUTH = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
RUN = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
PATCHES = []

# ── 补丁1：DEFAULTS ──
PATCHES.append((
    'C-DEFAULTS',
    "  criticTemperature: 0.7,",
    """  // ── 杠杆C 预算感知调度（2026-11-24；风险信号决定验证密度）──
  riskAdaptiveEnabled: true,
  riskControlHigh: 4,
  riskControlLow: 16,
  riskCriticBonusHigh: 1,
  criticTemperature: 0.7,""",
))

# ── 补丁2：riskProfile 函数（顶层，纯计算无闭包依赖）──
PATCHES.append((
    'C-函数定义',
    """// ── 杠杆B：错误恢复剧本（0 LLM；只读结构化字段，不扫内容）────────────────""",
    """// ── 杠杆C：风险画像（纯计算，0 LLM）──────────────────────────────────────
// risk 0=纯读 / 1=有写已验证 / 2=有写未验证或present / 3=错误累积
// 全部基于结构化 state 字段，不读正文。MTP 单步低不算高危（代码任务常驻 0.55-0.70）。
function riskProfile(s, cfg) {
  const st = s || {}
  if (cfg?.riskAdaptiveEnabled === false) return { level: 1, reasons: ['disabled'], interval: cfg?.controlEverySteps || 8 }
  const reasons = []
  let level = 0
  const writeCalls = Number(st.writeCalls || 0)
  const present = st.presentCalled === true
  const verified = st.verifyRan === true || st.stateReadbackOk === true
  const trail = Array.isArray(st.trail) ? st.trail : []
  const recent = trail.slice(-6)
  const bad = recent.filter((x) => x && (x.status === 'FAIL' || x.status === 'UNPRODUCTIVE')).length
  const rejected = Array.isArray(st.rejectedItems) ? st.rejectedItems.length : 0
  if (writeCalls > 0 || present) level = 1
  if ((writeCalls > 0 && !verified) || present) { level = 2; reasons.push(present ? 'present' : 'unverified-write') }
  // risk3：错误累积 / 连续失败 / 重复动作锁。
  // ⚠ MTP 接受率单步低【不算高危】——代码类任务 0.55-0.70 常驻，会误判（子任务实证）。
  // 只有纯读任务(level=0)且 specAcceptance 明确 <0.5 才升 risk。
  const spec = st.specAcceptance
  const lowSpecOnRead = level === 0 && typeof spec === 'number' && spec < 0.5
  if (bad >= 2 || rejected >= 2 || (st.patternLock === true) || lowSpecOnRead) {
    level = 3
    reasons.push(bad >= 2 ? 'repeated-failure' : rejected >= 2 ? 'rejected' : st.patternLock ? 'pattern-lock' : 'low-spec-read')
  }
  const base = Number(cfg?.controlEverySteps) || 8
  const hi = Math.max(1, Number(cfg?.riskControlHigh) || 4)
  const lo = Math.max(hi, Number(cfg?.riskControlLow) || 16)
  const interval = level >= 3 ? hi : level === 0 ? lo : base
  return { level, reasons: reasons.length ? reasons : ['baseline'], interval }
}

// ── 杠杆B：错误恢复剧本（0 LLM；只读结构化字段，不扫内容）────────────────""",
))

# ── 补丁3：控制回合条件改为动态间隔 ──
PATCHES.append((
    'C-控制回合',
    """      if (cfg.controlEnabled && s.step > 0 && s.step % cfg.controlEverySteps === 0 &&
          (s.controlCount || 0) < 1 &&   // 每轮至多一次（controlCount 在 turn/start 清零）
          (s.controlTotal || 0) < cfg.maxControlPerSession) {
        s.controlCount = (s.controlCount || 0) + 1
        s.controlTotal = (s.controlTotal || 0) + 1""",
    """      // ── 杠杆C：风险感知间隔（纯读放宽、高危加密；关闭时完全回到旧行为）──
      const rp = riskProfile(s, cfg)
      const ctrlInterval = rp.interval
      const ctrlDue = cfg.riskAdaptiveEnabled === false
        ? (s.step % ctrlInterval === 0)
        : ((s.step - (s.lastControlStep || 0)) >= ctrlInterval)
      if (cfg.controlEnabled && s.step > 0 && ctrlDue &&
          (s.controlCount || 0) < 1 &&   // 每轮至多一次（controlCount 在 turn/start 清零）
          (s.controlTotal || 0) < cfg.maxControlPerSession) {
        s.controlCount = (s.controlCount || 0) + 1
        s.controlTotal = (s.controlTotal || 0) + 1
        s.lastControlStep = s.step
        if (cfg.riskAdaptiveEnabled !== false) trace({ ts: new Date().toISOString(),
          sid: s.sid || '', kind: 'risk_adaptive', mechanism: 'control',
          risk: rp.level, reasons: rp.reasons, interval: ctrlInterval, step: s.step })""",
))

# ── 补丁4：Critic 上限按风险 ──
PATCHES.append((
    'C-Critic上限',
    """        (state.criticCount || 0) < cfg.maxCriticPerSession
      ) {
        state.criticCount = (state.criticCount || 0) + 1""",
    """        (state.criticCount || 0) < cfg.maxCriticPerSession + (
          cfg.riskAdaptiveEnabled === false ? 0
            : (riskProfile(state, cfg).level >= 3 ? (cfg.riskCriticBonusHigh || 1) : 0))
      ) {
        state.criticCount = (state.criticCount || 0) + 1
        if (cfg.riskAdaptiveEnabled !== false) trace({ ts: new Date().toISOString(),
          sid: sessionId || '', kind: 'risk_adaptive', mechanism: 'critic',
          risk: riskProfile(state, cfg).level, reasons: riskProfile(state, cfg).reasons,
          step: state.step })""",
))


def main():
    cur = sys.argv[1] if len(sys.argv) > 1 else hashlib.sha256(AUTH.read_bytes()).hexdigest()
    for path, expected in [(AUTH, cur), (RUN, None)]:
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if expected and actual != expected:
            print(f'ABORT sha {actual[:12]} != {expected[:12]}'); sys.exit(1)
        crlf = b'\r\n' in raw
        s = raw.decode('utf-8').replace('\r\n', '\n')
        for desc, old, new in PATCHES:
            cnt = s.count(old)
            if cnt != 1:
                print(f'ABORT [{desc}] 锚点 {cnt} 次'); sys.exit(1)
            s = s.replace(old, new, 1)
            print(f'  OK [{desc}]')
        path.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
        print(f'APPLIED leverC -> {path.name} sha={hashlib.sha256(path.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__': main()
