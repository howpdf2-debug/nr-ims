#!/usr/bin/env bash
# NR-IMS audit (READ-ONLY): kya chal raha hai, kya update hai, har phase kis LEVEL tak pahuncha.
#   bash scripts/audit_state.sh            # poora (docker + API + lint/mypy/pytest)
#   bash scripts/audit_state.sh --quick    # lint/mypy/pytest skip
#   bash scripts/audit_state.sh --static   # docker/API skip (sirf git + code)
# Levels: 1=CODE 2=+DB(migration lagi) 3=+RUNNING(logs/API) 4=+DATA(rows aa rahi hain)
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "repo ke andar chalao: cd ~/nr-ims"; exit 2; }
MODE="${1:-all}"; B=backend; GAPS=(); declare -A V   # V[phase.field] = Y | N | - (lagu nahi) | ? (jaanch nahi hui)
hdr(){ printf '\n== %s\n' "$1"; }
gap(){ GAPS+=("$1"); }
ex(){ [[ -e "$1" ]]; }
allex(){ local f; for f in "$@"; do ex "$f" || return 1; done; }
yn(){ if "$@" >/dev/null 2>&1; then echo Y; else echo N; fi; }

# ---------------- 1. GIT ----------------
hdr "1. GIT: local vs GitHub"
git fetch -q origin 2>/dev/null && FETCH=ok || FETCH=FAIL
CUR=$(git branch --show-current); UP=$(git rev-parse --abbrev-ref '@{u}' 2>/dev/null || echo "-")
echo "branch=${CUR:-DETACHED} upstream=$UP HEAD=$(git rev-parse --short HEAD) fetch=$FETCH"
[[ $FETCH == FAIL ]] && gap "GitHub se fetch fail (auth/network): 'git ls-remote origin' chala ke dekho"
UNC=$(git status --porcelain | wc -l); UNP=$(git log --branches --not --remotes --oneline 2>/dev/null | wc -l)
echo "uncommitted files=$UNC | commits jo kisi bhi branch par GitHub par nahi=$UNP"
git log -1 --format='origin/main aakhri commit: %ad  %s' --date=short origin/main 2>/dev/null
OM=$(git log -1 --format=%ct origin/main 2>/dev/null); [[ -n "$OM" ]] && echo "origin/main ki umar: $(( ( $(date +%s) - OM ) / 86400 )) din"
[[ $UNC -gt 0 ]] && gap "$UNC uncommitted files: bash scripts/git_safe_push.sh --dry-run"
[[ $UNP -gt 0 ]] && gap "$UNP commits GitHub par nahi: bash scripts/git_safe_push.sh"
gh_where(){ # file -> main | branch:<name> | NO
  git cat-file -e "origin/main:$1" 2>/dev/null && { echo main; return; }
  local rb; for rb in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin 2>/dev/null | grep -v 'origin/HEAD'); do
    git cat-file -e "$rb:$1" 2>/dev/null && { echo "branch:${rb#origin/}"; return; }; done; echo NO; }
declare -A GH
GH[P1]=$(gh_where $B/app/api/v1/devices.py); GH[P2]=$(gh_where $B/app/services/alarms.py)
GH[P2f]=$(gh_where frontend/src/lib/alarmSound.ts); GH[P3a1]=$(gh_where $B/app/models/monitoring.py); GH[P3a2]=$(gh_where $B/app/services/poller.py)

# ---------------- 2. CODE ----------------
hdr "2. CODE: files, STUB, migrations, invariants"
V[P1.code]=$(yn allex $B/app/models/{device,station,alarm,interface,user}.py $B/app/api/v1/{devices,alarms,dashboard,stations,auth}.py $B/app/security/rbac.py)
isstub(){ ex "$1" && grep -qi "STUB" "$1"; }
P2OK=Y; for f in $B/app/services/alarms.py $B/app/services/maintenance.py; do
  if ! ex $f; then P2OK=N; echo "  MISSING $f"; elif isstub $f; then P2OK=N; echo "  STUB    $f  (asli Account-1 file nahi)"; else echo "  real    $f"; fi; done
