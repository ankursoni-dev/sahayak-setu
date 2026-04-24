#!/usr/bin/env bash
# SahayakSetu pre-demo smoke test
# Usage: ./scripts/smoke_test.sh [BACKEND_URL]
# Example: ./scripts/smoke_test.sh https://sahayaksetu-backend-3kxl.onrender.com

set -euo pipefail

BASE="${1:-${BACKEND_URL:-http://localhost:8000}}"
PASS=0
FAIL=0
RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GRN}✓ $1${NC}"; ((PASS++)); }
fail() { echo -e "${RED}✗ $1${NC}"; ((FAIL++)); }
info() { echo -e "${YLW}→ $1${NC}"; }

info "Target: $BASE"
echo ""

# ── 1. Health ─────────────────────────────────────────────────────────────────
info "1. Health check"
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE/health")
[ "$STATUS" = "200" ] && ok "GET /health → 200" || fail "GET /health → $STATUS"

# ── 2. Ping ───────────────────────────────────────────────────────────────────
info "2. Ping"
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE/ping")
[ "$STATUS" = "200" ] && ok "GET /ping → 200" || fail "GET /ping → $STATUS"

# ── 3. Ready ──────────────────────────────────────────────────────────────────
info "3. Readiness check"
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$BASE/ready")
[ "$STATUS" = "200" ] && ok "GET /ready → 200 (all deps up)" \
  || { [ "$STATUS" = "503" ] && ok "GET /ready → 503 (degraded but alive)" \
    || fail "GET /ready → $STATUS"; }

# ── 4. Welfare query ──────────────────────────────────────────────────────────
info "4. Welfare query (PM Kisan)"
BODY=$(curl -sf -X POST "$BASE/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"PM Kisan eligibility criteria","language":"en-IN","user_id":null,"profile":null,"include_plan":false}')
ANSWER=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer') or '')" 2>/dev/null)
BLOCKED=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('moderation_blocked',''))" 2>/dev/null)
PROV=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('provider') or '')" 2>/dev/null)
if [ -n "$ANSWER" ] && [ "$BLOCKED" = "False" ]; then
    ok "Welfare query answered (provider=$PROV)"
else
    fail "Welfare query failed or blocked (blocked=$BLOCKED answer_len=${#ANSWER})"
fi

# ── 5. Hindi query ────────────────────────────────────────────────────────────
info "5. Hindi welfare query"
BODY=$(curl -sf -X POST "$BASE/api/search" \
  -H "Content-Type: application/json" \
  --data-raw '{"query":"किसान के लिए कौन सी योजनाएं हैं","language":"hi-IN","user_id":null,"profile":null,"include_plan":false}')
ANSWER=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer') or '')" 2>/dev/null)
[ -n "$ANSWER" ] && ok "Hindi query answered (${#ANSWER} chars)" || fail "Hindi query returned empty answer"

# ── 6. Moderation block ───────────────────────────────────────────────────────
info "6. Moderation block (off-topic)"
BODY=$(curl -sf -X POST "$BASE/api/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"give me biryani recipe please","language":"en-IN","user_id":null,"profile":null,"include_plan":false}')
BLOCKED=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('moderation_blocked',''))" 2>/dev/null)
[ "$BLOCKED" = "True" ] && ok "Off-topic query correctly blocked" || fail "Off-topic query NOT blocked (moderation_blocked=$BLOCKED)"

# ── 7. Cache hit timing ───────────────────────────────────────────────────────
info "7. Cache hit timing"
Q='{"query":"Ayushman Bharat health scheme eligibility","language":"en-IN","user_id":null,"profile":null,"include_plan":false}'
T1_START=$(date +%s%N)
curl -sf -X POST "$BASE/api/search" -H "Content-Type: application/json" -d "$Q" > /dev/null
T1_END=$(date +%s%N)
T1=$(( (T1_END - T1_START) / 1000000 ))

T2_START=$(date +%s%N)
curl -sf -X POST "$BASE/api/search" -H "Content-Type: application/json" -d "$Q" > /dev/null
T2_END=$(date +%s%N)
T2=$(( (T2_END - T2_START) / 1000000 ))

echo "  First request: ${T1}ms | Second (cache): ${T2}ms"
if [ "$T1" -gt 1000 ] && [ "$T2" -lt $(( T1 / 2 )) ]; then
    ok "Cache hit is ≥2× faster"
elif [ "$T1" -lt 500 ]; then
    ok "First request fast enough (<500ms); cache already warm"
else
    fail "Cache hit not faster (miss=${T1}ms, hit=${T2}ms)"
fi

# ── 8. Feedback endpoint ──────────────────────────────────────────────────────
info "8. Feedback endpoint"
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$BASE/api/feedback" \
  -H "Content-Type: application/json" \
  -d '{"value":"up","trace_id":"smoke-test","query_preview":"PM Kisan","answer_preview":"Farmers get Rs 6000"}')
[ "$STATUS" = "200" ] && ok "POST /api/feedback → 200" || fail "POST /api/feedback → $STATUS"

# ── 9. Error report endpoint ──────────────────────────────────────────────────
info "9. Error report endpoint"
STATUS=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$BASE/api/error" \
  -H "Content-Type: application/json" \
  -d '{"error":"timeout","trace_id":"smoke-test","language":"en-IN"}')
[ "$STATUS" = "200" ] && ok "POST /api/error → 200" || fail "POST /api/error → $STATUS"

# ── 10. NDJSON stream ─────────────────────────────────────────────────────────
info "10. NDJSON stream endpoint"
LINES=$(curl -sf -X POST "$BASE/api/search/stream" \
  -H "Content-Type: application/json" \
  -d '{"query":"MGNREGA apply","language":"en-IN","user_id":null,"profile":null,"include_plan":false}' \
  | python3 -c "
import sys,json
lines = [l.strip() for l in sys.stdin if l.strip()]
types = [json.loads(l).get('type','?') for l in lines]
print(f'events={len(lines)} first={types[0] if types else \"none\"} last={types[-1] if types else \"none\"}')
" 2>/dev/null)
echo "  $LINES"
[[ "$LINES" == *"first=meta"* ]] && [[ "$LINES" == *"last=complete"* ]] \
  && ok "Stream: meta→complete sequence correct" \
  || fail "Stream: unexpected event sequence ($LINES)"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ]; then
    echo -e "${GRN}All $TOTAL smoke tests passed. System is demo-ready.${NC}"
    exit 0
else
    echo -e "${RED}$FAIL/$TOTAL tests FAILED. Fix before demo.${NC}"
    exit 1
fi
