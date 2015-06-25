#!/usr/bin/python3
#coding: utf-8

import urllib.request, urllib.response, urllib.error
import os
import re
import time
import logging

class CachingFTURLopener(urllib.request.FancyURLopener):
    def __init__(self, *args, **kwargs):
        if 'cache' in kwargs and kwargs['cache']:
            self.cache = True
            self.cache_dir = kwargs.pop('cache')
        else:
            self.cache = False
            self.cache_dir = None

        if 'cache_errors' in kwargs:
            # Write an empty file to cache if an error is encountered
            self.cache_errors = kwargs['cache_errors']
        else:
            self.cache_errors = False

        if 'throttle' in kwargs:
            self.throttle = kwargs['throttle']
        else:
            self.throttle = 0

        urllib.request.FancyURLopener.__init__(self, *args, **kwargs)

    def http_error_default(self, url, fp, errcode, errmsg, headers):
        if errcode == 404:
            # reconstruct the error as fancy opener threw it away
            raise urllib.error.HTTPError(url, errcode, errmsg, headers, fp)
        elif errcode >= 300 and errcode < 400:
            pass # redirect or other happy error
        else:
            logging.warn('Got unexpected HTTP error %s %s' % (errcode,errmsg))

    def get_url(self, full_url, *args, **kwargs):
        if self.cache and self.cache_dir:
            cache_filename = os.path.join(os.path.expanduser(self.cache_dir),re.sub('[^0-9a-zA-Z]','_',full_url))
            try:
                response = open(cache_filename,'rb').read().decode('utf-8')
                logging.info('Cache hit: %s',full_url)
                return response
            except FileNotFoundError:
                cache_written = False
                try:
                    if self.throttle:
                        time.sleep(self.throttle)
                    response = self.get_url_force(full_url, *args, **kwargs)
                    if response:
                        logging.debug('Cache write: %s',full_url)
                        open(cache_filename,'wb').write(response.encode('utf-8'))
                        cache_written = True
                        return response
                finally:
                    if self.cache_errors and not cache_written:
                        open(cache_filename,'w').write('')
                
        else:
            return self.get_url_force(full_url, *args, **kwargs)

    def get_url_force(self, full_url, key='', cookie='', with_next=False, expect_encoding='utf-8'):
        logging.info('GET: %s %s %s %s' %
                     ((key and 'key') or '   ', (with_next and 'next') or '    ', (cookie and 'cookie' or '      '),
                     full_url))

        if key:
            logging.debug("X-Api-Key: %s" % key)
            self.addheader("X-Api-Key",key)

        if with_next:
            cookie = "FT_SITE=NEXT; " + cookie

        if cookie:
            logging.debug("Cookie: %s..." % cookie[:40])
            self.addheader("Cookie",cookie)

        try:
            response = self.open(full_url).read()
        except urllib.error.HTTPError as e:
            raise e
        except Exception as e:
            logging.warn('API error: %s' % e)
            return None

        try:
            return response.decode(expect_encoding)
        except UnicodeDecodeError as e:
            logging.warn('Response was not in expected encoding %s' % expect_encoding)
            return None
