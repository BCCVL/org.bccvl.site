from gu.plone.rdf.interfaces import IRDFContentTransform
from rdflib import RDF, RDFS, Literal, OWL
from ordf.namespace import FOAF
from org.bccvl.site.content.user import IBCCVLUser
from org.bccvl.site.content.group import IBCCVLGroup
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site.content.interfaces import ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment
from org.bccvl.site.interfaces import IJobTracker, IComputeMethod
from org.bccvl.site.namespace import DWC, BCCPROP
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
from zope.component import getUtility, adapter, queryUtility
from gu.z3cform.rdf.interfaces import IGraph
from gu.z3cform.rdf.utils import Period
from zc.async import local
from plone.dexterity.utils import createContentInContainer
from datetime import datetime
from zope.schema.interfaces import IVocabularyFactory
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
            # TODO: support language tagged values (e.g. remove only
            #       same language first and add new values)
            if not graph.value(graph.identifier, prop):
                graph.add((graph.identifier, prop, val))


@implementer(IJobTracker)
class JobTracker(object):

    def __init__(self, context):
        self.context = context

    def status(self):
        status = []
        for job in self.get_jobs():
            status.append((job.jobid, job.annotations['bccvl.status']['task']))
        return status

    def get_jobs(self):
        return getattr(self.context, 'current_jobs', [])

    def has_active_jobs(self):
        # FIXME: check all results for active jobs
        active = False
        for job in self.get_jobs():
            if job.status not in (None, COMPLETED):
                active = True
                break
        return active

    def clear_jobs(self):
        self.context.current_jobs = []

    def add_job(self, job):
        self.context.current_jobs.append(job)

    def start_job(self, request):
        raise NotImplementedError()


