#!/bin/bash
# Milestone 5 workload: load goes UP and DOWN in three waves so the autoscaler
# has to scale out and back in several times.
# Each number is an httperf session rate; every step lasts ~30 s (see httperf_script.sh).
# Rough effect with one core per container (2 requests per session):
#   100-300  light   -> 1-2 containers are enough, CPU low
#   500      medium  -> one container saturates, scale out to 2
#   2000     high    -> 3-4 containers
#   6000     peak    -> 4 containers (max)

step() {                       # step <rate> <number of 30 s steps>
for ((k = 0; k < $2; k++)); do
./httperf_script.sh $1
done
}

# wave 1: low -> medium -> high -> peak -> back down to idle
step 100  4      # 2 min idle baseline
step 500  4
step 2000 4
step 6000 6      # 3 min peak
step 300  6      # decreasing: containers scale in
step 100  4

# wave 2: smaller wave
step 500  4
step 2000 4
step 100  8      # 4 min low load -> back to 1 container

# wave 3: peak again, then a long quiet tail
step 6000 6
step 300  4
step 100  10     # 5 min low load so the last scale-in finishes

