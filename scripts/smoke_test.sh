#!/usr/bin/env bash
# Production smoke test for Rhodesli
# Usage: bash scripts/smoke_test.sh [BASE_URL]
# Example: bash scripts/smoke_test.sh https://rhodesli.nolanandrewfox.com

set -euo pipefail

BASE_URL="${1:-https://rhodesli.nolanandrewfox.com}"
# Known photo ID from photo_index.json (Image 001_compress.jpg)
TEST_PHOTO_ID="a3d2695fe0804844"

PASS=0
FAIL=0
RESULTS=""

check() {
    local name="$1"
    local status="$2"
    if [ "$status" = "PASS" ]; then
        PASS=$((PASS + 1))
        RESULTS="${RESULTS}\n  PASS  ${name}"
    else
        FAIL=$((FAIL + 1))
        RESULTS="${RESULTS}\n  FAIL  ${name}"
    fi
}

echo "Smoke testing: ${BASE_URL}"
echo "========================================="

# 1. Homepage loads
echo -n "1. Homepage... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/")
HTTP_CODE=$(echo "$BODY" | tail -1)
HTML=$(echo "$BODY" | sed '$d')
if [ "$HTTP_CODE" = "200" ] && echo "$HTML" | grep -qi "rhodesli"; then
    echo "OK (${HTTP_CODE})"
    check "Homepage loads" "PASS"
else
    echo "FAIL (${HTTP_CODE})"
    check "Homepage loads" "FAIL"
fi

# 2. Health check with ML status
echo -n "2. Health check... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/health")
HTTP_CODE=$(echo "$BODY" | tail -1)
HTML=$(echo "$BODY" | sed '$d')
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK (${HTTP_CODE})"
    check "Health endpoint" "PASS"
    # Print ML status if present
    ML_STATUS=$(echo "$HTML" | grep -oE '"ml_pipeline"\s*:\s*"[^"]*"' | head -1 || true)
    PROCESSING=$(echo "$HTML" | grep -oE '"processing_enabled"\s*:\s*[a-z]*' | head -1 || true)
    if [ -n "$ML_STATUS" ]; then
        echo "   ML: ${ML_STATUS}"
    fi
    if [ -n "$PROCESSING" ]; then
        echo "   ${PROCESSING}"
    fi
else
    echo "FAIL (${HTTP_CODE})"
    check "Health endpoint" "FAIL"
fi

# 3. Photo page renders with face overlays
echo -n "3. Photo page... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/photo/${TEST_PHOTO_ID}")
HTTP_CODE=$(echo "$BODY" | tail -1)
HTML=$(echo "$BODY" | sed '$d')
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK (${HTTP_CODE})"
    check "Photo page loads" "PASS"
    OVERLAY_COUNT=$(echo "$HTML" | grep -c "face-overlay" || true)
    echo "   Face overlays found: ${OVERLAY_COUNT}"
    if [ "$OVERLAY_COUNT" -gt 0 ]; then
        check "Face overlays render" "PASS"
    else
        check "Face overlays render" "FAIL"
    fi
else
    echo "FAIL (${HTTP_CODE})"
    check "Photo page loads" "FAIL"
    check "Face overlays render" "FAIL"
fi

# 4. Compare page loads
echo -n "4. Compare page... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/compare")
HTTP_CODE=$(echo "$BODY" | tail -1)
HTML=$(echo "$BODY" | sed '$d')
if [ "$HTTP_CODE" = "200" ] && echo "$HTML" | grep -qi "upload\|compare\|drop"; then
    echo "OK (${HTTP_CODE})"
    check "Compare page" "PASS"
else
    echo "FAIL (${HTTP_CODE})"
    check "Compare page" "FAIL"
fi

# 5. Estimate page loads
echo -n "5. Estimate page... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/estimate")
HTTP_CODE=$(echo "$BODY" | tail -1)
HTML=$(echo "$BODY" | sed '$d')
if [ "$HTTP_CODE" = "200" ] && echo "$HTML" | grep -qi "upload\|estimate\|drop"; then
    echo "OK (${HTTP_CODE})"
    check "Estimate page" "PASS"
else
    echo "FAIL (${HTTP_CODE})"
    check "Estimate page" "FAIL"
fi

# 6. Admin auth gate (should NOT show admin content to unauthenticated users)
echo -n "6. Admin auth gate... "
# Follow redirects, check we don't get admin panel content
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/admin")
HTTP_CODE=$(echo "$BODY" | tail -1)
HTML=$(echo "$BODY" | sed '$d')
# We should either get a login page/redirect or a 401/403
# The key check: admin content should NOT be exposed
if echo "$HTML" | grep -qi "admin dashboard\|admin panel\|manage identities"; then
    echo "FAIL (admin content exposed without auth!)"
    check "Admin auth gate" "FAIL"
else
    echo "OK (admin content not exposed, HTTP ${HTTP_CODE})"
    check "Admin auth gate" "PASS"
fi

# 7. People page loads
echo -n "7. People page... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/people")
HTTP_CODE=$(echo "$BODY" | tail -1)
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK (${HTTP_CODE})"
    check "People page" "PASS"
else
    echo "FAIL (${HTTP_CODE})"
    check "People page" "FAIL"
fi

# 8. Photos page loads
echo -n "8. Photos page... "
BODY=$(curl -sL -o - -w "\n%{http_code}" "${BASE_URL}/photos")
HTTP_CODE=$(echo "$BODY" | tail -1)
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK (${HTTP_CODE})"
    check "Photos page" "PASS"
else
    echo "FAIL (${HTTP_CODE})"
    check "Photos page" "FAIL"
fi

# Summary
echo ""
echo "========================================="
echo "RESULTS: ${PASS} passed, ${FAIL} failed"
echo "========================================="
echo -e "$RESULTS"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "Some tests FAILED!"
    exit 1
else
    echo "All tests PASSED!"
    exit 0
fi
