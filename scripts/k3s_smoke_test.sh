#!/usr/bin/env bash
# k3s smoke test for EyeGila
# Usage: ./scripts/k3s_smoke_test.sh [--namespace eyegila] [--server-url http://NODE_IP:30080]
set -euo pipefail

NS="eyegila"
SERVER_URL=""
PASS=0
FAIL=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --namespace)  NS="$2"; shift 2 ;;
    --server-url) SERVER_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Detect server URL from NodePort if not given
if [[ -z "$SERVER_URL" ]]; then
  NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || echo "")
  SERVER_URL="http://${NODE_IP}:30080"
fi

green()  { echo -e "\033[32m  ✓ $*\033[0m"; }
red()    { echo -e "\033[31m  ✗ $*\033[0m"; }
yellow() { echo -e "\033[33m  ~ $*\033[0m"; }
sep()    { echo -e "\n\033[1m── $* ──\033[0m"; }

check() {
  local label="$1"; shift
  if "$@" &>/dev/null; then
    green "$label"
    ((PASS++))
  else
    red "$label"
    ((FAIL++))
  fi
}

# ── 1. Namespace ──────────────────────────────────────────────────────────────
sep "Namespace"
check "Namespace '$NS' exists" kubectl get namespace "$NS"

# ── 2. Pods ───────────────────────────────────────────────────────────────────
sep "Pod health"
EXPECTED_APPS=(timescaledb pgbouncer redis server rq-worker frontend)
for app in "${EXPECTED_APPS[@]}"; do
  check "Pod $app is Running" bash -c \
    "kubectl get pods -n $NS -l app=$app --field-selector=status.phase=Running 2>/dev/null | grep -q Running"
done

# Workers: at least one running
WORKER_RUNNING=$(kubectl get pods -n "$NS" -l app=worker --field-selector=status.phase=Running --no-headers 2>/dev/null | wc -l)
if [[ "$WORKER_RUNNING" -ge 1 ]]; then
  green "At least one worker pod Running ($WORKER_RUNNING)"
  ((PASS++))
else
  red "No worker pods Running"
  ((FAIL++))
fi

# ── 3. Health endpoint ────────────────────────────────────────────────────────
sep "API health"
HEALTH_URL="${SERVER_URL}/api/health"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" 2>/dev/null || echo "000")
if [[ "$HTTP_STATUS" == "200" ]]; then
  green "GET /health → 200"
  ((PASS++))
else
  red "GET /health → $HTTP_STATUS (expected 200)"
  ((FAIL++))
fi

# ── 4. Login ──────────────────────────────────────────────────────────────────
sep "Auth"
TOKEN=$(curl -s -X POST "${SERVER_URL}/api/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}' \
  --max-time 5 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null || echo "")

if [[ -n "$TOKEN" ]]; then
  green "POST /login → token received"
  ((PASS++))
else
  red "POST /login → no token (check admin credentials)"
  ((FAIL++))
fi

# ── 5. Protected endpoint ─────────────────────────────────────────────────────
if [[ -n "$TOKEN" ]]; then
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    -H "Authorization: Bearer $TOKEN" "${SERVER_URL}/api/intersections/" 2>/dev/null || echo "000")
  if [[ "$HTTP_STATUS" == "200" ]]; then
    green "GET /intersections/ → 200"
    ((PASS++))
  else
    red "GET /intersections/ → $HTTP_STATUS"
    ((FAIL++))
  fi

  # 401 without token
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
    "${SERVER_URL}/api/intersections/" 2>/dev/null || echo "000")
  if [[ "$HTTP_STATUS" == "403" || "$HTTP_STATUS" == "401" ]]; then
    green "GET /intersections/ without token → $HTTP_STATUS (auth enforced)"
    ((PASS++))
  else
    red "GET /intersections/ without token → $HTTP_STATUS (expected 401/403)"
    ((FAIL++))
  fi
fi

# ── 6. Worker heartbeats ──────────────────────────────────────────────────────
sep "Worker camera claiming"
if [[ -n "$TOKEN" ]]; then
  METRICS=$(curl -s --max-time 5 \
    -H "Authorization: Bearer $TOKEN" "${SERVER_URL}/api/metrics/workers" 2>/dev/null || echo "")
  CLAIMED=$(echo "$METRICS" | grep 'worker_camera_claimed' | grep -v '#' | awk '{print $2}' | grep -c '^1$' || echo "0")
  if [[ "$CLAIMED" -ge 1 ]]; then
    green "$CLAIMED camera(s) claimed by workers"
    ((PASS++))
  else
    yellow "No cameras currently claimed (workers may still be starting)"
  fi
fi

# ── 7. Frontend ───────────────────────────────────────────────────────────────
sep "Frontend"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$SERVER_URL" 2>/dev/null || echo "000")
if [[ "$HTTP_STATUS" == "200" ]]; then
  green "GET / → 200 (frontend serving)"
  ((PASS++))
else
  red "GET / → $HTTP_STATUS"
  ((FAIL++))
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────────"
TOTAL=$((PASS + FAIL))
if [[ $FAIL -eq 0 ]]; then
  echo -e "\033[32m\033[1m  All $TOTAL checks passed\033[0m"
else
  echo -e "\033[31m\033[1m  $FAIL / $TOTAL checks failed\033[0m"
fi
echo "────────────────────────────────────────────"

exit $FAIL
