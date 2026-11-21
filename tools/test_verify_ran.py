# -*- coding: utf-8 -*-
"""test_verify_ran.py — S13 verifyRan tightening gate check.

Acceptance criteria:
1. index.mjs contains verifyEvidence marker (or equivalent naming)
2. read/cat no longer auto-sets verifyRan due to writeCalls > 0 (loose rule removed)
3. Exact match conditions for [VERIFY]/test_/verify_/_test.py are required

Usage: D:/Python/python.exe -B tools/test_verify_ran.py
Exit code: 0=PASS, 1=FAIL
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # .../dsh-behavior-guard/


def _read_lines():
    """Read index.mjs lines once."""
    idx = ROOT / "index.mjs"
    return idx.read_text(encoding="utf-8").split('\n')


def check_verify_evidence_field():
    """Criterion 1: index.mjs must contain verifyEvidence references."""
    lines = _read_lines()
    found = 0
    for line in lines:
        if 'verifyEvidence' not in line:
            continue
        stripped = line.strip()
        if any(kw in stripped for kw in ['verifyEvidence:', 'verifyEvidence=', '.verifyEvidence', 'st.verifyEvidence']):
            found += 1
    if found == 0:
        return False, "verifyEvidence field definition or reference not found"
    return True, f"Found {found} verifyEvidence reference(s)"


def check_read_no_auto_verifiran():
    """Criterion 2: read/cat + writeCalls > 0 should NOT unconditionally set verifyRan."""
    lines = _read_lines()
    for i, line in enumerate(lines):
        if 's.verifyRan = true' not in line:
            continue
        start = max(0, i - 5)
        end = min(len(lines), i + 6)
        context = '\n'.join(lines[start:end]).lower()
        if ('read' in context or 'cat' in context) and 'writecalls > 0' in context:
            return False, "Loose rule still exists: read/cat + writeCalls > 0 triggers verifyRan=true"
    return True, "Confirmed no loose read+writeCalls auto-trigger verifyRan logic"


def check_verify_evidence_conditions():
    """Criterion 3: New logic should have exact match conditions ([VERIFY] / test_ / verify_ / _test.py)."""
    text = (ROOT / "index.mjs").read_text(encoding="utf-8")
    
    checks = {
        '[VERIFY]': '[VERIFY] keyword',
        'test_': 'test_ prefix',
        'verify_': 'verify_ prefix',
        '_test\\.py': '_test.py suffix (regex)',
        '_test\\.mjs': '_test.mjs suffix (regex)',
    }
    missing = []
    for marker, label in checks.items():
        if marker not in text:
            # Also try without backslash as fallback search
            alt = marker.replace('\\\\.', '.')
            if alt.lower() not in text.lower():
                missing.append(label)
    
    if missing:
        return False, "Missing verification conditions: " + ", ".join(missing)
    return True, f"All {len(checks)} exact match condition types implemented"


def check_turn_reset():
    """Helper check: turn/start should reset verifyEvidence to 0."""
    lines = _read_lines()
    found_reset = False
    for i, line in enumerate(lines):
        if 'verifiedThisTurn' not in line:
            continue
        # Search next 10 lines for verifyEvidence and 0
        for j in range(i, min(i + 10, len(lines))):
            if 'verifyEvidence' in lines[j] and '0' in lines[j]:
                found_reset = True
                break
        if found_reset:
            break
    
    if not found_reset:
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
