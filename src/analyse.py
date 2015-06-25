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
import argparse
import ftapi

UUID_LENGTH = 36

parser = argparse.ArgumentParser(description="Discover the article types and ages for articles collected by collect.py")

parser.add_argument('csv', type=str, help='Input CSV file')
parser.add_argument('-p', '--poll-interval', type=int, help='Seconds to sleep between collecting', default=1)
parser.add_argument('-k', '--key', type=str, help='FT API key (default: ~/.ft_api_key)', default=None)
parser.add_argument('-C', '--cache', type=str, help='Cache directory for article responses', default=None)
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
    for uuid in line[2:]:
        # the old version had multiple uuids per line, this was quite a bad idea
        # but the 3 week data set does it this way
        # FIXME: remove support for the old data set
        if len(uuid)==UUID_LENGTH and uuid not in not_content:
            try:
                if uuid not in uuids:
                    content = Item(id=uuid)
                    logging.debug( 'Found %s' % content )
                    uuids[uuid] = [content]
                uuids[uuid].append( (when,src) ) # FIXME: relative time
            except ValueError as e:
                logging.debug(e)
                logging.info('%s was not content' % uuid)
                not_content.add(uuid)

DAY = datetime.timedelta(1,0,0)

for uuid,result in uuids.items():
    item = result[0]
    for when,src in result[1:]:
        interval = when - item.published_date
        if interval < DAY:
            if interval > datetime.timedelta(0,0,0):
                print('%s,%s,%s,%s,%s' % (uuid,src,item.origin,interval,item.title))
            else:
                # str(negative-interval) is unhelpful
                print('%s,%s,%s,-%s,%s' % (uuid,src,item.origin,-interval,item.title))


