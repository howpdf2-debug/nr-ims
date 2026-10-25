#!/usr/bin/env bash
# Edge smoke test: what the BROWSER sees through nginx (cache headers, CSP, API alias path, token header).
#   bash scripts/check_edge.sh                      # reads HTTP_PORT and NRIMS_SEED_ADMIN_PASSWORD from .env
#   BASE=http://127.0.0.1:8080 PW=secret USER_EMAIL=bsb@nr-ims.local bash scripts/check_edge.sh
# Exit code 0 = all checks passed, 1 = a check failed, 2 = nothing answers at $BASE.
# Needs: curl, python3, a running stack with the dev users seeded (make seed).
#
# If the LOGIN fails, every check that needs a token is reported as SKIP (not as five more failures) and the
# script says WHY: wrong/empty credentials, a 15-minute lockout (5 wrong passwords), or nothing listening.
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
skip() { printf '  \033[33mSKIP\033[0m %s\n' "$1"; }
hdrs() { curl -s -m 10 -D- -o /dev/null "$@" | tr -d '\r'; }
code() { curl -s -m 10 -o /dev/null -w '%{http_code}' "$@"; }

# expect_header "description" "<egrep over the response headers>" curl-args...
expect_header() {
  local desc=$1 re=$2; shift 2
  if hdrs "$@" | grep -qiE "$re"; then ok "$desc"; else bad "$desc"; fi
}
# expect_code "description" <status> curl-args...
expect_code() {
  local desc=$1 want=$2; shift 2
  local got; got=$(code "$@")
  if [ "$got" = "$want" ]; then ok "$desc"; else bad "$desc (HTTP $got, expected $want)"; fi
}
# json_field <name>  (reads JSON on stdin; prints "" when it is not JSON or has no such field)
json_field() {
  python3 -c 'import sys, json
try:
    v = json.load(sys.stdin).get(sys.argv[1], "")
    print(v if isinstance(v, str) else "")
except Exception:
    print("")' "$1"
}
# login <api-prefix incl. version, e.g. /nrims-api/v1 or /api/v1>  ->  sets TOKEN, LAST_CODE, LAST_BODY
login() {
  local out
  out=$(curl -s -m 10 -w '\n%{http_code}' --data-urlencode "username=$USER_EMAIL" --data-urlencode "password=$PW" \
        "$BASE$1/auth/login")
  LAST_CODE=${out##*$'\n'}
  LAST_BODY=${out%$'\n'*}
  TOKEN=$(printf '%s' "$LAST_BODY" | json_field access_token)
}
diagnose_login() {
  local detail; detail=$(printf '%s' "$LAST_BODY" | json_field detail)
  echo "       Login as $USER_EMAIL answered HTTP $LAST_CODE: ${detail:-${LAST_BODY:0:120}}"
  case "$LAST_CODE" in
    429) echo "       -> LOCKED OUT. 5 wrong passwords within 15 minutes lock the account, and then even the RIGHT"
         echo "          password is refused. Clear it now with:   make unlock-login     (or wait 15 minutes)" ;;
    401) echo "       -> nginx and the backend are fine, but they do not accept these credentials. Usually:"
         echo "          (a) the database has NO users: a recycled Cloud Shell VM starts with an empty database -> make seed"
         echo "          (b) the password in .env is not the one the users were created with -> make creds, compare"
         echo "          (c) $USER_EMAIL is not a seeded user -> USER_EMAIL=bsb@nr-ims.local bash scripts/check_edge.sh"
         if command -v docker >/dev/null 2>&1; then
           local n; n=$(timeout 15 docker compose exec -T db psql -U nrims -d nrims -Atc 'select count(*) from users' 2>/dev/null | tr -d '[:space:]')
           [ -n "$n" ] && echo "          users in the database right now: $n  $([ "$n" = 0 ] && echo '<- EMPTY: run make seed')"
         fi ;;
    000|"") echo "       -> no answer from $BASE/nrims-api: is the backend up? docker compose ps; docker compose logs backend --tail=40" ;;
    502|503|504) echo "       -> nginx is up but the backend is not answering (still starting?): docker compose logs backend --tail=40" ;;
    *)   echo "       -> unexpected answer: docker compose logs backend --tail=40" ;;
  esac
}

echo "Edge check against $BASE"
[ "$(curl -s -m 5 "$BASE/nginx-health")" = "ok" ] || { echo "nginx does not answer at $BASE (is the stack up? HTTP_PORT?)"; exit 2; }

CSP_RE="^content-security-policy:.*connect-src 'self' https://\*\.cloudshell\.dev"

