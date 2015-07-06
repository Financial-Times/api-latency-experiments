# api-latency-experiments

## Experiment 2

# 720 = 1h

src/collect.py --debug DEBUG -A -n 72000 -C cache/ API-V1 >> results/exp2-1.csv

src/analyse.py --debug DEBUG -C cache/ results/exp2-1.csv > results/exp2-2.csv

src/bucket.py results/exp2-2.csv > results/exp2-3.csv

