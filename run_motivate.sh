#!/bin/bash
set -e

declare -a WORKLOADS
WORKLOADS=(baseline_read baseline_decode baseline_redness baseline_redbus)

for w in ${WORKLOADS[@]}; do
    make drop-cache;
    python script/search_driver.py workload/$w.yml /mnt/hdd/fast20/jpeg/flickr50k --expname=$w --store_result=True;
    sleep 1;
done