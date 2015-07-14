#!/bin/bash

ssh -o ServerAliveInterval=60 $EXP_SSH \
  "tail -f $EXP_LOG"\
    | src/collect.py -C cache -I -F --debug INFO -w 5000 \
>> results/exp4-1.csv

