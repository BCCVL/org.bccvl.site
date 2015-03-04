from datetime import datetime
from decimal import Decimal
from urlparse import urlsplit
from itertools import chain
import os.path
import tempfile
from gu.z3cform.rdf.utils import Period
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site.content.remotedataset import IRemoteDataset
from org.bccvl.site.content.interfaces import (
    ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment,
    IEnsembleExperiment, ISpeciesTraitsExperiment)
from org.bccvl.site.interfaces import IJobTracker, IComputeMethod, IDownloadInfo, IBCCVLMetadata
from org.bccvl.site.api import dataset
from org.bccvl.tasks.ala_import import ala_import
from org.bccvl.tasks.plone import after_commit_task
from persistent.dict import PersistentDict
from plone import api
from plone.app.contenttypes.interfaces import IFile
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.dexterity.utils import createContentInContainer
from Products.ZCatalog.interfaces import ICatalogBrain
from zope.annotation.interfaces import IAnnotations
from zope.component import adapter, queryUtility
from zope.interface import implementer
import logging
from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName

LOG = logging.getLogger(__name__)


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
        contenttype = context.format
    else:
        filename = context.file.filename
        # TODO: context.format should look at file.contentType
        contenttype = context.file.contentType
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
        'filename': filename,
        'contenttype': contenttype or 'application/octet-stream',
    }


@implementer(IDownloadInfo)
@adapter(IRemoteDataset)
def RemoteDatasetDownloadInfo(context):
    url = urlsplit(context.remoteUrl)
    return {
        'url': context.remoteUrl,
        'alturl': (context.remoteUrl,),
        'filename': os.path.basename(url.path),
        'contenttype': context.format or 'application/octet-stream'
    }


@implementer(IDownloadInfo)
@adapter(ICatalogBrain)
def CatalogBrainDownloadInfo(brain):
    context = brain.getObject()
    return IDownloadInfo(context)
    # brain has at least getURL, getRemoteUrl


