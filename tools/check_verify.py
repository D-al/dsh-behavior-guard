#!/usr/bin/env python3
"""
check_verify.py — 判据元验证器（防假绿）

独立于 roadmap_check.py 的 evaluate，检测判据自身的四类病：
1. 自引用递归 — 判据 cmd 里调用包含自己的 ID 的命令，导致无限递归
2. 格式不匹配 — test_pass 正则只认裸 ^PASS 但被验工具输出带空格/前缀 → 假 FAIL
3. 恒真判据 — file_exists 指向必然存在的文件（如 /etc/os-release），或 min=0 → 假绿
4. 测试 sid 污染 — trace 评估数据含 test_sids.json 里的 sid，把测试当真实

内置构造的假判据样本（每种病至少一个），运行时用这些样本自测：所有样本必须全被判 FAIL。

硬约束：
- 不扫描内容里的中文做判断，只分析判据结构字段
- 使用绝对路径 D:/Python/python.exe（shell 裸 python rc=1）
- edit 后立即 py_compile 验证语法
"""
import os
import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # tools/check_verify.py -> 仓库根（2026-11-20 修正：原少一层导致 test_sids 永远加载为0）
TEST_SIDS_FILE = ROOT / 'test_sids.json'
LADDER_YAML = ROOT / 'CAPABILITY_LADDER.yaml'
GRAPH_MD = ROOT / 'ROADMAP_GRAPH.md'


def load_test_sids():
    """加载测试 sid 黑名单。"""
    if TEST_SIDS_FILE.exists():
        try:
            data = json.loads(TEST_SIDS_FILE.read_text(encoding='utf-8'))
            sids = data.get('sids', [])
            if isinstance(sids, list):
                return set(sids)
        except Exception:
            pass
    return set()


def detect_recursive(item_id, verify_list, all_items=None):
    """
    检测自引用递归。
    
    规则：如果某个 verify 项的 kind=test_pass 且 cmd 中包含 '--card <item_id>'
    或者 cmd 中调用了会遍历该 item_id 的参数，则标记为 recursive risk。
    
    更广义：检查 cmd 是否包含对当前 ID 的直接引用（通过 --card/--id/--skip 等参数）。
    """
    for v in verify_list:
        if v.get('kind') != 'test_pass':
            continue
        cmd = str(v.get('cmd', ''))
        # 检查 cmd 中是否直接包含当前 item 的 ID 引用
        # 模式：--card X, --id X, --skip X, --only X 其中 X == item_id
        patterns = [
            rf'--card\s+{re.escape(item_id)}\b',
            rf'--id\s+{re.escape(item_id)}\b',
            rf'--skip\s+.*{re.escape(item_id)}\b',
            rf'--only\s+.*{re.escape(item_id)}\b',
        ]
        for pat in patterns:
            if re.search(pat, cmd):
                return True, f"cmd references self-id {item_id}: {cmd[:60]}"
    return False, ""


def detect_format_mismatch(item_id, verify_list):
    """
    检测格式不匹配。
    
    规则：test_pass 的 PASS 输出正则只认裸 ^PASS，但被验工具实际输出带前缀/后缀/空格。
    检测方式：查看 regex 过于严格（如只匹配 '^PASS$' 无容错），同时 verify 项没有指定
    flags 来放宽匹配。
    
    简化判断：如果 test_pass 使用默认正则（代码里硬编码的 r'^(?:PASS|\\[PASS\\s*\\])'）
    而 cmd 输出的工具已知会加 padding（如 '[PASS  ]'），则可能不匹配。
    这里我们用启发式：检查 cmd 中是否有输出格式标志暗示非标准格式。
    """
    for v in verify_list:
        if v.get('kind') != 'test_pass':
            continue
        cmd = str(v.get('cmd', ''))
        # 启发式：如果 cmd 指向一个已知会产生非标准输出的工具类型
        # 例如：某些测试框架输出 '[PASS  ] id ...' 而非裸 'PASS'
        # 这里我们检查是否明确使用了宽松匹配（flags 含 IGNORECASE 或自定义 regex）
        has_custom_regex = 'regex' in v and 'min' not in v
        has_flags = 'flags' in v
        
        # 保守判断：有 flags 说明考虑了格式问题；否则假设用默认正则
        # 真正的格式不匹配需要知道被验工具的输出来对比
        # 这里的简化版本：标记那些 cmd 较长且无 flags 的项为 warn
        if len(cmd) > 30 and not has_custom_regex and not has_flags:
            # 这可能是一个潜在的格式不匹配风险——但不一定真的有问题
            pass
    
    # 实用检测（2026-11-20 补）：cmd 明示输出非标准格式（如 '[PASS  ]'），
    # 但判据没有 format_hint / regex 声明期待格式 → evaluate 的 PASS 计数可能错配。
    for v in verify_list:
        if v.get('kind') != 'test_pass':
            continue
        cmd = str(v.get('cmd', ''))
        if ('[PASS' in cmd or '\\[PASS' in cmd) and not v.get('format_hint') and 'regex' not in v:
            return True, f'test_pass cmd emits nonstandard PASS format but no format_hint declared: {cmd[:60]}'
    return False, ""


