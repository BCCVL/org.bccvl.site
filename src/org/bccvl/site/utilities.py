from gu.plone.rdf.interfaces import IRDFContentTransform
from zope.interface import implements
from rdflib import RDF, RDFS, Literal, OWL
from ordf.namespace import FOAF
from org.bccvl.site.content.user import IBCCVLUser
from org.bccvl.site.content.group import IBCCVLGroup
from org.bccvl.site.content.experiment import IExperiment
from org.bccvl.site.interfaces import IJobTracker
from gu.repository.content.interfaces import IRepositoryContainer, IRepositoryItem
from org.bccvl.compute import bioclim,  brt
from plone.app.uuid.utils import uuidToObject
from zope.component import getUtility
from plone.app.async.interfaces import IAsyncService
from plone.app.async import service
from zc.async.interfaces import COMPLETED
from zope.component import adapter
from zope.interface import implementer
from zope.dottedname.resolve import resolve
from gu.plone.rdf.namespace import CVOCAB
from ordf.namespace import DC as DCTERMS


class RDFTypeMapper(object):

    implements(IRDFContentTransform)

    def tordf(self, content, graph):
        if IRepositoryItem.providedBy(content):
            graph.add((graph.identifier, RDF['type'], CVOCAB['Item']))
        elif IRepositoryContainer.providedBy(content):
            graph.add((graph.identifier, RDF['type'], CVOCAB['Collection']))
        elif IBCCVLUser.providedBy(content):
            graph.add((graph.identifier, RDF['type'], FOAF['Person']))
        elif IBCCVLGroup.providedBy(content):
            graph.add((graph.identifier, RDF['type'], FOAF['Group']))  # foaf:Organization

        graph.add((graph.identifier, RDF['type'], OWL['Thing']))
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


@adapter(IExperiment)
@implementer(IJobTracker)
class JobTracker(object):

    def __init__(self, context):
        self.context = context

    def start_job(self):
        func = uuidToObject(self.context.functions)

        async = getUtility(IAsyncService)
        # TODO: default queue quota is 1. either set it to a defined value (see: plone.app.asnc.subscriber)
        #       or create and submit job manually
        #job = async.queueJob(execute, self.context, envfile, specfile)
        method = None
        if func is None:
            return 'error', u"Can't find function {}".format(self.context.functions)
        else:
            if not func.method.startswith('org.bccvl.compute'):
                return 'error', u"Method '{}' not in compute package".format(func.method)
            try:
                method = resolve(func.method)
            except ImportError:
                return 'error', u"Can't resolve method '{}'".format(func.method)
        if method is None:
            return 'error', u"Unknown error, method is None"
        # TODO: add some more checks, whether we have a valid function
        #      e.g. interface provided, registered in tool, etc...
        jobinfo = (method, self.context, (), {})
        # TODO: current job status
        if self.get_job_status() in (None, COMPLETED):
            job = async.wrapJob(jobinfo)
            queue = async.getQueues()['']
            job = queue.put(job)
            # don't forget the plone.app.async notification callbacks
            job.addCallbacks(success=service.job_success_callback,
                            failure=service.job_failure_callback)
            self.context.current_job = job
            return 'info', u'Job submitted {}'.format(job.status)
        else:
            return 'error', u'Current Job is still running'

    def get_job_status(self):
        """

        return status-id, status-msg
        """
        job = getattr(self.context, 'current_job', None)
        if job is not None:
            # job.result contains possible error message (e.g. twisted.Failure)
            return job.status
        return None