ls $B/migrations/versions/c4d2a8f61b30* >/dev/null 2>&1 || { P2OK=N; echo "  MISSING migration c4d2a8f61b30 (Phase 2)"; }
V[P2.code]=$P2OK; [[ $P2OK == N ]] && gap "Phase 2 asli nahi (stub/missing): Account 1 se alarms.py, maintenance.py, models/alarm.py, migration c4d2a8f61b30 lo"
V[P2f.code]=$(yn allex frontend/src/lib/{alarms,alarmSound,auth}.ts frontend/src/components/AlarmStatusBadge.tsx)
V[P3a1.code]=$(yn allex $B/app/models/monitoring.py $B/app/services/snmp_v3.py $B/app/monitoring/{profiles.py,profiles.toml,rates.py,security.py} $B/migrations/versions/b7e19c3a5d20*)
if allex $B/app/services/poller.py $B/app/api/v1/monitoring.py && grep -q poll_devices $B/arq_worker.py \
   && sed -n '/from app.api.v1 import/,/)/p;/^_V1/p' $B/app/main.py | grep -q monitoring; then V[P3a2.code]=Y; else V[P3a2.code]=N; fi
grep -q "NET_RAW" docker-compose.override.yml 2>/dev/null && echo "  worker NET_RAW: ok" || { echo "  worker NET_RAW: NAHI"; gap "docker-compose.override.yml worker me cap_add: [NET_RAW]"; }
sed -n '/from app.api.v1 import/,/)/p;/^_V1/p' $B/app/main.py | grep -q monitoring || { echo "  main.py: monitoring router register NAHI"; ex $B/app/api/v1/monitoring.py && gap "main.py me monitoring router register karo (nahi to /devices/{id}/metrics 404)"; }
grep -rq "device_status_history" $B/migrations $B/app 2>/dev/null && V[P3a3.code]=Y || V[P3a3.code]=N
for s in $(grep -ho "scripts/[A-Za-z0-9_./-]*\.\(sh\|py\)" Makefile docker-compose*.yml 2>/dev/null | sort -u); do ex "$s" || { echo "  Makefile/compose ka script MISSING: $s"; gap "missing script: $s"; }; done
grep -q "/nrims-api/v1" frontend/src/lib/api.ts 2>/dev/null && echo "  invariant /nrims-api/v1: ok" || gap "api.ts me /nrims-api/v1 nahi"
for f in frontend/src/lib/api.ts frontend/deploy/nginx.conf $B/app/deps.py; do grep -q "X-NRIMS-Auth" "$f" 2>/dev/null || { echo "  X-NRIMS-Auth missing: $f"; gap "X-NRIMS-Auth $f me nahi"; }; done
HEADS=$(python3 - <<'EOF'
import re,glob
r,d={}, set()
for f in glob.glob("backend/migrations/versions/*.py"):
    t=open(f).read(); m=re.search(r"^revision[^=]*=\s*['\"](\w+)",t,re.M); p=re.search(r"^down_revision[^=]*=\s*['\"](\w+)['\"]",t,re.M)
    if m: r[m.group(1)]=p.group(1) if p else None
    if p: d.add(p.group(1))
print(",".join(sorted(x for x in r if x not in d)))
EOF
)
echo "  alembic heads: $HEADS"; [[ "$HEADS" == *,* ]] && gap "alembic me ek se zyada heads: $HEADS"
if ls $B/migrations/versions/c4d2a8f61b30* >/dev/null 2>&1; then grep -q "down_revision.*c4d2a8f61b30" $B/migrations/versions/b7e19c3a5d20* 2>/dev/null || { echo "  chain: b7e19c3a5d20 abhi c4d2a8f61b30 se NAHI judta"; gap "migration chain: b7e19c3a5d20.down_revision = c4d2a8f61b30 karo (dev DB: make reset)"; }; fi

