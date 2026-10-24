#!/usr/bin/env bash
# Edge smoke test: what the BROWSER sees through nginx (cache headers, CSP, API alias path, token header).
#   bash scripts/check_edge.sh                      # reads HTTP_PORT and NRIMS_SEED_ADMIN_PASSWORD from .env
#   BASE=http://127.0.0.1:8080 PW=secret bash scripts/check_edge.sh
# Exit code 0 = all checks passed. Needs: curl, python3, a running stack with the dev users seeded (make seed).
set -u
cd "$(dirname "$0")/.."
envval() { [ -f .env ] && grep -E "^$1=" .env | tail -1 | cut -d= -f2- || true; }
PORT="${HTTP_PORT:-$(envval HTTP_PORT)}"; PORT="${PORT:-80}"
BASE="${BASE:-http://127.0.0.1:${PORT}}"
PW="${PW:-$(envval NRIMS_SEED_ADMIN_PASSWORD)}"
USER_EMAIL="${USER_EMAIL:-irca@nr-ims.local}"
FAILS=0
ok()   { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILS=$((FAILS + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }
hdrs() { curl -s -m 10 -D- -o /dev/null "$@" | tr -d '\r'; }
code() { curl -s -m 10 -o /dev/null -w '%{http_code}' "$@"; }

echo "Edge check against $BASE"
[ "$(curl -s -m 5 "$BASE/nginx-health")" = "ok" ] || { echo "nginx does not answer at $BASE (is the stack up? HTTP_PORT?)"; exit 2; }

echo "1. App shell is never cached"
for p in / /index.html /alarms; do
  check "$p sends Cache-Control: no-store" "hdrs $BASE$p | grep -qi '^cache-control:.*no-store'"
done
echo "2. Content-Security-Policy"
check "connect-src allows 'self' and https://*.cloudshell.dev" \
  "hdrs $BASE/ | grep -i '^content-security-policy' | grep -q \"connect-src 'self' https://\\*\\.cloudshell\\.dev\""
check "CSP is also present on the API path" "hdrs $BASE/nrims-api/v1/auth/login | grep -qi '^content-security-policy'"
check "security headers are not duplicated (one Referrer-Policy)" "[ \"\$(hdrs $BASE/nrims-api/v1/auth/login | grep -ci '^referrer-policy')\" = 1 ]"
echo "3. Hashed assets"
ASSET="$(curl -s -m 10 "$BASE/index.html" | grep -o '/assets/[^"]*\.js' | head -1)"
check "index.html references a hashed JS file ($ASSET)" "[ -n '$ASSET' ]"
check "that asset is immutable-cached" "hdrs $BASE$ASSET | grep -qi '^cache-control:.*immutable'"
check "a chunk that no longer exists is a real 404 (not the HTML shell)" "[ \"\$(code $BASE/assets/Dashboard-DOESNOTEXIST.js)\" = 404 ]"
echo "4. API through /nrims-api with X-NRIMS-Auth (no Authorization header)"
[ -n "$PW" ] || { bad "no password: set PW=... or NRIMS_SEED_ADMIN_PASSWORD in .env"; echo "FAILED: $FAILS"; exit 1; }
TOKEN="$(curl -s -m 10 -d "username=$USER_EMAIL&password=$PW" "$BASE/nrims-api/v1/auth/login" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)"
check "login via /nrims-api returns a token" "[ -n '$TOKEN' ]"
check "X-NRIMS-Auth: <token>          -> 200" "[ \"\$(code -H 'X-NRIMS-Auth: $TOKEN' $BASE/nrims-api/v1/dashboard/summary)\" = 200 ]"
check "X-NRIMS-Auth: Bearer <token>   -> 200" "[ \"\$(code -H 'X-NRIMS-Auth: Bearer $TOKEN' $BASE/nrims-api/v1/dashboard/summary)\" = 200 ]"
check "no token                       -> 401" "[ \"\$(code $BASE/nrims-api/v1/dashboard/summary)\" = 401 ]"
check "garbage token                  -> 401" "[ \"\$(code -H 'X-NRIMS-Auth: nope' $BASE/nrims-api/v1/dashboard/summary)\" = 401 ]"
check "X-Total-Count header survives the proxy" "hdrs -H 'X-NRIMS-Auth: $TOKEN' '$BASE/nrims-api/v1/devices/?limit=1' | grep -qi '^x-total-count'"
check "wrong password -> 401 with a JSON message the login form can show" \
  "curl -s -m 10 -d 'username=$USER_EMAIL&password=definitely-wrong' $BASE/nrims-api/v1/auth/login | grep -q '\"detail\"'"
echo "5. Backward compatibility (curl, scripts, Swagger)"
check "/api/v1 + Authorization: Bearer still works" "[ \"\$(code -H 'Authorization: Bearer $TOKEN' $BASE/api/v1/dashboard/summary)\" = 200 ]"

echo
if [ "$FAILS" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "FAILED CHECKS: $FAILS"; exit 1; fi
