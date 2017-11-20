from datetime import datetime
from itertools import chain
import logging
import os.path
from urlparse import urlsplit

from Products.ZCatalog.interfaces import ICatalogBrain
from Products.CMFCore.utils import getToolByName
from plone import api
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.dexterity.utils import createContentInContainer
from plone.uuid.interfaces import IUUID
from zope.component import adapter, queryUtility, getMultiAdapter
from zope.interface import implementer

from org.bccvl.site import defaults
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.content.remotedataset import IRemoteDataset
from org.bccvl.site.content.interfaces import (
    ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment,
    IEnsembleExperiment, ISpeciesTraitsExperiment, IMSDMExperiment, IMMExperiment)
from org.bccvl.site.interfaces import (
    IComputeMethod, IDownloadInfo, IBCCVLMetadata, IProvenanceData, IExperimentJobTracker)
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.site.utils import (
    build_ala_import_task, build_traits_import_task, build_ala_import_qid_task)
from org.bccvl.tasks.plone import after_commit_task
from zope.schema.interfaces import IVocabularyFactory
from zope.component import getUtility


LOG = logging.getLogger(__name__)


@implementer(IDownloadInfo)
@adapter(IDataset)
def DatasetDownloadInfo(context):
    # TODO: get rid of INTERNAL_URL
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
    downloadview = getMultiAdapter((context, context.REQUEST), name="download")
    downloadurl = u'{}/@@download/file/{}'.format(
        context.absolute_url(),
        filename
    )
    return {
        'url': downloadurl,
        'filename': filename,
        'contenttype': contenttype or 'application/octet-stream',
        'available': downloadview.check_allowed()
    }


@implementer(IDownloadInfo)
@adapter(IRemoteDataset)
def RemoteDatasetDownloadInfo(context):
    downloadview = getMultiAdapter((context, context.REQUEST), name="download")
    url = urlsplit(context.remoteUrl)
    filename = os.path.basename(url.path)
    return {
        'url': u'{}/@@download/{}'.format(
            context.absolute_url(),
            filename),
        'filename': os.path.basename(url.path),
        'contenttype': context.format or 'application/octet-stream',
        'available': downloadview.check_allowed()
    }


@implementer(IDownloadInfo)
@adapter(ICatalogBrain)
def CatalogBrainDownloadInfo(brain):
    context = brain.getObject()
    return IDownloadInfo(context)
    # brain has at least getURL, getRemoteUrl


@implementer(IExperimentJobTracker)
class MultiJobTracker(object):
    # used for content objects that don't track jobs directly, but may have
    # multiple child objects with separate jobs

    def __init__(self, context):
        self.context = context

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
            if all((state in ('COMPLETED',) for state in states)):
                # all finished successfully
                return 'COMPLETED'
            if all((state in ('FAILED',) for state in states)):
                # all failed
                return 'FAILED'
            return 'FINISHED'
        # is everything still in Nem or Queued?
        queued = all((state in ('PENDING', 'QUEUED') for state in states))
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

    def is_active(self):
        return (self.state not in
                (None, 'COMPLETED', 'FAILED', 'REMOVED'))


