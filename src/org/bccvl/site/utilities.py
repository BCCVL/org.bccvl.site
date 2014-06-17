from datetime import datetime
from urlparse import urlsplit
import os.path
from gu.plone.rdf.interfaces import IRDFContentTransform
from gu.plone.rdf.namespace import CVOCAB
from gu.repository.content.interfaces import (
    IRepositoryContainer, IRepositoryItem)
from gu.z3cform.rdf.interfaces import IGraph
from gu.z3cform.rdf.interfaces import IRDFTypeMapper
from gu.z3cform.rdf.utils import Period
from ordf.namespace import DC as DCTERMS
from ordf.namespace import FOAF
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site.content.remotedataset import IRemoteDataset
from org.bccvl.site.content.group import IBCCVLGroup
from org.bccvl.site.content.interfaces import (
    ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment,
    IFunctionalResponseExperiment, IEnsembleExperiment)
from org.bccvl.site.content.user import IBCCVLUser
from org.bccvl.site.interfaces import IJobTracker, IComputeMethod, IDownloadInfo
from org.bccvl.site.namespace import DWC, BCCPROP
from org.bccvl.tasks.ala_import import ala_import
from org.bccvl.tasks.plone import after_commit_task
from persistent.dict import PersistentDict
from plone import api
from plone.app.contenttypes.interfaces import IFile
from plone.app.uuid.utils import uuidToObject
from plone.dexterity.utils import createContentInContainer
from rdflib import RDF, RDFS, Literal, OWL
import tempfile
from zope.annotation.interfaces import IAnnotations
from zope.component import adapter, queryUtility
from zope.interface import implementer
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

# FIXME: update JOB Info stuff.... for message queueing
#
# FIXME: define job state dictionary and possible states (esp. FINISHED states)


@implementer(IDownloadInfo)
@adapter(IDataset)
def DatasetDownloadInfo(context):
    # TODO: get rid of INTERNAL_URL
    import os
    INTERNAL_URL = 'http://127.0.0.1:8201'
    int_url = os.environ.get("INTERNAL_URL", INTERNAL_URL)
    if context.file is None or context.file.filename is None:
        # TODO: What to do here? the download url doesn't make sense
        #        for now use id as filename
        filename = context.getId()
    else:
        filename = context.file.filename
    # generate downloaurl
    downloadurl = '{}/@@download/file/{}'.format(
        context.absolute_url(),
        filename
    )
    internalurl = '{}{}/@@download/file/{}'.format(
        int_url,
        "/".join(context.getPhysicalPath()),
        filename
    )
    return {
        'url': downloadurl,
        'alturl': (internalurl,),
        'filename': filename
    }


@implementer(IDownloadInfo)
@adapter(IRemoteDataset)
def RemoteDatasetDownloadInfo(context):
    url = urlsplit(context.remoteUrl)
    return {
        'url': context.remoteUrl,
        'alturl': (context.remoteUrl,),
        'filename': os.path.basename(url.path)
    }


@implementer(IJobTracker)
class JobTracker(object):
    # TODO: maybe split state and progress....
    #       state ... used as internal state tracking
    #       progress ... used to track steps a task walks through
    #                    maybe even percentage?
    # job_info:
    #   - taskid ... unique id of task
    #   - name ... task name
    #   - state ... QUEUED, RUNNING, COMPLETED, FAILED
    #   - progress ... a dict with task specific progress
    #     - state ... short note of activity
    #     - message ... short descr of activity
    #     - .... could be more here; e.g. percent complete, steps, etc..

    _states = ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')

    def __init__(self, context):
        self.context = context
        annots = IAnnotations(self.context)
        # FIXME: this is not the place to set the annotation dictionary
        #        in case we only read from here we don't want to write'
        self._state = annots.get('org.bccvl.state', None)
        if self._state is None:
            self._state = annots['org.bccvl.state'] = PersistentDict()

    def _comparestate(self, state1, state2):
        """
        -1 if state1 < state2
        0  if state1 == state2
        1  if state1 > state2
        """
        # TODO: may raise ValueError if state not in list
        idx1 = self._states.index(state1)
        idx2 = self._states.index(state2)
        return cmp(idx1, idx2)

    @property
    def state(self):
        return self._state.get('state', None)

    @state.setter
    def state(self, state):
        # make sure we can only move forward in state
        if self._comparestate(self.state, state):
            self._state['state'] = state

    def is_active(self):
        return (self.state not in
                (None, 'COMPLETED', 'FAILED'))

    def new_job(self, taskid, name):
        self._state.clear()
        self._state.update({
            'state': 'QUEUED',
            'taskid': taskid,
            'name': name})

    def set_progress(self, state, message, **kw):
        self._state['progress'] = dict(
            state=state,
            message=message,
            **kw
        )

    def start_job(self, request):
        raise NotImplementedError()


