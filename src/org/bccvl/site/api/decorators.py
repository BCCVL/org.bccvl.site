import inspect
import json
import logging
import os.path
import sys
from urlparse import urlsplit

from decorator import decorator
from zope import contenttype
from zope.annotation.interfaces import IAnnotations
from zope.publisher.browser import BrowserView
from zope.publisher.interfaces.browser import IBrowserRequest

from org.bccvl.site.utils import decimal_encoder


LOG = logging.getLogger(__name__)


class IJSONRequest(IBrowserRequest):
    """
    Marker interface for request
    """

    pass


class JSONErrorView(BrowserView):

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        self.request.response['CONTENT-TYPE'] = 'application/json'
        if self.__parent__.errors:
            return json.dumps({
                'errors': [
                    self.__parent__.errors
                ]
            })
        else:
            # assume standard exception
            return json.dumps({
                'errors': [{
                    'title': self.context.message
                }]
            })


def api(schema):
    """A Class decorator to build a dictionary with all publishable methods.

    Use schema to annotate class. Link relations found in schema, are
    used to annotate methods on class as api methods, which are published.

    schema can be a dictionary or a string. If it is a string, it will be
    resolved as file name, and the schema will be read from this file.
    """
    if isinstance(schema, str):
        # determine current path ...
        # @api is supposed to be used on module level
        #    -> TODO: maybe get current folder from cls in annotate method?
        path = os.path.dirname(sys._getframe().f_globals['__file__'])
        # TODO: check if file exists, also would be nice to auto reload schema
        #       in debug mode
        schema = json.load(open(os.path.join(path, schema), 'r'))
    else:
        schema = {}

    def annotate(cls):
        # apply schema properties to class
        for prop in ('title', 'description'):
            if not getattr(cls, prop):
                setattr(cls, prop, schema[prop])

        # annotate methods
        # make sure we have a new dict on the class (avoid changing base class
        # __methods__
        cls.__methods__ = {}
        methods = dict(inspect.getmembers(cls, inspect.ismethod))
        for link in schema['links']:
            # rel is used to match up link relations with methods
            # TODO: assumes there is at least a non pattern string at
            #       the end of href .... will fail for e.g. href="{id}"
            # TODO: alternative would be o either map rel to method name
            #       or add custom property 'method' (which is still supported)
            methodname = urlsplit(link['href']).path.rpartition('/')[-1]
            if methodname in methods:
                # store link information about method
                if methodname in cls.__methods__:
                    # we already have a schema assigned...
                    import ipdb
                    ipdb.set_trace()
                # set defaults:
                link.setdefault('method', 'GET')
                link.setdefault('encType', 'application/json')
                # TODO: schema annotation should be a list or similar,
                #       to support multiple encType and methods
                # add method to __methods__ dict to enable view lookup
                cls.__methods__[methodname] = link
            else:
                LOG.warn("Method '%s' from schema not defined on class '%s'",
                         methodname, cls)
        return cls

    return annotate


# self passed in as *args
@decorator
def returnwrapper(f, *args, **kw):
    """
    A function wrapped with this will either return text/xml or application/json.


    """
    # TODO: do some generic form validation in here:
    #       see http://code.google.com/p/mimeparse/
    #       self.request.get['HTTP_ACCEPT']
    #       self.request.get['CONTENT_TYPE']
    #       self.request.get['method'']
    #       in case of post extract parameters and pass in?
    #       jsonrpc:
    #            content-type: application/json-rpc (or application/json,
    #            application/jsonrequest) accept: application/json-rpc (or
    #            --""--)
    #       jsonapi? application/vnd.api+json?

    isxmlrpc = False
    view = args[0]
    try:
        # TODO: could I ask the the request somehow? (ZPublisher should have
        # created some IXMLRPCRequest?
        # NOTE: parsing may fail esp. for GET requests where there is no
        #       content
        ct = contenttype.parse.parse(view.request['CONTENT_TYPE'])
        if ct[0:2] == ('text', 'xml'):
            # we have xmlrpc
            isxmlrpc = True
    except Exception as e:
        # it's not valid xmlrpc
        # TODO: log this ?
        pass

    try:
        if not isxmlrpc:
            # TODO: apply JSONAPIRequest marker to request, so that error templates
            #       can be looked up?
            from zope.interface import alsoProvides
            from .decorators import IJSONRequest
            alsoProvides(view.request, IJSONRequest)

        # Can't really parse here, as the zope engine expects that all parameters
        #     required by the wrapped method are passed in the request (and zope
        #     can only parse form / url parameters)
        # if ct[0:2] == ('application', 'json'):
        #     # TODO: assumes that content type is only set on request methods
        #     #       that allow body content
        #     # TODO: check content length?
        #     # TODO: could do json schema validation here
        #     input = json.load(view.request.BODYFILE)
        #     # if isinstance(input, list):
        #     #     args = input
        #     # elif isinstance(input, dict):
        #     #     kw = input
        #     # else:
        #     #     # TODO: is this valid?
        #     #     args = [input]
        #     args = [input]

        ret = f(*args, **kw)
    except Exception as e:
        if isxmlrpc:
            # let zope handle it
            raise
        # TODO: special handlings for:
        #    unauthorized -> json
        #    others?

        # view.request.response.setStatus(e.__class__)
        # view.request.response['CONTENT-TYPE'] = 'application/json'
        # return '{"errors": "test error"}'

        # view.request.response._error_format = 'application/json'
        # view.request.response.setBody('{"error": "test error"}')
        raise
    # return ACCEPT encoding here or IStreamIterator, that encodes
    # stuff on the fly could handle response encoding via
    # request.setBody ... would need to replace response instance of
    # request.response. (see ZPublisher.xmlprc.response, which wraps a
    # default Response)
    # FIXME: this is a bad workaround for - this method sholud be wrapped around tools and then be exposed as BrowserView ... ont as tool and BrowserView
    #        we call these wrapped functions internally, from templates and
    #        as ajax calls and xmlrpc calls, and expect different return encoding.
    #        ajax: json
    #        xmlrpc: xml, done by publisher
    #        everything else: python

    # if we don't have xmlrpc we serialise to json
    if not isxmlrpc:
        # TODO: maybe add HTTP link header to refer to schema?
        ret = json.dumps(ret, default=decimal_encoder)
        annots = IAnnotations(view.request)
        if 'json.schema' in annots:
            ctype = 'application/json;profile="{}"'.format(
                annots['json.schema'])
        else:
            ctype = 'application/json'
        view.request.response['CONTENT-TYPE'] = ctype
        # FIXME: caching headers should be more selective
        # prevent caching of ajax results... should be more selective here
    return ret
