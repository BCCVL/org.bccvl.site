from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
#from zope.publisher.browser import BrowserView as Z3BrowserView
#from zope.publisher.browser import BrowserPage as Z3BrowserPage  # + publishTraverse
#from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces import NotFound
#from functools import wraps
from decorator import decorator
from plone.app.contenttypes.interfaces import IFile
from plone.app.uuid.utils import uuidToObject
from plone.uuid.interfaces import IUUID

# self passed in as *args
@decorator  # well behaved decorator that preserves signature so that apply can inspect it
def returnwrapper(f, *args, **kw):
    # see http://code.google.com/p/mimeparse/
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
    # instance of request.response. (see ZPublisher.xmlprc.response, which
    # wraps a default Response)
    return ret


def getdsmetadata(ds):
    # extract info about files
    return {'url': ds.absolute_url(),
            'id': IUUID(ds),
            'mimetype': ds.file.contentType,
            'filename': ds.file.filename,
            'file': '{}/@@download/file/{}'.format(ds.absolute_url(),
                                                   ds.file.filename)}


class DataSetManager(BrowserView):

    @returnwrapper
    def getMetadata(self, datasetid):
        ds = uuidToObject(datasetid)
        if ds is None:
            raise NotFound(self.context,  datasetid,  self.request)
        return getdsmetadata(ds)

    # return: type, id, format, source, path, metadata dict

    @returnwrapper
    def getPath(self, datasetid):
        ds = uuidToObject(datasetid)
        if ds is None:
            raise NotFound(self.context,  datasetid,  self.request)
        return {'url': ds.absolute_url()}


class DataSetAPI(BrowserView):

    @returnwrapper
    def getMetadata(self):
        return getdsmetadata(self.context)


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