echo "1. App shell is never cached"
for p in / /index.html /alarms; do
  expect_header "$p sends Cache-Control: no-store" '^cache-control:.*no-store' "$BASE$p"
done

echo "2. Content-Security-Policy and security headers"
expect_header "connect-src allows 'self' and https://*.cloudshell.dev" "$CSP_RE" "$BASE/"
expect_header "CSP is also present on the API path" '^content-security-policy:' "$BASE/nrims-api/v1/auth/login"
if [ "$(hdrs "$BASE/nrims-api/v1/auth/login" | grep -ci '^referrer-policy')" = 1 ]; then
  ok "security headers are not duplicated (one Referrer-Policy)"; else bad "Referrer-Policy is duplicated on the API path"; fi

echo "3. Hashed assets"
ASSET="$(curl -s -m 10 "$BASE/index.html" | grep -o '/assets/[^"]*\.js' | head -1)"
if [ -n "$ASSET" ]; then
  ok "index.html references a hashed JS file ($ASSET)"
  expect_header "that asset is immutable-cached" '^cache-control:.*immutable' "$BASE$ASSET"
else
  bad "index.html does not reference any /assets/*.js file"
fi
expect_code "a chunk that no longer exists is a real 404 (not the HTML shell)" 404 "$BASE/assets/Dashboard-DOESNOTEXIST.js"

echo "4. Login and API through /nrims-api with X-NRIMS-Auth (no Authorization header)"
if [ -z "$PW" ]; then
  bad "no password: set PW=... or NRIMS_SEED_ADMIN_PASSWORD in .env (make creds)"
  TOKEN=""
else
  login /nrims-api/v1
  if [ -n "$TOKEN" ]; then ok "login via /nrims-api returns a token"; else bad "login via /nrims-api returns a token"; diagnose_login; fi
fi
if [ -n "$TOKEN" ]; then
  expect_code "X-NRIMS-Auth: <token>          -> 200" 200 -H "X-NRIMS-Auth: $TOKEN" "$BASE/nrims-api/v1/dashboard/summary"
  expect_code "X-NRIMS-Auth: Bearer <token>   -> 200" 200 -H "X-NRIMS-Auth: Bearer $TOKEN" "$BASE/nrims-api/v1/dashboard/summary"
  expect_header "X-Total-Count header survives the proxy" '^x-total-count: [0-9]+' \
    -H "X-NRIMS-Auth: $TOKEN" "$BASE/nrims-api/v1/devices/?limit=1"
else
  skip "X-NRIMS-Auth: <token>          -> 200            (needs a token)"
  skip "X-NRIMS-Auth: Bearer <token>   -> 200            (needs a token)"
  skip "X-Total-Count header survives the proxy          (needs a token)"
fi
expect_code "no token                       -> 401" 401 "$BASE/nrims-api/v1/dashboard/summary"
expect_code "garbage token                  -> 401" 401 -H "X-NRIMS-Auth: nope" "$BASE/nrims-api/v1/dashboard/summary"
# A made-up user name: the probe must never count against (and lock) a real account.
R=$(curl -s -m 10 -w '\n%{http_code}' --data-urlencode "username=edge-check-$RANDOM@nr-ims.local" \
      --data-urlencode "password=definitely-wrong" "$BASE/nrims-api/v1/auth/login")
if [ "${R##*$'\n'}" = 401 ] && [ -n "$(printf '%s' "${R%$'\n'*}" | json_field detail)" ]; then
  ok "wrong password -> 401 with a JSON message the login form can show"
else bad "wrong password -> 401 with a JSON message the login form can show (HTTP ${R##*$'\n'})"; fi

echo "5. Backward compatibility (curl, scripts, Swagger): the legacy /api/v1 path"
if [ -z "$PW" ]; then
  skip "legacy login and Authorization: Bearer             (needs a password)"
else
  login /api/v1
  if [ -n "$TOKEN" ]; then
    ok "login via the legacy /api/v1 path returns a token"
    expect_code "/api/v1 + Authorization: Bearer -> 200" 200 -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/dashboard/summary"
    expect_code "/api/v1 + X-NRIMS-Auth         -> 200" 200 -H "X-NRIMS-Auth: $TOKEN" "$BASE/api/v1/dashboard/summary"
  else
    bad "login via the legacy /api/v1 path returns a token"; diagnose_login
    skip "/api/v1 + Authorization: Bearer -> 200           (needs a token)"
  fi
fi

echo
if [ "$FAILS" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "FAILED CHECKS: $FAILS"; exit 1; fi
