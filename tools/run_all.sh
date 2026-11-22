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

# PYTHON 解析：优先 D:/Python/python.exe（装有 PyYAML 等依赖）
# 不能先信 python3——WindowsApps shim 或别的 Python 可能没有 yaml，导致测试假 FAIL
PYTHON="${PYTHON:-}"
if [ -n "$PYTHON" ]; then
    :  # 外部显式指定，尊重
elif [ -f "/d/Python/python.exe" ]; then
    PYTHON="/d/Python/python.exe"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" >/dev/null 2>&1; then
    PYTHON="python3"
elif command -v python >/dev/null 2>&1 && python -c "import yaml" >/dev/null 2>&1; then
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

# Check 2: Python tests (PYTHON resolved once at top — do NOT reassign here;
#          a prior duplicate block silently overrode it to a yaml-less python3)
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
    # A6 判据2：全部 test_*.py 纳入门禁（此前仅1/12，改坏也全绿）
    for t in "$ROOT"/tools/test_*.py; do
        fname=$(basename "$t")
        case "$fname" in
            test_strategy_alignment.py) continue ;;  # 上面已显式跑
        esac
        run_test "py-$fname" "$PYTHON \"$t\""
    done
    run_test "test-census" "$PYTHON \"$ROOT/tools/test_census.py\""
    # A6/FG：地基不变量巡检（编排6条硬约束,零LLM,几秒）——地基漂移则整门禁红
    run_test "foundation-guard" "$PYTHON \"$ROOT/tools/foundation_guard.py\""
    # 规则包版本钉住:agent不得偷改评判规则(INV-7也含此检查,这里双保险)
    run_test "rulepack-pinned" "$PYTHON \"$ROOT/tools/rulepack_guard.py\""
    # 判据执行层体检:解释器/路径/正则/门槛腐化(INV-8也含此检查,双保险)
    run_test "criteria-health" "$PYTHON \"$ROOT/tools/audit_criteria_health.py\""
    # 目的追溯制:每个机制必须追溯到STRATEGY条款,orphan需人工判断
    run_test "traceability" "$PYTHON \"$ROOT/tools/audit_traceability.py\""
    # 证据生成器诚实性:防生成器造假(probe不污染/缺输入N-M退出)
    run_test "generator-honesty" "$PYTHON \"$ROOT/tools/audit_generator_honesty.py\""
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
