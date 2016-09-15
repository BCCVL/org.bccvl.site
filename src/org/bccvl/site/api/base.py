from Acquisition import aq_parent

from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer, providedBy, alsoProvides
from zope.component import getSiteManager, getMultiAdapter
from zope.location import locate
from zope.publisher.browser import BrowserView
from zope.publisher.interfaces import NotFound, IPublishTraverse
from zope.traversing.browser.interfaces import IAbsoluteURL

from org.bccvl.site.api.decorators import api_method, IJSONRequest
from org.bccvl.site.api.interfaces import IAPIService, IAPITraverser


@implementer(IPublishTraverse)
class BaseAPITraverser(BrowserView):
    #
    # supports lookup of registered services
    # supports self.url/schema
    # supports self.__call__ description (to schema)

    title = None
    description = None
    service_iface = None
    linkrel = None

    def __init__(self, context, request, parent=None):
        super(BaseAPITraverser, self).__init__(context, request)
        # we are moving into API land, let's annotate the request object if
        # necessary (mostly needed to avoid Plone's default error handling)
        if not IJSONRequest.providedBy(self.request):
            alsoProvides(self.request, IJSONRequest)
        self.parent = parent

    def lookup_service(self, name):
        service = getMultiAdapter((self.context, self.request, self),
                                  self.service_iface, name)
        locate(service, self, name)
        return service

    def get_services(self, name=None):
        # Looks for adapters (context, request, self) -> IAPIService
        #
        # assumes: self.service_iface
        if name is None:
            service_list = []
            # return list of services
            sm = getSiteManager()
            services = dict(sm.adapters.lookupAll(
                map(providedBy, (self.context, self.request, self)), self.service_iface))
            for name in services.keys():
                service_list.append(self.lookup_service(name))
            return service_list
        else:
            return self.lookup_service(name)

    @api_method
    def schema(self):
        # """
        # assumes: self.title, description, __name__, method
        url = getMultiAdapter((self, self.request), IAbsoluteURL)()
        purl = getMultiAdapter((self.__parent__, self.request), IAbsoluteURL)()
        schema = {
            "$schema": "http://json-schema.org/draft-04/hyper-schema#",
            'title': self.title,
            'description': self.description,
            #'id': self.__name__ + '/schema',
            'type': 'object',
            'links': [
                {'rel': 'self',
                 'href': url,  # '{id}',
                 }
            ]
        }
        parent = aq_parent(self)
        if (parent and (IAPITraverser.providedBy(parent) or IAPIService.providedBy(parent))):
            schema['links'].append(
                {'rel': 'up',
                 'href': purl,
                 'title': parent.title,
                 'description': parent.description
                 }
            )

        # add links to sub services
        for service in self.get_services():
            schema["links"].append({
                "rel": self.linkrel,  # the service id/title/whatever
                "href": '{id}/' + service.__name__,
                "title": service.title,
                "description": service.description,
                "method": 'GET'  # this is always get for sub service traversers
            })
        # self.request.response['CONTENT-TYPE'] = 'application/json;
        # profile=http://json-schema.org/draft-04/hyper-schema#'
        return schema

    def publishTraverse(self, request, name):
        if name == 'schema':
            return self.schema
        try:
            return self.get_services(name)
        except:
            raise NotFound(self, name, request)

    @api_method
    def __call__(self, *args, **kw):
        # TODO: IAbsoluteURL does not ad @@ for view name
        url = getMultiAdapter((self, self.request), IAbsoluteURL)()
        IAnnotations(self.request)['json.schema'] = '{}/schema'.format(url)
        # self.request.response["access-control-allow-origin"] = "*"
        # "access-control-allow-headers": "Content-Type, api_key, Authorization",
        # "access-control-allow-methods": "GET, POST, DELETE, PUT",
        return {
            'id': self.__name__,
            'title': self.title,
            'description': self.description,
        }


@implementer(IPublishTraverse)
class BaseService(BrowserView):

    __name__ = None

    title = None
    description = None
    __methods__ = None
    errors = None
    # should we store __schema__ here?

    def __init__(self, context, request, parent):
        super(BaseService, self).__init__(context, request)
        self.parent = parent
        self.errors = []

    # TODO: rename record_error to set/add_error or so?
    def record_error(self, title, status=None, detail=None, source=None):
        error = {'title': title}
        if status:
            error['status'] = status
        if detail:
            error['detail'] = detail
        if source:
            error['source'] = source
        self.errors.append(error)

    def get_methods(self, name=None):
        if name == None:
            return self.__methods__.values()
        if name in self.__methods__:
            return self.__methods__[name]
        raise NotFound(self, name, self.request)

    @api_method
    def schema(self):
        # TODO: could just return original schema?
        url = getMultiAdapter((self, self.request), IAbsoluteURL)()
        purl = getMultiAdapter((self.__parent__, self.request), IAbsoluteURL)()
        schema = {
            "$schema": "http://json-schema.org/draft-04/hyper-schema#",
            'title': self.title,
            'description': self.description,
            #'id': self.__name__ + '/schema',
            'type': 'object',
            'links': [
                {'rel': 'self',
                 'href': url,  # '{id}',
                 },
                {'rel': 'up',
                 'href': purl,
                 'title': self.__parent__.title,
                 'description': self.__parent__.description
                 }
            ]
        }
        # add method infos:
        for method in self.get_methods():
            schema['links'].append(method)
        # self.request.response['CONTENT-TYPE'] = 'application/json;
        # profile=http://json-schema.org/draft-04/hyper-schema#'
        return schema

    def publishTraverse(self, request, name):
        if name == 'schema':
            return self.schema
        try:
            method = self.get_methods(name)
            func = getattr(self, name)  # method['method'])
            return func
        except:
            raise NotFound(self, name, request)

    @api_method
    def __call__(self, *args, **kw):
        # TODO: IAbsoluteURL does not ad @@ for view name
        url = getMultiAdapter((self, self.request), IAbsoluteURL)()
        # self.request.response["access-control-allow-origin"] = "*"
        IAnnotations(self.request)['json.schema'] = '{}/schema'.format(url)
        # "access-control-allow-headers": "Content-Type, api_key, Authorization",
        # "access-control-allow-methods": "GET, POST, DELETE, PUT",
        return {
            'id': self.__name__,
            'title': self.title,
            'description': self.description
        }