# TODO: should this be named adapter as well in case there are multiple
#       different jobs for experiments
@adapter(ISDMExperiment)
class SDMJobTracker(MultiJobTracker):

    def _create_result_container(self, title):
        result = createContentInContainer(
            self.context, 'Folder', title=title)
        return result

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, RDFS, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            if key in ('species_occurrence_dataset', 'species_absence_dataset'):
                if not result.job_params[key]:
                    # skip empty values
                    continue
                param.add(BCCVL['value'], LOCAL[value])
            elif key in ('environmental_datasets',):
                # FIXME: got two env datasets with overlapping layer set (e.g. B08 selected in both)
                # FIXME: look for dict params in other experiment types as well
                # value is a dictionary, where keys are dataset uuids and
                # values are a set of selected layers
                for uuid, layers in value.items():
                    param.add(BCCVL['value'], LOCAL[uuid])
                    for layer in layers:
                        # TODO: maybe URIRef?
                        param.add(BCCVL['layer'], LOCAL[layer])
            else:
                param.add(BCCVL['value'], Literal(value))

        # iterate over all input datasets and add them as entities
        for key in ('species_occurrence_dataset', 'species_absence_dataset'):
            dsbrain = uuidToCatalogBrain(result.job_params[key])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[dsbrain.UID])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            dsprov.add(BCCVL['scientificName'], Literal(
                md['species']['scientificName']))
            if md['species'].get('taxonID'):
                dsprov.add(BCCVL['taxonID'], Literal(md['species']['taxonID']))
            dsprov.add(DCTERMS['extent'], Literal(
                '{} rows'.format(md.get('rows', 'N/A'))))
            # ... species data, ... species id

            # link with activity
            activity.add(PROV['used'], dsprov)


        for uuid, layers in result.job_params['environmental_datasets'].items():
            key = 'environmental_datasets'
            ds = uuidToObject(uuid)
            dsprov = Resource(graph, LOCAL[key])
            dsprov.add(RDF['type'], PROV['Entity'])
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # TODO: genre ...
            for layer in layers:
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            # location / source
            # layers selected + layer metadata
            # ... raster data, .. layers

            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")


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
                title = u'{} - {} {}'.format(self.context.title, func.getId(),
                                             datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                result = self._create_result_container(title)

                # Build job_params store them on result and submit job
                result.job_params = {
                    'resolution': IBCCVLMetadata(self.context)['resolution'],
                    'function': func.getId(),
                    'species_occurrence_dataset': self.context.species_occurrence_dataset,
                    'species_absence_dataset': self.context.species_absence_dataset,
                    'environmental_datasets': self.context.environmental_datasets,
                    'scale_down': self.context.scale_down,
                    'modelling_region': self.context.modelling_region,
                    # TO DO: This shall be input from user??
                    'generate_convexhull': False,
                }
                # add toolkit params:
                result.job_params.update(self.context.parameters[IUUID(func)])
                self._createProvenance(result)
                # submit job
                LOG.info("Submit JOB %s to queue", func.getId())
                method(result, func)
                resultjt = IJobTracker(result)
                job = resultjt.new_job('TODO: generate id',
                                       'generate taskname: sdm_experiment')
                job.type = self.context.portal_type
                job.function = func.getId()
                job.toolkit = IUUID(func)
                # reindex job object here ... next call should do that
                resultjt.set_progress('PENDING',
                                      u'{} pending'.format(func.getId()))
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well in case there are multiple
#       different jobs for experiments
@adapter(IMSDMExperiment)
class MSDMJobTracker(MultiJobTracker):

    def _create_result_container(self, title):
        result = createContentInContainer(
            self.context, 'Folder', title=title)
        return result

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, RDFS, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            if key in ('species_occurrence_dataset', 'species_absence_dataset'):
                if not result.job_params[key]:
                    # skip empty values
                    continue
                param.add(BCCVL['value'], LOCAL[value])
            elif key in ('environmental_datasets',):
                # FIXME: got two env datasets with overlapping layer set (e.g. B08 selected in both)
                # FIXME: look for dict params in other experiment types as well
                # value is a dictionary, where keys are dataset uuids and
                # values are a set of selected layers
                for uuid, layers in value.items():
                    param.add(BCCVL['value'], LOCAL[uuid])
                    for layer in layers:
                        # TODO: maybe URIRef?
                        param.add(BCCVL['layer'], LOCAL[layer])
            else:
                param.add(BCCVL['value'], Literal(value))

        # iterate over all input datasets and add them as entities
        for key in ('species_occurrence_dataset', ):
            dsbrain = uuidToCatalogBrain(result.job_params[key])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[dsbrain.UID])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            dsprov.add(BCCVL['scientificName'], Literal(
                md['species']['scientificName']))
            if md['species'].get('taxonID'):
                dsprov.add(BCCVL['taxonID'], Literal(md['species']['taxonID']))
            dsprov.add(DCTERMS['extent'], Literal(
                '{} rows'.format(md.get('rows', 'N/A'))))
            # ... species data, ... species id

            # link with activity
            activity.add(PROV['used'], dsprov)

        for uuid, layers in result.job_params['environmental_datasets'].items():
            key = 'environmental_datasets'
            ds = uuidToObject(uuid)
            dsprov = Resource(graph, LOCAL[key])
            dsprov.add(RDF['type'], PROV['Entity'])
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # TODO: genre ...
            for layer in layers:
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            # location / source
            # layers selected + layer metadata
            # ... raster data, .. layers

            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")

    def start_job(self, request):
        # split sdm jobs across multiple algorithms,
        # and multiple species input datasets
        # TODO: rethink and maybe split jobs based on enviro input datasets?
        if not self.is_active():
            func = uuidToObject(self.context.function)
            for occur_coll in self.context.species_occurrence_collections:
                for occur_ds in self.context.species_occurrence_collections[occur_coll]:
                    # get utility to execute this experiment
                    method = queryUtility(IComputeMethod,
                                          name=ISDMExperiment.__identifier__)
                    if method is None:
                        return ('error',
                                u"Can't find method to run SDM Experiment")
                    # create result object:
                    # TODO: refactor this out into helper method
                    title = u'{} - {} {}'.format(self.context.title, func.getId(),
                                                 datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                    result = self._create_result_container(title)
                    # Build job_params store them on result and submit job
                    result.job_params = {
                        'resolution': IBCCVLMetadata(self.context)['resolution'],
                        'function': func.getId(),
                        'species_occurrence_dataset': occur_ds,
                        'environmental_datasets': self.context.environmental_datasets,
                        'scale_down': self.context.scale_down,
                        'modelling_region': self.context.modelling_region,
                        # TO DO: This shall be input from user??
                        'generate_convexhull': True,
                    }

                    # add toolkit params:
                    result.job_params.update(
                        self.context.parameters[IUUID(func)])
                    self._createProvenance(result)
                    # submit job
                    LOG.info("Submit JOB %s to queue", func.getId())
                    method(result, func)
                    resultjt = IJobTracker(result)
                    job = resultjt.new_job('TODO: generate id',
                                           'generate taskname: sdm_experiment')
                    job.type = self.context.portal_type
                    job.function = func.getId()
                    job.toolkit = IUUID(func)
                    # reindex job object here ... next call should do that
                    resultjt.set_progress('PENDING',
                                          u'{} pending'.format(func.getId()))
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well in case there are multiple
#       different jobs for experiments
@adapter(IMMExperiment)
class MMJobTracker(MultiJobTracker):

    def _create_result_container(self, title):
        result = createContentInContainer(
            self.context, 'Folder', title=title)
        return result

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, RDFS, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            if key in ('species_occurrence_dataset', 'species_absence_dataset'):
                if not result.job_params[key]:
                    # skip empty values
                    continue
                param.add(BCCVL['value'], LOCAL[value])
            elif key in ('environmental_datasets',):
                # FIXME: got two env datasets with overlapping layer set (e.g. B08 selected in both)
                # FIXME: look for dict params in other experiment types as well
                # value is a dictionary, where keys are dataset uuids and
                # values are a set of selected layers
                for uuid, layers in value.items():
                    param.add(BCCVL['value'], LOCAL[uuid])
                    for layer in layers:
                        # TODO: maybe URIRef?
                        param.add(BCCVL['layer'], LOCAL[layer])
            else:
                param.add(BCCVL['value'], Literal(value))

        # iterate over all input datasets and add them as entities
        for key in ('species_occurrence_dataset', ):
            dsbrain = uuidToCatalogBrain(result.job_params[key])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[dsbrain.UID])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            dsprov.add(BCCVL['scientificName'], Literal(
                md['species']['scientificName']))
            if md['species'].get('taxonID'):
                dsprov.add(BCCVL['taxonID'], Literal(md['species']['taxonID']))
            dsprov.add(DCTERMS['extent'], Literal(
                '{} rows'.format(md.get('rows', 'N/A'))))
            # ... species data, ... species id

            # link with activity
            activity.add(PROV['used'], dsprov)

        for uuid, layers in result.job_params['environmental_datasets'].items():
            key = 'environmental_datasets'
            ds = uuidToObject(uuid)
            dsprov = Resource(graph, LOCAL[key])
            dsprov.add(RDF['type'], PROV['Entity'])
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # TODO: genre ...
            for layer in layers:
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            # location / source
            # layers selected + layer metadata
            # ... raster data, .. layers

            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")

    def _get_resolution(self, datasets):
        res_vocab = getUtility(
            IVocabularyFactory, 'resolution_source')(self.context)
        resolution_idx = -1
        for dsbrain in (uuidToCatalogBrain(d) for d in datasets):
            idx = res_vocab._terms.index(
                res_vocab.getTerm(dsbrain.BCCResolution))
            if idx > resolution_idx:
                resolution_idx = idx
        return res_vocab._terms[resolution_idx].value


    def start_job(self, request):
        # split sdm jobs across multiple algorithms,
        # and across multiple subset of species according to months
        if not self.is_active():
            func = uuidToObject(self.context.function)
            for datasubset in self.context.datasubsets:
                subset = datasubset['subset']
                environmental_datasets = datasubset['environmental_datasets']
                # get utility to execute this experiment
                method = queryUtility(IComputeMethod,
                                      name=ISDMExperiment.__identifier__)
                if method is None:
                    return ('error',
                            u"Can't find method to run SDM Experiment")
                # create result object:
                # TODO: refactor this out into helper method
                title = u'{} - {} {} {}'.format(self.context.title, func.getId(), subset['title'],
                                             datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                result = self._create_result_container(title)
                # Build job_params store them on result and submit job
                result.job_params = {
                    'resolution': self._get_resolution(environmental_datasets),
                    'function': func.getId(),
                    'species_occurrence_dataset': self.context.species_occurrence_dataset,
                    'environmental_datasets': environmental_datasets,
                    # TODO: this sholud rather be a filter expression?
                    #       -> <csv column> in <subset values>
                    'species_filter': map(int, subset['value']),
                    'subset': subset['title'],
                    'scale_down': self.context.scale_down,
                    'modelling_region': self.context.modelling_region,
                    # TO DO: This shall be input from user??
                    'generate_convexhull': True,
                }

                # add toolkit params:
                result.job_params.update(
                    self.context.parameters[IUUID(func)])
                self._createProvenance(result)
                # submit job
                LOG.info("Submit JOB %s to queue", func.getId())
                method(result, func)
                resultjt = IJobTracker(result)
                job = resultjt.new_job('TODO: generate id',
                                       'generate taskname: sdm_experiment')
                job.type = self.context.portal_type
                job.function = func.getId()
                job.toolkit = IUUID(func)
                # reindex job object here ... next call should do that
                resultjt.set_progress('PENDING',
                                      u'{} pending'.format(func.getId()))
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


# TODO: should this be named adapter as well
@adapter(IProjectionExperiment)
class ProjectionJobTracker(MultiJobTracker):

    def _get_sdm_projection_result(self, sdmdsObj):
        # BCCVL-101: get only the constraint projection geotif results of SDM
        pc = getToolByName(self.context, 'portal_catalog')
        projbrains = pc.searchResults(path='/'.join(sdmdsObj.__parent__.getPhysicalPath()),
                                      BCCDataGenre=['DataGenreCP'])
        # FIXME what to do if there is still no projbrains?
        #       we probably can't run a CC experiment without it.
        #       we certainly shouldn't fail with indexerror 0 (empty search result)
        return [projbrains[0].UID]

    def _create_result_container(self, sdmthreshold, dsbrain, projlayers):
        # create result object:
        # Get the algorithm used in SDM experiment
        sdmuuid, threshold = sdmthreshold
        sdmdsObj = uuidToCatalogBrain(sdmuuid).getObject()
        algorithm = sdmdsObj.__parent__.job_params['function']
        subset = sdmdsObj.__parent__.job_params.get('subset')

        # get more metadata about dataset
        dsmd = IBCCVLMetadata(dsbrain.getObject())
        year = dsmd.get('year', None)
        month = dsmd.get('month', None)
        # TODO: get proper labels for emsc, gcm
        title = u'{} - project {}_{}_{} {} {}'.format(
            self.context.title, dsmd['emsc'], dsmd[
                'gcm'], year or '', month or '',
            datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
        result = createContentInContainer(
            self.context,
            'Folder',
            title=title)
        result.job_params = {
            'species_distribution_models': sdmuuid,
            'sdm_projections': self._get_sdm_projection_result(sdmdsObj),
            'year': year,
            'month': month,
            'emsc': dsmd['emsc'],
            'gcm': dsmd['gcm'],
            'resolution': dsmd['resolution'],
            'future_climate_datasets': projlayers,
            'function': algorithm,
            'subset': subset,
            'projection_region': self.context.projection_region,
            # TO DO: This shall be input from user??
            'generate_convexhull': False,
            'threshold': threshold.get('value')
        }

        # Add subset title
        subsetTitle = sdmdsObj.__parent__.job_params.get('subset', None)
        if subsetTitle:
            result.job_params['subset'] = subsetTitle
        return result

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            # We have only dataset references as parameters
            if key in ('future_climate_datasets',):
                for dsuuid in value.keys():
                    param.add(BCCVL['value'], LOCAL[dsuuid])
            elif key in ('species_distribution_models',):
                param.add(BCCVL['value'], LOCAL[value])
            else:
                param.add(BCCVL['value'], Literal(value))
        # iterate over all input datasets and add them as entities
        for key in ('species_distribution_models',):
            dsbrain = uuidToCatalogBrain(result.job_params[key])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[result.job_params[key]])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            dsprov.add(BCCVL['scientificName'], Literal(
                md['species']['scientificName']))
            if md['species'].get('taxonID'):
                dsprov.add(BCCVL['taxonID'], Literal(md['species']['taxonID']))

            # ... species data, ... species id
            for layer in md.get('layers_used', ()):
                dsprov.add(BCCVL['layer'], LOCAL[layer])

            # link with activity
            activity.add(PROV['used'], dsprov)

        for uuid, layers in result.job_params['future_climate_datasets'].items():

            key = 'future_climate_datasets'
            ds = uuidToObject(uuid)
            dsprov = Resource(graph, LOCAL[uuid])
            dsprov.add(RDF['type'], PROV['Entity'])
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # TODO: genre, resolution, emsc, gcm, year(s) ...
            for layer in layers:
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            # location / source
            # layers selected + layer metadata
            # ... raster data, .. layers

            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")

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
            # TODO: what if two datasets provide the same layer?
            # start a new job for each sdm and future dataset
            for sdm_threshold in self.context.species_distribution_models[expuuid].items():
                for dsuuid in self.context.future_climate_datasets:
                    dsbrain = uuidToCatalogBrain(dsuuid)
                    dsobj = dsbrain.getObject()
                    dsmd = IBCCVLMetadata(dsobj)
                    futurelayers = set(dsmd['layers'].keys())
                    # match sdm exp layers with future dataset layers
                    projlayers = {}
                    # Get the environmental dataset from the job params
                    sdmdsuuid, threshold = sdm_threshold
                    sdmdsObj = uuidToCatalogBrain(sdmdsuuid).getObject()
                    environmental_datasets = sdmdsObj.__parent__.job_params['environmental_datasets']
                    for ds, dslayerset in environmental_datasets.items():
                        dslayerset = set(dslayerset)
                        # add matching layers
                        projlayers.setdefault(dsuuid, set()).update(
                            dslayerset.intersection(futurelayers))
                        # remove matching layers
                        projlayers[ds] = dslayerset - futurelayers
                        if not projlayers[ds]:
                            # remove if all layers replaced
                            del projlayers[ds]
                    # create result
                    result = self._create_result_container(
                        sdm_threshold, dsbrain, projlayers)
                    # update provenance
                    self._createProvenance(result)
                    # submit job
                    LOG.info("Submit JOB project to queue")
                    method(result, "project")  # TODO: wrong interface
                    resultjt = IJobTracker(result)
                    job = resultjt.new_job('TODO: generate id',
                                           'generate taskname: projection experiment')
                    job.type = self.context.portal_type
                    job.function = result.job_params['function']
                    job.toolkit = IUUID(
                        api.portal.get()[defaults.TOOLKITS_FOLDER_ID][job.function])
                    # reindex job object here ... next call should do that
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

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, RDFS, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            # We have only dataset references as parameters
            if key in ('projections',):
                for val in value:
                    param.add(BCCVL['value'], LOCAL[val['dataset']])
            else:
                param.add(BCCVL['value'], Literal(value))
        # iterate over all input datasets and add them as entities
        for value in result.job_params['projections']:
            dsbrain = uuidToCatalogBrain(value['dataset'])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[value['dataset']])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # threshold used:
            # FIXME: what's the label of manually entered value?
            dsprov.add(BCCVL['threshold_label'],
                       Literal(value['threshold']['label']))
            dsprov.add(BCCVL['threshold_value'],
                       Literal(value['threshold']['value']))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            dsprov.add(BCCVL['scientificName'], Literal(
                md['species']['scientificName']))
            if md['species'].get('taxonID'):
                dsprov.add(BCCVL['taxonID'], Literal(md['species']['taxonID']))

            # ... species data, ... species id
            for layer in md.get('layers_used', ()):
                dsprov.add(BCCVL['layer'], LOCAL[layer])

            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")

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

                emsc = dsmd.get('emsc')
                gcm = dsmd.get('gcm')
                year = dsmd.get('year')
                month = dsmd.get('month')
                resolution = dsmd.get('resolution')
                if not year:
                    year = 'current'
                key = (emsc, gcm, year, month, resolution)
                datasets.setdefault(key, []).append((projds, threshold))

            # create one job per dataset group
            for key, datasets in datasets.items():
                (emsc, gcm, year, month, resolution) = key

                # create result object:
                if year == 'current':
                    title = u'{} - biodiverse {} {}'.format(
                        self.context.title, year,
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                else:
                    title = u'{} - biodiverse {}_{}_{} {}'.format(
                        self.context.title, emsc, gcm, year,
                        datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
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
                # update provenance
                self._createProvenance(result)

                # submit job to queue
                LOG.info("Submit JOB Biodiverse to queue")
                method(result, "biodiverse")  # TODO: wrong interface
                resultjt = IJobTracker(result)
                job = resultjt.new_job('TODO: generate id',
                                       'generate taskname: biodiverse')

                job.type = self.context.portal_type
                # reindex job object here ... next call should do that

                resultjt.set_progress('PENDING',
                                      'biodiverse pending')
            return 'info', u'Job submitted {0} - {1}'.format(
                self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


@adapter(IEnsembleExperiment)
class EnsembleJobTracker(MultiJobTracker):

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            # We have only dataset references as parameters
            if key in ('datasets',):
                for dsuuid in value:
                    param.add(BCCVL['value'], LOCAL[dsuuid])
            else:
                param.add(BCCVL['value'], Literal(value))
        # iterate over all input datasets and add them as entities
        for dsuuid in result.job_params['datasets']:
            dsbrain = uuidToCatalogBrain(dsuuid)
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[result.job_params[key]])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            dsprov.add(BCCVL['scientificName'], Literal(
                md['species']['scientificName']))
            if md['species'].get('taxonID'):
                dsprov.add(BCCVL['taxonID'], Literal(md['species']['taxonID']))

            # ... species data, ... species id
            for layer in md.get('layers_used', ()):
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            for layer in md.get('layers', ()):
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")

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
                self.context.title, datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
            result = createContentInContainer(
                self.context,
                'Folder',
                title=title)

            # build job_params and store on result
            # FIXME: probably should split ensemble jobs based on resolution
            #        for now pick first one to make result import work
            #        datasets is dict with expkey and list of datasets...
            #           can probably get resolution from exp or ds
            dsid = self.context.datasets.values()[0][0]
            dsmd = IBCCVLMetadata(uuidToObject(dsid))
            result.job_params = {
                'datasets': list(chain.from_iterable(self.context.datasets.values())),
                'resolution': dsmd['resolution']
            }
            # update provenance
            self._createProvenance(result)

            # submit job to queue
            LOG.info("Submit JOB Ensemble to queue")
            method(result, "ensemble")  # TODO: wrong interface
            resultjt = IJobTracker(result)
            job = resultjt.new_job('TODO: generate id',
                                   'generate taskname: ensemble')

            job.type = self.context.portal_type
            # job reindex happens in next call

            resultjt.set_progress('PENDING',
                                  'ensemble pending')
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


@adapter(ISpeciesTraitsExperiment)
class SpeciesTraitsJobTracker(MultiJobTracker):

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, RDFS, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL Job Script'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity
        for idx, (key, value) in enumerate(result.job_params.items()):
            param = Resource(graph, LOCAL[u'param_{}'.format(idx)])
            activity.add(BCCVL['algoparam'], param)
            param.add(BCCVL['name'], Literal(key))
            # We have only dataset references as parameters
            if key in ('traits_dataset',):
                param.add(BCCVL['value'], LOCAL[value])
            elif key in ('environmental_datasets', ):
                # FIXME: got two env datasets with overlapping layer set (e.g. B08 selected in both)
                # FIXME: look for dict params in other experiment types as well
                # value is a dictionary, where keys are dataset uuids and
                # values are a set of selected layers
                if not value:
                    continue
                for uuid, layers in value.items():
                    param.add(BCCVL['value'], LOCAL[uuid])
                    for layer in layers:
                        # TODO: maybe URIRef?
                        param.add(BCCVL['layer'], LOCAL[layer])
            else:
                param.add(BCCVL['value'], Literal(value))
        # iterate over all input datasets and add them as entities
        for key in ('traits_dataset',):
            dsbrain = uuidToCatalogBrain(result.job_params[key])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            dsprov = Resource(graph, LOCAL[result.job_params[key]])
            dsprov.add(RDF['type'], PROV['Entity'])
            #dsprov.add(PROV['..'], Literal(''))
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # location / source
            # graph.add(uri, DCTERMS['source'], Literal(''))
            # TODO: genre ...
            # TODO: resolution
            # species metadata
            md = IBCCVLMetadata(ds)
            # dsprov.add(BCCVL['scientificName'], Literal(md['species']['scientificName']))
            # dsprov.add(BCCVL['taxonID'], URIRef(md['species']['taxonID']))

            # ... species data, ... species id
            for layer in md.get('layers_used', ()):
                dsprov.add(BCCVL['layer'], LOCAL[layer])

            # link with activity
            activity.add(PROV['used'], dsprov)

        envds = result.job_params.get('environmental_datasets') or {}
        for uuid, layers in envds.items():
            key = 'environmental_datasets'
            ds = uuidToObject(uuid)
            dsprov = Resource(graph, LOCAL[key])
            dsprov.add(RDF['type'], PROV['Entity'])
            dsprov.add(DCTERMS['creator'], Literal(ds.Creator()))
            dsprov.add(DCTERMS['title'], Literal(ds.title))
            dsprov.add(DCTERMS['description'], Literal(ds.description))
            dsprov.add(DCTERMS['rights'], Literal(ds.rights))
            if ((ds.portal_type == 'org.bccvl.content.dataset' and ds.file is not None)
                    or
                    (ds.portal_type == 'org.bccvl.content.remotedataset' and ds.remoteUrl)):
                dsprov.add(DCTERMS['format'], Literal(ds.format))
            # TODO: genre ...
            for layer in layers:
                dsprov.add(BCCVL['layer'], LOCAL[layer])
            # location / source
            # layers selected + layer metadata
            # ... raster data, .. layers

            # link with activity
            activity.add(PROV['used'], dsprov)

        provdata.data = graph.serialize(format="turtle")

    def start_job(self, request):
        if not self.is_active():
            for algorithm in (uuidToCatalogBrain(f) for f in chain(self.context.algorithms_species,
                                                                   self.context.algorithms_diff)):
                # get utility to execute this experiment
                method = queryUtility(IComputeMethod,
                                      name=ISpeciesTraitsExperiment.__identifier__)
                if method is None:
                    return ('error',
                            u"Can't find method to run Species Traits Experiment")
                # create result object:
                # TODO: refactor this out into helper method
                title = u'{} - {} {}'.format(self.context.title, algorithm.id,
                                             datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
                result = createContentInContainer(self.context,
                                                  'Folder',
                                                  title=title)

                # Build job_params store them on result and submit job
                result.job_params = {
                    'algorithm': algorithm.id,
                    'traits_dataset': self.context.species_traits_dataset,
                    'traits_dataset_params': self.context.species_traits_dataset_params,
                    'environmental_datasets': self.context.environmental_datasets,
                    'modelling_region': self.context.modelling_region,
                }
                # add toolkit params:
                result.job_params.update(
                    self.context.parameters[algorithm.UID])
                # update provenance
                self._createProvenance(result)
                # submit job
                LOG.info("Submit JOB %s to queue", algorithm.id)
                method(result, algorithm.getObject())
                resultjt = IJobTracker(result)
                job = resultjt.new_job('TODO: generate id',
                                       'generate taskname: sdm_experiment')

                job.type = self.context.portal_type
                job.function = algorithm.id
                job.toolkit = algorithm.UID
                # job reindex happens in next call

                resultjt.set_progress('PENDING',
                                      u'{} pending'.format(algorithm.id))
            return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)
        else:
            return 'error', u'Current Job is still running'


# TODO: named adapter
@adapter(IDataset)
class ALAJobTracker(MultiJobTracker):

    def _createProvenance(self, result):
        provdata = IProvenanceData(result)
        from rdflib import URIRef, Literal, Namespace, Graph
        from rdflib.namespace import RDF, RDFS, FOAF, DCTERMS, XSD
        from rdflib.resource import Resource
        PROV = Namespace(u"http://www.w3.org/ns/prov#")
        BCCVL = Namespace(u"http://ns.bccvl.org.au/")
        LOCAL = Namespace(u"urn:bccvl:")
        graph = Graph()
        # the user is our agent

        member = api.user.get_current()
        username = member.getProperty('fullname') or member.getId()
        user = Resource(graph, LOCAL['user'])
        user.add(RDF['type'], PROV['Agent'])
        user.add(RDF['type'], FOAF['Person'])
        user.add(FOAF['name'], Literal(username))
        user.add(FOAF['mbox'],
                 URIRef('mailto:{}'.format(member.getProperty('email'))))
        # add software as agent
        software = Resource(graph, LOCAL['software'])
        software.add(RDF['type'], PROV['Agent'])
        software.add(RDF['type'], PROV['SoftwareAgent'])
        software.add(FOAF['name'], Literal('BCCVL ALA Importer'))
        # script content is stored somewhere on result and will be exported with zip?
        #   ... or store along with pstats.json ? hidden from user

        # -> execenvironment after import -> log output?
        # -> source code ... maybe some link expression? stored on result ? separate entity?
        activity = Resource(graph, LOCAL['activity'])
        activity.add(RDF['type'], PROV['Activity'])
        # TODO: this is rather queued or created time for this activity ...
        # could capture real start time on running status update (or start
        # transfer)
        now = datetime.now().replace(microsecond=0)
        activity.add(PROV['startedAtTime'],
                     Literal(now.isoformat(), datatype=XSD['dateTime']))
        activity.add(PROV['hasAssociationWith'], user)
        activity.add(PROV['hasAssociationWith'], software)
        # add job parameters to activity

        provdata.data = graph.serialize(format="turtle")

    def start_job(self):
        if self.is_active():
            return 'error', u'Current Job is still running'
        # The dataset object already exists and should have all required
        # metadata
        md = IBCCVLMetadata(self.context)
        # TODO: this assumes we have an lsid in the metadata
        #       should check for it
        if md['genre'] == 'DataGenreTraits':
            traits_import_task = build_traits_import_task(
                self.context, self.context.REQUEST)
            after_commit_task(traits_import_task)
            # FIXME: we don't have a backend task id here as it will be started
            #        after commit, when we shouldn't write anything to the db
            #        maybe add another callback to set task_id?
            jt = IJobTracker(self.context)
            job = jt.new_job('TODO: generate id',
                             'generate taskname: traits_import')
            job.type = self.context.portal_type
            # job reindex happens in next call
            jt.set_progress('PENDING', u'Data import pending')
        else:
            if hasattr(self.context, 'import_params'):
                ala_import_task = build_ala_import_qid_task(
                    self.context.import_params, self.context,
                    self.context.REQUEST)

                # TODO: add title, and url for dataset? (like with experiments?)
                # update provenance
                self._createProvenance(self.context)
                after_commit_task(ala_import_task)

                # FIXME: we don't have a backend task id here as it will be started
                #        after commit, when we shouldn't write anything to the db
                #        maybe add another callback to set task_id?
                jt = IJobTracker(self.context)
                job = jt.new_job('TODO: generate id',
                                 'generate taskname: ala_import')
                job.type = self.context.portal_type
                # job reindex happens in next call
                jt.set_progress('PENDING', u'Data import pending')

            else:
                lsid = md['species']['taxonID']

                # ala_import will be submitted after commit, so we won't get a
                # result here
                # FIXME: hacky way to get to request
                ala_import_task = build_ala_import_task(
                    lsid, self.context, self.context.REQUEST)

                # TODO: add title, and url for dataset? (like with experiments?)
                # update provenance
                self._createProvenance(self.context)
                after_commit_task(ala_import_task)

                # FIXME: we don't have a backend task id here as it will be started
                #        after commit, when we shouldn't write anything to the db
                #        maybe add another callback to set task_id?
                jt = IJobTracker(self.context)
                job = jt.new_job('TODO: generate id',
                                 'generate taskname: ala_import')
                job.type = self.context.portal_type
                job.lsid = lsid
                # job reindex happens in next call
                jt.set_progress('PENDING', u'Data import pending')

        return 'info', u'Job submitted {0} - {1}'.format(self.context.title, self.state)

    @property
    def state(self):
        jt = IJobTracker(self.context, None)
        if jt is None:
            return None
        return jt.state