# FIXME: update JOB Info stuff.... for message queueing
#
# FIXME: define job state dictionary and possible states (esp. FINISHED states)
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

    def progress(self):
        return self._state.get('progress', None)


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
                    'Folder',
                    title=title)

                # Build job_params store them on result and submit job
                result.job_params = {
                    'resolution': IBCCVLMetadata(self.context)['resolution'],
                    'function': func.getId(),
                    'species_occurrence_dataset': self.context.species_occurrence_dataset,
                    'species_absence_dataset': self.context.species_absence_dataset,
                    'species_pseudo_absence_points': self.context.species_pseudo_absence_points,
                    'species_number_pseudo_absence_points': self.context.species_number_pseudo_absence_points,
                    'environmental_datasets': self.context.environmental_datasets,
                }
                # add toolkit params:
                result.job_params.update(self.context.parameters[IUUID(func)])
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

    def _create_result_container(self, sdmuuid, dsbrain, projlayers):
        # create result object:
        # get more metadata about dataset
        dsmd = IBCCVLMetadata(dsbrain.getObject())

        year = Period(dsmd['temporal']).start if dsmd['temporal'] else None
        # TODO: get proper labels for emsc, gcm
        title = u'{} - project {}_{}_{} {}'.format(
            self.context.title, dsmd['emsc'], dsmd['gcm'], year,
            datetime.now().isoformat())
        result = createContentInContainer(
            self.context,
            'Folder',
            title=title)
        result.job_params = {
            'species_distribution_models': sdmuuid,
            'year': year,
            'emsc': dsmd['emsc'],
            'gcm': dsmd['gcm'],
            'resolution': dsmd['resolution'],
            'future_climate_datasets': projlayers,
            }
        return result

    def start_job(self, request):
        if not self.is_active():
            # get utility to execute this experiment
            method = queryUtility(IComputeMethod,
                                  name=IProjectionExperiment.__identifier__)
            if method is None:
                # TODO: lookup by script type (Perl, Python, etc...)
                return ('error',
                        u"Can't find method to run Projection Experiment")
            expuuid = self.context.species_distribution_models.keys()[0]
            exp = uuidToObject(expuuid)
            # TODO: what if two datasets provide the same layer?
            # start a new job for each sdm and future dataset
            for sdmuuid in self.context.species_distribution_models[expuuid]:
                for dsuuid in self.context.future_climate_datasets:
                    dsbrain = uuidToCatalogBrain(dsuuid)
                    dsmd = IBCCVLMetadata(dsbrain.getObject())
                    futurelayers = set(dsmd['layers'].keys())
                    # match sdm exp layers with future dataset layers
                    projlayers = {}
                    for ds, dslayerset in exp.environmental_datasets.items():
                        # add matching layers
                        projlayers.setdefault(dsuuid, set()).update(dslayerset.intersection(futurelayers))
                        # remove matching layers
                        projlayers[ds] = dslayerset - futurelayers
                        if not projlayers[ds]:
                            # remove if all layers replaced
                            del projlayers[ds]
                    # create result
                    result = self._create_result_container(sdmuuid, dsbrain, projlayers)
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
            # FIXME: add resolution grouping?
            datasets = {}
            for projds, threshold in chain.from_iterable(map(lambda x: x.items(), self.context.projection.itervalues())):
                dsobj = uuidToObject(projds)
                dsmd = IBCCVLMetadata(dsobj)

                # FIXME: sdm datasets have no resolution
                emsc = dsmd.get('emsc')
                gcm = dsmd.get('gcm')
                period = dsmd.get('temporal')
                resolution = dsmd.get('resolution')
                if not period:
                    year = 'current'
                else:
                    year = Period(period).start if period else None
                key = (emsc, gcm, year, resolution)
                datasets.setdefault(key, []).append((projds, threshold))

            # create one job per dataset group
            for key, datasets in datasets.items():
                (emsc, gcm, year, resolution) = key

                # create result object:
                title = u'{} - biodiverse {}_{}_{} {}'.format(
                    self.context.title, emsc, gcm, year,
                    datetime.now().isoformat())
                result = createContentInContainer(
                    self.context,
                    'Folder',
                    title=title)

                dss = []
                for ds, thresh in datasets:
                    dss.append({
                        'dataset': ds,
                        'threshold': thresh
                    })

                # build job_params and store on result
                result.job_params = {
                    # datasets is a list of dicts with 'threshold' and 'uuid'
                    'projections': dss,
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


@adapter(IEnsembleExperiment)
class EnsembleJobTracker(MultiJobTracker):

    def start_job(self, request):
        if not self.is_active():
            # get utility to execute this experiment
            method = queryUtility(IComputeMethod,
                                  name=IEnsembleExperiment.__identifier__)
            if method is None:
                return ('error',
                        u"Can't find method to run Ensemble Experiment")

            # create result container
            title = u'{} - ensemble {}'.format(
                self.context.title, datetime.now().isoformat())
            result = createContentInContainer(
                self.context,
                'Folder',
                title=title)

            # build job_params and store on result
            result.job_params = {
                'datasets': list(chain.from_iterable(self.context.datasets.values()))
            }

            # submit job to queue
            LOG.info("Submit JOB Ensemble to queue")
            method(result, "ensemble")  # TODO: wrong interface
            resultjt = IJobTracker(result)
            resultjt.new_job('TODO: generate id',
                             'generate taskname: ensemble')
            resultjt.set_progress('PENDING',
                                  'ensemble pending')
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


@adapter(ISpeciesTraitsExperiment)
class SpeciesTraitsJobTracker(MultiJobTracker):

    def start_job(self, request):
        if not self.is_active():
            # get utility to execute this experiment
            method = queryUtility(IComputeMethod,
                                  name=ISpeciesTraitsExperiment.__identifier__)
            if method is None:
                return ('error',
                        u"Can't find method to run Species Traits Experiment")
            # iterate over all datasets and group them by emsc,gcm,year
            algorithm = uuidToCatalogBrain(self.context.algorithm)

            # create result object:
            # TODO: refactor this out into helper method
            title = u'%s - %s %s' % (self.context.title, algorithm.id,
                                     datetime.now().isoformat())
            result = createContentInContainer(
                self.context,
                'Folder',
                title=title)

            # Build job_params store them on result and submit job
            result.job_params = {
                'algorithm': algorithm.id,
                'formula': self.context.formula,
                'data_table': self.context.data_table,
            }
            # add toolkit params:
            result.job_params.update(self.context.parameters[algorithm.UID])
            # submit job
            LOG.info("Submit JOB %s to queue", algorithm.id)
            method(result, algorithm.getObject())
            resultjt = IJobTracker(result)
            resultjt.new_job('TODO: generate id',
                             'generate taskname: sdm_experiment')
            resultjt.set_progress('PENDING',
                                  u'{} pending'.format(algorithm.id))
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


# TODO: named adapter
@adapter(IDataset)
class ALAJobTracker(JobTracker):

    def start_job(self):
        if self.is_active():
            return 'error', u'Current Job is still running'
        # The dataset object already exists and should have all required metadata
        md = IBCCVLMetadata(self.context)
        # TODO: this assumes we have an lsid in the metadata
        #       should check for it
        lsid = md['species']['taxonID']

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
