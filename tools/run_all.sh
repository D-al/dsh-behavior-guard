#!/bin/bash
# run_all.sh — 廉价 e2e 最小集合 (A3_5)
# 排除 verify_agent.py (35B, 600s)
# 用法: bash tools/run_all.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PASS=0
FAIL=0
ERRORS=""

run_test() {
    local name="$1"
    shift
    echo "[run_all] $*"
    if eval "$@" > /dev/null 2>&1; then
        echo "  PASS: $name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $name"
        FAIL=$((FAIL + 1))
        ERRORS="${ERRORS}\n  - ${name}"
    fi
}

echo "========================================="
echo " A3_5 Cheap E2E Test Suite"
echo " $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "========================================="

# Check 1: node --check index.mjs
if command -v node >/dev/null 2>&1; then
    run_test "node--check-index" "node --check \"$ROOT/index.mjs\""
else
    echo "[skip] node not found in PATH"
fi

# Check 2: Python config_check.py — try python3 first, fallback to python
if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    PYTHON=""
fi
if command -v "$PYTHON" >/dev/null 2>&1; then
    run_test "config-check" "$PYTHON \"$ROOT/tools/config_check.py\""
else
    echo "[skip] python not found"
fi

# Check 3-17: Run all test_*.mjs files (excluding verify_agent.py)
for t in "$ROOT"/tools/test_*.mjs; do
    fname=$(basename "$t")
    # Skip verify_agent.py equivalent (not mjs but skip anyway)
    case "$fname" in
        verify_*) continue ;;
    esac
    run_test "test-$fname" "node --experimental-modules \"$t\""
done

echo ""
echo "========================================="
echo " Results: $PASS pass, $FAIL fail"
if [ $FAIL -gt 0 ]; then
    echo " Failures:${ERRORS}"
fi
echo "========================================="

exit $((FAIL > 0 ? 1 : 0))
