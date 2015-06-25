#!/usr/bin/python3
#coding: utf-8

import argparse
import logging
import json
import urllib.request, urllib.parse, urllib.error
import datetime
import time
import sys
import re
import random
import subprocess
import os
import asyncio
import ftapi


UUID_LENGTH = 36

URLS = { 'WWW.FT.COM': ['http://www.ft.com/home/uk', None, False, False, False],
         'API-V2': ['http://api.ft.com/content/notifications?since=%s', ['since'], True, False, False],
         'API-V1': ['http://api.ft.com/content/notifications/v1/items?since=%s', ['since'], True, False, False],
         'NEXT.FT.COM': ['http://next.ft.com/uk', None, False, False, True],
         'WWW.FT.COM-RSS': ['http://www.ft.com/rss/home/uk', None, False, False, False],
         'APP.FT.COM': ['http://app.ft.com/api/v1/structure/v7?edition=dynamic&region=uk&icb=23887251&contenttype=magazine', None, False, False, False], 
         'FASTFT': ['http://clamo.ftdata.co.uk/api?request=%5B%7B%22action%22%3A%22search%22%2C%22arguments%22%3A%7B%22query%22%3A%22%22%2C%22limit%22%3A5%2C%22offset%22%3A0%2C%22outputfields%22%3A%7B%22id%22%3Atrue%2C%22title%22%3Atrue%2C%22content%22%3A%22html%22%2C%22abstract%22%3A%22html%22%2C%22datepublished%22%3Atrue%2C%22shorturl%22%3Atrue%2C%22metadata%22%3Atrue%2C%22tags%22%3A%22visibleonly%22%2C%22authorpseudonym%22%3Atrue%2C%22attachments%22%3A%22html%22%2C%22slug%22%3Atrue%7D%7D%7D%5D', None, False, False, False] }

ARTICLE_URLS = { 'WWW.FT.COM-ART': ['http://www.ft.com/cms/s/0/%s.html', ['uuid'], False, True, False],
               'NEXT.FT.COM-ART': ['http://next.ft.com/%s', ['uuid'], False, True, True],
               'API-V1-ART': ['http://api.ft.com/content/items/v1/%s', ['uuid'], True, False, False],
               'API-V2-ART': ['http://api.ft.com/content/%s', ['uuid'], True, False, False] }

ARTICLE_URL_KEYS = list(ARTICLE_URLS.keys())

parser = argparse.ArgumentParser(description="Collect new UUIDs from various FT API URLs. Writes CSV to stdout in the form <time>,<url_name>,<uuid>,0.")

parser.add_argument('apis', type=str, nargs='*', help='APIs to collect from: %s (default: all)' % list(URLS.keys()))
parser.add_argument('-n', '--repeat', type=int, help='How many times to poll (default: forever)', default=True)
parser.add_argument('-p', '--poll-interval', type=int, help='Seconds to sleep between collecting', default=5)
parser.add_argument('-s', '--since', type=int, help='Seconds before now to request notifications for', default=None)
parser.add_argument('-a', '--articles', action='store_true', help='Investigate article URLs asynchronously.', default=False)
parser.add_argument('-A', '--article-stats', action='store_true', help='Capture result of article URL investigation. Adds extra lines to CSV in the form <time>,<article_url_name>,<uuid>,<status>, implies -a', default=False)
parser.add_argument('-k', '--key', type=str, help='FT API key (default: ~/.ft_api_key)', default=None)
parser.add_argument('-c', '--cookie', type=str, help='FT cookie (default: ~/.ft_cookie)', default=None)
parser.add_argument('-C', '--cache', type=str, help='Cache directory for article responses', default=None)
parser.add_argument('--debug', type=str, help='Set log level (default:WARN)', default=None)

args = parser.parse_args()

if args.debug:
    logging.root.setLevel(getattr(logging,args.debug))
else:
    logging.root.setLevel(logging.WARN)

if not args.apis:
    args.apis = list(URLS.keys())
logging.info("Collecting from %s" % args.apis)

logging.info("Collecting articles from %s" % ARTICLE_URL_KEYS)

logging.info("Using poll interval of %s s" % args.poll_interval)

