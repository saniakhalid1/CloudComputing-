#!/bin/bash
httperf --hog --timeout=60 --server=10.99.140.33 --port=80 --wsesslog=10000000,0,urls.txt --rate $1 -v &
sleep 30
pkill -2 httperf
