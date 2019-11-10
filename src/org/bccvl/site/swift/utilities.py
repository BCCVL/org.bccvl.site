import hashlib
import hmac
import os
from time import time
from urlparse import urlsplit
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.interface import implementer
from org.bccvl.site.swift.interfaces import ISwiftUtility
from org.bccvl.site.swift.interfaces import ISwiftSettings


@implementer(ISwiftUtility)
class SwiftUtility(object):

    def generate_temp_url(self, url=None, path=None, duration=300, method='GET'):

        settings = getUtility(IRegistry).forInterface(ISwiftSettings)
        # storage_url contains version and account
        storage_url = getattr(settings, 'storage_url', os.environ.get('OS_STORAGE_URL'))
        storage_url = urlsplit(storage_url)

        if url:
            url = urlsplit(url)
            if storage_url.netloc.rsplit(':', 1)[0] != url.netloc.rsplit(':', 1)[0]:
                # not our swift store
                return url.geturl()
        elif path:
            # build storage url; path contains container name and starts with /
            url = '{0}://{1}{2}{3}'.format(
                storage_url.scheme, storage_url.netloc,
                storage_url.path, path
            )
            url = urlsplit(url)
        else:
            raise Exception('Need either path or url')
        # build temp_url
        key = getattr(settings, 'temp_url_key', os.environ.get('OS_TEMP_URL_KEY'))
        if not key:
            return url.geturl()
        expires = int(time() + duration)
        hmac_body = u"\n".join((method.upper().encode(),
                               str(expires),
                               url.path))
        sig = hmac.new(key.encode('utf-8'),
                       hmac_body.encode('utf-8'),
                       hashlib.sha1).hexdigest()
        # remove legacy port number in swift-url
        if url.port:
           url = url._replace(netloc=url.hostname)
        temp_url = u"{url}?temp_url_sig={sig}&temp_url_expires={expires}".format(
            url=url.geturl(), sig=sig, expires=expires)
        return temp_url
