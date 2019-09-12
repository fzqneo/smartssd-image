#!/bin/bash
set -e

SORT=${SORT:-0}
WORKERS=${WORKERS:-4}
BASEDIR=/mnt/hdd/fast20/jpeg/flickr50k
EXP_APPEND=${EXP_APPEND:-""}

[ 1 -eq $SORT ] && echo "Sorting!"

declare -a WORKLOADS

WORKLOADS=(workload/simple_read.yml workload/simple_decode.yml  workload/simple_redness.yml)
# WORKLOADS=(workload/smart_decode.yml  workload/smart_redness.yml)


for w in ${WORKLOADS[@]}; do
    echo $w
    make drop-cache
    sleep 1
    if [ 1 -eq $SORT ]; then
        taskset -c "18-$((18+${WORKERS}-1))" python script/search_driver.py $w $BASEDIR --num_workers=$WORKERS --store_result=True --sort_fie=True  --expname_append="-sorted$EXP_APPEND";
    else
        taskset -c "18-$((18+${WORKERS}-1))" python script/search_driver.py $w $BASEDIR --num_workers=$WORKERS --store_result=True --expname_append="$EXP_APPEND";
    fi;
    sleep 2
done;
