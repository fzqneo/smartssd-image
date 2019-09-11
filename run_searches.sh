#!/bin/bash
set -e

SORT=${SORT:-0}
WORKERS=${WORKERS:-4}
BASEDIR=/mnt/hdd/fast20/jpeg/flickr2500

[ 1 -eq $SORT ] && echo "Sorting!"

declare -a WORKLOADS

# WORKLOADS=(workload/simple_read.yml workload/simple_read_decode.yml workload/simple_rgbhist1d.yml)
WORKLOADS=(workload/smart_decode.yml) # workload/smart_rgbhist1d.yml)


for w in ${WORKLOADS[@]}; do
    echo $w
    make drop-cache
    sleep 1
    if [ 1 -eq $SORT ]; then
        cgexec -g cpuset,memory:/s3dexphost python script/search_driver.py $w $BASEDIR --num_workers=$WORKERS --store_result=True --sort_fie=True  --expname_append=-sorted;
    else
        cgexec -g cpuset,memory:/s3dexphost python script/search_driver.py $w $BASEDIR --num_workers=$WORKERS --store_result=True;
    fi;
    sleep 2
done;
