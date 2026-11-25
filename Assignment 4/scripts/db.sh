#!/bin/bash
# Milestone 4 load tests, same style as load.sh (monitor.sh starts and stops by itself).
#
#   ./m4.sh fixed   -> 15 runs: 1, 2, 3 replicas x 10, 25, 50, 100, 200 req/s
#                      every run 60 s, 30 s rest after each (~25 min)
#                      saved in results/m4_fixed/
#
#   ./m4.sh hpa     -> HPA test (10 min): 10 req/s for 2 min, 100 req/s for 5 min, 10 req/s for 3 min
#                      HPA: 1-5 replicas, target 50% CPU
#                      saved in results/m4_hpa/
#
# Each folder gets: output.txt (httperf results), pods.csv, host_cpu.csv, hpa.csv
MODE=$1
if [ "$MODE" != fixed ] && [ "$MODE" != hpa ]; then
  echo "usage: ./m4.sh fixed   or   ./m4.sh hpa"; exit 1
fi
OUT=results/m4_$MODE; mkdir -p $OUT
exec > >(tee $OUT/output.txt) 2>&1                       # show on screen and save

run() {                         # run <rate> <seconds>
  echo "=== ${HDR}rate=$1 start=$(date +%s)"
  ./httperf_script.sh $1 $2
}

if [ "$MODE" = fixed ]; then
  kubectl delete hpa emi-web -n emi --ignore-not-found   # HPA off: replicas stay fixed
  ./monitor.sh $OUT > /dev/null & MON=$!
  for rep in 1 2 3; do
    kubectl scale deployment emi-web -n emi --replicas=$rep
    kubectl rollout status deployment emi-web -n emi
    sleep 30                                             # new pods settle
    HDR="replicas=$rep "
    for rate in 10 25 50 100 200; do
      run $rate 60
      sleep 30                                           # rest, so runs don't mix
    done
  done
else
  kubectl scale deployment emi-web -n emi --replicas=1
  kubectl apply -f hpa.yaml
  kubectl rollout status deployment emi-web -n emi
  echo "waiting 60 s so everything is idle before the test..."; sleep 60
  ./monitor.sh $OUT > /dev/null & MON=$!
  HDR=""
  run 10  120          # 2 min low
  run 100 300          # 5 min high  -> HPA scales out
  run 10  180          # 3 min low   -> HPA waits 5 min before scaling in
  echo "=== rate=0 start=$(date +%s)"
  sleep 60             # one more minute of monitoring
fi

kill $MON
echo "done: results in $OUT"
