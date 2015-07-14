#!/bin/bash

ssh -o ServerAliveInterval=60 $EXP_SSH \
  "tail -f $EXP_LOG"\
    | src/collect.py -C cache -I -A --debug INFO -w 5000 \
>> results/exp3-1.csv

