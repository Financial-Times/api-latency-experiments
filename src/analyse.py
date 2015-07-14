#!/usr/bin/python3
#coding: utf-8

import logging
import json
import urllib.request, urllib.parse, urllib.error
import datetime
import time
import sys
import csv
import os
import re
import argparse
import ftapi
import pygal
import math

UUID_LENGTH = 36
UUID_REGEX = re.compile('([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})')

DATE_REGEX = re.compile('([0-9]{4}).([0-9]{2}).([0-9]{2}).([0-9]{2}).([0-9]{2}).([0-9]{2}).([0-9]+)')

parser = argparse.ArgumentParser(description="Discover the article types and ages for articles collected by collect.py")

parser.add_argument('csv', type=str, help='Input CSV file')
parser.add_argument('-b', '--base', type=str, help='Calculate intervals relative to which point', choices=['published_date', 'first_appearance', 'first_external_mention'], default='published_date')
parser.add_argument('-m', '--mention-file', type=str, help='Log file to look for mentions (use with -b first_external_mention)')
parser.add_argument('-z', '--zeroes', action='store_true', help='Include results with zero interval (default: discard these)')
parser.add_argument('-p', '--poll-interval', type=int, help='Seconds to sleep between collecting', default=1)
parser.add_argument('-k', '--key', type=str, help='FT API key (default: ~/.ft_api_key)', default=None)
parser.add_argument('-C', '--cache', type=str, help='Cache directory for article responses', default=None)
parser.add_argument('-g', '--graph', type=str, help='Render SVG graph to this file')
parser.add_argument('--debug', type=str, help='Set log level (default:WARN)', default=None)

args = parser.parse_args()

if args.debug:
    logging.root.setLevel(getattr(logging,args.debug))
else:
    logging.root.setLevel(logging.WARN)

if not args.key:
    try:
        args.key = open(os.path.expanduser('~/.ft_api_key'),'r').read().strip()
    except IOError:
        args.key = None

mentions={}
if args.mention_file:
    for line in open( args.mention_file,'r' ).readlines():
        for match in UUID_REGEX.findall(line):
            uuid = match.lower()
            if uuid not in mentions:
                mentions[uuid]=[]
            mentions[uuid].append(line.strip())

if args.base == 'first_external_mention' and not args.mention_file:
    raise Exception('No file supplied for external mentions: expected -m <filename>')

def really_dump(o):
    try:
        return o.__json__()
    except:
        try:
            return o.__dict__
        except:
            return str(o)

def json_dump(o, **args):
    return json.dumps(o, default=really_dump, **args)

class Item:
    KEY = args.key
    CACHE = args.cache
    THROTTLE_INTERVAL = args.poll_interval

    def __init__(self, id=None):
        self._id = id
        _json = Item.get_content(self._id)
        self._obj = json.loads(_json)
        self.origin = self.sniff_origin()
        self.type = self._obj.get('type', None)
        self.title = self._obj.get('title', None) or self._obj.get('description', None)
        #logging.debug( json_dump(self._obj, indent=4) )
        self.published_date = datetime.datetime.strptime(self._obj['publishedDate'][:26], "%Y-%m-%dT%H:%M:%S.%fZ")

    def sniff_origin(self):
        if 'webUrl' in self._obj:
            if 'www.ft.com/cms' in self._obj['webUrl']:
                return 'METHODE'
            elif 'blogs.ft.com/' in self._obj['webUrl']:
                return 'BLOGS'
            elif 'www.ft.com/fastft' in self._obj['webUrl']:
                return 'FASTFT'
        return 'UNKNOWN'

    def __hash__(self):
        return id(self)
                
    def __str__(self):
        return '<%s %s "%s">' % (self.origin, Item.str_type(self.type), self.title)
                   
    CONTENT_URL = "http://api.ft.com/content"
    ONTOLOGY_URL = "http://www.ft.com/ontology/content"

    @staticmethod
    def get_content(i_d):
        i_d = i_d[-UUID_LENGTH:] # get rid of any http:// prefix
        try:
            return ftapi.CachingFTURLopener(throttle=Item.THROTTLE_INTERVAL,cache=Item.CACHE,cache_errors=True).get_url( Item.CONTENT_URL+"/"+i_d, key=Item.KEY)
        except urllib.error.HTTPError as e:
            raise ValueError('No content')

    @staticmethod
    def str_type(type):
        if type.startswith(Item.ONTOLOGY_URL):
            return type[len(Item.ONTOLOGY_URL)+1:]
        else:
            return type