class MultiJobTracker(JobTracker):
    # used for content objects that don't track jobs directly, but may have
    # multiple child objects with separate jobs

    @property
    def state(self):
        """
        Return single status across all jobs for this experiment.

        Failed -> in case one snigle job failed
          bccvl-status-error, alert-error
        New -> in case there is a job in state New
          bccvl-status-running (maps onto queued)
        Queued -> in case there is a job queued
          bccvl-status-running
        Completed -> in case all jobs completed successfully
          bccvl-status-complete, alert-success
        All other states -> running
          bccvl-status-running
        """
        states = self.states
        # filter out states only and ignore algorithm
        if states:
            states = set((state for _, state in states))
        else:
            return None
        # are all jobs completed?
        completed = all((state in ('COMPLETED', 'FAILED') for state in states))
        # do we have failed jobs if all completed?
        if completed:
            if 'FAILED' in states:
                return u'FAILED'
            else:
                return u'COMPLETED'
        # is everything still in Nem or Queued?
        queued = all((state in ('QUEUED', ) for state in states))
        if queued:
            return u'QUEUED'
        return u'RUNNING'

    @property
    def states(self):
        states = []
        for item in self.context.values():
            jt = IJobTracker(item, None)
            if jt is None:
                continue
            state = jt.state
            if state:
                states.append((item.getId(), state))
        return states


# TODO: should this be named adapter as well in case there are multiple
#       different jobs for experiments
@adapter(ISDMExperiment)
class SDMJobTracker(MultiJobTracker):

    def start_job(self, request):
        # split sdm jobs across multiple algorithms,
        # and multiple species input datasets
        # TODO: rethink and maybe split jobs based on enviro input datasets?
        if not self.is_active():
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
                method(result, func)
                resultjt = IJobTracker(result)
                resultjt.new_job('TODO: generate id',
                                 'generate taskname: sdm_experiment')
                resultjt.set_progress('PENDING',
                                      u'{} pending'.format(func.getId()))
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well
@adapter(IProjectionExperiment)
class ProjectionJobTracker(MultiJobTracker):

    def start_job(self, request):
        if not self.is_active():
            # split jobs across future climate datasets
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
                method(result, "project")  # TODO: wrong interface
                resultjt = IJobTracker(result)
                resultjt.new_job('TODO: generate id',
                                 'generate taskname: projection experiment')
                resultjt.set_progress('PENDING',
                                      u'projection pending')
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            # TODO: in case there is an error should we abort the transaction
            #       to cancel previously submitted jobs?
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well
@adapter(IBiodiverseExperiment)
class BiodiverseJobTracker(MultiJobTracker):

    def start_job(self, request):
        # TODO: split biodiverse job across years, gcm, emsc
        if not self.is_active():
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
                result.job_params = {
                    # datasets is a list of dicts with 'threshold' and 'uuid'
                    'projections': datasets,
                    'cluster_size': self.context.cluster_size,
                }

                # submit job to queue
                LOG.info("Submit JOB Biodiverse to queue")
                method(result, "biodiverse")  # TODO: wrong interface
                resultjt = IJobTracker(result)
                resultjt.new_job('TODO: generate id',
                                 'generate taskname: biodiverse')
                resultjt.set_progress('PENDING',
                                      'biodiverse pending')
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


@adapter(IFunctionalResponseExperiment)
class FunctionalResponseJobTracker(MultiJobTracker):

    def start_job(self, request):
        # TODO: split biodiverse job across years, gcm, emsc
        return 'error', u'Not yet implemented'


@adapter(IEnsembleExperiment)
class EnsembleJobTracker(MultiJobTracker):

    def start_job(self, request):
        # TODO: split biodiverse job across years, gcm, emsc
        return 'error', u'Not yet implemented'


# TODO: named adapter
@adapter(IDataset)
class ALAJobTracker(JobTracker):

    def start_job(self):
        if self.is_active():
            return 'error', u'Current Job is still running'
        md = IGraph(self.context)
        # TODO: this assumes we have an lsid in the metadata
        #       should check for it
        lsid = md.value(md.identifier, DWC['taxonID'])

        # we need site-path, context-path and lsid for this job
        #site_path = '/'.join(api.portal.get().getPhysicalPath())
        context_path = '/'.join(self.context.getPhysicalPath())
        member = api.user.get_current()
        # a folder for the datamover to place files in
        tmpdir = tempfile.mkdtemp()

        # ala_import will be submitted after commit, so we won't get a
        # result here
        ala_import_task = ala_import(
            lsid, tmpdir, {'context': context_path,
                           'user': {
                               'id': member.getUserName(),
                               'email': member.getProperty('email'),
                               'fullname': member.getProperty('fullname')
                           }})
        # TODO: add title, and url for dataset? (like with experiments?)
        after_commit_task(ala_import_task)

        # FIXME: we don't have a backend task id here as it will be started
        #        after commit, when we shouldn't write anything to the db
        #        maybe add another callback to set task_id?
        self.new_job('TODO: generate id', 'generate taskname: ala_import')
        self.set_progress('PENDING', u'ALA import pending')

        return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)

