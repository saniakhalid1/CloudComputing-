httperf --hog  --timeout=60 --server=192.168.56.13 --port=80 --wsesslog=10000000,0,urls.txt --rate $1 -v&
sleep 60
skill -2 httperf
