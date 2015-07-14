#!/usr/bin/python3
#coding: utf-8

import logging
import csv
import os,sys
import re
import argparse
import math
import pygal

parser = argparse.ArgumentParser(description="Distribute results of analyse.py by age buckets")

parser.add_argument('csv', type=str, help='Input CSV file')
parser.add_argument('-s', '--bucket-size', type=float, help='Bucket size in seconds', default=5)
parser.add_argument('-l', '--limit', type=int, help='Maximum number of buckets (default:all)', default=0)
parser.add_argument('-n', '--not-found', action='store_true', help='Include lines with 4xx status (default: exclude)')
parser.add_argument('-c', '--cumulative', action='store_true', help='Report accumulation of values')
parser.add_argument('-p', '--percentage', action='store_true', help='Report values as a percentage of matching results')
parser.add_argument('-L', '--last', action='store_true', help='For each item+method, use the last entry supplied (default: first)')
parser.add_argument('-g', '--graph', type=str, help='Render SVG graph to this file')
parser.add_argument('--debug', type=str, help='Set log level (default:WARN)', default=None)

args = parser.parse_args()

if args.debug:
    logging.root.setLevel(getattr(logging,args.debug))
else:
    logging.root.setLevel(logging.WARN)

data = csv.reader( open( args.csv, 'r').readlines() )

BUCKETS = {}

max_bucket = 0

lines_to_include = {}

for line in data:
    key = ':'.join(line[:3])+':'.join(line[4:-1])

    if args.last:
        lines_to_include[key] = line
    elif key not in lines_to_include:
        lines_to_include[key] = line

for line in lines_to_include.values():
    if len(line)<5:
        continue

    if line[2]=='UNKNOWN':
        continue

    method = '%s:%s:%s' % (line[1], line[2], ':'.join(line[4:-1]))

    interval = re.match('(-?)([0-9]+):([0-9]+):([0-9.]+)',line[3])

    status = line[4]

    if not interval:
        logging.warn("Couldn't get interval from line %s" % line)
    elif status.startswith('4') and not args.not_found:
        logging.debug("Discarding 4xx line %s" % line)
    else:
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

RESULTS = []
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

    RESULTS.append( (b*args.bucket_size,) + tuple(prop_counts) )
    print('%s,%s' % (b*args.bucket_size, ','.join(prop_counts)))

if args.graph:
    xy = pygal.XY(width=800,
                  height=450,
                  show_dots=False,
                  legend_at_bottom=True,
                  truncate_legend=40)
    xy.title = 'title'
    for i,method in enumerate(methods):
        line = []
        for point in RESULTS:
            line.append( (float(point[0]), float(point[i+1])) )
        xy.add(method, line)
    xy.render_to_file(args.graph)

