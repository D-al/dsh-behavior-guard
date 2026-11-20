"""活跃循环检测器（刹车 P0）：发现"token 在动但内容在循环"的会话。

背景（2026-11-21 生产实证）：
  freeze_watch 判据是"token 不动 + 功耗<30W"——只对冻死有效。
  但 C-REJECT 死循环里 token 一直动、功耗正常 → 看门狗判"慢但未冻，不打断"。
  bridge cancel 也未能刹住：会话最终是模型自己在 seq75 说"没有需要推进的工作"才收尾，
  没有任何 cancelled 标记——即我们当时没有任何可靠的外部刹车。

本工具只读事件流，检测重复的守卫注入模式，**告警并给出信息，不自动执行**
（破坏性操作留给人，符合身份纪律）。

用法：
  python tools/loop_breaker.py                    # 扫所有 running 会话
  python tools/loop_breaker.py --json             # 机器可读
  python tools/loop_breaker.py --sid <sessionId>  # 只看指定会话
"""
import argparse
import json
import re
import sys
import urllib.request
import urllib.parse
from pathlib import Path

DESC = Path('D:/Brain/dsh-data/session-bridge.json')
LOOP_PATTERNS = {
    'critic-reject': r'产物评审 C-REJECT',
    'todo-nag': r'立即停下.*todo_write|连续多步没有更新 todo',
    'verify-stop': r'停止条件.*必须执行',
    'control-turn': r'控制回合.*元决策',
}
DEFAULT_THRESHOLD = 3


def api(path, timeout=8):
    """直连 HTTP——不用 bridge CLI 输出（它把每行截到 300 字符，循环文本在截断外读不到）。"""
    d = json.loads(DESC.read_text(encoding='utf-8'))
    req = urllib.request.Request(f"http://127.0.0.1:{d['port']}{path}",
                                 headers={'Authorization': 'Bearer ' + str(d.get('token', ''))})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8'))


def sessions():
    try:
        return [x.get('sessionId') for x in api('/v1/sessions').get('items', []) if x.get('running')]
    except Exception:
        return []


def events(sid, limit='200'):
    try:
        return api(f'/v1/sessions/{urllib.parse.quote(sid)}/events?limit={limit}').get('records', [])
    except Exception:
        return []


def analyze(sid, threshold):
    rows = events(sid)
    texts = []
    for r in rows:
        ev = r.get('event') or {}
        if ev.get('type') not in ('user/message', 'agent/inbox/spliced'):
            continue
        texts.append(json.dumps(ev.get('data', {}), ensure_ascii=False))
    hits = {}
    for name, pat in LOOP_PATTERNS.items():
        n = sum(1 for t in texts if re.search(pat, t))
        if n:
            hits[name] = n
    looping = {k: v for k, v in hits.items() if v >= threshold}
    return {'sessionId': sid, 'events': len(rows), 'hits': hits,
            'looping': bool(looping), 'loop_details': looping}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--sid')
    ap.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD)
    a = ap.parse_args()

    sids = [a.sid] if a.sid else sessions()
    results = [analyze(s, a.threshold) for s in sids]
    loops = [r for r in results if r['looping']]

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not sids:
            print('无 running 会话')
        for r in results:
            status = 'LOOP' if r['looping'] else 'OK'
            print(f"{status}  {r['sessionId']}  events={r['events']}  hits={r['hits']}")
            if r['looping']:
                print(f"  循环证据: {r['loop_details']}")
        print('\n注意：本工具只读告警，不自动 cancel——且 2026-11-21 实证 cancel 对活跃循环无效，')
        print('      停止需靠：消除注入源（重启/改配置）或模型自行收尾。')

    return 1 if loops else 0


if __name__ == '__main__':
    sys.exit(main())
