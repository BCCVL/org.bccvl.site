
from plone import api
from plone.app.uuid.utils import uuidToObject
from zope.annotation import IAnnotations
from zope.component import getUtility

from org.bccvl.site import defaults
from .interfaces import IStatsUtility


def count_dataset_created(obj, event):
    # IBLobDataset
    # IRemoteDataset
    # IDatasetCollection -> IMultiSpeciesDataset
    if IAnnotations(obj.REQUEST).get('org.bccvl.site.stats.delay'):
        # skip this event, we have been called from transmogrify chain, where
        # we collect stats later
        # tell stats collector that we really created a new object
        IAnnotations(obj.REQUEST)['org.bccvl.site.stats.created'] = True
        return
    dataSrc = obj.dataSource
    if not dataSrc:
        if obj.part_of:
            # part of multispecies file ... get dataSource from master file
            master = uuidToObject(obj.part_of)
            dataSrc = master.dataSource
    if not dataSrc:
        # find default
        # check whether we are inside an experiment:
        if defaults.EXPERIMENTS_FOLDER_ID in obj.getPhysicalPath():
            dataSrc = 'experiment'
        else:
            dataSrc = 'upload'
    getUtility(IStatsUtility).count_dataset(
        source=dataSrc,
        portal_type=obj.portal_type
    )


def count_experiment_created(obj, event):
    # could also use obj.Creator() ?
    getUtility(IStatsUtility).count_experiment(
        api.user.get_current().getId(),
        obj.portal_type,
    )


def count_job_created(obj, event):
    # count a job created
    getUtility(IStatsUtility).count_job(
        function=obj.function,
        portal_type=obj.type,
    )
    # if we have created a job object with a final state,
    # then count that as well.as
    if obj.state in ('COMPLETED', 'FINISHED', 'FAILED'):
        getUtility(IStatsUtility).count_job(
            function=obj.function,
            portal_type=obj.type,
            state=obj.state
        )
