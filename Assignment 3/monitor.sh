#!/bin/bash
# Records the cluster state every 5 seconds into metrics.csv. Stop with Ctrl+C.
INTERVAL=5
echo "time,replicas,ready,hpa_cpu_pct,pods_cpu_m,pods_mem_mi" > metrics.csv
while true; do
  T=$(date +%s)
  REP=$(kubectl get deploy fft-deployment -o jsonpath='{.status.replicas}')
  READY=$(kubectl get deploy fft-deployment -o jsonpath='{.status.readyReplicas}')
  HPA=$(kubectl get hpa fft-hpa -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}')
  read CPU MEM <<< $(kubectl top pods -l app=fft --no-headers 2>/dev/null | awk '{gsub("m","",$2); gsub("Mi","",$3); c+=$2; m+=$3} END {print c+0, m+0}')
  echo "$T,${REP:-0},${READY:-0},${HPA:-0},${CPU:-0},${MEM:-0}" | tee -a metrics.csv
  # wait so that each row starts exactly INTERVAL seconds after the previous one
  LEFT=$(( INTERVAL - ($(date +%s) - T) ))
  [ $LEFT -gt 0 ] && sleep $LEFT
done
