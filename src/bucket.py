#!/usr/bin/python3
#coding: utf-8

import logging
import csv
import os
import re
import argparse
import math

parser = argparse.ArgumentParser(description="Distribute results of analyse.py by age buckets")

parser.add_argument('csv', type=str, help='Input CSV file')
parser.add_argument('-s', '--bucket-size', type=float, help='Bucket size in seconds', default=5)
parser.add_argument('-l', '--limit', type=int, help='Maximum number of buckets (default:all)', default=0)
parser.add_argument('-n', '--not-found', action='store_true', help='Include lines with 4xx status (default: exclude)')
parser.add_argument('-c', '--cumulative', action='store_true', help='Values accumulate')
parser.add_argument('-p', '--percentage', action='store_true', help='Report values as % of lines of each type')
parser.add_argument('--debug', type=str, help='Set log level (default:WARN)', default=None)

args = parser.parse_args()

if args.debug:
    logging.root.setLevel(getattr(logging,args.debug))
else:
    logging.root.setLevel(logging.WARN)

data = csv.reader( open( args.csv, 'r').readlines() )

BUCKETS = {}

max_bucket = 0

# Only consider the first sighting of each item in each method
already_seen = set()

for line in list(data):
    if len(line)<5:
        continue

    if line[2]=='UNKNOWN':
        continue

    method = '%s:%s' % (line[1], line[2])

    if (line[0]+method) in already_seen:
        logging.debug('Already seen %s' % line[0]+method)
        continue

    interval = re.match('(-?)([0-9]+):([0-9]+):([0-9.]+)',line[3])

    status = line[4]

    if not interval:
        logging.warn("Couldn't get interval from line %s" % line)
    elif status.startswith('4') and not args.not_found:
        logging.debug("Discarding 4xx line %s" % line)
    else:
        already_seen.add(line[0]+method)
        seconds = float(interval.group(4)) + int(interval.group(3))*60 + int(interval.group(2))*60*60
        if interval.group(1) == '-':
            seconds = -seconds
        seconds = math.ceil( seconds / args.bucket_size )
        if method not in BUCKETS:
            BUCKETS[method] = {}
        if seconds not in BUCKETS[method]:
            BUCKETS[method][seconds] = 0
        BUCKETS[method][seconds] += 1
        if seconds > max_bucket:
            max_bucket = seconds

methods = sorted( BUCKETS.keys() )

counts = [0] * len(methods)

# count up everything to get true percentages
for b in range(0,max_bucket+1):
    for i,method in enumerate(methods):
        if b in BUCKETS[method]:
            counts[i] += BUCKETS[method][b]

s = 'time'

for i,method in enumerate(methods):
    if counts[i]>0:
        s += ',%s' % method

print(s)

max_counts = counts

logging.info( 'Methods and counts: %s', [(methods[x], counts[x]) for x,_ in enumerate(methods)] )

counts = [0] * len(methods)

if not args.limit:
    args.limit = max_bucket + 1

for b in range(0,args.limit):
    for i,method in enumerate(methods):
        if b in BUCKETS[method]:
            if args.cumulative:
                counts[i] += BUCKETS[method][b]
            else:
                counts[i] = BUCKETS[method][b]
        else:
            if not args.cumulative:
                counts[i] = 0

    prop_counts = []
    for i,count in enumerate(counts):
        if max_counts[i] > 0:
            if args.percentage:
                prop_counts.append( str(count*100 / max_counts[i]) )
            else:
                prop_counts.append( str(count) )

    print('%s,%s' % (b*args.bucket_size, ','.join(prop_counts)))
