#!/bin/bash
# Writes urls.txt: 1000 POST /api/emi requests with random loan numbers (one request per session).
for i in $(seq 1 1000); do
  echo "/api/emi method=POST contents='{\"principal\":$((RANDOM * 10 + 10000)),\"rate\":$((RANDOM % 20 + 1)),\"months\":$((RANDOM % 120 + 6))}'"
  echo
done > urls.txt
echo "urls.txt written: $(grep -c api urls.txt) requests"
