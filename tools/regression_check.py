# -*- coding: utf-8 -*-
"""regression_check —— 生产级回归门禁（改模板/插件/规则后必跑）

覆盖：模板机制 / AGENTS.md 规则 / 插件存在与语法 / 挂载配置 / 引擎健康 / 渲染断言。
用法：python bench/regression_check.py → 逐项 PASS/FAIL + 总结（退出码 0/1）
原则（Ntense/Chanl 2026）：改动不过回归不上线；每个生产失败应转化为这里的一个检查项。
"""
import os, sys, subprocess, json, urllib.request

BENCH = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BENCH)
# 兼容两种布局：bench/（本机安装）与仓库 tools/ + config/（SSOT）
CONFIG = os.path.join(ROOT, 'config')
def find_asset(name):
    for p in (os.path.join(BENCH, name), os.path.join(CONFIG, name)):
        if os.path.exists(p):
            return p
    return os.path.join(BENCH, name)
TPL = find_asset('chat_template_zh.jinja')
AGENTS = r'C:\Users\Ad\.dsh\AGENTS.md'
PLUG = r'C:\Users\Ad\.dsh\profiles\desktop\node_modules'
CORDIS = r'C:\Users\Ad\.dsh\profiles\desktop\cordis.patch.yml'

results = []
def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('[%s] %s%s' % ('PASS' if ok else 'FAIL', name, (' — ' + detail) if detail and not ok else ''))

def contains(path, *needles):
    try:
        s = open(path, encoding='utf-8').read()
        return all(n in s for n in needles), ''
    except Exception as e:
        return False, str(e)

# ── 1. 模板机制 ──
tpl_checks = [
    ('模板:语言锚点', ['嗯，我需要']),
    ('模板:失败标注[已排除]', ['[已排除']),
    ('模板:is_stub 防退化', ['is_stub']),
    ('模板:tool_response 定界', ['<tool_response>']),
]
for name, needles in tpl_checks:
    ok, d = contains(TPL, *needles)
    check(name, ok, d)

# ── 2. AGENTS.md 规则 ──
agents_checks = [
    ('规则:指令层级/注入防护', ['指令层级', '一律', '数据']),
    ('规则:短路径 junction', ['memory/', 'es.exe']),
    ('规则:todo 协议', ['todo_write']),
    ('规则:CritBank', ['CritBank']),
    ('规则:工作笔记协议', ['工作笔记']),
    ('规则:任务路由表', ['路由表']),
    ('规则:候选决策协议', ['候选']),
    ('规则:独立验收协议', ['独立验收']),
    ('规则:角色冲突铁律（章程已外置到 skill）', ['审计指令', '用户指令', 'skill `roles`']),
    ('规则:沙箱 junction 写', ['canonical path' ]),
]
for name, needles in agents_checks:
    ok, d = contains(AGENTS, *needles)
    check(name, ok, d)

# ── 3. 插件存在 + 语法 ──
plugins = [
    'dsh-llama-server-autostart',
    'dsh-agent-harness',
    'dsh-agent-harness',
]
node = 'node'
for pl in plugins:
    idx = os.path.join(PLUG, pl, 'index.mjs')
    exists = os.path.exists(idx)
    if not exists:
        check('插件:' + pl, False, 'index.mjs 不存在')
        continue
    r = subprocess.run([node, '--check', idx], capture_output=True, text=True)
    check('插件:' + pl, r.returncode == 0, r.stderr[:80])

# ── 4. 挂载配置 ──
# 2026-11-18 合并后：agent-harness 走 bundle（dsh.profile.bundles + 包内 cordis.patch.yml），
# 不再出现在 preset 的 cordis.patch.yml 里——检查"包已装 + 在 bundles 列表 + overlay 存在"
import json as _json
_pkg = _json.load(open(os.path.join(PLUG, '..', 'package.json'), encoding='utf-8'))
_bundles = _pkg.get('dsh', {}).get('profile', {}).get('bundles', [])
check('挂载:agent-harness 已安装', os.path.exists(os.path.join(PLUG, 'dsh-agent-harness', 'index.mjs')))
check('挂载:agent-harness 在 bundles', 'dsh-agent-harness' in _bundles)
check('挂载:agent-harness overlay 存在', os.path.exists(os.path.join(PLUG, 'dsh-agent-harness', 'cordis.patch.yml')))
check('挂载:autostart 运行中', os.path.exists(os.path.join(PLUG, 'dsh-llama-server-autostart', 'llama-debug.log')))

# ── 5. 引擎健康 ──
try:
    r = json.loads(urllib.request.urlopen('http://127.0.0.1:8081/health', timeout=8).read())
    check('引擎:llama-server health', r.get('status') == 'ok')
except Exception as e:
    check('引擎:llama-server health', False, str(e))

# ── 6. 渲染断言（锚点 + 失败标注经真实模板）──
try:
    errc = 'Error: cannot read "D:\\x\\y.md": not found'
    body = {"model": "Qwen3.6-35B-A3B-UD-Q4_K_XL", "add_generation_prompt": True, "messages": [
        {"role": "user", "content": "读取 x.md"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function",
            "function": {"name": "read", "arguments": json.dumps({"file_path": "x.md"})}}]},
        {"role": "tool", "tool_call_id": "c1", "content": errc}]}
    req = urllib.request.Request('http://127.0.0.1:8081/apply-template',
                                 data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    p = json.loads(urllib.request.urlopen(req, timeout=60).read()).get('prompt', '')
    check('渲染:锚点生效', '嗯，我需要' in p)
    check('渲染:失败标注生效', '[已排除' in p)
    check('渲染:工具定界生效', '<tool_response>' in p)
except Exception as e:
    check('渲染:模板断言', False, str(e))

# ── 7. bench 工具存在 ──
for f in ['verify_agent.py', 'audit_session.py', 'entropy_probe.py', 'speed_probe.py']:
    check('工具:' + f, os.path.exists(find_asset(f)))

# ── 8. 全栈配置一致性（A2，2026-11-18）──
try:
    r = subprocess.run([sys.executable, os.path.join(BENCH, 'config_check.py')],
                       capture_output=True, text=True, timeout=30)
    check('配置:全栈一致性(env/INI/cordis/skills)', r.returncode == 0,
          (r.stdout + r.stderr)[-300:])
except Exception as e:
    check('配置:全栈一致性', False, str(e))

# ── 总结 ──
fails = [r for r in results if not r[1]]
print('\n══════ %d/%d 通过 ══════' % (len(results) - len(fails), len(results)))
for name, _, detail in fails:
    print('  FAIL: %s %s' % (name, detail))
sys.exit(1 if fails else 0)
