# this should be sent upstream to z3c.form.converter:
#   in case the siglecheckbox-empty-marker is not present in the request,
#   the widget extracts NO_VALUE and passes this on to this converter.toFieldValue
#   which expects the value to be a list.
#   other option would be to make NO_VALUE evaluate to False. bool(NO_VALUE)
#-> possibly related to custom singlechockboxwidget in plone.z3cform? (which renders a radio as workaround?)
#-> empt-marker no longer needed on checkbox


from plone.app.dexterity.behaviors.exclfromnav import IExcludeFromNavigation

IExcludeFromNavigation['exclude_from_nav'].required = False


# plone.namedfile uses blob.consumeFile when loading data from a file
# object/descriptor consumeFile tries to be efficient and moves the
# file instead of copying it. This may have unwanted side effects,
# like on a transaction abort it won't restore the original file. (bad
# for conflicterror retries)
from zope.interface import implementer
from plone.namedfile.interfaces import IStorage
from plone.namedfile.interfaces import NotStorable
import shutil


@implementer(IStorage)
class FileDescriptorStorable(object):

    def store(self, data, blob):
        if not isinstance(data, file):
            raise NotStorable("Could not store data (not of 'file').")

        # The original used consumeFile which tries to move a file if possible
        # filename = getattr(data, "name", None)
        # if filename is not None:
        #     blob.consumeFile(filename)
        #     return
        # Let us use any file object and just copy it
        import logging
        logging.getLogger("BLOB PATCH").info("USE MY BLOB STORAGE ADAPTER")
        dest = blob.open('w')
        # TODO: should we seek to 0?
        shutil.copyfileobj(data, dest)


# updated boolean html attributes to cover html 5 attributes
BOOLEAN_HTML_ATTRS = frozenset([
    # List of Boolean attributes in HTML that should be rendered in
    # minimized form (e.g. <img ismap> rather than <img ismap="">)
    # From http://www.w3.org/TR/xhtml1/#guidelines (C.10)
    # TODO: The problem with this is that this is not valid XML and
    # can't be parsed back!
    "compact", "nowrap", "ismap", "declare", "noshade", "checked",
    "disabled", "readonly", "multiple", "selected", "noresize",
    "defer", "required"
])


boolean_html_attrs = lambda: BOOLEAN_HTML_ATTRS  # Now we have a callable method!


# plone.session.tktauth patches
#   ... these should go upstream,...
#   ... does url (un)quoting of userid (allows ! in userid)
#   ... should fix digest length (use hexdigest) for sha256 digest
# TODO: could monkey patch pyramid compatible sha256 support in here

from socket import inet_aton
from struct import pack
import time
import hmac
import hashlib
from urllib import quote, unquote
from plone.session.tktauth import mod_auth_tkt_digest


def createTicket(secret, userid, tokens=(), user_data='', ip='0.0.0.0', timestamp=None, encoding='utf-8', mod_auth_tkt=False):
    """
    By default, use a more compatible
    """
    if timestamp is None:
        timestamp = int(time.time())
    if encoding is not None:
        userid = userid.encode(encoding)
        tokens = [t.encode(encoding) for t in tokens]
        user_data = user_data.encode(encoding)
    # if type(userid) == unicode:
        # userid = userid.encode('utf-8')

    token_list = ','.join(tokens)

    # ip address is part of the format, set it to 0.0.0.0 to be ignored.
    # inet_aton packs the ip address into a 4 bytes in network byte order.
    # pack is used to convert timestamp from an unsigned integer to 4 bytes
    # in network byte order.
    # Unfortunately, some older versions of Python assume that longs are always
    # 32 bits, so we need to trucate the result in case we are on a 64-bit
    # naive system.
    data1 = inet_aton(ip)[:4] + pack("!I", timestamp)
    data2 = '\0'.join((userid, token_list, user_data))
    if mod_auth_tkt:
        digest = mod_auth_tkt_digest(secret, data1, data2)
    else:
        # a sha256 digest is the same length as an md5 hexdigest
        # TODO: this should be fixed in plone.session....
        #       the digest length should not be fixed and sha256 should also use hexdigest, ... if we patch this here, we have to patch splitTicket and validateTicket as well?
        digest = hmac.new(secret, data1+data2, hashlib.sha256).digest()

    # digest + timestamp as an eight character hexadecimal + userid + !
    ticket = "%s%08x%s!" % (digest, timestamp, quote(userid))
    if tokens:
        ticket += token_list + '!'
    ticket += user_data

    return ticket


