# -*- coding: utf-8 -*-
"""杠杆B补丁：错误恢复剧本（首次失败给确定性动作，0 LLM）。

只处理首次失败；D1（重复探测）/D2（同参双败）继续管重复，不冲突。
铁律：只读结构化字段（工具名、参数、status），绝不扫 fullArgs 内容。
"""
import sys, hashlib, shutil
from pathlib import Path

AUTH = Path('D:/Brain/publish/dsh-behavior-guard/index.mjs')
RUN = Path('D:/Brain/dsh-data/profiles/desktop/node_modules/dsh-agent-harness/index.mjs')
PATCHES = []

# ── 补丁1：DEFAULTS ──
PATCHES.append((
    'B-DEFAULTS',
    "  criticTemperature: 0.7,",
    """  // ── 杠杆B 错误恢复剧本（2026-11-24；首次失败确定性动作，0 LLM）──
  errorPlaybookEnabled: true,
  errorPlaybookMaxPerTurn: 2,
  criticTemperature: 0.7,""",
))

# ── 补丁2：errorPlaybook 函数（插在 taskProfile 后）──
PATCHES.append((
    'B-函数定义',
    """// ── 路径解析层（2026-11-20 平台整治 P0）──""",
    """// ── 杠杆B：错误恢复剧本（0 LLM；只读结构化字段，不扫内容）────────────────
// 只处理【首次失败】：D1/D2 管重复探测，本函数管第一次出错时的确定性修正动作。
const EP_KNOWN_PATH_KEYS = new Set(['file_path', 'path', 'filePath', 'target_file', 'notebook_path', 'target'])
const EP_HINT_KEYS = new Set(['filename', 'file', 'name', 'target_path', 'output_path'])

function errorPlaybook(s, cfg, c, status) {
  const st = s || {}
  if (cfg?.errorPlaybookEnabled === false) return null
  if (status !== 'FAIL' && status !== 'UNPRODUCTIVE' && status !== 'ERROR') return null
  if ((st.errorPlaybookCount || 0) >= (cfg?.errorPlaybookMaxPerTurn || 2)) return null
  const name = String(c?.name || '')
  let a = {}
  try { a = JSON.parse(c?.fullArgs || c?.args || '{}') || {} } catch { return null }
  const kind = st.errorPlaybookKind || {}
  let action = null, type = ''

  // ① 参数名错：有可疑路径键但没有标准键
  const hasStd = [...EP_KNOWN_PATH_KEYS].some((k) => typeof a[k] === 'string' && a[k].trim())
  const badKey = [...EP_HINT_KEYS].find((k) => typeof a[k] === 'string' && a[k].trim())
  if (!hasStd && badKey) {
    type = 'param-key'
    action = `[harness 错误剧本] 工具 ${name} 调用失败：参数名 "${badKey}" 可能不被识别。` +
      `该工具期望路径参数（file_path / path / filePath）。请把 "${badKey}" 的值改用 file_path 重试，不要换工具。`
  }
  // ② 路径不存在：从失败结果的结构化标志判定（不读正文）
  else if (c?.pathMissing === true || a?.pathMissing === true) {
    type = 'path-missing'
    action = `[harness 错误剧本] 路径不存在：先用 glob 或 list 工具列出上级目录，确认真实文件名后再重试，不要重复同一个路径。`
  }
  // ③ 工具名不存在/禁用
  else if (status === 'ERROR' && (c?.unknownTool === true || name === '')) {
    type = 'unknown-tool'
    action = `[harness 错误剧本] 调用了不存在的工具。先用工具列表确认可用工具名，再重试。`
  }
  if (!action || kind[type]) return null  // 每类每轮最多一次
  st.errorPlaybookCount = (st.errorPlaybookCount || 0) + 1
  st.errorPlaybookKind = { ...kind, [type]: true }
  try {
    trace({ ts: new Date().toISOString(), sid: st.sid || '', kind: 'error_playbook',
      tool: name, errorType: type, step: st.step || 0, injected: !st.pendingInject })
  } catch { /* trace 失败不影响注入 */ }
  return { type, text: action }
}

// ── 路径解析层（2026-11-20 平台整治 P0）──""",
))

# ── 补丁3：state 每轮重置 ──
PATCHES.append((
    'B-state重置',
    """        verifyEvidence: 0,""",
    """        verifyEvidence: 0,
        errorPlaybookCount: 0, errorPlaybookKind: {},""",
))

# ── 补丁4：tool/result 分支挂点（D1/D2 前）──
PATCHES.append((
    'B-挂点',
    """          // v3.1 确定性信号（代码判定，不等审计窗口）：""",
    """          // ── 杠杆B：首次失败的确定性恢复剧本（D1/D2 管重复，这里管首次）──
          if (!s.pendingInject) {
            const ep = errorPlaybook(s, cfg, c, status)
            if (ep) s.pendingInject = ep.text
          }
          // v3.1 确定性信号（代码判定，不等审计窗口）：""",
))


def main():
    cur = sys.argv[1] if len(sys.argv) > 1 else hashlib.sha256(AUTH.read_bytes()).hexdigest()
    for path, expected in [(AUTH, cur), (RUN, None)]:
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if expected and actual != expected:
            print(f'ABORT {path.name}: sha {actual[:12]} != {expected[:12]}'); sys.exit(1)
        if not expected:
            # 运行版应已被前一次 copy 同步；若不同则说明状态异常
            print(f'运行版预检 sha={actual[:12]}')
        crlf = b'\r\n' in raw
        s = raw.decode('utf-8').replace('\r\n', '\n')
        for desc, old, new in PATCHES:
            cnt = s.count(old)
            if cnt != 1:
                print(f'ABORT [{desc}] 锚点 {cnt} 次'); sys.exit(1)
            s = s.replace(old, new, 1)
            print(f'  OK [{desc}]')
        path.write_bytes((s.replace('\n', '\r\n') if crlf else s).encode('utf-8'))
        print(f'APPLIED leverB -> {path.name} sha={hashlib.sha256(path.read_bytes()).hexdigest()[:12]}')


if __name__ == '__main__': main()
