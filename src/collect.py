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
import os
import asyncio
import select
import ftapi



UUID_LENGTH = 36
UUID_REGEX = re.compile('[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}')

URLS = {
         'API-V2': ['http://api.ft.com/content/notifications?since=%s', ['since'], True, False, False],
         'API-V1': ['http://api.ft.com/content/notifications/v1/items?since=%s', ['since'], True, False, False],
       }

URL_KEYS = list(URLS.keys())

#         'APP.FT.COM': ['http://app.ft.com/api/v1/structure/v7?edition=dynamic&region=uk&icb=23887251&contenttype=magazine', None, False, False, False],
#         'WWW.FT.COM': ['http://www.ft.com/home/uk', None, False, False, False],
#         'NEXT.FT.COM': ['http://next.ft.com/uk', None, False, False, True],
#         'WWW.FT.COM-RSS': ['http://www.ft.com/rss/home/uk', None, False, False, False],
#         'FASTFT': ['http://clamo.ftdata.co.uk/api?request=%5B%7B%22action%22%3A%22search%22%2C%22arguments%22%3A%7B%22query%22%3A%22%22%2C%22limit%22%3A5%2C%22offset%22%3A0%2C%22outputfields%22%3A%7B%22id%22%3Atrue%2C%22title%22%3Atrue%2C%22content%22%3A%22html%22%2C%22abstract%22%3A%22html%22%2C%22datepublished%22%3Atrue%2C%22shorturl%22%3Atrue%2C%22metadata%22%3Atrue%2C%22tags%22%3A%22visibleonly%22%2C%22authorpseudonym%22%3Atrue%2C%22attachments%22%3A%22html%22%2C%22slug%22%3Atrue%7D%7D%7D%5D', None, False, False, False] 



ARTICLE_URLS = { 'WWW.FT.COM-ART': ['http://www.ft.com/cms/s/0/%s.html', ['uuid'], False, True, False],
               'NEXT.FT.COM-ART': ['http://next.ft.com/%s', ['uuid'], False, True, True],
               'API-V1-ART': ['http://api.ft.com/content/items/v1/%s', ['uuid'], True, False, False],
               'API-V2-ART': ['http://api.ft.com/content/%s', ['uuid'], True, False, False] }

ARTICLE_URL_KEYS = list(ARTICLE_URLS.keys())

parser = argparse.ArgumentParser(description="Collect new UUIDs from various FT API URLs. Writes CSV to stdout in the form <time>,<url_name>,<uuid>,0.")

parser.add_argument('apis', type=str, nargs='*', help='APIs to collect from: %s (default: all)' % list(URLS.keys()))
parser.add_argument('-I', '--stdin', action='store_true', help='Collect UUIDs from standard input (overrides api list)')
parser.add_argument('-n', '--repeat', type=int, help='How many times to poll (default: forever)', default=True)
parser.add_argument('-p', '--poll-interval', type=int, help='Seconds to sleep between collecting', default=5)
parser.add_argument('-s', '--since', type=int, help='Seconds before now to request notifications for', default=None)
parser.add_argument('-a', '--articles', action='store_true', help='Investigate article URLs asynchronously.', default=False)
parser.add_argument('-A', '--article-stats', action='store_true', help='Capture result of article URL investigation. Adds extra lines to CSV in the form <time>,<article_url_name>,<uuid>,<status>, implies -a', default=False)
parser.add_argument('-f', '--feeds', action='store_true', help='Investigate feed URLs asynchronously (use with -I)', default=False)
parser.add_argument('-F', '--feed-stats', action='store_true', help='Capture result of feed URL investigation. Adds extra lines to CSV in the form <time>,<feed_url_name>,<uuid>,<status>, implies -f', default=False)
parser.add_argument('-k', '--key', type=str, help='FT API key (default: ~/.ft_api_key)', default=None)
parser.add_argument('-c', '--cookie', type=str, help='FT cookie (default: ~/.ft_cookie)', default=None)
parser.add_argument('-C', '--cache', type=str, help='Cache directory for article responses', default=None)
parser.add_argument('-b', '--backoff-rate', type=float, help='Exponential backoff factor (default: 1.1)', default=1.1)
parser.add_argument('-w', '--initial_wait', type=int, help='Maximum ms to wait before making first asynchronous call', default=2000)
parser.add_argument('--debug', type=str, help='Set log level (default:WARN)', default=None)

