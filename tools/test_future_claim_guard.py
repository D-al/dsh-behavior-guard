#!/usr/bin/env python3
"""test_future_claim_guard.py — A1_6 将来时承诺守卫测试

从 index.mjs 提取三个 CLAIM 正则（单一源，不复制正则避免漂移），
用 Python re 验证行为（这些模式在 JS/Python 间兼容）：
  ①过去时声明 ②将来时承诺 ③"我将"承诺 → 都应被识别为路径声明
  ④无具体产物的进度说明 → 不应识别（避免误拦正常汇报）
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'index.mjs'
text = SRC.read_text(encoding='utf-8')


def extract(name):
    """从 index.mjs 提取 `const NAME = /pattern/flags` 的 pattern。"""
    m = re.search(r'const ' + re.escape(name) + r' = /(.+?)/([a-z]*)\s*\n', text)
    if not m:
        raise RuntimeError(f'cannot extract {name} from index.mjs')
    return m.group(1)


PATS = [re.compile(extract(n)) for n in ('WRITE_CLAIM', 'FUTURE_CLAIM', 'WILL_CLAIM')]


def is_claim(line):
    return any(p.search(line) for p in PATS)


CASES = [
    ('过去时-已写入', '我已写入 tools/check_verify.py', True),
    ('将来时-现在写', '现在编写 tools/test_future_claim_guard.py', True),
    ('将来时-接下来创建', '接下来创建 docs/FUTURE_CLAIM_GUARD_20261120.md', True),
    ('将来时-马上实现', '马上实现 ./tools/foo.mjs', True),
    ('IWill-我将写', '我将写 ./tools/bar.py', True),
    ('无产物-考虑', '下一步我会考虑优化一下', False),
    ('无产物-进度说明', '正在分析现有逻辑，稍等', False),
    ('普通叙述', '这是一个纯咨询问题', False),
]


def main():
    passed = failed = 0
    for name, line, expected in CASES:
        got = bool(is_claim(line))
        ok = got == expected
        print(f'{"PASS" if ok else "FAIL"}  {name}: recognized={got} expected={expected}')
        if ok:
            passed += 1
        else:
            failed += 1
    print(f'\nRESULT: {passed} PASS / {failed} FAIL')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
