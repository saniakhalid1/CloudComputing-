#!/bin/bash
# Long wave workload (~40 min), same idea as Assignment 3's load.sh.
# Load goes UP and DOWN in three waves; every step lasts 60 s.
#   10 req/s  light  -> 1 pod is enough (~6% CPU)
#   50        medium -> ~1 pod (~30-55% CPU)
#   100       high   -> HPA needs ~2 pods
#   200       peak   -> HPA needs ~4-5 pods; 1 fixed pod fails here
# Usage:  ./load.sh fixed <replicas>    e.g.  ./load.sh fixed 1
#         ./load.sh hpa
# Everything is saved in results/long_fixed<N>/ or results/long_hpa/
MODE=$1; REP=${2:-1}
if [ "$MODE" = hpa ]; then NAME=long_hpa; HDR=""; else NAME=long_fixed$REP; HDR="replicas=$REP "; fi
OUT=results/$NAME; mkdir -p $OUT
exec > >(tee $OUT/output.txt) 2>&1                      # show on screen and save

if [ "$MODE" = hpa ]; then
  kubectl scale deployment emi-web -n emi --replicas=1
  kubectl apply -f hpa.yaml
else
  kubectl delete hpa emi-web -n emi --ignore-not-found   # HPA off: replicas stay fixed
  kubectl scale deployment emi-web -n emi --replicas=$REP
fi
kubectl rollout status deployment emi-web -n emi
echo "waiting 60 s so everything is idle before the test..."; sleep 60

./monitor.sh $OUT > /dev/null & MON=$!                  # pods.csv, host_cpu.csv, hpa.csv

step() {                       # step <rate> <number of 60 s steps>
  for ((k = 0; k < $2; k++)); do
    echo "=== ${HDR}rate=$1 start=$(date +%s)"
    ./httperf_script.sh $1 60
  done
}

# wave 1: low -> medium -> high -> peak -> back down to idle
step 10  2
step 50  2
step 100 2
step 200 3      # 3 min peak
step 100 2
step 10  6      # 6 min quiet: HPA scales in (it waits 5 min)

# wave 2: smaller wave
step 50  2
step 100 3
step 10  6

# wave 3: peak again, then a long quiet tail
step 200 3
step 50  2
step 10  6

echo "=== ${HDR}rate=0 start=$(date +%s)"
sleep 60                        # one more minute of monitoring
kill $MON
echo "done: results in $OUT"
