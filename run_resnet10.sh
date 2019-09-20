#!/bin/bash
set -e

WORKERS=${WORKERS:-4}
BASEDIR=/mnt/hdd/fast20/jpeg/flickr2500
EXP_APPEND=${EXP_APPEND:-""}

# 1. baseline
make drop-cache
python script/run_resnet10.py $BASEDIR --num_workers=$WORKERS --expname="baseline_resnet10$EXP_APPEND";
sleep 1

# 2. baseline-sorted
make drop-cache
python script/run_resnet10.py $BASEDIR --num_workers=$WORKERS --sort_fie=True --expname="baseline_resnet10-sorted$EXP_APPEND";
sleep 1

# 3. smart-sorted
make drop-cache
python script/run_resnet10.py $BASEDIR --num_workers=$WORKERS --sort_fie=True --smart=True --expname="smart_resnet10-sorted$EXP_APPEND";
sleep 1
