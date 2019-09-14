#!/bin/bash
set -e

SORT=${SORT:-0}
WORKERS=${WORKERS:-4}
BASEDIR=/mnt/hdd/fast20/jpeg/flickr2500
EXP_APPEND=${EXP_APPEND:-""}

[ 1 -eq $SORT ] && echo "Sorting!"

declare -a WORKLOADS
# WORKLOADS=(workload/baseline_read.yml workload/baseline_decode.yml  workload/baseline_redness.yml workload/baseline_redbus.yml)
WORKLOADS=(workload/smart_decode.yml  workload/smart_redness.yml workload/smart_redbus.yml)

for w in ${WORKLOADS[@]}; do
    echo $w
    make drop-cache
    sleep 1
    if [ 1 -eq $SORT ]; then
        python script/search_driver.py $w $BASEDIR --num_workers=$WORKERS --store_result=True --sort_fie=True  --expname_append="-sorted$EXP_APPEND";
    else
        python script/search_driver.py $w $BASEDIR --num_workers=$WORKERS --store_result=True --expname_append="$EXP_APPEND";
    fi;
    sleep 1
done;
