from Products.Five import BrowserView
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.interfaces import IDownloadInfo, IBCCVLMetadata
from org.bccvl.site.browser.interfaces import IDatasetTools
from org.bccvl.site.api.dataset import getdsmetadata
from Products.CMFCore.utils import getToolByName
from zope.security import checkPermission
from zope.component import getMultiAdapter, getUtility
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
import Missing


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
        #return checkPermission('cmf.RequestReview', self.context)
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

    def metadata(self, itemobj=None):
        if itemobj is None:
            itemobj = self.context
        return getdsmetadata(itemobj)

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

    @property
    def genre_vocab(self):
        if self._genre_vocab is None:
            genre_list = ('DataGenreSpeciesOccurrence', 'DataGenreSpeciesAbsence',
                          'DataGenreSpeciesAbundance', 'DataGenreE',
                          'DataGenreCC', 'DataGenreFC', 'DataGenreTraits',
                          'DataGenreSDMModel')
            genre_source = getUtility(IVocabularyFactory, 'genre_source')(self.context)
            self._genre_vocab = SimpleVocabulary([genre_source.getTerm(genre) for genre in genre_list])
        return self._genre_vocab

    def genre_list(self):
        selected = self.request.get('datasets.filter.genre', ())
        for genre in self.genre_vocab:
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
            self._layer_vocab = getUtility(IVocabularyFactory, 'layer_source')(self.context)
        return self._layer_vocab

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
            self._resolution_vocab = getUtility(IVocabularyFactory, 'resolution_source')(self.context)
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
            self._emsc_vocab = getUtility(IVocabularyFactory, 'emsc_source')(self.context)
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
            self._gcm_vocab = getUtility(IVocabularyFactory, 'gcm_source')(self.context)
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
            self._source_vocab = SimpleVocabulary((
                SimpleTerm('user', 'user', u'My Datasets'),
                SimpleTerm('admin', 'admin', u'Provided by BCCVL'),
                # SimpleTerm('ala', 'ala', u'Imported from ALA'),
                SimpleTerm('shared', 'shared', 'Shared'),
            ))
        return self._source_vocab

    def source_list(self):
        selected = self.request.get('datasets.filter.source', ())
        for genre in self.source_vocab:
            yield {
                'selected': genre.token in selected,
                'disabled': False,
                'token': genre.token,
                'label': genre.title
            }




# FIXME: this view needs to exist for default browser layer as well
#        otherwise diazo.off won't find the page if set up.
#        -> how would unthemed markup look like?
#        -> theme would only have updated template.
from Products.AdvancedQuery import In, Eq, Not, Generic, And