args = parser.parse_args()

if args.debug:
    logging.root.setLevel(getattr(logging,args.debug))
else:
    logging.root.setLevel(logging.WARN)

if not args.apis and not args.stdin:
    args.apis = list(URLS.keys())

logging.info("Collecting from %s" % args.apis)

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
def collect_article(uuid, article_apis=None, article_stats=False, article_cache=None, key='', cookie='',
                        backoff_rate=1.5, wait_time=0, backoff=250, give_up_time=20000):

    if not article_apis:
        logging.debug('No APIs for %s',uuid)
        return # nowhere to get articles from
    if not article_stats and not article_cache:
        logging.debug('No stats or caching for %s',uuid)
        return # no need to do anything as there will be no result

    url_name = random.choice(article_apis)
    url, fields, with_key, with_cookie, with_next = ARTICLE_URLS[url_name]
    url = populate_fields(url, fields, uuid=uuid)
    key = (with_key and key) or ''
    cookie = (with_cookie and cookie) or ''

    # if not told how long to wait, wait a random time
    if wait_time:
        logging.info('%s (%s): told to wait %sms' % (uuid,url_name,wait_time))
    else:
        wait_time = random.random()*backoff
        backoff *= backoff_rate
        logging.info('%s (%s): backing off for %sms (out of %s)' % (uuid,url_name,wait_time,backoff))

    yield from asyncio.sleep(wait_time/1000.0)

    result_code = 200

    try:
        response = ftapi.CachingFTURLopener(cache=article_cache,cache_errors=False).get_url(url, key, cookie, with_next)
    except urllib.error.HTTPError as e:
        response = None
        result_code = e.code

    if article_stats:
        logging.debug('Article %s:%s status %s' % (url_name, uuid, result_code))
        print( '%s,%s,%s,%s' % ( datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), url_name, uuid, result_code) )

    if result_code == 200:
        logging.info('%s (%s): found, stopping' % (uuid, url_name))
    elif backoff > give_up_time:
        logging.info('%s (%s): giving up' % (uuid, url_name))
    else:
        # retry (after another random time)
        logging.debug('%s (%s): retrying now' % (uuid,url_name))
        asyncio.async(collect_article(uuid, [url_name], article_stats, article_cache, key, cookie, backoff_rate=backoff_rate,
            backoff=backoff))