# TODO: should this be named adapter as well in case there are multiple
#       different jobs for experiments
@adapter(ISDMExperiment)
class SDMJobTracker(JobTracker):

    def start_job(self, request):
        # split sdm jobs across multiple algorithms,
        # and multiple species input datasets
        # TODO: rethink and maybe split jobs based on enviro input datasets?
        if not self.has_active_jobs():
            self.clear_jobs()
            for func in (uuidToObject(f) for f in self.context.functions):
                # get utility to execute this experiment
                method = queryUtility(IComputeMethod,
                                      name=ISDMExperiment.__identifier__)
                if method is None:
                    return ('error',
                            u"Can't find method to run SDM Experiment")
                # create result object:
                # TODO: refactor this out into helper method
                title = u'%s - %s %s' % (self.context.title, func.getId(),
                                         datetime.now().isoformat())
                result = createContentInContainer(
                    self.context,
                    'gu.repository.content.RepositoryItem',
                    title=title)

                # Build job_params store them on result and submit job
                result.job_params = {
                    'resolution': self.context.resolution,
                    'function': func.getId(),
                    'species_occurrence_dataset': self.context.species_occurrence_dataset,
                    'species_absence_dataset': self.context.species_absence_dataset,
                    'species_pseudo_absence_points': self.context.species_pseudo_absence_points,
                    'species_number_pseudo_absence_points': self.context.species_number_pseudo_absence_points,
                    'environmental_datasets': self.context.environmental_datasets,
                }
                # add toolkit params:
                result.job_params.update(self.context.parameters[func.getId()])
                # submit job
                LOG.info("Submit JOB %s to queue", func.getId())
                job = method(result, func)
                self.add_job(job)
            return 'info', u'Job submitted {}'.format(self.status())
        else:
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well
@adapter(IProjectionExperiment)
class ProjectionJobTracker(JobTracker):

    def start_job(self, request):
        if not self.has_active_jobs():
            # split jobs across future climate datasets
            self.clear_jobs()
            for dsbrain in self.context.future_climate_datasets():
                # get utility to execute this experiment
                method = queryUtility(IComputeMethod,
                                      name=IProjectionExperiment.__identifier__)
                if method is None:
                    return ('error',
                            u"Can't find method to run Projection Experiment")
                # create result object:
                # get more metadata about dataset
                dsobj = dsbrain.getObject()
                dsmd = IGraph(dsobj)
                emsc = dsmd.value(dsmd.identifier, BCCPROP['emissionscenario'])
                gcm = dsmd.value(dsmd.identifier, BCCPROP['gcm'])
                period = dsmd.value(dsmd.identifier, DCTERMS['temporal'])
                # get display values for metadata
                emsc = emsc.split('#', 1)[-1] if emsc else None
                gcm = gcm.split('#', 1)[-1] if gcm else None
                year = Period(period).start if period else None

                title = u'{} - project {}_{}_{} {}'.format(
                    self.context.title, emsc, gcm, year,
                    datetime.now().isoformat())
                result = createContentInContainer(
                    self.context,
                    'gu.repository.content.RepositoryItem',
                    title=title)

                # build job_params and store on result
                result.job_params = {
                    'resolution': self.context.resolution,
                    'species_distribution_models': self.context.species_distribution_models,
                    # TODO: URI values or titles?
                    'year': year,
                    'emission_scenario': emsc,
                    'climate_models': gcm,
                    'future_climate_datasets': dsbrain.UID,
                }

                # submit job
                LOG.info("Submit JOB project to queue")
                job = method(result, "project")  # TODO: wrong interface
                self.add_job(job)
            return 'info', u'Job submitted {}'.format(self.status())
        else:
            # TODO: in case there is an error should we abort the transaction
            #       to cancel previously submitted jobs?
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well
@adapter(IBiodiverseExperiment)
class BiodiverseJobTracker(JobTracker):

    def start_job(self, request):
        # TODO: split biodiverse job across years, gcm, emsc
        if not self.has_active_jobs():
            self.clear_jobs()
            # get utility to execute this experiment
            method = queryUtility(IComputeMethod,
                                  name=IBiodiverseExperiment.__identifier__)
            if method is None:
                return ('error',
                        u"Can't find method to run Biodiverse Experiment")

            # iterate over all datasets and group them by emsc,gcm,year
            datasets = {}
            for projds in self.context.projection:
                dsobj = uuidToObject(projds['dataset'])
                dsmd = IGraph(dsobj)
                emsc = dsmd.value(dsmd.identifier, BCCPROP['emissionscenario'])
                gcm = dsmd.value(dsmd.identifier, BCCPROP['gcm'])
                period = dsmd.value(dsmd.identifier, DCTERMS['temporal'])
                year = Period(period).start if period else None
                key = (emsc, gcm, year)
                if key not in datasets:
                    datasets[key] = []
                datasets[key].append(projds)

            # create one job per dataset group
            for key, datasets in datasets.items():
                (emsc, gcm, year) = key
                emsc = emsc.split('#', 1)[-1] if emsc else None
                gcm = gcm.split('#', 1)[-1] if gcm else None

                # create result object:
                title = u'{} - biodiverse {}_{}_{} {}'.format(
                    self.context.title, emsc, gcm, year,
                    datetime.now().isoformat())
                result = createContentInContainer(
                    self.context,
                    'gu.repository.content.RepositoryItem',
                    title=title)

                # build job_params and store on result
                job_params = {
                    # datasets is a list of dicts with 'threshold' and 'uuid'
                    'projections': datasets,
                    'cluster_size': self.context.cluster_size,
                }
                result.job_params = job_params

                # submit job to queue
                LOG.info("Submit JOB Biodiverse to queue")
                job = method(result, "biodiverse")  # TODO: wrong interface
                self.add_job(job)
            return 'info', u'Job submitted {}'.format(self.status())
        else:
            return 'error', u'Current Job is still running'


# TODO: named adapter
@adapter(IDataset)
class ALAJobTracker(JobTracker):

    def start_job(self):
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
            LOG.fatal("ALA import failed %s: %s", jobstatus['status'],
                      jobstatus['reason'])
            return

        #transmogrify.dexterity.schemaupdater needs a REQUEST on context????
        from ZPublisher.HTTPResponse import HTTPResponse
        from ZPublisher.HTTPRequest import HTTPRequest
        import sys
        response = HTTPResponse(stdout=sys.stdout)
        env = {'SERVER_NAME': 'fake_server',
               'SERVER_PORT': '80',
               'REQUEST_METHOD': 'GET'}
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