data = csv.reader( open( args.csv, 'r').readlines() )

uuids = {}
not_content = set()

for line in list(data):
    when = datetime.datetime.strptime(line[0], "%Y-%m-%dT%H:%M:%S.%fZ")
    src = line[1]
    line_uuids = []
    line_extras = []
    for field in line[2:]:
        # the old version had multiple uuids per line, this was quite a bad idea
        # but the 3 week data set does it this way.
        # Therefore, spot UUIDs in fields and collect other fields into 'extras'
        # FIXME: remove support for the old data set
        if len(field)==UUID_LENGTH:
            line_uuids.append(field)
        else:
            line_extras.append(field)

    for uuid in line_uuids:
        if uuid not in not_content:
            try:
                if uuid not in uuids:
                    content = Item(id=uuid)
                    logging.debug( 'Found %s' % content )
                    uuids[uuid] = [content]
                uuids[uuid].append( (when,src,line_extras) )
            except ValueError as e:
                logging.debug(e)
                logging.info('%s was not content' % uuid)
                not_content.add(uuid)

DAY = datetime.timedelta(1,0,0)

RESULTS = {}
GROUPS = set()
TITLES = {}

for uuid,result in sorted(list(uuids.items())):
    item = result[0]
    TITLES[uuid] = item.title
    RESULTS[uuid]={}

    for when,src,extras in result[1:]:

        interval = None

        if args.base == 'first_appearance':
            interval = when - result[1][0]
        elif args.base == 'first_external_mention':
            if uuid not in mentions:
                logging.debug('No mentions of %s, discarding' % uuid)
            else:
                logging.debug('Finding first mention of %s' % uuid)
                first_time = None
                for line in mentions[uuid]:
                    logging.debug(line)
                    mention_time = DATE_REGEX.match(line)
                    if not mention_time:
                        logging.debug("Don't understand line %s" % uuid)
                    else:
                        this_time = datetime.datetime(int(mention_time.group(1)),
                                        int(mention_time.group(2)),
                                        int(mention_time.group(3)),
                                        int(mention_time.group(4)),
                                        int(mention_time.group(5)),
                                        int(mention_time.group(6)),
                                        int((mention_time.group(7)+'000000')[:6]))
                        if first_time is None or this_time < first_time:
                            first_time = this_time
                interval = when - first_time
        else:
            interval = when - item.published_date

        if len(extras)>0:
            group = str(extras[0])+':'+item.origin+':'+src
        else:
            group = '0'+':'+item.origin+':'+src
        GROUPS.add(group)
        if group not in RESULTS[uuid]:
            RESULTS[uuid][group] = []

        if interval is not None and interval < DAY:
            safe_title = item.title.replace('"',r'\"')
            if interval > datetime.timedelta(0,0,0):
                print('%s,%s,%s,%s,%s,"%s"' % (uuid,src,item.origin,interval,','.join(extras),safe_title))
            elif interval == datetime.timedelta(0,0,0):
                if args.zeroes:
                    print('%s,%s,%s,%s,%s,"%s"' % (uuid,src,item.origin,interval,','.join(extras),safe_title))
            else:
                # str(negative-interval) is unhelpful
                print('%s,%s,%s,-%s,%s,"%s"' % (uuid,src,item.origin,-interval,','.join(extras),safe_title))

            RESULTS[uuid][group].append( interval )

if args.graph:
    filter = re.compile('.+:METHODE')

    x = {}
    xy = pygal.XY(stroke=False,
                  width=800,
                  height=450,
                  legend_at_bottom=True,
                  truncate_legend=40,
                  dots_size=1.5)

    my_groups = [g for g in reversed(sorted(GROUPS)) if filter.match(g)]

    for i,group in enumerate(my_groups):
        r = []
        for uuid, g in sorted(list(RESULTS.items())):
            if group in g and g[group]:
                for interval in g[group]:
                    if uuid not in x:
                        x[uuid] = len(x)
                    s = interval.days*86400+interval.seconds+interval.microseconds*0.000001
                    if s>0:
                        r.append( (x[uuid] + (i+1)*(1.0/(len(my_groups)+2)), s) )

        if r:
            xy.add(group,r)

    logging.info('x-values for graph are:')
    for uuid in sorted(list(x.keys())):
        logging.info('%s = %s : %s' % (uuid,x[uuid],TITLES[uuid]))

    xy.render_to_file(args.graph)
