from Products.Five.browser import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.WorkflowCore import WorkflowException
#from zope.publisher.browser import BrowserView as Z3BrowserView
#from zope.publisher.browser import BrowserPage as Z3BrowserPage  # + publishTraverse
#from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces import NotFound
#from functools import wraps
from decorator import decorator
from plone.app.uuid.utils import uuidToObject
from plone.uuid.interfaces import IUUID
from org.bccvl.site.interfaces import IJobTracker
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site import defaults
import logging
from gu.z3cform.rdf.interfaces import IGraph, IORDF
from zope.component import getUtility, queryUtility
from org.bccvl.site.namespace import BCCPROP, BIOCLIM, NFO
from zope.i18n import translate
from zope.schema.vocabulary import getVocabularyRegistry
from zope.schema.interfaces import IContextSourceBinder
from urllib2 import urlopen, Request
from urllib import urlencode
from rdflib import URIRef
from gu.plone.rdf.repositorymetadata import getContentUri
import json
from Products.statusmessages.interfaces import IStatusMessage


LOG = logging.getLogger(__name__)


# self passed in as *args
@decorator  # well behaved decorator that preserves signature so that
            # apply can inspect it
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
    if view.request['CONTENT_TYPE'] == 'text/xml':
        # we have xmlrpc
        isxmlrpc = True

    ret = f(*args, **kw)
    # return ACCEPT encoding here or IStreamIterator, that encodes
    # stuff on the fly could handle response encoding via
    # request.setBody ... would need to replace response instance of
    # request.response. (see ZPublisher.xmlprc.response, which wraps a
    # default Response)

    # if we don't have xmlrpc we serialise to json
    if not isxmlrpc:
        ret = json.dumps(ret)
        view.request.response['CONTENT-TYPE'] = 'text/json'
    return ret


def getdsmetadata(ds):
    # extract info about files
    return {'url': ds.absolute_url(),
            'id': IUUID(ds),
            'mimetype': ds.file.contentType,
            'filename': ds.file.filename,
            'file': '{}/@@download/file/{}'.format(ds.absolute_url(),
                                                   ds.file.filename),
            'layers': getbiolayermetadata(ds)}


def getbiolayermetadata(ds):
    # TODO: use a sparql query to get all infos in one go...
    #       could get layer friendly names as well
    query = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ns: <http://www.bccvl.org.au/individual/>
PREFIX cvocab: <http://namespaces.griffith.edu.au/collection_vocab#>
PREFIX bccprop: <http://namespaces.bccvl.org.au/prop#>
PREFIX bioclim: <http://namespaces.bccvl.org.au/bioclim#>
PREFIX nfo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#>