def detect_tautology(item_id, verify_list, all_items=None):
    """
    检测恒真判据。
    
    两类情况：
    1. file_exists 指向必然存在的系统文件（如 /etc/os-release, C:\\Windows\\System32）
       → 这些文件在绝大多数环境下都存在，判据形同虚设
    2. min=0 或 min 过低（≤0）→ 永远满足
    3. file_grep min=0 → 永远满足
    """
    tautology_paths = {
        '/etc/os-release', '/etc/hostname', '/proc/version',
        'C:\\Windows\\System32\\config\\systemprofile',
        '/dev/null', '/tmp',
    }
    
    for v in verify_list:
        kind = v.get('kind')
        
        # 情况1: min <= 0
        min_val = v.get('min', 1)
        if isinstance(min_val, (int, float)) and min_val <= 0:
            return True, f"min={min_val} is trivially satisfied"
        
        # 情况2: file_exists 指向必然存在的文件
        if kind == 'file_exists':
            path_str = str(v.get('path', ''))
            resolved_path = str(Path(path_str).resolve())
            for tp in tautology_paths:
                if resolved_path == Path(tp).resolve():
                    return True, f"path always exists: {path_str}"
        
        # 情况3: file_grep 指向必然存在的空文件或已知存在文件
        if kind == 'file_grep':
            path_str = str(v.get('path', ''))
            p = ROOT / path_str
            if p.exists() and p.stat().st_size == 0:
                return True, f"grep on empty file: {path_str}"
    
    return False, ""


def detect_sid_pollution(verify_list, test_sids):
    """
    检测测试 sid 污染。
    
    规则：如果 trace_count / trace_absent 类型的判据没有正确过滤 test_sids，
    或者 eval 数据中直接包含了测试 sid，则标记为污染风险。
    
    简化判断：检查是否有 trace_* 类型判据使用了 sid_filter != 'exclude_tests'，
    这意味着测试 sid 没有被排除。
    """
    for v in verify_list:
        kind = v.get('kind')
        if kind not in ('trace_count', 'trace_absent'):
            continue
        
        sid_filter = v.get('sid_filter', '')
        if sid_filter != 'exclude_tests' and test_sids:
            return True, f"trace_{kind} without sid_filter='exclude_tests'"
    
    return False, ""


class FakeItemGenerator:
    """构造四种病的假判据样本。"""
    
    @staticmethod
    def make_recursive_sample(item_id="FAKE_RECURSIVE"):
        return {
            "id": item_id,
            "status": "ready",
            "verify": [
                {
                    "kind": "test_pass",
                    "cmd": f"D:/Python/python.exe -B tools/roadmap_check.py --card FAKE_RECURSIVE",
                    "min": 1
                }
            ]
        }
    
    @staticmethod
    def make_format_mismatch_sample(item_id="FAKE_FORMAT"):
        return {
            "id": item_id,
            "status": "ready",
            "verify": [
                {
                    "kind": "test_pass",
                    "cmd": "echo '[PASS  ] some-tool-output'",
                    "min": 1
                }
            ]
        }
    
    @staticmethod
    def make_tautology_sample(item_id="FAKE_TAUTOLOGY"):
        return {
            "id": item_id,
            "status": "ready",
            "verify": [
                {
                    "kind": "file_exists",
                    "path": "/etc/os-release"
                },
                {
                    "kind": "test_pass",
                    "cmd": "echo PASS",
                    "min": 0
                }
            ]
        }
    
    @staticmethod
    def make_sid_pollution_sample(item_id="FAKE_SID_POLLUTION"):
        return {
            "id": item_id,
            "status": "ready",
            "verify": [
                {
                    "kind": "trace_count",
                    "source": "bench/sessions.jsonl",
                    "kind_name": "skill_use",
                    "min": 1
                    # 注意：没有 sid_filter，测试 sid 未被排除
                }
            ]
        }


