import inspect
import json

from decorator import decorator
from zope import contenttype
from zope.annotation.interfaces import IAnnotations
from zope.publisher.browser import BrowserView
from zope.publisher.interfaces.browser import IBrowserRequest

from org.bccvl.site.utils import decimal_encoder


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


def apimethod(name=None, title=None,
              description=None,
              method=None,  # TODO: allow more than one method
              encType=None,  # TODO: need multiple encType,
              # protos=None,
              properties=None):
    """Add metadata to a function.

    This metadata is used to publish the method and generate a json
    schema description.

    """
    # methods: GET, POST, PUT, DELETE, ...
    # enc_types: application/x-www-form-urlencoded, mulipart/form-data, application/json
    # protocols: json, xmlrpc, ...
    def annotate(f):
        schema = {
            'id': name or f.__name__,
            'title': title or name or f.__name__,
            'description': description or f.__doc__ or '',
        }
        if method:
            schema['method'] = method
        if encType:
            schema['encType'] = encType

        argspec = inspect.getargspec(f)
        if (properties or argspec.args):
            # TODO: mix properties and argspec together
            schema['schema'] = {
                'properties': properties
            }
        f.__schema__ = schema
        return f

    return annotate


def api(cls):
    """A Class decorator to build a dictionary with all publishable methods.

    Finds all methods which have metadata attached via @apimethod
    decorator, and makes them publishable

    """
    # make sure we have a new dict on the class (avoid changing base class
    # __methods__
    cls.__methods__ = {}
    for name, func in inspect.getmembers(cls, inspect.ismethod):
        if not getattr(func, '__schema__', None):
            continue
        # FIXME: this code is probably never executed
        # we have an api func ,... create a metadata
        schema = func.__schema__
        for attr, default in (('method', 'GET'),
                              ('encType', 'application/x-www-form-urlencoded')):
            if attr not in schema:
                schema[attr] = getattr(cls, attr, default)
        cls.__methods__[schema['id']] = {
            'method': func.__name__,
            'schema': schema
        }
    return cls


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
            ctype = 'application/json; profile={}'.format(
                annots['json.schema'])
        else:
            ctype = 'application/json'
        view.request.response['CONTENT-TYPE'] = ctype
        # FIXME: chaching headers should be more selective
        # prevent caching of ajax results... should be more selective here
    return ret
