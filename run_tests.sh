#!/usr/bin/env bash
# Run unit tests for use cases.
#
# Usage:
#   ./run_tests.sh                  # run all tests
#   ./run_tests.sh -v               # verbose output
#   ./run_tests.sh -k create        # filter by name (e.g. only CreateSession tests)
#   ./run_tests.sh --cov            # with coverage report (requires pytest-cov)
#   ./run_tests.sh --cov-check      # coverage report + per-directory threshold checks
#
# Per-directory thresholds (edit below to adjust):
#   server/application/domain/model/  → THRESHOLD_DOMAIN
#   server/application/domain/service/ → THRESHOLD_USE_CASES
#   server/adapter/                    → THRESHOLD_ADAPTERS
#   server/                            → THRESHOLD_TOTAL  (overall)
THRESHOLD_DOMAIN=95
THRESHOLD_USE_CASES=95
THRESHOLD_ADAPTERS=0
THRESHOLD_TOTAL=0

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv: prefer a local venv, fall back to system python3
if [ -f ".venv/bin/activate" ]; then
    VENV_ACTIVATE=".venv/bin/activate"
elif [ -f "venv/bin/activate" ]; then
    VENV_ACTIVATE="venv/bin/activate"
else
    VENV_ACTIVATE=""
fi

if [ -n "$VENV_ACTIVATE" ]; then
    # shellcheck source=/dev/null
    source "$VENV_ACTIVATE"
    trap deactivate EXIT
    echo "Using Python: $(python --version) (venv: $VIRTUAL_ENV)"
else
    echo "Warning: no venv found, using system python3"
fi

# Install / upgrade test dependencies silently
pip install --quiet -r requirements.txt -r requirements-dev.txt

# Run tests
_has_flag() { local flag="$1"; shift; [[ " $* " == *" $flag "* ]]; }

if _has_flag "--cov-check" "$@"; then
    # 1. Collect coverage data without printing a report yet
    python -m pytest --cov=server --cov-report= "${@/--cov-check/}" tests/use_cases/ tests/domain/ tests/adapter/
    echo ""
    echo "── Coverage report ──────────────────────────────────────"
    python -m coverage report --show-missing
    echo ""
    echo "── Per-directory threshold checks ───────────────────────"
    _check() {
        local label="$1" pattern="$2" threshold="$3"
        local actual
        # Parse percentage from the TOTAL line, e.g. "TOTAL  339  3  99%"
        actual=$(python -m coverage report --include="$pattern" 2>/dev/null \
            | awk '/^TOTAL/{gsub(/%/,"",$NF); print $NF+0}')
        actual="${actual:-0}"
        if [ "$actual" -ge "$threshold" ]; then
            printf "  ✓ %-20s %3d%% >= %d%%\n" "$label" "$actual" "$threshold"
            return 0
        else
            printf "  ✗ %-20s %3d%% <  %d%% (FAIL)\n" "$label" "$actual" "$threshold"
            return 1
        fi
    }
    FAIL=0
    _check "server/application/domain/model/"    "server/application/domain/model/*"    "$THRESHOLD_DOMAIN"    || FAIL=1
    _check "server/application/domain/service/" "server/application/domain/service/*" "$THRESHOLD_USE_CASES" || FAIL=1
    _check "server/adapter/"  "server/adapter/*"   "$THRESHOLD_ADAPTERS"  || FAIL=1
    _check "server/ (total)"   "server/*"           "$THRESHOLD_TOTAL"     || FAIL=1
    echo "─────────────────────────────────────────────────────────"
    exit "$FAIL"
elif _has_flag "--cov" "$@"; then
    python -m pytest --cov=server --cov-report=term-missing "${@/--cov/}" tests/use_cases/ tests/domain/ tests/adapter/
else
    python -m pytest "$@" tests/use_cases/ tests/domain/ tests/adapter/
fi
