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
from org.bccvl.site.interfaces import IJobTracker
from org.bccvl.site import defaults


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
    # DS Manager API on Site Root

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
    # DS Manager API on Dataset

    @returnwrapper
    def getMetadata(self):
        return getdsmetadata(self.context)


class JobManager(BrowserView):
    # job manager on Site Root

    @returnwrapper
    def getJobs(self):
        return ['job1', 'job2']

    @returnwrapper
    def getJobStatus(self,  jobid):
        return {'status': 'running'}


class JobManagerAPI(BrowserView):
    # job manager on experiment

    @returnwrapper
    def getJobStatus(self):
        return IJobTracker(self.context).status()


class ExperimentManager(BrowserView):

    @returnwrapper
    def getExperiments(self, id):
        return {'data': 'experimentmetadata+datasetids+jobid'}


class DataMover(BrowserView):

    @returnwrapper
    def pullOccurrenceFromALA(self, lsid):
        from xmlrpclib import ServerProxy
        s = ServerProxy('http://127.0.0.1:6543/data_mover')
        ret = s.pullOccurrenceFromALA(lsid)
        from zope.component import getUtility
        from plone.app.async.interfaces import IAsyncService
        from plone.app.async import service
        async = getUtility(IAsyncService)
        jobinfo = (alaimport, self.context, (ret, lsid), {})
        job = async.wrapJob(jobinfo)
        queue = async.getQueues()['']
        job = queue.put(job)
        job.addCallbacks(success=service.job_success_callback,
                         failure=service.job_failure_callback)
        return ret

    @returnwrapper
    def checkALAJobStatus(self, job_id):
        from xmlrpclib import ServerProxy
        s = ServerProxy('http://127.0.0.1:6543/data_mover')
        ret = s.checkALAJobStatus(job_id)
        return ret

    @returnwrapper
    def importOccurenceFromALA(self, path, lsid):
        # portal_url = getToolByName(self.context, "portal_url")
        # portal = portal_url.getPortalObject()
        portal = self.context
        ds = portal[defaults.DATASETS_FOLDER_ID]
        from collective.transmogrifier.transmogrifier import Transmogrifier
        transmogrifier = Transmogrifier(ds)
        transmogrifier(u'org.bccvl.site.alaimport',
                       alasource={'path': path,
                                  'lsid': lsid})


def alaimport(context, jobstatus, lsid):
    # jobstatus e.g. {'id': 2, 'status': 'PENDING'}
    import time
    from xmlrpclib import ServerProxy
    from collective.transmogrifier.transmogrifier import Transmogrifier
    import os
    portal_properties = getToolByName(context, 'portal_properties')
    path = portal_properties.site_properties.getProperty('datamover')
    s = ServerProxy('http://127.0.0.1:6543/data_mover')
    while jobstatus['status'] in ('PENDING', "DOWNLOADING"):
        time.sleep(1)
        jobstatus = s.checkALAJobStatus(jobstatus['id'])
    # TODO: check status for errors?
    #       for now assume it always works ;)

    #transmogrify.dexterity.schemaupdater needs a REQUEST on context????
    from ZPublisher.HTTPResponse import HTTPResponse
    from ZPublisher.HTTPRequest import HTTPRequest
    import sys
    response = HTTPResponse(stdout=sys.stdout)
    env = {'SERVER_NAME':'fake_server',
           'SERVER_PORT':'80',
           'REQUEST_METHOD':'GET'}
    request = HTTPRequest(sys.stdin, env, response)

    # Set values from original request
    # original_request = kwargs.get('original_request')
    # if original_request:
    #     for k,v in original_request.items():
    #       request.set(k, v)
    context.REQUEST = request

    ds = context[defaults.DATASETS_FOLDER_ID]
    transmogrifier = Transmogrifier(ds)
    transmogrifier(u'org.bccvl.site.alaimport',
                   alasource={'path': path,
                              'lsid': lsid})

    # cleanup fake request
    del context.REQUEST