class DatasetsListingTool(BrowserView):
    '''
    Accepted search parameters:

    datasets.filter.text: searches full text index SearchableText
    datasets.filter.genre:list: matches BCCDataGenre index
    datasets.filter.resolution:list: matches in BCCResolution index
    datasets.filter.layer:list: matches selected layers in BCCEnviroLayer
    datasets.filter.emsc:list: matches emission scenarios in BCCEmissionScenario
    datasets.filter.gcm:list: matches global ciruclation models in BCCGlobalClimateModel
    TODO: datasets.filter.year:list: matches years in ????
    datasets.filter.source:list: ...
    datasets.filter.sort: ....
    datasets.filter.order: asc, desc
    b_size: batch size
    b_start: batch start
    '''

    _dstools = None
    path = None

    @property
    def dstools(self):
        if not self._dstools:
            self._dstools = getMultiAdapter((self.context, self.request),
                                            name="dataset_tools")
        return self._dstools

    def contentFilterAQ(self):
        '''
        Parse request and generate AdvancedQuery query
        '''
        portal_state = getMultiAdapter(
            (self.context, self.request), name="plone_portal_state")
        member = portal_state.member()

        query_parts = []

        text = self.request.get('datasets.filter.text')
        if text:
            query_parts.append(Eq('SearchableText', text))

        genre = self.request.get('datasets.filter.genre')
        genre_vocab = self.dstools.genre_vocab
        if genre:
            # convert token from request to value
            query_parts.append(In('BCCDataGenre', [genre_vocab.getTermByToken(token).value for token in genre if token in genre_vocab.by_token]))
        else:
            # if nothing selcted use all values in vocab
            query_parts.append(In('BCCDataGenre', list(genre_vocab.by_value.keys())))

        resolution = self.request.get('datasets.filter.resolution')
        resolution_vocab = self.dstools.resolution_vocab
        if resolution:
            # convert token to value
            query_parts.append(In('BCCResolution', [resolution_vocab.getTermByToken(token).value for token in resolution if token in resolution_vocab.by_token]))

        layer = self.request.get('datasets.filter.layer')
        layer_vocab = self.dstools.layer_vocab
        if layer:
            query_parts.append(In('BCCEnviroLayer', [layer_vocab.getTermByToken(token).value for token in layer if token in layer_vocab.by_token]))

        emsc = self.request.get('datasets.filter.emsc')
        emsc_vocab = self.dstools.emsc_vocab
        if emsc:
            query_parts.append(In('BCCEmissionScenario', [emsc_vocab.getTermByToken(token).value for token in emsc if token in emsc_vocab.by_token]))

        gcm = self.request.get('datasets.filter.gcm')
        gcm_vocab = self.dstools.gcm_vocab
        if gcm:
            query_parts.append(In('BCCGlobalClimateModel', [gcm_vocab.getTermByToken(token).value for token in gcm if token in gcm_vocab.by_token]))

        # TODO: year

        # FIXME: source filter is incomplete
        source = self.request.get('datasets.filter.source')
        if source:
            for token in source:
                if token == 'user':
                    query_parts.append(Eq('Creator', member.getId()))
                elif token == 'admin':
                    query_parts.append(Eq('Creator', 'BCCVL'))
                elif token == 'shared':
                    query_parts.append(Not(In('Creator', (member.getId(), 'BCCVL'))))
                # FIXME: missing: shared, ala

        # add path filter
        if self.path:
            query_parts.append(
                Generic('path', {'query': self.path,
                                 'depth': -1}))
        # add additional query filters
        query_parts.append(
            Eq('object_provides', IDataset.__identifier__)
        )
        return And(*query_parts)

    def contentFilter(self):
        portal_state = getMultiAdapter(
            (self.context, self.request), name="plone_portal_state")
        member = portal_state.member()

        query = {}
        
        query['job_state'] = ['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED']

        text = self.request.get('datasets.filter.text')
        if text:
            query['SearchableText'] = text

        genre = self.request.get('datasets.filter.genre')
        genre_vocab = self.dstools.genre_vocab
        if genre:
            # convert token from request to value
            query['BCCDataGenre'] = [genre_vocab.getTermByToken(token).value for token in genre if token in genre_vocab.by_token]
        else:
            # if nothing selcted use all values in vocab
            query['BCCDataGenre'] =  list(genre_vocab.by_value.keys())

        resolution = self.request.get('datasets.filter.resolution')
        resolution_vocab = self.dstools.resolution_vocab
        if resolution:
            # convert token to value
            query['BCCResolution'] = [resolution_vocab.getTermByToken(token).value for token in resolution if token in resolution_vocab.by_token]

        layer = self.request.get('datasets.filter.layer')
        layer_vocab = self.dstools.layer_vocab
        if layer:
            query['BCCEnviroLayer'] = [layer_vocab.getTermByToken(token).value for token in layer if token in layer_vocab.by_token]

        emsc = self.request.get('datasets.filter.emsc')
        emsc_vocab = self.dstools.emsc_vocab
        if emsc:
            query['BCCEmissionScenario'] = [emsc_vocab.getTermByToken(token).value for token in emsc if token in emsc_vocab.by_token]

        gcm = self.request.get('datasets.filter.gcm')
        gcm_vocab = self.dstools.gcm_vocab
        if gcm:
            query['BCCGlobalClimateModel'] = [gcm_vocab.getTermByToken(token).value for token in gcm if token in gcm_vocab.by_token]

        # TODO: year

        # FIXME: source filter is incomplete
        source = self.request.get('datasets.filter.source')
        if source:
            for token in source:
                if token == 'user':
                    query['Creator'] = member.getId()
                elif token == 'admin':
                    query['Creator'] = 'BCCVL'
                elif token == 'shared':
                    pc = getToolByName(self.context, 'portal_catalog')
                    vals = filter(lambda x: x not in ('BCCVL', member.getId()),
                                  pc.uniqueValuesFor('Creator'))
                    query['Creator'] = vals
                # FIXME: missing: ala

        # add path filter
        if self.path:
            query['path'] = {
                'query': self.path,
                'depth': -1
            }

        # add fixed query parameters:
        query['object_provides'] = IDataset.__identifier__

        return query

    def datasetslisting(self):
        """
        Render the datasets listing section.

        Accepted parameters:
        - Batch range
        - filters
        - ajax ... render only list
        - uuid + ajax ... render only one entry
        """
        # FIXME: decide AdvancedQuery or not; need to do some performance tests with ManagedIndex and Incrementalsearch offered by AQ
        USE_AQ = False
        if USE_AQ:
            query_params = self.contentFilterAQ()
        else:
            query_params = self.contentFilter()
        b_size = safe_int(self.request.get('b_size'), 20)
        b_start = safe_int(self.request.get('b_start'), 0)
        # get sort parameters
        orderby = self.request.get('datasets.filter.sort')
        orderby = {
            'modified': ('modified', 'desc'),
            'created': ('created', 'desc'),
            'title': ('sortable_title', 'asc')
        }.get(orderby, ('modified', 'desc'))

        # use descending as default for last modified sorting
        # TODO: use different defaults for different filters?
        order = self.request.get('datasets.filter.order', orderby[1])
        if order not in ('asc', 'desc'):
            order = orderby[1]

        pc = getToolByName(self.context, 'portal_catalog')
        from Products.CMFPlone import Batch
        if USE_AQ:
            # TODO: we could do multi field sorting here
            brains = pc.evalAdvancedQuery(query_params, ((orderby[0], order), ))
        else:
            order = {'asc': 'ascending',
                     'desc': 'descending'}.get(order)
            query_params.update({
                'sort_on': orderby[0],
                'sort_order': order})
            brains = pc.searchResults(query_params)  # show_all=1?? show_inactive=show_inactive?
        batch = Batch(brains, b_size, b_start, orphan=0)
        return batch


