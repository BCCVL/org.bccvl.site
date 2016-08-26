from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer, providedBy
from zope.component import getSiteManager, getMultiAdapter
from zope.location import locate
from zope.publisher.browser import BrowserView
from zope.publisher.interfaces import NotFound, IPublishTraverse
from zope.traversing.browser.interfaces import IAbsoluteURL

from org.bccvl.site.api.decorators import returnwrapper


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

    @returnwrapper
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
                 },
                {'rel': 'up',
                 'href': purl,
                 'title': self.__parent__.title,
                 'description': self.__parent__.description
                 }
            ]
        }
        # add links to sub services
        for service in self.get_services():
            schema["links"].append({
                "rel": self.linkrel,
                "href": '{id}/' + service.__name__,
                "title": service.title,
                "description": service.description,
                "method": service.method
                #schema, encType
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

    @returnwrapper
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

    def __init__(self, context, request, parent):
        super(BaseService, self).__init__(context, request)
        self.parent = parent
        self.errors = []

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

    @returnwrapper
    def schema(self):
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
            schema['links'].append({
                'rel': 'method',
                'href': '{id}/' + method['schema']['id'],
                'title': method['schema']['title'],
                'description': method['schema']['description'],
                'method': method['schema']['method'],
                'schema': method['schema']['schema'],
                'encType': method['schema']['encType'],
                # TODO: target method['schema'] ... return value
            })
        # self.request.response['CONTENT-TYPE'] = 'application/json;
        # profile=http://json-schema.org/draft-04/hyper-schema#'
        return schema

    def publishTraverse(self, request, name):
        if name == 'schema':
            return self.schema
        try:
            method = self.get_methods(name)
            func = getattr(self, method['method'])
            return func
        except:
            raise NotFound(self, name, request)

    @returnwrapper
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
