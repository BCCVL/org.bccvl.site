from gu.plone.rdf.interfaces import IRDFContentTransform
from rdflib import RDF, RDFS, Literal, OWL
from ordf.namespace import FOAF
from org.bccvl.site.content.user import IBCCVLUser
from org.bccvl.site.content.group import IBCCVLGroup
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site.interfaces import IJobTracker
from org.bccvl.site.namespace import DWC
from org.bccvl.site.browser.ws import IDataMover
from gu.repository.content.interfaces import (
    IRepositoryContainer,
    IRepositoryItem,
    )
from plone.app.uuid.utils import uuidToObject
from zc.async.interfaces import COMPLETED
from zope.interface import implementer
from zope.dottedname.resolve import resolve
from gu.plone.rdf.namespace import CVOCAB
from ordf.namespace import DC as DCTERMS
from gu.z3cform.rdf.interfaces import IRDFTypeMapper
from plone.app.contenttypes.interfaces import IFile
from plone.app.async.interfaces import IAsyncService
from plone.app.async import service
from zope.component import getUtility
from gu.z3cform.rdf.interfaces import IGraph
from zc.async import local
import logging

LOG = logging.getLogger(__name__)


@implementer(IRDFTypeMapper)
class RDFTypeMapper(object):

    def __init__(self, context, request, form):
        self.context = context
        self.request = request
        self.form = form

    def applyTypes(self, graph):
        pt = self.form.portal_type
        typemap = {'org.bccvl.content.user': FOAF['Person'],
                   'org.bccvl.content.group': FOAF['Group'],
                   'org.bccvl.content.dataset': CVOCAB['Dataset'],
                   # TODO: remove types below someday
                   'gu.repository.content.RepositoryItem': CVOCAB['Item'],
                   'gu.repository.content.RepositoryContainer': CVOCAB['Collection'],
                   'File': CVOCAB['File']}
        rdftype = typemap.get(pt, OWL['Thing'])
        graph.add((graph.identifier, RDF['type'], rdftype))


@implementer(IRDFContentTransform)
class RDFContentBasedTypeMapper(object):

    def tordf(self, content, graph):
        # We might have a newly generated empty graph here, so let's apply the
        # all IRDFTypeMappers as well
        if IDataset.providedBy(content):
            graph.add((graph.identifier, RDF['type'], CVOCAB['Dataset']))
        elif IBCCVLUser.providedBy(content):
            graph.add((graph.identifier, RDF['type'], FOAF['Person']))
        elif IBCCVLGroup.providedBy(content):
            graph.add((graph.identifier, RDF['type'], FOAF['Group']))  # foaf:Organization
        # TODO: remove types below some day
        elif IRepositoryItem.providedBy(content):
            graph.add((graph.identifier, RDF['type'], CVOCAB['Item']))
        elif IRepositoryContainer.providedBy(content):
            graph.add((graph.identifier, RDF['type'], CVOCAB['Collection']))
        elif IFile.providedBy(content):
            graph.add((graph.identifier, RDF['type'], FOAF['File']))

        graph.add((graph.identifier, RDF['type'], OWL['Thing']))


@implementer(IRDFContentTransform)
class RDFDataMapper(object):

    def tordf(self, content, graph):
        # FIXME: use only one way to describe things ....
        #        see dc - rdf mapping at http://dublincore.org/documents/dcq-rdf-xml/
        #        maybe dc app profile not as good as it might sound, but translated to RDF is better (or even owl)
        # FIXME: maybe move the next part into a separate utility
        # TODO: check content for attributes/interface before trying to access them
        for prop, val in ((DCTERMS['title'], Literal(content.title)),
                          (RDFS['label'], Literal(content.title)),
                          (DCTERMS['description'], Literal(content.description)),
                          (RDFS['comment'], Literal(content.description)),
                          ):
            if not graph.value(graph.identifier, prop):
                graph.add((graph.identifier, prop, val))