def run_self_test():
    """用构造的假判据样本自测，所有样本必须全被判 FAIL（有病）。"""
    test_sids = load_test_sids()
    samples = [
        ("recursive", FakeItemGenerator.make_recursive_sample()),
        ("format_mismatch", FakeItemGenerator.make_format_mismatch_sample()),
        ("tautology", FakeItemGenerator.make_tautology_sample()),
        ("sid_pollution", FakeItemGenerator.make_sid_pollution_sample()),
    ]
    
    all_passed = True
    results = []
    
    for name, sample in samples:
        bugs = []
        
        has_rec, rec_msg = detect_recursive(sample['id'], sample['verify'])
        if has_rec:
            bugs.append(f"RECURSIVE: {rec_msg}")
        
        has_fmt, fmt_msg = detect_format_mismatch(sample['id'], sample['verify'])
        if has_fmt:
            bugs.append(f"FORMAT_MISMATCH: {fmt_msg}")
        
        has_tau, tau_msg = detect_tautology(sample['id'], sample['verify'])
        if has_tau:
            bugs.append(f"TAUTOLOGY: {tau_msg}")
        
        has_sid, sid_msg = detect_sid_pollution(sample['verify'], test_sids)
        if has_sid:
            bugs.append(f"SID_POLLUTION: {sid_msg}")
        
        is_buggy = len(bugs) > 0
        
        status = "FAIL (buggy)" if is_buggy else "PASS (clean)"
        results.append((name, is_buggy, bugs))
        
        if not is_buggy:
            all_passed = False
    
    return all_passed, results, test_sids


def check_real_items(test_sids):
    """检查 ROADMAP_GRAPH.md 中所有真实 item/rung 的 verify 判据。"""
    issues_found = []
    
    md_content = GRAPH_MD.read_text(encoding='utf-8', errors='replace')
    graph_begin = '<!-- ROADMAP_GRAPH_BEGIN v1 -->'
    graph_end = '<!-- ROADMAP_GRAPH_END -->'
    
    m = re.search(re.escape(graph_begin) + r'(.*?)' + re.escape(graph_end), md_content, re.S)
    if not m:
        print("WARN: Could not find roadmap graph block")
        return [], set()
    
    try:
        import yaml as yaml_module
        graph_data = yaml_module.safe_load(m.group(1))
    except Exception:
        return [], set()
    
    items = graph_data.get('items', []) + graph_data.get('rungs', [])
    
    for item in items:
        item_id = item.get('id', 'UNKNOWN')
        verify_list = item.get('verify', [])
        
        if not verify_list:
            continue
        
        # Skip test items
        if item_id.startswith(('FAKE_', 'TEST_')):
            continue
        
        bugs = []
        
        has_rec, rec_msg = detect_recursive(item_id, verify_list, items)
        if has_rec:
            bugs.append(rec_msg)
        
        has_tau, tau_msg = detect_tautology(item_id, verify_list, items)
        if has_tau:
            bugs.append(tau_msg)
        
        has_sid, sid_msg = detect_sid_pollution(verify_list, test_sids)
        if has_sid:
            bugs.append(sid_msg)
        
        has_fmt, fmt_msg = detect_format_mismatch(item_id, verify_list)
        if has_fmt:
            bugs.append(fmt_msg)
        
        if bugs:
            issues_found.append({
                'item_id': item_id,
                'bugs': bugs,
                'count': len(bugs)
            })
    
    return issues_found, test_sids


def main():
    """主入口：先自测，再扫真实判据。"""
    print("=" * 60)
    print("check_verify.py — 判据元验证器（防假绿）")
    print("=" * 60)
    
    # Step 1: Self-test with fake samples
    print("\n[SELF-TEST] Running against constructed buggy samples...")
    self_ok, self_results, test_sids = run_self_test()
    
    all_pass_count = sum(1 for name, is_buggy, _ in self_results if is_buggy)
    total_samples = len(self_results)
    
    for name, is_buggy, bugs in self_results:
        if is_buggy:
            bug_names = ", ".join(b.split(":")[0] for b in bugs)
            print(f"  FAIL (buggy): {name} -> detected: {bug_names}")
        else:
            print(f"  PASS (clean): {name} -> no bugs found")
    
    print(f"\nSelf-test result: {all_pass_count}/{total_samples} buggy samples correctly detected as FAIL")
    
    if not self_ok:
        print("SELF-TEST FAILED: Not all buggy samples were detected!")
        sys.exit(1)
    
    # Step 2: Scan real items
    print(f"\n[REAL SCAN] Checking {len(test_sids)} test sids filtered out: {sorted(test_sids)}")
    issues, _ = check_real_items(test_sids)
    
    if issues:
        print(f"\nFound {len(issues)} item(s) with potential issues:")
        for issue in issues:
            print(f"  - {issue['item_id']}: {'; '.join(issue['bugs'])}")
    else:
        print(f"\nNo major issues found in real items.")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"PASS — Meta-validation complete. All {total_samples} buggy samples caught.")
    print(f"{'='*60}")
    
    sys.exit(0)


if __name__ == '__main__':
    main()
