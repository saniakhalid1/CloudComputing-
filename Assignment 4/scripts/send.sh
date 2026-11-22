#!/bin/bash
# Sends POST /api/emi requests through the Ingress and shows which pod (and app version) answered.
# Usage: ./scripts/send.sh <count> [delay_seconds]
#   ./scripts/send.sh 30          -> 30 requests, then the number of requests per pod
#   ./scripts/send.sh 600 0.2     -> about 2-3 minutes of requests (rolling-update test)
# Each line: time, request number, HTTP code, pod that served it, app version. Ctrl+C or SIGTERM prints the summary.
URL=${URL:-http://emi.local/api/emi}
N=${1:-30}; DELAY=${2:-0}
ok=0; fail=0; pods=""

now() {   # HH:MM:SS.mmm from bash built-ins (uutils `date +%3N` drops leading zeros: .005 prints as .555)
  local t=$EPOCHREALTIME
  local f=${t#*[.,]}
  printf '%(%T)T.%s' "${t%[.,]*}" "${f:0:3}"
}

summary() {
  echo "----"
  echo "requests per pod:"; printf "%b" "$pods" | sort | uniq -c
  echo "ok=$ok failed=$fail"
}
trap 'summary; exit' INT TERM

for i in $(seq 1 "$N"); do
  P=$((RANDOM * 10 + 10000)); R=$((RANDOM % 20 + 1)); M=$((RANDOM % 120 + 1))
  out=$(curl -s -m 5 -w ' %{http_code}' -H 'Content-Type: application/json' \
        -d "{\"principal\":$P,\"rate\":$R,\"months\":$M}" "$URL")
  code=${out##* }
  pod=$(echo "$out" | grep -o '"servedBy":"[^"]*"' | cut -d'"' -f4)
  ver=$(echo "$out" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
  printf "%s %4d  %s  %s %s\n" "$(now)" "$i" "$code" "${pod:--}" "${ver:+v$ver}"
  if [ "$code" = 200 ]; then ok=$((ok + 1)); pods+="$pod\n"; else fail=$((fail + 1)); fi
  sleep "$DELAY"
done
summary
