import functools
import inspect
import json
import logging
import os.path
import sys
from urlparse import urlsplit
import xmlrpclib

from zope import contenttype
from zope.annotation.interfaces import IAnnotations
from zope.publisher.browser import BrowserView
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.security.interfaces import IUnauthorized
from zope.security.interfaces import Forbidden

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
        if IUnauthorized.providedBy(self.context):
            # FIXME: here we are hacking the Zope2.App.startup.ZPublisherExceptionHook.__call__
            #        We should have been called from there. Problem is that it re-raises
            #        unauthorised exception and therefore makes it impossible to
            #        override response body.
            # Returned status code is not entirely correct, but at least body
            # content is json
            import sys
            caller = sys._getframe().f_back
            # replace exception class with another that is not re-raised
            caller.f_locals.update({'t': Forbidden})
            import ctypes
            # call python to turn locals dict in other frame into fast
            # variables
            ctypes.pythonapi.PyFrame_LocalsToFast(
                ctypes.py_object(caller), ctypes.c_int(0))
        if self.__parent__.errors:
            return json.dumps({
                'errors': [
                    self.__parent__.errors
                ]
            })
        elif self.context.message:
            # assume standard exception
            return json.dumps({
                'errors': [{
                    'title': self.context.message
                }]
            })
        else:
            return json.dumps({
                'errors': [{
                    'title': 'Sorry, I have no meaningful error message available'
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
                    LOG.warn(
                        "Method %s.%s already published as API method",
                        cls, methodname)
                # set defaults:
                link.setdefault('method', 'GET')
                link.setdefault('encType', 'application/json')
                # TODO: schema annotation should be a list or similar,
                #       to support multiple encType and methods
                # add method to __methods__ dict to enable view lookup
                cls.__methods__[methodname] = link
                # wrap instancemethod as well
                setattr(cls, methodname, api_method(
                    getattr(cls, methodname).im_func))
            else:
                LOG.warn("Method '%s' from schema not defined on class '%s'",
                         methodname, cls)
        return cls

    return annotate


def api_method(f):
    """
    A method decorated with this will process a request according to a defined json hyper schema.
    """
    # TODO: do some generic form validation in here:
    #       see http://code.google.com/p/mimeparse/
    #       self.request.get['HTTP_ACCEPT']
    #       self.request.get['CONTENT_TYPE']
    #       self.request.get['method'']

    @functools.wraps(f)
    def process_request(*args, **kw):
        # instance is passed as first argument. this is usually the current
        # view
        view = args[0]
        ct = None
        # TODO: getting the schema this way is a bit clunky
        link = view.__methods__[f.__name__]
        # TODO: extract correct link if multiple encodings are supported

        # No body on GET, HEAD, DELETE
        if view.request['method'] not in ('GET', 'HEAD', 'DELET'):
            # parse body
            ct = contenttype.parse.parse(view.request['CONTENT_TYPE'])
            if ct[0:2] == ('application', 'json'):
                # it's json, let's parse it and attach to request.form
                # TODO: check request length?
                data = json.load(view.request.BODYFILE)
                # TODO: validate against schema?
                view.request.form.update(data)
        # all other content types and methods should be handled by Zope
        # already

        # validate request method
        # if possible validate request parameters as well / payload

        # methods are expected to check request or parameters
        ret = f(*args, **kw)

        # get result content type
        ctype = link.get('mediaType', 'application/json')
        if ctype == 'application/json':
            # TODO: maybe add HTTP link header to refer to schema?
            ret = json.dumps(ret, default=decimal_encoder)
            annots = IAnnotations(view.request)
            if 'json.schema' in annots:
                ctype = "{};profile={}".format(
                    ctype, annots['json.schema'])
        elif ctype == 'text/xml':
            # we do xml-rpc serialisation here

            ret = xmlrpclib.dumps(
                (ret,), methodresponse=True, allow_none=True)

        else:
            # this really should not happen and is a programming error
            raise Exception('Server Error ... unkown return media type')
        view.request.response['CONTENT-TYPE'] = ctype
        # FIXME: caching headers should be more selective
        # prevent caching of ajax results... should be more selective here
        return ret

    return process_request
