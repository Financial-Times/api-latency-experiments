# api-latency-experiments

## Experiment 1

# Collect for at least 1 hour (5 seconds * 720)
src/collect.py -C cache/ -n 720 > results/exp1-1.csv

src/analyse.py -C cache/ results/exp1-1.csv > results/exp1-2.csv

src/bucket.py -p -c exp1-2.csv > results/exp1-3.csv

cat results/exp1-3.csv

