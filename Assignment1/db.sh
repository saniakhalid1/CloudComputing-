#!/bin/bash

for (( i=50; i<=12000; i+=100 ))
do
	./httperf_script.sh $i 
done

