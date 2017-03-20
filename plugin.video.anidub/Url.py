# -*- coding: utf-8 -*-

import os
import urllib
import urllib2
import cookielib
import xbmc
from debug import CDebug


class Url:
    headers = {
        'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1) ; .NET CLR 1.1.4322; .NET CLR 2.0.50727; .NET CLR 3.0.4506.2152; .NET CLR 3.5.30729; .NET4.0C)',
        'Accept': 'text/html, application/xml, application/xhtml+xml, image/png, image/jpeg, image/gif, image/x-xbitmap, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Accept-Charset': 'utf-8, utf-16, *;q=0.1',
        'Accept-Encoding': 'identity, *;q=0'
    }

    def __init__(self, use_auth=False, auth_state=False):
        self.use_auth = use_auth
        if self.use_auth:
            self.cj = cookielib.MozillaCookieJar()
            self.url_opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))
            self.auth_state = auth_state
            self.sid_file = ''
            self.search_cookie_name = 'dle_user_id'
            self.auth_url = ''
            self.auth_post_data = {}
        else:
            self.url_opener = urllib2.build_opener()
        self.cb_auth_ok = None
        self.download_dir = None
        self.show_errors = True
        self.log = CDebug(prefix='URL')

    def get(self, target, referer='', post=None):
        Url.headers['Referer'] = referer
        if self.use_auth:
            if not self.auth_try():
                return None
        try:
            url = self.url_opener.open(urllib2.Request(url=target, data=post, headers=Url.headers))
            data = url.read()
            return data
        except Exception, e:
            self.log(target + ' ' + e)
            if self.show_errors:
                xbmc.executebuiltin('XBMC.Notification("HTTP_ERROR", "%s", 3000, "")' % e)
            return None

    def download_file(self, target, referer='', post=None, dest_name=None):
        if not self.download_dir:
            return None
        Url.headers['Referer'] = referer
        if self.use_auth:
            if not self.auth_try():
                return None
        try:
            if not dest_name:
                dest_name = os.path.basename(target)
            url = self.url_opener.open(urllib2.Request(url=target, data=post, headers=Url.headers))
            fl = open(os.path.join(self.download_dir, dest_name), "wb")
            fl.write(url.read())
            fl.close()
            return os.path.join(self.download_dir, dest_name)
        except urllib2.HTTPError, e:
            if int(e.getcode()) == 503:
                from cfscrape import CloudflareScraper
                scraper = CloudflareScraper()
                self.log('Loading CF protected image %s > %s' % (target, dest_name))
                fl = open(os.path.join(self.download_dir, dest_name), "wb")
                c = scraper.get(target).content
                fl.write(c)
                fl.close()
                return os.path.join(self.download_dir, dest_name)
            else:
                self.log(target + ' ' + e)
                if self.show_errors:
                    xbmc.executebuiltin('XBMC.Notification("HTTP_ERROR", "%s", 3000, "")' % e)
                return None


    def auth_try(self):
        if not self.use_auth or self.sid_file == '' or self.auth_url == '':
            return False
        if self.auth_state:
            try:
                self.cj.load(self.sid_file)
                auth = self._search_cook_in_cj()
            except:
                self.url_opener.open(urllib2.Request(self.auth_url, urllib.urlencode(self.auth_post_data), Url.headers))
                auth = self._search_cook_in_cj()
                self.cj.save(self.sid_file)
        else:
            self.url_opener.open(urllib2.Request(self.auth_url, urllib.urlencode(self.auth_post_data), Url.headers))
            auth = self._search_cook_in_cj()
            self.cj.save(self.sid_file)
        self.auth_state = auth
        if self.cb_auth_ok:
            self.cb_auth_ok()
        return auth

    def _search_cook_in_cj(self):
        for cook in self.cj:
            if cook.name == self.search_cookie_name:
                return True
        return False

