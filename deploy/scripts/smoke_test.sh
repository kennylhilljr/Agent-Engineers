#!/usr/bin/env bash
# smoke_test.sh - Post-deployment smoke tests for Agent Dashboard
# Usage: ./deploy/scripts/smoke_test.sh [BASE_URL]
#
# Runs after a deployment to verify core functionality.
#
# EXIT CODES:
#   0 - All smoke tests passed
#   1 - One or more smoke tests failed

set -euo pipefail

BASE_URL="${1:-https://staging.agent-dashboard.example.com}"
TIMEOUT=15

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

FAILURES=0
TESTS_RUN=0

smoke_test() {
    local name="$1"
    local method="${2:-GET}"
    local path="$3"
    local expected_status="${4:-200}"
    local data="${5:-}"

    TESTS_RUN=$((TESTS_RUN + 1))
    local url="$BASE_URL$path"
    info "[$TESTS_RUN] $method $path (expect HTTP $expected_status)"

    local curl_args=(-s -o /tmp/smoke_response.json -w "%{http_code}" --max-time "$TIMEOUT")
    if [ "$method" = "POST" ]; then
        curl_args+=(-X POST -H "Content-Type: application/json")
        if [ -n "$data" ]; then
            curl_args+=(-d "$data")
        fi
    fi

    local http_status
    http_status=$(curl "${curl_args[@]}" "$url" 2>/dev/null) || http_status=0

    if [ "$http_status" = "$expected_status" ]; then
        pass "$name: HTTP $http_status"
        return 0
    else
        fail "$name: Expected HTTP $expected_status, got $http_status"
        if [ -f /tmp/smoke_response.json ]; then
            info "Response: $(cat /tmp/smoke_response.json | head -c 200)"
        fi
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

check_json_field() {
    local name="$1"
    local field="$2"
    local expected="$3"
    local file="${4:-/tmp/smoke_response.json}"

    TESTS_RUN=$((TESTS_RUN + 1))
    local actual
    actual=$(python3 -c "
import json, sys
try:
    data = json.load(open('$file'))
    val = data
    for key in '$field'.split('.'):
        val = val.get(key, None)
        if val is None:
            break
    print(str(val).lower() if isinstance(val, bool) else str(val))
except Exception as e:
    print('ERROR: ' + str(e))
" 2>/dev/null)

    if [ "$actual" = "$expected" ]; then
        pass "$name: $field = '$actual'"
        return 0
    else
        fail "$name: expected $field='$expected', got '$actual'"
        FAILURES=$((FAILURES + 1))
        return 1
    fi
}

echo "=============================================="
echo " Agent Dashboard Smoke Tests"
echo " Target: $BASE_URL"
echo " Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=============================================="
echo ""

# --- Health & Readiness ---
info "=== Health & Readiness ==="
smoke_test "Health check" GET /health 200
check_json_field "Health status" "status" "ok"

smoke_test "API health check" GET /api/health 200
check_json_field "API health status" "status" "ok"

smoke_test "Readiness check" GET /ready 200
check_json_field "Readiness" "ready" "true"

smoke_test "API readiness" GET /api/ready 200
check_json_field "API readiness" "ready" "true"

echo ""

# --- Core API endpoints ---
info "=== Core API Endpoints ==="
smoke_test "Metrics endpoint" GET /api/metrics 200
smoke_test "Agents endpoint" GET /api/agents 200
smoke_test "System status" GET /api/agents/system-status 200

echo ""

# --- Auth endpoints (expect 400 for missing data, not 500) ---
info "=== Auth Endpoints ==="
smoke_test "Auth login reachable" POST /api/auth/login 400 '{"email":"","password":""}'

echo ""

# --- Static assets ---
info "=== Static Assets ==="
smoke_test "Dashboard HTML" GET / 200

echo ""

# --- Security headers ---
info "=== Security Headers ==="
TESTS_RUN=$((TESTS_RUN + 1))
HEADERS=$(curl -s -I --max-time "$TIMEOUT" "$BASE_URL/" 2>/dev/null)
if echo "$HEADERS" | grep -qi "X-Content-Type-Options"; then
    pass "Security headers: X-Content-Type-Options present"
else
    fail "Security headers: X-Content-Type-Options missing"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "=============================================="
echo " Results: $((TESTS_RUN - FAILURES))/$TESTS_RUN passed"
if [ "$FAILURES" -eq 0 ]; then
    pass "All smoke tests passed!"
    echo "=============================================="
    exit 0
else
    fail "$FAILURES/$TESTS_RUN smoke test(s) FAILED!"
    echo "=============================================="
    exit 1
fi
