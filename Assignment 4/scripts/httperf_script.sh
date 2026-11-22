#!/bin/bash
# One load step. Usage: ./httperf_script.sh <rate> <seconds>
httperf --hog --timeout=10 --server=emi.local --port=80 \
        --add-header='Content-Type: application/json\n' \
        --wsesslog=10000000,0,urls.txt --rate $1 &
sleep $2
pkill -2 httperf
wait
