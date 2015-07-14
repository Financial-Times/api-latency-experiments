# api-latency-experiments

echo 'Getting article info'
src/analyse.py -C cache/ -b first_appearance results/exp3-1.csv > results/exp3-2.csv -g results/exp3-2.svg

echo 'Finding Methode articles'
grep ',METHODE,' results/exp3-2.csv > results/exp3-2gM.csv

grep ',404,' results/exp3-2gM.csv > results/exp3-2gM404.csv
grep ',200,' results/exp3-2gM.csv > results/exp3-2gM200.csv

echo 'Bucketing last 404s'
src/bucket.py -n -c -p -s 0.1 -l 2000 -L results/exp3-2gM404.csv > results/exp3-3.csv -g results/exp3-3-404.svg
echo 'Bucketing first 200s'
src/bucket.py -n -c -p -s 0.1 -l 2000 results/exp3-2gM200.csv > results/exp3-3.csv -g results/exp3-3-200.svg

