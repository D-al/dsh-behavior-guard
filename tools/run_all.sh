#!/bin/bash
# run_all.sh — 廉价 e2e 最小集合 (A3_5)
# 排除 verify_agent.py (35B, 600s)
# 用法: bash tools/run_all.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Path resolution for Windows environments where node/python are not in default PATH
if ! command -v node >/dev/null 2>&1; then
    for p in \
        "/d/Brain/dsh-data/dsh-runtimes/dsh-primary-runtime/dependencies/node/bin" \
        "C:/Program Files/nodejs" \
        "C:/Users/Ad/AppData/Roaming/npm"; do
        if [ -f "$p/node.exe" ]; then
            export PATH="$p:$PATH"
            break
        fi
    done
fi

PYTHON="${PYTHON:-}"
if ! command -v python3 >/dev/null 2>&1 || ! python3 --version >/dev/null 2>&1; then
    if [ -f "/d/Python/python.exe" ]; then
        PYTHON="/d/Python/python.exe"
    elif command -v python3 >/dev/null 2>&1; then
        PYTHON="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON="python"
    else
        PYTHON=""
    fi
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON="python"
else
    PYTHON=""
fi

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
    # 引用-决策对应守卫（2026-11-20 用户架构级要求）：决策引用幻觉证据即 FAIL
    run_test "citation-guard" "$PYTHON \"$ROOT/tools/citation_guard.py\" --quiet"
    run_test "strategy-alignment" "$PYTHON \"$ROOT/tools/test_strategy_alignment.py\""
    run_test "verify-audit" "$PYTHON \"$ROOT/tools/audit_verify.py\" --strict"
    run_test "tech-tree" "$PYTHON \"$ROOT/tools/tech_tree.py\" --check"
    run_test "implicit-deps" "$PYTHON \"$ROOT/tools/audit_implicit_deps.py\" --strict"
    run_test "tool-frequency" "$PYTHON \"$ROOT/tools/tool_audit.py\" --json"
    run_test "gate-evidence" "$PYTHON \"$ROOT/tools/audit_gate_evidence.py\" --strict"
    run_test "self-harness-gate" "$PYTHON \"$ROOT/tools/self_harness_gate.py\" --self-test"
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
