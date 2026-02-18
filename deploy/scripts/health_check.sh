#!/usr/bin/env bash
# health_check.sh - Verify the Agent Dashboard health and readiness endpoints
# Usage: ./deploy/scripts/health_check.sh [BASE_URL]
#
# EXIT CODES:
#   0 - All checks passed
#   1 - One or more checks failed

set -euo pipefail

BASE_URL="${1:-http://localhost:8080}"
MAX_RETRIES=10
RETRY_INTERVAL=5
TIMEOUT=10

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

FAILURES=0

check_endpoint() {
    local name="$1"
    local url="$2"
    local expected_status="${3:-200}"
    local expected_field="${4:-}"
    local expected_value="${5:-}"

    info "Checking $name at $url ..."
    local response
    local http_status

    http_status=$(curl -s -o /tmp/health_response.json -w "%{http_code}" \
        --max-time "$TIMEOUT" \
        "$url" 2>/dev/null) || http_status=0

    if [ "$http_status" != "$expected_status" ]; then
        fail "$name: Expected HTTP $expected_status, got $http_status"
        FAILURES=$((FAILURES + 1))
        return 1
    fi

    if [ -n "$expected_field" ] && [ -n "$expected_value" ]; then
        local actual_value
        actual_value=$(python3 -c "
import json, sys
try:
    data = json.load(open('/tmp/health_response.json'))
    print(data.get('$expected_field', ''))
except Exception as e:
    print('')
" 2>/dev/null)

        if [ "$actual_value" != "$expected_value" ]; then
            fail "$name: Expected $expected_field='$expected_value', got '$actual_value'"
            FAILURES=$((FAILURES + 1))
            return 1
        fi
    fi

    pass "$name: HTTP $http_status"
    return 0
}

wait_for_service() {
    info "Waiting for service to be available at $BASE_URL ..."
    local attempt=0
    while [ $attempt -lt $MAX_RETRIES ]; do
        attempt=$((attempt + 1))
        if curl -s --max-time "$TIMEOUT" "$BASE_URL/health" > /dev/null 2>&1; then
            pass "Service is responding after $attempt attempt(s)"
            return 0
        fi
        info "Attempt $attempt/$MAX_RETRIES failed, retrying in ${RETRY_INTERVAL}s ..."
        sleep "$RETRY_INTERVAL"
    done
    fail "Service did not become available after $MAX_RETRIES attempts"
    return 1
}

echo "========================================"
echo " Agent Dashboard Health Check"
echo " Target: $BASE_URL"
echo "========================================"
echo ""

# Wait for service to be up
wait_for_service

echo ""
info "Running health checks..."
echo ""

# 1. /health endpoint
check_endpoint "/health (alias)" \
    "$BASE_URL/health" \
    "200" "status" "ok"

# 2. /api/health endpoint
check_endpoint "/api/health" \
    "$BASE_URL/api/health" \
    "200" "status" "ok"

# 3. /ready endpoint
check_endpoint "/ready" \
    "$BASE_URL/ready" \
    "200" "ready" "true"

# 4. /api/ready endpoint
check_endpoint "/api/ready" \
    "$BASE_URL/api/ready" \
    "200" "ready" "true"

echo ""
echo "========================================"
if [ "$FAILURES" -eq 0 ]; then
    pass "All health checks passed!"
    echo "========================================"
    exit 0
else
    fail "$FAILURES health check(s) failed!"
    echo "========================================"
    exit 1
fi
