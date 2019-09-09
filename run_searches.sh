#!/bin/bash
set -e

declare -a WORKLOADS
WORKLOADS=(workload/simple_read.yml workload/simple_read_decode.yml workload/simple_rgbhist1d.yml)

for w in ${WORKLOADS[@]}; do
    echo $w
    make drop-cache
    sleep 1
    cgexec -g cpuset,memory:/s3dexphost python script/search_driver.py $w  /mnt/hdd/fast20/jpeg/flickr2500 --num_workers=4 --store_result=True --sort_fie=True  --expname_append=-sorted
    sleep 2
done;
