#!/usr/bin/env python3
"""M10 会话生命周期治理（刹车）—— 真实行为测试（2026-11-22）。

为什么存在这个文件
------------------
M10 原先的强判据 test_kill_switch.mjs(min=4) 测的是"事件指纹"逻辑，
与卡片 what 宣称的 `sessionController.cancel 刹车` 错配：指纹绿 ≠ 真的会刹车。
本脚本直接针对"刹车"这个行为本身取证，不复用任何字符串哈希指纹。

四条独立断言（均顶格输出，roadmap_check 的 ^\\[PASS 正则可识别）：
  1. cancel 端点在 bridge CLI / 服务两侧成对存在（验证调用链契约，不是 grep 单个词）
  2. 真·行为契约：拉起一个真实 bridge 实例（spy sessionController），发真实 HTTP
     POST /v1/sessions/<sid>/cancel，断言 accepted + controller 真的收到调用 +
     错误 token 被拒 + 无 cancel 能力时返回 501（绝不伪造"刹车成功"）
  3. kill_switch.py 的"非进展 → L2 cancel"状态机接线（状态机转换契约）
  4. 本地 live bridge 对一个随机不存在的测试 sid 做 cancel 干跑；
     服务不可达则 SKIP，绝不 PASS 假证据，绝不 cancel 用户真实会话

输出 / 退出码
-------------
  [PASS] / [FAIL] / [SKIP] 顶格，末行 `N/M pass`
  全 PASS（无 FAIL、N≥1）→ 0；有 FAIL → 1；零 PASS 且零 FAIL（全 SKIP）→ 2
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'

results = []


def emit(status, name, detail=''):
    """顶格输出一条断言结果；detail 放到同一行但不会破坏 ^[ 开头。"""
    line = f'[{status}] {name}'
    if detail:
        line += ' | ' + ' '.join(str(detail).split())[:400]
    print(line, flush=True)
    results.append(status)


def short(text, n=400):
    return ' '.join(str(text).split())[:n]


def first_existing(paths):
    for p in paths:
        try:
            if p and Path(p).is_file():
                return Path(p)
        except (OSError, ValueError):
            continue
    return None


# ---------- 定位被测对象（从 kill_switch.py 的权威常量推导，带兜底） ----------
def locate():
    ks_path = TOOLS / 'kill_switch.py'
    ks = ks_path.read_text(encoding='utf-8') if ks_path.is_file() else ''
    m_bridge = re.search(r"^BRIDGE\s*=\s*Path\(['\"]([^'\"]+)['\"]\)", ks, re.M)
    m_desc = re.search(r"^DESC\s*=\s*Path\(['\"]([^'\"]+)['\"]\)", ks, re.M)

    bridge = first_existing([
        m_bridge.group(1) if m_bridge else None,
        'D:/Brain/workspace/bench/dsh-session-bridge/bridge.mjs',
        ROOT / 'bench' / 'dsh-session-bridge' / 'bridge.mjs',
    ])
    bridge_dir = bridge.parent if bridge else None
    index = first_existing([
        (bridge_dir / 'index.mjs') if bridge_dir else None,
        'D:/Brain/workspace/bench/dsh-session-bridge/index.mjs',
        ROOT / 'bench' / 'dsh-session-bridge' / 'index.mjs',
    ])
    desc = first_existing([
        m_desc.group(1) if m_desc else None,
        'D:/Brain/dsh-data/session-bridge.json',
        Path.home() / '.dsh' / 'session-bridge.json',
    ])
    return ks, ks_path, bridge, index, desc


# ---------- 断言 1：端点调用链契约（真实读源码，验证成对映射） ----------
def assert_endpoint_contract(bridge, index):
    name = 'cancel 端点在 bridge CLI/服务两侧成对存在（调用链契约）'
    if not bridge or not index:
        emit('FAIL', name, f'找不到 bridge 源码 bridge={bridge} index={index}')
        return
    bsrc = bridge.read_text(encoding='utf-8')
    isrc = index.read_text(encoding='utf-8')

    m = re.search(r"case 'cancel'([\s\S]{0,600})", bsrc)
    seg = m.group(1) if m else ''
    checks = {
        'CLI case cancel': bool(m),
        'CLI POST /cancel': '/cancel' in seg and "method: 'POST'" in seg,
        'inject sessionController': "inject = ['sessionController']" in isrc,
        'route matches cancel': 'events|messages|cancel' in isrc,
        'calls ctrl.cancel({sessionId})': 'ctrl.cancel({ sessionId: sid })' in isrc,
        '501 when cancel unavailable': "typeof ctrl.cancel !== 'function'" in isrc and 'status = 501' in isrc,
        'returns accepted': 'accepted:' in isrc and 'sessionId: sid' in isrc,
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        emit('FAIL', name, '缺失契约: ' + ', '.join(bad))
    else:
        emit('PASS', name,
             f'bridge.mjs:case cancel→POST /v1/sessions/<sid>/cancel; '
             f'index.mjs:ctrl.cancel({{sessionId}}) + 501 guard + accepted 回执 '
             f'({len(checks)}/{len(checks)} checks)')


# ---------- 断言 2：真·行为契约（in-process 拉起真实 bridge，HTTP 打 cancel） ----------
HARNESS = r"""
import { pathToFileURL } from 'node:url'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'

const idx = process.env.BRAKE_INDEX
const testSid = process.env.BRAKE_TEST_SID
const tmp = process.env.BRAKE_TMP
const { apply } = await import(pathToFileURL(idx).href)

const calls = []
const baseCtrl = {
  list: async () => ({ items: [] }),
  events: async () => ({ records: [], hasMore: false, cursor: null }),
  prompt: async () => ({ accepted: true }),
  create: async () => ({ sessionId: 'harness-created' }),
}
const spyCtrl = { ...baseCtrl, cancel: async ({ sessionId }) => { calls.push(sessionId); return { accepted: true } } }
const noCancelCtrl = { ...baseCtrl }
const ctxOf = (ctrl) => ({ sessionController: ctrl, logger: { info(){}, warn(){}, error(){} }, effect: () => {} })

function emit(name, ok, detail = '') {
  console.log(`CHECK ${name} ${ok ? 'PASS' : 'FAIL'} ${detail}`.trimEnd())
}
async function start(ctrl, tag) {
  const descPath = join(tmp, `desc-${tag}.json`)
  await apply(ctxOf(ctrl), { port: 0, tokenPath: descPath, allowCreate: false, auditLog: false })
  const d = JSON.parse(await readFile(descPath, 'utf8'))
  return { base: `http://127.0.0.1:${d.port}`, token: d.token }
}
async function req(base, token, path, opts = {}) {
  const r = await fetch(base + path, {
    ...opts,
    headers: { Authorization: `Bearer ${token}`, ...(opts.body ? { 'content-type': 'application/json' } : {}) },
  })
  let body = null
  try { body = await r.json() } catch {}
  return { status: r.status, body }
}

try {
  const good = await start(spyCtrl, 'good')
  const h = await req(good.base, good.token, '/v1/health')
  emit('harness_health', h.status === 200 && h.body?.ok === true, JSON.stringify(h.body))

  const url = `/v1/sessions/${encodeURIComponent(testSid)}/cancel`
  const c = await req(good.base, good.token, url, { method: 'POST' })
  emit('cancel_200_accepted',
    c.status === 200 && c.body?.accepted === true && c.body?.sessionId === testSid, JSON.stringify(c.body))
  emit('cancel_reached_sessionController',
    calls.length === 1 && calls[0] === testSid, JSON.stringify(calls))

  const bad = await req(good.base, 'wrong-token', url, { method: 'POST' })
  emit('cancel_rejects_bad_token', bad.status === 401 && !!bad.body?.error, 'status=' + bad.status)

  const noCancel = await start(noCancelCtrl, 'nocancel')
  const nc = await req(noCancel.base, noCancel.token, url, { method: 'POST' })
  emit('cancel_unavailable_returns_501',
    nc.status === 501 && !!nc.body?.error && /cancel unavailable/i.test(nc.body.error), JSON.stringify(nc.body))
} catch (e) {
  emit('harness_error', false, String(e?.stack || e))
}
console.log('HARNESS_DONE')
process.exit(0)
"""


def assert_behavior_contract(index):
    name = 'cancel 真行为：HTTP POST → sessionController.cancel 实调用（非伪造）'
    if not index:
        emit('FAIL', name, '找不到 index.mjs，无法拉起 bridge')
        return
    with tempfile.TemporaryDirectory(prefix='brake-harness-') as td:
        harness = Path(td) / 'harness.mjs'
        harness.write_text(HARNESS, encoding='utf-8')
        env = dict(os.environ)
        env['BRAKE_INDEX'] = str(index)
        env['BRAKE_TMP'] = td
        env['BRAKE_TEST_SID'] = 'session-BRAKE-HARNESS-' + uuid.uuid4().hex[:10]
        env['DSH_HOME'] = td  # 隔离，绝不碰真实 ~/.dsh / D:/Brain/dsh-data
        try:
            p = subprocess.run(['node', str(harness)], env=env, capture_output=True,
                               text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            emit('FAIL', name, f'harness 无法运行: {e}')
            return
    lines = [ln.strip() for ln in p.stdout.splitlines()]
    checks = {}
    for ln in lines:
        if ln.startswith('CHECK '):
            _, nm, status, *rest = ln.split()
            checks[nm] = (status == 'PASS', ' '.join(rest))
    expected = ['harness_health', 'cancel_200_accepted', 'cancel_reached_sessionController',
                'cancel_rejects_bad_token', 'cancel_unavailable_returns_501']
    bad = [k for k in expected if not checks.get(k, (False, 'missing'))[0]]
    if p.returncode != 0 or 'HARNESS_DONE' not in lines:
        emit('FAIL', name, f'harness rc={p.returncode} stderr={short(p.stderr, 200)}')
    elif bad:
        emit('FAIL', name, '行为断言未通过: ' + ', '.join(bad) +
             ' | ' + '; '.join(f'{k}={checks.get(k, ("?", ""))[1]}' for k in bad))
    else:
        emit('PASS', name,
             f'真实 bridge 实例: health=200, cancel accepted=true, '
             f'spy 收到 sessionId, 坏 token=401, 无 cancel=501（{len(expected)}/{len(expected)} 行为断言）')


# ---------- 断言 3：kill_switch 的「非进展 → L2 cancel」状态机接线 ----------
def assert_state_machine(ks, ks_path):
    name = 'kill_switch 无进展→L2 cancel 状态机接线（进程外刹车链）'
    if not ks:
        emit('FAIL', name, f'找不到 {ks_path}')
        return
    checks = {
        'bridge_cancel 定义': 'def bridge_cancel(sid):' in ks,
        'CLI 调 node bridge.mjs cancel': bool(
            re.search(r"subprocess\.run\(\[['\"]node['\"][\s\S]{0,200}?['\"]cancel['\"]", ks)),
        'L2 阈值判据': 'n >= a.cancel_limit' in ks,
        'L2 等级幂等门': "st['level'] < 2" in ks,
        'L2-CANCEL 打点': "log('L2-CANCEL'" in ks,
        '有进展即重置等级': "st['level'] = 0" in ks,
        '指纹不含 cursor': "','.join(types) + '|' + last" in ks,
    }
    bad = [k for k, v in checks.items() if not v]
    if bad:
        emit('FAIL', name, '状态机契约缺失: ' + ', '.join(bad))
    else:
        emit('PASS', name,
             '非进展计数→L1告警→(cancel_limit) L2 bridge.cancel + 幂等 level 门 + '
             f'有进展重置；指纹仅用 event types+last data（{len(checks)}/{len(checks)} checks）')


# ---------- 断言 4：live bridge 干跑（只打随机不存在的 sid，可达才 PASS） ----------
def assert_live_dry_run(desc):
    name = 'live bridge 对测试 sid 的 cancel 干跑（不碰真实会话）'
    if not desc:
        emit('SKIP', name, '找不到 session-bridge descriptor，无法做 live 干跑')
        return
    try:
        d = json.loads(desc.read_text(encoding='utf-8'))
        addr, port, token = d['address'], int(d['port']), str(d.get('token', ''))
        base = f'http://{addr}:{port}'
    except Exception as e:
        emit('SKIP', name, f'descriptor 不可用: {e}')
        return

    def call(path, method='GET'):
        req = urllib.request.Request(base + path, method=method, data=b'' if method == 'POST' else None,
                                     headers={'Authorization': 'Bearer ' + token,
                                              'Host': f'{addr}:{port}'})
        try:
            r = urllib.request.urlopen(req, timeout=5)
            return r.status, r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', 'replace')

    try:
        st, body = call('/v1/health')
        if st != 200 or '"ok":true' not in body.replace(' ', ''):
            emit('SKIP', name, f'live bridge 健康探测失败 status={st} body={short(body, 120)}')
            return
    except Exception as e:
        emit('SKIP', name, f'live bridge 不可达（不伪造 PASS）: {e}')
        return

    test_sid = 'session-BRAKE-DRYRUN-' + uuid.uuid4().hex[:10]
    # 安全闸：确认这个 sid 不在真实会话列表里，才允许 cancel
    try:
        st, body = call('/v1/sessions')
        listed = [x.get('sessionId') for x in json.loads(body).get('items', [])]
        if test_sid in listed:
            emit('SKIP', name, '测试 sid 意外出现在会话列表，拒绝 cancel')
            return
    except Exception:
        pass  # 列表读不到不影响：sid 是随机 uuid，不可能命中真实会话

    from urllib.parse import quote
    try:
        st, body = call(f'/v1/sessions/{quote(test_sid)}/cancel', method='POST')
    except Exception as e:
        emit('SKIP', name, f'cancel 请求不可达: {e}')
        return
    low = body.lower()
    reached_controller = (
        (st == 200 and '"accepted":true' in body.replace(' ', '').lower())
        or (st in (500, 400) and ('not found' in low or 'not attached' in low))
    )
    if st in (404, 501):
        emit('FAIL', name, f'cancel 路由/能力缺失 status={st} body={short(body)}')
    elif reached_controller:
        emit('PASS', name,
             f'status={st} body={short(body, 160)}（业务 not-found=ctrl.cancel 已真实触达，'
             f'测试 sid={test_sid}，非用户会话）')
    else:
        emit('FAIL', name, f'cancel 返回无法证明触达 sessionController status={st} body={short(body)}')


def main():
    ks, ks_path, bridge, index, desc = locate()
    assert_endpoint_contract(bridge, index)
    assert_behavior_contract(index)
    assert_state_machine(ks, ks_path)
    assert_live_dry_run(desc)

    npass = results.count('PASS')
    nfail = results.count('FAIL')
    print(f'\n{npass}/{len(results)} pass', flush=True)
    if nfail:
        sys.exit(1)
    if npass == 0:
        sys.exit(2)  # 全 SKIP：绝不把"测不到"伪装成通过
    sys.exit(0)


if __name__ == '__main__':
    main()
