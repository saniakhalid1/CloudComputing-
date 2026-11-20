#!/bin/bash
# Milestone 3 workload: load goes UP and DOWN in three waves so the HPA
# has to scale out and back in several times.
# Each number is an httperf session rate; every step lasts ~30 s (see httperf_script.sh).
# One pod answers ~20 req/s at full CPU; HPA target (50% of 200m) = ~4 req/s per pod.
#   2    light   -> 1 pod is enough, CPU low
#   8    medium  -> scale out to 2 pods
#   15   high    -> 3-4 pods
#   30   peak    -> 5 pods (max)

step() {                       # step <rate> <number of 30 s steps>
for ((k = 0; k < $2; k++)); do
./httperf_script.sh $1
done
}

# wave 1: low -> medium -> high -> peak -> back down to idle
step 2    4      # 2 min idle baseline
step 8    4
step 15   4
step 30   6      # 3 min peak
step 8    6      # decreasing: pods scale in
step 2    4

# wave 2: smaller wave
step 8    4
step 15   4
step 2    8      # 4 min low load -> back to 1 pod

# wave 3: peak again, then a long quiet tail
step 30   6
step 8    4
step 2    10     # 5 min low load so the last scale-in finishes
