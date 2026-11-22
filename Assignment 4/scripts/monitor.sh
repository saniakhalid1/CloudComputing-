#!/bin/bash
# Records into a folder (default results/) until Ctrl+C or kill.
# Usage: ./monitor.sh [folder]
#   host_cpu.csv  host CPU %, every 1 s          (mpstat)
#   pods.csv      CPU (m) and memory (Mi) of each pod, every 15 s   (kubectl top pods)
#   hpa.csv       HPA replicas and average CPU %, every 15 s        (kubectl get hpa)
DIR=${1:-results}
mkdir -p $DIR
echo "time,host_cpu_pct" > $DIR/host_cpu.csv
echo "time,pod,cpu_m,mem_mi" > $DIR/pods.csv
echo "time,replicas,cpu_pct" > $DIR/hpa.csv

( while true; do
    T=$(date +%s)
    mpstat 1 1 | awk -v t=$T '/Average/ {print t "," 100 - $NF}' >> $DIR/host_cpu.csv
  done ) &
trap "kill $!; exit" INT TERM

while true; do
  T=$(date +%s)
  kubectl top pods -n emi --no-headers 2>/dev/null |
    awk -v t=$T '{gsub("m","",$2); gsub("Mi","",$3); print t "," $1 "," $2 "," $3}' >> $DIR/pods.csv
  H=$(kubectl get hpa emi-web -n emi -o jsonpath='{.status.currentReplicas},{.status.currentMetrics[0].resource.current.averageUtilization}' 2>/dev/null)
  [ -n "$H" ] && echo "$T,$H" >> $DIR/hpa.csv
  echo "$(date +%T) recorded"
  LEFT=$(( 15 - ($(date +%s) - T) )); [ $LEFT -gt 0 ] && sleep $LEFT
done