if not args.since:
    # default to at least 1 minute more than the poll interval
    args.since = (args.poll_interval // 60)*60 + 120
logging.info("Using since interval of %s s" % args.since)

if not args.key:
    try:
        args.key = open(os.path.expanduser('~/.ft_api_key'),'r').read().strip()
    except IOError:
        args.key = None

if not args.cookie:
    try:
        args.cookie = open(os.path.expanduser('~/.ft_cookie'),'r').read().strip()
    except IOError:
        args.cookie = None



def populate_fields(url, fields, **replace):
    if fields is None:
        return url
    else:
        field_values = []
        for field in fields:
            if field in replace:
                field_values.append( replace[field] )
            else:
                field_values.append( '' )
        return url % tuple(field_values)


@asyncio.coroutine
def collect_article(uuid, article_apis=None, article_stats=False, article_cache=None, key='', cookie='', backoff=250):

    if not article_apis:
        return # nowhere to get articles from
    if not article_stats and not article_cache:
        return # no need to do anything as there will be no result

    url_name = random.choice(article_apis)
    url, fields, with_key, with_cookie, with_next = ARTICLE_URLS[url_name]
    url = populate_fields(url, fields, uuid=uuid)
    key = (with_key and key) or ''
    cookie = (with_cookie and cookie) or ''

    # wait a random time
    wait_time = random.random()*backoff +1  

    logging.debug('Waiting %sms to get %s from %s' % (wait_time,uuid,url_name))
    yield from asyncio.sleep(wait_time/1000.0)

    result_code = 200

    try:
        response = ftapi.CachingFTURLopener(cache=article_cache,cache_errors=True).get_url(url, key, cookie, with_next)
    except urllib.error.HTTPError as e:
        response = None
        result_code = e.code

    if article_stats:
        logging.debug('Article %s:%s status %s' % (url_name, uuid, result_code))
        print( '%s,%s,%s,%s' % ( datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), url_name, uuid, result_code) )

    if result_code != 200:
        # retry (after another random time)
        logging.debug('Retrying %s from %s' % (uuid,url_name))
        asyncio.async(collect_article(uuid, [url_name], article_stats, article_cache, key, cookie, backoff*2))


@asyncio.coroutine
def collect_main(apis,since,repeat,
                 article_apis=None, article_stats=False, article_cache=None,
                 key='',cookie=''):

    urls_to_hit = [(x, URLS[x]) for x in apis]
    last_time_ids = {}

    while repeat:
        if repeat is not True:
            repeat -=1

        now = datetime.datetime.utcnow()
        then = now - datetime.timedelta(0,since,0)

        random.shuffle(urls_to_hit)
    
        for url_name,(url, fields, with_key, with_cookie, with_next) in urls_to_hit:
            url = populate_fields(url, fields, since=then.strftime("%Y-%m-%dT%H:%M:%SZ") )

            this_key = (with_key and key) or ''
            this_cookie = (with_cookie and cookie) or ''

            try:
                response = ftapi.CachingFTURLopener().get_url(url, this_key, this_cookie, with_next)
            except urllib.error.HTTPError:
                response = None

            if response:
                items = set()
                uuids = re.findall('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', response)
            
                # Assume every UUID is an item id, we'll sort out discrepancies later
                ids_included = set(uuids)

                if url_name in last_time_ids:
                    new_ids = ids_included.difference(last_time_ids[url_name])
                    logging.debug('%d new ids out of %d' % (len(new_ids), len(ids_included)) )
                else:
                    new_ids = ids_included

                if url_name in last_time_ids:
                    # don't print out the very first requests, or we will slurp everything
                    for new_id in new_ids:
                        print( '%s,%s,%s,0' % ( now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), url_name, new_id ) )
                        asyncio.async(collect_article(new_id, 
                                                      article_apis, article_stats, article_cache,
                                                      key=key, cookie=cookie))

                last_time_ids[url_name] = ids_included
           

        # ensure things are written for followers
        sys.stdout.flush()
        yield from asyncio.sleep(args.poll_interval)

loop = asyncio.get_event_loop()

if args.articles:
    article_apis = ARTICLE_URL_KEYS
else:
    article_apis = []

loop.run_until_complete(collect_main(args.apis, args.since, args.repeat, article_apis, args.article_stats, args.cache, args.key, args.cookie))
loop.close()