@asyncio.coroutine
def collect_feed(uuid, then,
                 feed_apis=None, feed_stats=False, feed_cache=None, key='', cookie='',
                 backoff_rate=1.5, wait_time=0, backoff=1000, give_up_time=100000):

    logging.info('collect_feed %s' % feed_apis)

    if not feed_apis:
        logging.debug('No APIs for %s',uuid)
        return # nowhere to get feeds from
    if not feed_stats and not feed_cache:
        logging.debug('No stats or caching for %s',uuid)
        return # no need to do anything as there will be no result

    url_name = random.choice(feed_apis)
    url, fields, with_key, with_cookie, with_next = URLS[url_name]

    url = populate_fields(url, fields, uuid=uuid, since=then.strftime("%Y-%m-%dT%H:%M:%SZ") )

    key = (with_key and key) or ''
    cookie = (with_cookie and cookie) or ''

    # if not told how long to wait, wait a random time
    if wait_time:
        logging.info('%s (%s): told to wait %sms' % (uuid,url_name,wait_time))
    else:
        wait_time = random.random()*backoff
        backoff *= backoff_rate
        logging.info('%s (%s): backing off for %sms (out of %s)' % (uuid,url_name,wait_time,backoff))

    yield from asyncio.sleep(wait_time/1000.0)

    result_code = 200

    try:
        response = ftapi.CachingFTURLopener(cache=feed_cache,cache_errors=False).get_url(url, key, cookie, with_next)
    except urllib.error.HTTPError as e:
        response = None
        result_code = e.code

    if result_code == 200:
        if response is None:
            logging.warn('Got None for URL %s',url)
            result_code = 404
        else:
            if uuid not in response:
                result_code = 444 # article was not in the feed

    if feed_stats:
        logging.debug('Feed %s:%s status %s' % (url_name, uuid, result_code))
        print( '%s,%s,%s,%s' % ( datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"), url_name, uuid, result_code) )

    if result_code == 200:
        logging.info('%s (%s): found, stopping' % (uuid, url_name))
    elif backoff > give_up_time:
        logging.info('%s (%s): giving up' % (uuid, url_name))
    else:
        # retry (after another random time)
        logging.debug('%s (%s): retrying now' % (uuid,url_name))
        asyncio.async(collect_feed(uuid, then, [url_name], feed_stats, feed_cache, key, cookie, backoff_rate=backoff_rate,
            backoff=backoff))


@asyncio.coroutine
def collect_stdin(article_apis=None, article_stats=False, since=None,
                  feed_apis=None, feed_stats=False, cache=None,
                 key='',cookie=''):
    seen_ids = set()
    while True:
        # FIXME: find a way to use asyncio to get stdin asynchronously
        while sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline()
            if line:
                logging.info('Got line: %s' % line)
                new_ids = [uuid for uuid in UUID_REGEX.findall(line) if uuid not in seen_ids]
                if new_ids:
                    logging.info('UUIDs found: %s' % new_ids)
                now = datetime.datetime.utcnow()
                for new_id in new_ids:
                    print( '%s,%s,%s,0' % ( now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), 'STDIN', new_id ) )
                    for article_api in article_apis:
                        asyncio.async(collect_article(new_id, 
                                     [article_api], article_stats, cache,
                                     key=key, cookie=cookie, backoff_rate=args.backoff_rate,
                                     wait_time=random.random()*args.initial_wait))

                    now = datetime.datetime.utcnow()
                    then = now - datetime.timedelta(0,since,0)
                    for feed_api in feed_apis:
                        asyncio.async(collect_feed(new_id, then,
                                     [feed_api], feed_stats, cache,
                                     key=key, cookie=cookie, backoff_rate=args.backoff_rate,
                                     wait_time=random.random()*args.initial_wait))
                    seen_ids.add(new_id)
            else:
                raise SystemExit('No more input.')
        else:
            yield from asyncio.sleep(0.05)

@asyncio.coroutine
def collect_main(apis,since,repeat,
                 article_apis=None, article_stats=False,
                 feed_apis=None, feed_stats=False,
                 article_cache=None, key='',cookie=''):

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
                uuids = UUID_REGEX.findall(response)
            
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
                        for article_api in article_apis:
                            asyncio.async(collect_article(new_id, 
                                                      [article_api], article_stats, article_cache,
                                                      key=key, cookie=cookie, backoff_rate=args.backoff_rate,
                                                      wait_time=random.random()*args.initial_wait))

                last_time_ids[url_name] = ids_included
           

        # ensure things are written for followers
        sys.stdout.flush()
        yield from asyncio.sleep(args.poll_interval)

loop = asyncio.get_event_loop()

if args.articles or args.article_stats:
    logging.info("Collecting articles from %s" % ARTICLE_URL_KEYS)
    article_apis = ARTICLE_URL_KEYS
else:
    article_apis = []

if args.feeds or args.feed_stats:
    logging.info("Collecting feeds from %s" % URL_KEYS)
    feed_apis = URL_KEYS
else:
    feed_apis = []

if args.stdin:
    loop.run_until_complete(collect_stdin(article_apis, args.article_stats, args.since,
                                          feed_apis, args.feed_stats,
                                          args.cache, args.key, args.cookie))
    loop.close()
else:
    loop.run_until_complete(collect_main(args.apis, args.since, args.repeat, article_apis, args.article_stats, args.cache, args.key, args.cookie))
    loop.close()


