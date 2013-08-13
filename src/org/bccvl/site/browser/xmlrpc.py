from Products.Five.browser import BrowserView
from zope.publisher.browser import BrowserView as Z3BrowserView
from zope.publisher.browser import BrowserPage as Z3BrowserPage #+ publishTraverse
from zope.publisher.interfaces import IPublishTraverse,  NotFound
from functools import wraps
from decorator import decorator
from plone.app.uuid.utils import uuidToObject


# self passed in as *args
@decorator # well behaved decorator that preserves signature so tha mapply can inspecit it
def returnwrapper(f, *args,  **kw):
    # self.request.get['HTTP_ACCEPT']
    # self.request.get['CONTENT_TYPE']
    # self.request.get['method'']
    # ... decide on what type of call it is ... json?(POST), xmlrpc?(POST), url-call? (GET)
    # in case of post extract parameters and pass in?
    # jsonrpc:
    #    content-type: application/json-rpc (or application/json, application/jsonrequest)
    #    accept: application/json-rpc (or --""--)
    ret = f(*args, **kw)
    # return ACCEPT encoding here or IStreamIterator, that encodes stuff on the fly
    # could handle response encoding via request.setBody ... would need to replace response
    #   instance of request.response. (see ZPublisher.xmlprc.response, which wraps a default Response)
    return ret


class DataSetManager(BrowserView):

    @returnwrapper
    def getDetails(self, datasetid):
        return {'a': "test1",
                'id': datasetid}
    # return: type, id, format, source, path, metadata dict

    @returnwrapper
    def getPath(self, datasetid):
        ob = uuidToObject(datasetid)
        if ob is None:
            raise NotFound(self.context,  datasetid,  self.request)
        return {'path': ob.absolute_url_path()}

    @returnwrapper
    def getMetadat(self, datasetid):
        return {'a': 'test3',
                'id': datasetid}


class JobManager(BrowserView):

    @returnwrapper
    def getJobs(self):
        return ['job1', 'job2']

    @returnwrapper
    def getJobStatus(self,  jobid):
        return {'status': 'running'}


class ExperimentManager(BrowserView):

    @returnwrapper
    def getExperiments(self, id):
        return {'data': 'experimentmetadata+datasetids+jobid'}
