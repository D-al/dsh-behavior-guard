# -*- coding: utf-8 -*-
"""test_verify_ran.py - S13 verifyRan tightening gate check.

Acceptance criteria:
1. index.mjs contains verifyEvidence marker (or equivalent naming)
2. read/cat no longer auto-sets verifyRan due to writeCalls > 0 (loose rule removed)
3. Exact match conditions for [VERIFY]/test_/verify_/_test.py are required

Usage: D:/Python/python.exe -B tools/test_verify_ran.py
Exit code: 0=PASS, 1=FAIL
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # .../dsh-behavior-guard/


def check_verify_evidence_field():
    """Criterion 1: index.mjs must contain verifyEvidence references."""
    idx = ROOT / "index.mjs"
    text = idx.read_text(encoding="utf-8")

    patterns = [
        r'verifyEvidence\s*[=:]',           # variable declaration/assignment
        r's\.verifyEvidence',                # state object property access
        r'st\.verifyEvidence',               # snapshot parameter access
    ]
    found = any(re.search(p, text) for p in patterns)
    if not found:
        return False, "verifyEvidence field definition or reference not found"
    count = sum(1 for p in patterns if re.search(p, text))
    return True, f"Found {count} verifyEvidence reference(s)"


def check_read_no_auto_verifiran():
    """Criterion 2: read/cat + writeCalls > 0 should NOT unconditionally set verifyRan."""
    idx = ROOT / "index.mjs"
    text = idx.read_text(encoding="utf-8")

    # Old pattern that should have been removed
    old_pattern = (
        r"(callName\s*===\s*['\"]read['\"].*?callName\s*===\s*['\"]cat['\"]|.*?(?:read|cat).*?.*?callName).+?"
        r"s\.writeCalls\s*>\s*0\s*\)\s*s\.verifyRan\s*=\s*true"
    )
    if re.search(old_pattern, text, re.S):
        return False, "Loose rule still exists: read/cat + writeCalls > 0 triggers verifyRan=true"
    return True, "Confirmed no loose read+writeCalls auto-trigger verifyRan logic"


def check_verify_evidence_conditions():
    """Criterion 3: New logic should have exact match conditions ([VERIFY] / test_ / verify_ / _test.py)."""
    idx = ROOT / "index.mjs"
    text = idx.read_text(encoding="utf-8")

    required_patterns = [
        (r'\[VERIFY\]', '[VERIFY] keyword check'),
        (r'test_', 'test_ prefix check'),
        (r'verify_', 'verify_ prefix check'),
        (r'_test[\\.]py', '_test.py suffix check'),
        (r'_test[\\.]mjs', '_test.mjs suffix check'),
    ]
    missing = []
    for pat, label in required_patterns:
        if not re.search(pat, text):
            missing.append(label)

    if missing:
        return False, "Missing verification conditions: " + ", ".join(missing)
    return True, f"All {len(required_patterns)} exact match condition types implemented"


def check_turn_reset():
    """Helper check: turn/start should reset verifyEvidence to 0."""
    idx = ROOT / "index.mjs"
    text = idx.read_text(encoding="utf-8")

    pattern = r'verifiedThisTurn.*?verifyEvidence.*?0'
    if not re.search(pattern, text, re.DOTALL):
        return False, "verifyEvidence reset to 0 not found at turn/start"
    return True, "Confirmed verifyEvidence is reset at turn/start"


def main():
    tests = [
        ("verifyEvidence field exists", check_verify_evidence_field),
        ("no-auto-verifyRan via read", check_read_no_auto_verifiran),
        ("exact-match conditions complete", check_verify_evidence_conditions),
        ("turn/start reset", check_turn_reset),
    ]

    all_pass = True
    results = []
    for name, fn in tests:
        ok, msg = fn()
        results.append((name, ok, msg))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {msg}")
        if not ok:
            all_pass = False

    total = len(tests)
    passed = sum(1 for _, ok, _ in results if ok)
    print("\n" + "=" * 50)
    print(f"S13 verifyRan tightening gate: {passed}/{total} PASS")
    print("=" * 50)

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