# ---------------- 3. LIVE ----------------
hdr "3. LIVE: containers, DB, worker, API"
LIVE=0; if [[ $MODE != --static ]] && command -v docker >/dev/null 2>&1 && docker compose ps >/dev/null 2>&1; then LIVE=1; fi
if [[ $LIVE -eq 0 ]]; then echo "  (docker/stack nahi mila ya --static: live checks skip)"; else
  while IFS='|' read -r s st h; do printf '  %-9s %-8s %s\n' "$s" "$st" "${h:-no-healthcheck}"
    [[ "$st" != running ]] && gap "container $s nahi chal raha ($st): docker compose logs $s"
    [[ "$h" == unhealthy && $s == worker ]] && gap "worker 'unhealthy' = image ka HTTP healthcheck (worker me HTTP nahi). compose worker me healthcheck: [CMD, arq, --check, arq_worker.WorkerSettings]"
    [[ "$h" == unhealthy && $s != worker ]] && gap "$s unhealthy: docker compose logs $s"
  done < <(docker compose ps --format '{{.Service}}|{{.State}}|{{.Health}}' 2>/dev/null)
  Q(){ docker compose exec -T db psql -U nrims -d nrims -Atc "$1" 2>/dev/null | tr -d '\r'; }
  DBREV=$(Q "select version_num from alembic_version" | head -1); echo "  DB alembic revision: ${DBREV:-?}"
  APPLIED=$(python3 - "$DBREV" <<'EOF'
import re,glob,sys
p={}
for f in glob.glob("backend/migrations/versions/*.py"):
    t=open(f).read(); m=re.search(r"^revision[^=]*=\s*['\"](\w+)",t,re.M); d=re.search(r"^down_revision[^=]*=\s*['\"](\w+)['\"]",t,re.M)
    if m: p[m.group(1)]=d.group(1) if d else None
x=sys.argv[1]; out=[]
while x and x in p: out.append(x); x=p[x]
print(" ".join(out))
EOF
)
  [[ -n "$DBREV" && "$HEADS" != *"$DBREV"* ]] && gap "DB revision $DBREV head ($HEADS) se peeche: docker compose exec backend alembic upgrade head"
  tbl(){ [[ "$(Q "select to_regclass('public.$1') is not null")" == t ]]; }
  cnt(){ Q "select count(*) from $1" | head -1; }
  V[P1.db]=Y; for t in devices stations interfaces alarms users; do tbl $t || V[P1.db]=N; done
  [[ "$(cnt devices)" -gt 0 ]] 2>/dev/null && V[P1.data]=Y || V[P1.data]=N
  [[ "$(cnt alarms)" -gt 0 ]] 2>/dev/null && V[P2.data]=Y || V[P2.data]=N
  [[ " $APPLIED " == *" c4d2a8f61b30 "* ]] && V[P2.db]=Y || V[P2.db]=N
  V[P3a1.db]=Y; for t in snmp_credential_profiles device_poll_state device_metrics interface_metrics; do tbl $t || V[P3a1.db]=N; done
  [[ " $APPLIED " == *" b7e19c3a5d20 "* ]] || V[P3a1.db]=N
  V[P3a2.db]=$([[ ${V[P3a1.db]} == Y ]] && echo Y || echo N)
  [[ "$(cnt snmp_credential_profiles)" -gt 0 ]] 2>/dev/null && V[P3a1.data]=Y || { V[P3a1.data]=N; gap "SNMP credential profile nahi: sirf ICMP polling, device_metrics nahi bante"; }
  [[ "$(cnt device_metrics)" -gt 0 ]] 2>/dev/null && V[P3a2.data]=Y || V[P3a2.data]=N
  echo "  rows: devices=$(cnt devices) alarms=$(cnt alarms) poll_state=$(cnt device_poll_state) poll_enabled=$(Q 'select count(*) from device_poll_state where poll_enabled') device_metrics=$(cnt device_metrics) interface_metrics=$(cnt interface_metrics)"
  tbl device_status_history && V[P3a3.db]=Y || V[P3a3.db]=N
  ALL=$(docker compose logs --tail 3000 worker 2>&1); LOGS=$(docker compose logs --since 5m worker 2>&1)
  echo "  --- worker startup self-checks:"
  for c in "database connectivity OK" "table device_poll_state present" "SNMP credential key OK" "ICMP self-check OK"; do grep -q "$c" <<<"$ALL" && echo "    ok   $c" || echo "    NAHI $c"; done
  grep -q "ICMP self-check FAILED" <<<"$ALL" && gap "ICMP self-check FAILED: worker me NET_RAW nahi"
  grep -q "SNMP vendor profiles loaded" <<<"$ALL" && V[P3a1.run]=Y || V[P3a1.run]=N
  echo "  --- worker polling (pichhle 5 min):"
  CYC=$(grep "poll cycle:" <<<"$LOGS" | tail -1); if [[ -n "$CYC" ]]; then echo "    last: ${CYC#*poll cycle: }"
    sum=0; for k in up down inconclusive skipped_budget errors; do v=$(grep -o " $k=[0-9]*" <<<"$CYC" | head -1 | cut -d= -f2); sum=$((sum+${v:-0})); done
    [[ "$sum" == "$(grep -o 'devices=[0-9]*' <<<"$CYC" | cut -d= -f2)" ]] || gap "poll cycle counters ka jod devices se nahi milta"
    grep -qE " errors=[1-9]" <<<"$CYC" && gap "poll cycle me errors>0: docker compose logs worker | grep -i 'could not record'"
  else echo "    pichhle 5 min me koi 'poll cycle' nahi (polling band ya worker down)"; fi
  STUBLOG=0; grep -q "is a STUB" <<<"$ALL" && { STUBLOG=1; echo "    WARN Phase-2 STUB chal raha hai (status/alarm persist nahi hote)"; }
  grep -q "Phase-2 adapter .* failed" <<<"$ALL" && gap "Phase-2 adapter fail: poller.py ke PHASE-2 ADAPTER block ki signatures asli alarms.py/maintenance.py se milao"
  grep -q "no SNMP credential profiles" <<<"$LOGS" && echo "    note ICMP-only mode"
  PORT=$(docker compose port frontend 8080 2>/dev/null | sed 's/.*://'); PORT=${PORT:-8080}; BASE="http://127.0.0.1:$PORT"
  PW=${NRIMS_ADMIN_PASSWORD:-$(grep -s '^NRIMS_SEED_ADMIN_PASSWORD=' .env | cut -d= -f2)}
  c(){ curl -s -m 10 -o /dev/null -w '%{http_code}' "$@"; }
  FE=$(c "$BASE/"); echo "  --- API ($BASE): frontend / -> $FE"; [[ $FE == 200 ]] && V[P2f.run]=Y || V[P2f.run]=N
  if [[ -z "$PW" ]]; then echo "    login skip: .env me NRIMS_SEED_ADMIN_PASSWORD nahi (ya NRIMS_ADMIN_PASSWORD=... set karo)"
  else TOKEN=$(curl -s -m 10 --data-urlencode "username=irca@nr-ims.local" --data-urlencode "password=$PW" "$BASE/nrims-api/v1/auth/login" | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
    if [[ -z "$TOKEN" ]]; then echo "    login FAIL"; gap "login fail ($BASE/nrims-api/v1/auth/login): password 'make creds' se milao"; V[P1.run]=N
    else echo "    login ok"; a(){ c -H "X-NRIMS-Auth: $TOKEN" "$BASE/nrims-api/v1$1"; }
      S=$(a /dashboard/summary); AL=$(a "/alarms/?limit=1"); NH=$(a /dashboard/network-health)
      echo "    /dashboard/summary=$S /alarms/=$AL /dashboard/network-health=$NH"
      [[ $S == 200 && $AL == 200 ]] && V[P1.run]=Y || V[P1.run]=N
      [[ $AL == 200 && $STUBLOG -eq 0 ]] && V[P2.run]=Y || V[P2.run]=N
      [[ $NH == 200 && -n "$CYC" ]] && V[P3a2.run]=Y || V[P3a2.run]=N
      [[ $NH == 404 ]] && gap "network-health 404: main.py me monitoring router register karo + backend rebuild"
      [[ $(c "$BASE/nrims-api/v1/dashboard/summary") =~ ^40[13]$ ]] || gap "bina token ke API khuli hai ya galat code"
    fi; fi
fi

# ---------------- 4. QUALITY ----------------
hdr "4. QUALITY"
python3 scripts/check_forbidden.py >/dev/null 2>&1 && echo "  guards: ok" || { echo "  guards: FAIL"; gap "scripts/check_forbidden.py fail"; }
if [[ $MODE == --quick || $MODE == --static ]]; then echo "  lint/mypy/pytest skip ($MODE)"; else
  T=""; for d in .venv/bin venv/bin; do [[ -x $d/ruff ]] && T=$(pwd)/$d; done
  if [[ -z "$T" ]]; then echo "  venv nahi mila: make install"; else
    r(){ local n=$1; shift; if (cd $B && "$@") >/tmp/audit_$n.log 2>&1; then echo "  $n: ok"; else echo "  $n: FAIL (/tmp/audit_$n.log)"; tail -3 /tmp/audit_$n.log | sed 's/^/      /'; gap "$n fail: $(grep -m1 -E 'ERROR|FAILED|error:|Found [0-9]+ error' /tmp/audit_$n.log | cut -c1-110) [/tmp/audit_$n.log]"; fi; }
    r ruff $T/ruff check .; r mypy $T/mypy app arq_worker.py; r pytest $T/pytest -q -p no:cacheprovider -o addopts="" --ignore=tests/integration; fi; fi

# ---------------- 5. LEVEL MATRIX ----------------
hdr "5. PHASE LEVEL (CODE > DB > RUNNING > DATA)"
printf '  %-34s %-5s %-4s %-4s %-5s %-16s %s\n' PHASE CODE DB RUN DATA GITHUB LEVEL
lvl(){ local p=$1 f x st="0 ADHURA (code poora nahi)"; local -A nm=([code]="1 CODE ONLY" [db]="2 CODE+DB" [run]="3 RUNNING" [data]="4 DATA FLOWING")
  for f in code db run data; do x=${V[$p.$f]:-?}; case $x in Y) st=${nm[$f]};; -) ;; '?') [[ $st != 0* ]] && st="$st (aage ki jaanch nahi hui)"; break;; *) break;; esac; done; echo "$st"; }
row(){ local p=$1 name=$2 f; printf '  %-34s' "$name"; for f in code db run data; do printf ' %-4s' "${V[$p.$f]:-?}"; done; printf ' %-16s %s\n' "${GH[$p]:--}" "$(lvl $p)"; }
V[P2f.db]=-; V[P2f.data]=-; V[P3a3.run]=${V[P3a3.run]:-?}
row P1 "Phase 1  core API/UI"; row P2 "Phase 2  alarm lifecycle/maint."; row P2f "Phase 2f UI (alarms, auth edge)"
row P3a1 "Phase 3a-1 monitoring models/SNMP"; row P3a2 "Phase 3a-2 polling engine+API"; row P3a3 "Phase 3a-3 history/retention (NEXT)"
echo "  (? = jaanch nahi hui/--static ; - = lagu nahi ; GITHUB: main | branch:<naam> | NO)"

hdr "6. GAPS / NEXT ACTION ($(( ${#GAPS[@]} )))"
if [[ ${#GAPS[@]} -eq 0 ]]; then echo "  koi gap nahi"; else n=1; for g in "${GAPS[@]}"; do echo "  $n. $g"; n=$((n+1)); done; fi
exit 0
