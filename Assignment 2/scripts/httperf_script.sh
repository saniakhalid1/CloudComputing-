httperf --hog  --timeout=60 --server=localhost --port=8080 --wsesslog=10000000,0,urls.txt --rate $1 -v&
sleep 30
pkill -2 httperf