def splitTicket(ticket, encoding=None):
    digest = ticket[:32]
    val = ticket[32:40]
    remainder = ticket[40:]
    if not val:
        raise ValueError
    timestamp = int(val, 16) # convert from hexadecimal+

    if encoding is not None:
        remainder = remainder.decode(encoding)
    parts = remainder.split("!")

    if len(parts) == 2:
        userid, user_data = parts
        tokens = ()
    elif len(parts) == 3:
        userid, token_list, user_data = parts
        tokens = tuple(token_list.split(','))
    else:
        raise ValueError

    return (digest, unquote(userid), tokens, user_data, timestamp)


def apply_patched_const(scope, original, replacement):
    """
    Helper method for collective.monkeypatcher to replace
    module level constants.
    """
    setattr(scope, original, replacement())
    return


from Products.CMFPlone.utils import safeToInt
from zope.component import queryUtility
from eea.facetednavigation.plonex import ISolrSearch
import operator
from eea.facetednavigation.widgets.widget import compare


def faceted_widget_vocabulary(self, **kwargs):
        """ Return data vocabulary
        """
        reverse = safeToInt(self.data.get('sortreversed', 0))
        mapping = self.portal_vocabulary()
        catalog = self.data.get('catalog', None)

        if catalog:
            mapping = dict(mapping)
            values = []

            # get values from SOLR if collective.solr is present
            searchutility = queryUtility(ISolrSearch)
            if searchutility is not None and searchutility.getConfig() and searchutility.getConfig().active:
                index = self.data.get('index', None)
                kw = {'facet': 'on',
                  'facet.field': index,    # facet on index
                  'facet.limit': -1,       # show unlimited results
                  'rows':0}                # no results needed
                result = searchutility.search('*:*', **kw)
                try:
                    values = result.facet_counts['facet_fields'][index].keys()
                except (AttributeError, KeyError):
                    pass

            if not values:
                values = self.catalog_vocabulary()

            res = [(val, mapping.get(val, val)) for val in values]
            res.sort(key=operator.itemgetter(1), cmp=compare)
        else:
            res = mapping

        if reverse:
            res.reverse()
        return res


# We have a problem here with our job state indexer.
#   when the indexing queue get's processed at the end of a transaction
#   e.g. when deleteing an experiment the last element in the queue
#        triggers (e.g. /experiments folder) will be reindexed, which triggers
#        our job state indexer which then triggers another indexing queue process.
#        At this stage, the indexing queue has not been emptied and all unindex
#        operations will be re-run again, but will log an error because these
#        objects have been unindexed in the first run already
#  workaround: pop each processed item from the queue, so that they can't be re-run
#        this may cause a bit of a performance hit, as the queue can't optimize
#        already processed elements anymore (but as they have been run already,
#        it's probably not necessary to optimse them anymore)
from zope.component import getSiteManager
from collective.indexing.interfaces import IIndexQueueProcessor
from collective.indexing.config import INDEX, REINDEX, UNINDEX
# TODO: logger (debug) should not be instantiated at module load time
from collective.indexing.queue import InvalidQueueOperation, debug


def indexing_queue_process(self):
    self.optimize()
    if not self.queue:
        return 0
    sm = getSiteManager()
    utilities = list(sm.getUtilitiesFor(IIndexQueueProcessor))
    processed = 0
    for name, util in utilities:
        util.begin()
    # TODO: must the queue be handled independently for each processor?
    while self.queue:
        op, obj, attributes = self.queue.pop()
        for name, util in utilities:
            if op == INDEX:
                util.index(obj, attributes)
            elif op == REINDEX:
                util.reindex(obj, attributes)
            elif op == UNINDEX:
                util.unindex(obj)
            else:
                raise InvalidQueueOperation(op)
        processed += 1
    self.clear()
    return processed
