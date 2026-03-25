#!/usr/bin/env bash
# Run all tests (backend + frontend) and report combined results.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0

echo "========================================"
echo "  Science Assessor — Full Test Suite"
echo "========================================"
echo ""

# ── Backend (pytest) ─────────────────────────────────────────────────────────
echo ">>> Backend tests (pytest)"
echo ""

cd "$ROOT"
if python -m pytest backend/tests/ -v --tb=short 2>&1; then
    BACKEND_STATUS="PASS"
else
    BACKEND_STATUS="FAIL"
fi

# Parse pytest counts from output by re-running with -q for counts
BACKEND_COUNTS=$(python -m pytest backend/tests/ -q --tb=no 2>&1 | tail -1 || true)

echo ""
echo "Backend: $BACKEND_STATUS  ($BACKEND_COUNTS)"
echo ""

# ── Frontend (vitest) ─────────────────────────────────────────────────────────
echo ">>> Frontend tests (vitest)"
echo ""

cd "$ROOT/frontend"
if npm run test -- --run 2>&1; then
    FRONTEND_STATUS="PASS"
else
    FRONTEND_STATUS="FAIL"
fi

echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
echo "========================================"
echo "  Results"
echo "========================================"
echo "  Backend :  $BACKEND_STATUS"
echo "  Frontend:  $FRONTEND_STATUS"
echo ""

if [ "$BACKEND_STATUS" = "PASS" ] && [ "$FRONTEND_STATUS" = "PASS" ]; then
    echo "  ALL TESTS PASSED"
    exit 0
else
    echo "  SOME TESTS FAILED"
    exit 1
fi
