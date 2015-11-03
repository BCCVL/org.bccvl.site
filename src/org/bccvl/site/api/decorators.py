import inspect
from decorator import decorator
from zope import contenttype
from zope.annotation.interfaces import IAnnotations

from org.bccvl.site.utils import DecimalJSONEncoder


def apimethod(name=None, title=None,
              description=None,
              # methods=None,
              #enc_types=None, protos=None,
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
            'method': 'GET',
            'enc_type': 'application/x-www-form-urlencoded',
        }

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
    # make sure we have a new dict on the class (avoid changing base class __methods__
    cls.__methods__ = {}
    for name, func in inspect.getmembers(cls, inspect.ismethod):
        if not getattr(func, '__schema__', None):
            continue
        # we have an api func ,... create a metadata
        schema = func.__schema__
        cls.__methods__[schema['id']] = {
            'method': func.__name__,
            'schema': schema
        }
    return cls


# self passed in as *args
@decorator
def returnwrapper(f, *args, **kw):
    # see http://code.google.com/p/mimeparse/
    # self.request.get['HTTP_ACCEPT']
    # self.request.get['CONTENT_TYPE']
    # self.request.get['method'']
    # ... decide on what type of call it is ... json?(POST),
    #     xmlrpc?(POST), url-call? (GET)

    # in case of post extract parameters and pass in?
    # jsonrpc:
    #    content-type: application/json-rpc (or application/json,
    #    application/jsonrequest) accept: application/json-rpc (or
    #    --""--)

    isxmlrpc = False
    view = args[0]
    try:
        # TODO: could I ask the the request somehow? (ZPublisher should have created some IXMLRPCRequest?
        ct = contenttype.parse.parse(view.request['CONTENT_TYPE'])
        if ct[0:2] == ('text', 'xml'):
            # we have xmlrpc
            isxmlrpc = True
    except Exception as e:
        # it's not valid xmlrpc
        # TODO: log this ?
        pass

    ret = f(*args, **kw)
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
        ret = DecimalJSONEncoder().encode(ret)
        annots = IAnnotations(view.request)
        if 'json.schema' in annots:
            ctype = 'application/json; profile={}'.format(annots['json.schema'])
        else:
            ctype = 'application/json'
        view.request.response['CONTENT-TYPE'] = ctype
        # FIXME: chaching headers should be more selective
        # prevent caching of ajax results... should be more selective here
    return ret
