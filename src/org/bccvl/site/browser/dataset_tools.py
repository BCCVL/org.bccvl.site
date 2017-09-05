import json
from Products.Five import BrowserView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.app.contentlisting.interfaces import IContentListingObject
from plone import api
from org.bccvl.site.content.interfaces import ISDMExperiment, IMSDMExperiment, IProjectionExperiment, IMMExperiment
from org.bccvl.site.interfaces import IDownloadInfo, IBCCVLMetadata
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.site.browser.interfaces import IDatasetTools
from org.bccvl.site.api.dataset import getdsmetadata
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.interfaces import ISiteRoot
from zope.security import checkPermission
from zope.component import getMultiAdapter, getUtility
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
import Missing
from org.bccvl.site import defaults
from org.bccvl.site.behavior.collection import ICollection
from org.bccvl.site.vocabularies import BCCVLSimpleVocabulary
from itertools import chain


def get_title_from_uuid(uuid):
    obj = uuidToObject(uuid)
    if obj:
        return obj.title
    return None


def safe_int(val, default):
    '''
    convert val to int without throwing an exception
    '''
    try:
        return int(val)
    except:
        return default


@implementer(IDatasetTools)
class DatasetTools(BrowserView):
    """A helper view to deal with datasets.

    It provides a couple of methods that are helpful within a page template.
    """

    _genre_vocab = None
    _layer_vocab = None
    _source_vocab = None
    _resolution_vocab = None
    _emsc_vocab = None
    _gcm_vocab = None

    def get_transition(self, itemob=None):
        # TODO: should this return all possible transitions?
        # return checkPermission('cmf.RequestReview', self.context)
        if itemob is None:
            itemob = self.context
        wftool = getToolByName(itemob, 'portal_workflow')
        wfid = wftool.getChainFor(itemob)[0]
        wf = wftool.getWorkflowById(wfid)
        # TODO: use workflow_tool.getTransitionsFor
        # check whether user can invoke transition
        # TODO: expects simple publication workflow publish/retract
        for transition in ('publish', 'retract'):
            if wf.isActionSupported(itemob, transition):
                return transition
        return {}

    def get_download_info(self, item=None):
        if item is None:
            item = self.context
        return IDownloadInfo(item)

    def can_modify(self, itemob=None):
        if itemob is None:
            itemob = self.context
        return checkPermission('cmf.ModifyPortalContent', itemob)

    # TODO: maybe move to different tools view? (not dataset specific)
    def local_roles_action(self, itemobj=None):
        if itemobj is None:
            itemobj = self.context
        context_state = getMultiAdapter((itemobj, self.request),
                                        name=u'plone_context_state')
        for action in context_state.actions().get('object'):
            if action.get('id') == 'local_roles':
                return action
        return {}

    def metadata(self, itemobj=None, uuid=None):
        if itemobj is None and uuid is None:
            itemobj = self.context
        if uuid:
            itemobj = uuidToObject(uuid)
        if itemobj is None:
            return None
        return getdsmetadata(itemobj)

    def species_metadata_for_result(self, result):
        job_params = result.job_params
        if 'species_occurrence_dataset' in job_params:
            # It's an SDM .... just get metadata
            return self.metadata(uuid=job_params['species_occurrence_dataset'])
        if 'species_distribution_models' in job_params:
            # It's a projection result
            return self.metadata(uuid=job_params['species_distribution_models'])

    # FIXME: make sure self.metadata is cached somehow and requseted only once per request
    # TODO: use more suitable serialisation (pure json doesn't have CRS)
    def bbox(self, itemobj=None):
        md = self.metadata(itemobj)
        if 'bounds' in md:
            return json.dumps(md.get("bounds", ""))
        # get first bounds of first layer... all layers should have thesame
        # bounds
        layermd = md['layers'].values()[0]
        return json.dumps(layermd.get("bounds", ""))

    def bccvlmd(self, itemobj=None):
        if itemobj is None:
            itemobj = self.context
        return IBCCVLMetadata(itemobj)

    def job_state(self, itemobj=None):
        if itemobj is None:
            itemobj = self.context
        # FIXME: assume we have a IContentListingObject
        return itemobj._brain.job_state

    def job_progress(self, itemobj=None):
        if itemobj is None:
            itemobj = self.context
        progress = IJobTracker(itemobj.getObject()).progress()
        if progress:
            return progress.get('message')
        return None

    # TODO: this is a result method
    def get_primary_output(self, resultobj=None):
        # FIXME: assumes resultobj or context is a brain
        if resultobj is None:
            resultobj = self.context
        pc = api.portal.get_tool('portal_catalog')
        for brain in pc.searchResults(path={'query': resultobj.getPath(), 'depth': 1},
                                      BCCDataGenre=('DataGenreCP', 'DataGenreCP_ENVLOP', 'DataGenceFP', 'DataGenreENDW_RICHNESS')):
            return IContentListingObject(brain)
        return None

    def get_biodiverse_output(self, resultobj=None):
        if resultobj is None:
            resultobj = self.context
        pc = api.portal.get_tool('portal_catalog')
        for brain in pc.searchResults(path={'query': resultobj.getPath(), 'depth': 1},
                                      BCCDataGenre=('DataGenreBiodiverseOutput')):
            return IContentListingObject(brain)
        return None

    def get_viz_class(self, itemobj=None, view='result'):
        md = self.bccvlmd(itemobj)
        default = {
            'DataGenreSpeciesOccurrence': 'bccvl-occurrence-viz',
            'DataGenreSpeciesAbsence': 'bccvl-absence-viz',
        }
        views = {
            'result': default,
            'biodiverse-viz': {
                'DataGenreSpeciesOccurrence': 'bccvl-occurrence-viz',
                'DataGenreSpeciesAbsence': 'bccvl-absence-viz',
                'DataGenreBiodiverseOutput': 'bccvl-biodiverse-viz',
            }
        }
        return views.get(view, default).get(md.get('genre'), 'bccvl-auto-viz')

    @property
    def genre_vocab(self):
        if self._genre_vocab is None:
            self._genre_vocab = getUtility(
                IVocabularyFactory, 'genre_source')(self.context)
        return self._genre_vocab

    def genre_list(self):
        selected = self.request.get('datasets.filter.genre', ())
        for genre in self.genre_vocab:
            if genre.value not in (
                    'DataGenreSpeciesOccurrence', 'DataGenreSpeciesAbsence',
                    'DataGenreSpeciesAbundance', 'DataGenreE',
                    'DataGenreCC', 'DataGenreFC', 'DataGenreTraits',
                    'DataGenreSDMModel'):
                continue
            yield {
                'selected': genre.token in selected,
                'disabled': False,
                'token': genre.token,
                'label': genre.title
            }

    def genre_title(self, genre):
        try:
            return self.genre_vocab.by_value[genre].title
        except Missing.Value:
            return u'Missing Genre'
        except TypeError:
            return u'Invalid Genre {0}'.format(repr(genre))
        except KeyError:
            return u'Genre not found {0}'.format(genre)
        except IndexError:
            return u'Invalid Genre {0}'.format(repr(genre))

    @property
    def layer_vocab(self):
        if self._layer_vocab is None:
            self._layer_vocab = getUtility(
                IVocabularyFactory, 'layer_source')(self.context)
        return self._layer_vocab

    def layer_title(self, layer):
        try:
            return self.layer_vocab.getTerm(layer).title
        except:
            return layer

    def layer_list(self):
        selected = self.request.get('datasets.filter.layer', ())
        for genre in self.layer_vocab:
            yield {
                'selected': genre.token in selected,
                'disabled': False,
                'token': genre.token,
                'label': genre.title
            }

    @property
    def resolution_vocab(self):
        if self._resolution_vocab is None:
            self._resolution_vocab = getUtility(
                IVocabularyFactory, 'resolution_source')(self.context)
        return self._resolution_vocab

    def resolution_list(self):
        selected = self.request.get('datasets.filter.resolution', ())
        for genre in self.resolution_vocab:
            yield {
                'selected': genre.token in selected,
                'disabled': False,
                'token': genre.token,
                'label': genre.title
            }

    @property
    def emsc_vocab(self):
        if self._emsc_vocab is None:
            self._emsc_vocab = getUtility(
                IVocabularyFactory, 'emsc_source')(self.context)
        return self._emsc_vocab

    def emsc_list(self):
        selected = self.request.get('datasets.filter.emsc', ())
        for genre in self.emsc_vocab:
            yield {
                'selected': genre.token in selected,
                'disabled': False,
                'token': genre.token,
                'label': genre.title
            }

    @property
    def gcm_vocab(self):
        if self._gcm_vocab is None:
            self._gcm_vocab = getUtility(
                IVocabularyFactory, 'gcm_source')(self.context)
        return self._gcm_vocab

    def gcm_list(self):
        selected = self.request.get('datasets.filter.gcm', ())
        for genre in self.gcm_vocab:
            yield {
                'selected': genre.token in selected,
                'disabled': False,
                'token': genre.token,
                'label': genre.title
            }

    @property
    def source_vocab(self):
        # TODO: this should be a lookup
        if self._source_vocab is None:
            portal = api.portal.get()
            dsfolder = portal[defaults.DATASETS_FOLDER_ID]
            self._source_vocab = BCCVLSimpleVocabulary(
                chain((
                    SimpleTerm('user', 'user', u'My Datasets'),
                    SimpleTerm('admin', 'admin', u'Provided by BCCVL'),
                    SimpleTerm('shared', 'shared', 'Shared')),
                    (SimpleTerm(item.getPhysicalPath(), '-'.join((group.getId(), item.getId())), item.Title())
                     for group in dsfolder.values()
                     for item in group.values())
                ))
        return self._source_vocab

    def source_list(self):
        selected = self.request.get('datasets.filter.source', ())
        portal = api.portal.get()
        dsfolder = portal[defaults.DATASETS_FOLDER_ID]
        # yield user groups first:
        yield {
            'label': 'Collection by Users',
            'items': [
                {'selected': genre.token in selected,
                 'disabled': False,
                 'token': genre.token,
                 'label': genre.title
                 } for genre in (SimpleTerm('user', 'user', u'My Datasets'),
                                 SimpleTerm('admin', 'admin',
                                            u'Provided by BCCVL'),
                                 SimpleTerm('shared', 'shared', 'Shared'))]
        }
        # yield collections
        for group in dsfolder.values():
            yield {
                'label': group.title,
                'items': [
                    {'selected': '-'.join((group.getId(), item.getId())) in selected,
                     'disabled': False,
                     'token': '-'.join((group.getId(), item.getId())),
                     'label': item.title,
                     } for item in group.values()]
            }
        # for genre in self.source_vocab:
        #     yield {
        #         'selected': genre.token in selected,
        #         'disabled': False,
        #         'token': genre.token,
        #         'label': genre.title
        #     }

    def experiment_inputs(self, context=None):
        # return visualisable input datasets for experiment
        # - used in overlay and compare pages
        if context is None:
            context = self.context
        pc = getToolByName(self.context, 'portal_catalog')
        if ISDMExperiment.providedBy(context):
            # for sdm we return selected occurrence and absence dataset
            # TODO: once available include pesudo absences from result
            for dsuuid in (context.species_occurrence_dataset,
                           context.species_absence_dataset):
                brain = uuidToCatalogBrain(dsuuid)
                if brain:
                    yield brain
        elif IMMExperiment.providedBy(context):
            # for mme we return selected occurrence dataset only
            # TODO: once available include pesudo absences from result
            for dsuuid in (context.species_occurrence_dataset,):
                brain = uuidToCatalogBrain(dsuuid)
                if brain:
                    yield brain
        elif IMSDMExperiment.providedBy(context):
            # muilt species sdm inputs
            for dsuuid in (context.species_occurrence_collections):
                brain = uuidToCatalogBrain(dsuuid)
                if brain:
                    yield brain
        elif IProjectionExperiment.providedBy(context):
            # one experiment - multiple models
            for sdmuuid, models in context.species_distribution_models.items():
                sdm = uuidToObject(sdmuuid)
                if not sdm:
                    continue
                # yield occurrence / absence points
                for x in self.experiment_inputs(sdm):
                    yield x
                for model in models:
                    # yield current projections for each model
                    model_brain = uuidToCatalogBrain(model)
                    if not model_brain:
                        continue
                    res_path = model_brain.getPath().rsplit('/', 1)
                    for projection in pc.searchResults(path=res_path,
                                                       BCCDataGenre=('DataGenreCP', 'DataGenreCP_ENVLOP')):
                        yield projection

    def experiment_results(self, context=None):
        # return visualisable results for experiment
        # - used in overlay and compare
        if context is None:
            context = self.context
        pc = getToolByName(self.context, 'portal_catalog')
        genres = ('DataGenreFP', 'DataGenreCP', 'DataGenreSpeciesAbsence',
                  'DataGenreFP_ENVLOP', 'DataGenreCP_ENVLOP', 'DataGenreBinaryImage',
                  'DataGenreENDW_CWE', 'DataGenreENDW_WE',
                  'DataGenreENDW_RICHNESS', 'DataGenreENDW_SINGLE',
                  'DataGenreREDUNDANCY_SET1', 'DataGenreREDUNDANCY_SET2',
                  'DataGenreREDUNDANCY_ALL', 'DataGenreRAREW_CWE',
                  'DataGenreRAREW_RICHNESS', 'DataGenreRAREW_WE',
                  'DataGenreEnsembleResult', 'DataGenreClimateChangeMetricMap')
        # context should be a result folder
        for brain in pc.searchResults(path='/'.join(context.getPhysicalPath()),
                                      BCCDataGenre=genres):
            yield brain

    # FIXME: this method should be merged with experiment_results above
    # TODO: both methods are good candidates for ajax API methods and template
    # API methods (also should be more generic like finding results from
    # different experiments / results)
    def experiment_plots(self, context=None):
        # return visualisable results for experiment
        # - used in overlay and compare
        if context is None:
            context = self.context
        pc = getToolByName(self.context, 'portal_catalog')
        genres = ('DataGenreSDMEval', )
        # context should be a result folder
        for brain in pc.searchResults(path='/'.join(context.getPhysicalPath()),
                                      BCCDataGenre=genres):
            # FIXME: this check is very inefficient but we are lacking a
            # contentype index field
            dlinfo = IDownloadInfo(brain.getObject())
            if not dlinfo['contenttype'].startswith('image/'):
                continue
            yield brain

    def details(self, context=None):
        # fetch details about dataset, if attributes are unpopulated
        # get data from associated collection
        if context is None:
            context = self.context
        coll = context
        while not (ISiteRoot.providedBy(coll) or ICollection.providedBy(coll)):
            coll = coll.__parent__
        # we have either hit siteroot or found a collection
        ret = {
            'title': context.title,
            'description': context.description or coll.description,
            'attribution': context.attribution or getattr(coll, 'attribution'),
            'rights': context.rights or coll.rights,
            'external_description': context.external_description or getattr(coll, 'external_description'),
        }
        md = IBCCVLMetadata(context)
        if 'layers' in md:
            layers = []
            for layer in sorted(md.get('layers', ())):
                try:
                    layers.append(self.layer_vocab.getTerm(layer))
                except:
                    layers.append(SimpleTerm(layer, layer, layer))
            if layers:
                ret['layers'] = layers
        return ret

    def collection_layers(self, context=None):
        # return a list of layers for the whole collection
        if context is None:
            context = self.context
        pc = api.portal.get_tool('portal_catalog')
        query = {
            'path': {
                'query': '/'.join(context.getPhysicalPath()),
                'depth': -1
            },
            'portal_type': ('org.bccvl.content.dataset',
                            'org.bccvl.content.remotedataset')
        }
        # search for datasets
        brains = pc.searchResults(**query)
        index = pc._catalog.getIndex('BCCEnviroLayer')
        # get all layers for all datasets
        layers = set((l for brain in brains for l in (
            index.getEntryForObject(brain.getRID()) or ())))
        layer_vocab = getUtility(IVocabularyFactory, 'layer_source')(context)
        for layer in sorted(layers):
            try:
                yield layer_vocab.getTerm(layer)
            except:
                yield SimpleTerm(layer, layer, layer)