@implementer(IFolderContentsView)
class DatasetsListingView(BrowserView):
    '''
    Accepted search parameters:

    datasets.filter.text: searches full text index SearchableText
    datasets.filter.genre: matches BCCDataGenre index
    datasets.filter.resolution: matches in BCCResolution index
    datasets.filter.layer:list: matches selected layers in BCCEnviroLayer
    datasets.filter.emsc:list: matches emission scenarios in BCCEmissionScenario
    datasets.filter.gcm:list: matches global ciruclation models in BCCGlobalClimateModel
    # TODO: year
    datasets.filter.source: ...
    datasets.filter.sort: ....
    datasets.filter.order: asc, desc
    b_size: batch size
    b_start: batch start
    '''

    def __call__(self):
        # initialise instance variables, we'll do it here so that we have
        # security set up and have to do it only once per request
        self.dstools = getMultiAdapter((self.context, self.request),
                                       name="dataset_tools")
        return super(DatasetsListingView, self).__call__()

    def datasetslisting(self):
        dslisttool = DatasetsListingTool(self.context, self.request)
        dslisttool.path = '/'.join(self.context.getPhysicalPath())
        return dslisttool.datasetslisting()


class DatasetsListingPopup(BrowserView):
    # TODO: ... maybe update the layers widget to select datasets,
    #           and use widget on page to activate layers? (a bit like sdm experiment and model selection for Projectien experiment)

    genre = 'DataGenreSpeciesOccurrence'

    def __call__(self):
        # initialise instance variables, we'll do it here so that we have
        # security set up and have to do it only once per request
        self.dstools = getMultiAdapter((self.context, self.request),
                                       name="dataset_tools")
        return super(DatasetsListingPopup, self).__call__()

    def datasetslisting(self):
        dslisttool = DatasetsListingTool(self.context, self.request)
        return dslisttool.datasetslisting()

    def match_selectedlayers(self, md):
        selected = self.request.get('datasets.filter.layer', ())
        layer_vocab = self.dstools.layer_vocab
        # FIXME: there should never be a dataset without layers here
        for layer in md.get('layers', ()):
            if not selected:
                # no filter set.. just yield everything
                yield layer_vocab.getTerm(layer)
            else:
                # filter set...
                layerterm = layer_vocab.getTerm(layer)
                if layerterm.token in selected:
                    yield layerterm