SELECT ?bvar ?blabel ?fnam WHERE {{
  Graph ?g {{
  <{subject}> a cvocab:Dataset .
  <{subject}> bccprop:hasArchiveItem ?ar .
  }}
  Graph ?a {{
    ?ar bioclim:bioclimVariable ?bvar .
    ?ar nfo:fileName ?fnam .
  }}
  Graph ?b {{
    ?bvar rdfs:label ?blabel .
  }}
}}"""
    # FIXME: need to clean up getContentUri function
    uri = getContentUri(ds)
    q = query.format(subject=uri)
    ret = {}
    handler = getUtility(IORDF).getHandler()
    for row in handler.query(q):
        ret[row['bvar']] = {'label': unicode(row['blabel']),
                            'filename': unicode(row['fnam'])}
    return ret


class DataSetManager(BrowserView):
    # DS Manager API on Site Root

    @returnwrapper
    def getMetadata(self, datasetid):
        ds = uuidToObject(datasetid)
        if ds is None:
            raise NotFound(self.context,  datasetid,  self.request)
        return getdsmetadata(ds)

    @returnwrapper
    def queryDataset(self, genre=None, layers=None):
        pc = getToolByName(self.context, 'portal_catalog')
        params = {'object_provides': IDataset.__identifier__}
        if genre:
            if not isinstance(genre, (tuple, list)):
                genre = (genre, )
            params['BCCDataGenre'] = {'query': [URIRef(g) for g in genre],
                                      'operator': 'or'}
        if layers:
            if not isinstance(layers, (tuple, list)):
                layers = (layers, )
            params['BCCEnviroLayer'] = {'query': [URIRef(l) for l in layers],
                                        'operator': 'and'}
        result = []
        for brain in pc.searchResults(**params):
            result.append({'uuid': brain.UID,
                           'title': brain.Title})
        return result

    @returnwrapper
    def getVocabulary(self, name):
        # TODO: check if there are vocabularies that need to be protected
        vocab = ()
        try:
            vr = getVocabularyRegistry()
            vocab = vr.get(self.context, name)
        except:
            # eat all exceptions
            pass
        if not vocab:
            # try IContextSourceBinder
            vocab = queryUtility(IContextSourceBinder, name=name)
            if vocab is None:
                return []
            vocab = vocab(self.context)
        result = []
        for term in vocab:
            result.append({'token': term.token,
                           'title': term.title})
        return result


class DataSetAPI(BrowserView):
    # DS Manager API on Dataset

    @returnwrapper
    def getMetadata(self):
        return getdsmetadata(self.context)

    @returnwrapper
    def share(self):
        # TODO: status message and redirect are not useful for ajax
        msg = u"Status changed"
        msg_type = 'info'
        try:
            wtool = getToolByName(self.context, 'portal_workflow')
            wtool.doActionFor(self.context,  'publish')
        except WorkflowException as e:
            msg = u"Status change failed"
            msg_type = 'error'
        IStatusMessage(self.request).add(msg, type=msg_type)
        self.request.response.redirect(self.request['HTTP_REFERER'])

    @returnwrapper
    def unshare(self):
        # TODO: status message and redirect are not useful for ajax
        msg = u"Status changed"
        msg_type = 'info'
        try:
            wtool = getToolByName(self.context, 'portal_workflow')
            wtool.doActionFor(self.context,  'retract')
        except WorkflowException as e:
            msg = u"Status change failed"
            msg_type = 'error'
        IStatusMessage(self.request).add(msg, type=msg_type)
        self.request.response.redirect(self.request['HTTP_REFERER'])


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


from ZPublisher.Iterators import IStreamIterator
from zope.interface import implementer


@implementer(IStreamIterator)
class UrlLibResponseIterator(object):

    def __init__(self, resp):
        self.resp = resp
        try:
            self.length = int(resp.headers.getheader('Content-Length'))
        except:
            self.length = 0

    def __iter__(self):
        return self

    def next(self):
        data = self.resp.next()
        if not data:
            raise StopIteration
        return data

    def __len__(self):
        return self.length


class ALAProxy(BrowserView):

    #@returnwrapper ... returning file here ... returnwrapper not handling it properly
    def autojson(self):
        # TODO: do parameter checking and maybe set defaults so that js side doesn't have to do it
        url = 'http://bie.ala.org.au/ws/search/auto.json?{}'.format(
            self.request['QUERY_STRING'])
        return self._dorequest(url)

    #@returnwrapper ... returning file here ... returnwrapper not handling it properly
    def searchjson(self):
        # TODO: do parameter checking and maybe set defaults so that js side doesn't have to do it
        url = 'http://bie.ala.org.au/ws/search.json?{}'.format(
            self.request['QUERY_STRING'])
        return self._dorequest(url)

    #@returnwrapper ... returning file here ... returnwrapper not handling it properly
    def visualisespecies(self):
        url = 'http://bie.ala.org.au/species/Macropus+rufus'
        LOG.info('visualise yay!')
        return self._dorequest(url)

    def _dorequest(self, url):
        # TODO: add headers like:
        #    User-Agent
        #    orig-request
        #    etc...
        req = Request(url)
        # TODO: do proper exception handling
        resp = urlopen(req)
        # TODO: check response code?
        for name in ('Date', 'Pragma', 'Expires', 'Content-Type', 'Cache-Control', 'Content-Language', 'Content-Length', 'transfer-encoding'):
            value = resp.headers.getheader(name)
            if value:
                self.request.response.setHeader(name, value)
        self.request.response.setStatus(resp.code)
        ret = UrlLibResponseIterator(resp)
        if len(ret) != 0:
            # we have a content-length so let the publisher stream it
            return ret
        # we don't have content-length and stupid publisher want's one for stream
        # so let's stream it ourselves.
        while True:
            try:
                data = ret.next()
                self.request.response.write(data)
            except StopIteration:
                break


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
FILE_NAME_TEMPLATE = u'move_job_{id:d}_1_ala_dataset.json'


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

        ds = context[defaults.DATASETS_FOLDER_ID][defaults.DATASETS_SPECIES_FOLDER_ID]
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
