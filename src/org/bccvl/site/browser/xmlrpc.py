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
import logging
from gu.z3cform.rdf.interfaces import IGraph, IORDF
from zope.component import getUtility
from rdflib import Namespace
from org.bccvl.site.namespace import BCCPROP
from zope.i18n import translate
NFO = Namespace(u'http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#')
BIOCLIM = Namespace(u'http://namespaces.bccvl.org.au/bioclim#')

LOG = logging.getLogger(__name__)


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

def getbiolayermetadata(ds):
    graph = IGraph(ds)
    ret = {}
    handler = getUtility(IORDF).getHandler()
    for archiveitem in graph.objects(graph.identifier, BCCPROP['hasArchiveItem']):
        item = handler.get(archiveitem)
        ret[item.value(item.identifier, BIOCLIM['bioclimVariable'])] = item.value(item.identifier, NFO['fileName'])
    return ret

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
        status = IJobTracker(self.context).status()
        return status


class ExperimentManager(BrowserView):

    @returnwrapper
    def getExperiments(self, id):
        return {'data': 'experimentmetadata+datasetids+jobid'}


class DataMover(BrowserView):

    @returnwrapper
    def pullOccurrenceFromALA(self, lsid):
        # TODO: check permisions?
        from zope.component import getUtility
        from plone.app.async.interfaces import IAsyncService
        from plone.app.async import service
        async = getUtility(IAsyncService)
        jobinfo = (alaimport, self.context, (lsid, ), {})
        job = async.wrapJob(jobinfo)
        queue = async.getQueues()['']
        job = queue.put(job)
        ret = job.addCallbacks(success=service.job_success_callback,
                               failure=service.job_failure_callback)
        # return message id and localized message
        return (str(ret.status), translate(ret.status))

    @returnwrapper
    def checkALAJobStatus(self, job_id):
        # TODO: check permissions? or maybe git rid of this here and
        #       use job tracking for status. (needs job annotations)
        from xmlrpclib import ServerProxy
        s = ServerProxy(DATA_MOVER)
        ret = s.check_move_status(job_id)
        return ret


# TODO: get data mover location from config
DATA_MOVER = u'http://127.0.0.1:10700/data_mover'
FILE_NAME_TEMPLATE = u'move_job_{id:d}_ala_dataset.json'


def alaimport(context, lsid):
    # jobstatus e.g. {'id': 2, 'status': 'PENDING'}
    import time
    from xmlrpclib import ServerProxy
    from collective.transmogrifier.transmogrifier import Transmogrifier
    import os
    from tempfile import mkdtemp
    path = mkdtemp()
    try:
        # TODO: get data movel location from config
        s = ServerProxy(DATA_MOVER)
        # TODO: fix up params
        jobstatus = s.move({'type': 'ala', 'lsid': lsid},
                     {'host': 'plone',
                      'path': path})
        # TODO: check return status
        while jobstatus['status'] in ('PENDING', "IN_PROGRESS"):
            time.sleep(1)
            jobstatus = s.check_move_status(jobstatus['id'])
        # TODO: call to xmlrpc server might also throw socket errors. (e.g. socket.error: [Errno 61] Connection refused)
        if jobstatus['status'] in ("FAILED",  "REJECTED"):
            # Do something useful here; how to notify user about failure?
            LOG.fatal("ALA import failed %s: %s", jobstatus['status'], jobstatus['reason'])
            return

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
        metadata_file = FILE_NAME_TEMPLATE.format(**jobstatus)
        transmogrifier = Transmogrifier(ds)
        transmogrifier(u'org.bccvl.site.alaimport',
                       alasource={'file': os.path.join(path, metadata_file),
                                  'lsid': lsid})

        # cleanup fake request
        del context.REQUEST
    finally:
        import shutil
        shutil.rmtree(path)