@implementer(IJobTracker)
class JobTracker(object):

    def __init__(self, context):
        self.context = context

    def start_job(self, request):
        if not self.has_active_jobs():
            self.context.current_jobs = []
            for func in (uuidToObject(f) for f in self.context.functions):
                # TODO: default queue quota is 1. either set it to a defined value (see: plone.app.asnc.subscriber)
                #       or create and submit job manually
                #job = async.queueJob(execute, self.context, envfile, specfile)
                method = None
                if func is None:
                    # FIXME: hack around predict functions ... implement proper checks
                    # return ('error',
                    #         u"Can't find function {}".format(self.context.functions))
                    from .content.function import Function
                    func = Function()
                    func.method = self.context.functions[0]

                if not func.method.startswith('org.bccvl.compute'):
                    return 'error', u"Method '{}' not in compute package".format(func.method)
                try:
                    method = resolve(func.method)
                except ImportError as e:
                    return 'error', u"Can't resolve method '{}'- {}".format(func.method, e)
                if method is None:
                    return 'error', u"Unknown error, method is None"

                # submit job to queue
                LOG.info("Submit JOB %s to queue", func.method)
                # TODO: do I need request here? (and pass it into this method?)
                job = method(self.context, request)
                self.context.current_jobs.append(job)
            return 'info', u'Job submitted {}'.format(self.status())
        else:
            return 'error', u'Current Job is still running'

    def start_ala_job(self):
        if self.has_active_jobs():
            return 'error', u'Current Job is still running'
        self.context.current_jobs = []
        async = getUtility(IAsyncService)
        md = IGraph(self.context)
        # TODO: this assumes we have an lsid in the metadata
        #       should check for it
        lsid = md.value(md.identifier, DWC['taxonID'])

        jobinfo = (alaimport, self.context, (unicode(lsid), ), {})
        queue = async.getQueues()['']
        job = async.wrapJob(jobinfo)
        job = queue.put(job)
        job.jobid = 'alaimport'
        job.annotations['bccvl.status'] = {
            'step': 0,
            'task': u'Queued'}
        job.addCallbacks(success=service.job_success_callback,
                         failure=service.job_failure_callback)
        self.context.current_jobs = [job]
        return 'info', u'Job submitted {}'.format(self.status())

    def status(self):
        status = []
        for job in self.get_jobs():
            status.append((job.jobid, job.annotations['bccvl.status']['task']))
        return status

    def get_jobs(self):
        return getattr(self.context, 'current_jobs', [])

    def has_active_jobs(self):
        active = False
        for job in self.get_jobs():
            if job.status not in (None, COMPLETED):
                active = True
                break
        return active


# TODO: move stuff below to separate module
def alaimport(dataset, lsid):
    # jobstatus e.g. {'id': 2, 'status': 'PENDING'}
    status = local.getLiveAnnotation('bccvl.status')
    status['task'] = 'Running'
    local.setLiveAnnotation('bccvl.status', status)
    import time
    from collective.transmogrifier.transmogrifier import Transmogrifier
    import os
    from tempfile import mkdtemp
    path = mkdtemp()
    try:
        dm = getUtility(IDataMover)
        # TODO: fix up params
        jobstatus = dm.move({'type': 'ala', 'lsid': lsid},
                            {'host': 'plone', 'path': path})
        # TODO: do we need some timeout here?
        while jobstatus['status'] in ('PENDING', "IN_PROGRESS"):
            time.sleep(1)
            jobstatus = dm.check_move_status(jobstatus['id'])
        if jobstatus['status'] in ("FAILED",  "REJECTED"):
            # TODO: Do something useful here; how to notify user about failure?
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
        context = dataset.__parent__
        context.REQUEST = request

        metadata_file = 'ala_dataset.json'
        status['task'] = 'Transferring'
        local.setLiveAnnotation('bccvl.status', status)
        transmogrifier = Transmogrifier(context)
        transmogrifier(u'org.bccvl.site.alaimport',
                       alasource={'file': os.path.join(path, metadata_file),
                                  'lsid': lsid,
                                  'id': dataset.getId()})

        # cleanup fake request
        del context.REQUEST
        # TODO: catch errors and create state Failed annotation
    finally:
        import shutil
        shutil.rmtree(path)
        status['task'] = 'Completed'
        local.setLiveAnnotation('bccvl.status', status)
