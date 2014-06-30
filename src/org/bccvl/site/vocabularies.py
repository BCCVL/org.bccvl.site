from zope.schema.interfaces import IContextSourceBinder, IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from org.bccvl.site import defaults
from zope.interface import implementer, provider
from zope.component import getUtility, queryUtility
from gu.z3cform.rdf.interfaces import IORDF
from gu.z3cform.rdf.utils import Period
from Products.CMFCore.utils import getToolByName
from gu.z3cform.rdf.vocabulary import SparqlInstanceVocabularyFactory
from org.bccvl.site.namespace import BCCGCM, BCCEMSC, BIOCLIM, BCCVOCAB
from rdflib import RDF
from Products.CMFPlone.interfaces import IPloneSiteRoot


class QueryAPI(object):
    """
    Provides API for common queries
    """
    def __init__(self, context):
        site = queryUtility(IPloneSiteRoot)

        self.context = context
        self.site = site
        self.site_physical_path = '/'.join(site.getPhysicalPath())
        self.portal_catalog = site.portal_catalog

    # def getDatasets(self, genre):
    def getDatasets(self, **query_params):
        # datasets_physical_path = '/'.join(
        #     [self.site_physical_path, defaults.DATASETS_FOLDER_ID]
        # )
        # brains = self.portal_catalog(
        #     path={'query': datasets_physical_path},
        #     # BCCDataGenre = genre,
        #     **query_params
        # )
        # path query won't find result datasets
        brains = self.portal_catalog(
            object_provides='org.bccvl.site.content.interfaces.IDataset',
            ** query_params)
        return brains

    def getSpeciesOccurrenceDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreSO'],
                                job_state='COMPLETED')

    def getSpeciesDistributionModelEvaluationDatasets(self):
        return self.getDatasets(BCCDateGenre=BCCVOCAB['DataGenreSDMEval'])

    def getEnviroLayers(self):
        return self.portal_catalog.uniqueValuesFor('BCCEnviroLayer')

    def getExperiments(self):
        experiments_physical_path = '/'.join(
            [self.site_physical_path, defaults.EXPERIMENTS_FOLDER_ID]
        )
        brains = self.portal_catalog(
            path={'query': experiments_physical_path},
            object_provides='org.bccvl.site.content.interfaces.IExperiment',
            sort_on='created',
            sort_order='descending'
        )
        return brains


# species occurrence datasets
from zope.site.hooks import getSite


# TODO: optimize catalog vocabulary for lazy sliced access
class BrainsVocabulary(SimpleVocabulary):
    # term.value ... UUID
    # term.token ... UUID
    # term.title ... Title
    # term.brain ... the brain

    # implements IVocaburaryTokenized

    @classmethod
    def createTerm(cls, brain, context):
        term = SimpleTerm(value=brain['UID'],
                          token=brain['UID'],
                          title=brain.Title)
        term.brain = brain
        return term

    @classmethod
    def fromBrains(cls, brains, context, *interfaces):
        terms = [cls.createTerm(brain, context) for brain in brains]
        return cls(terms, *interfaces)


@implementer(IVocabularyFactory)
class CatalogVocabularyFactory(object):

    def __init__(self, name, query):
        self.__name__ = name
        self.query = query

    def __call__(self, context):
        try:
            catalog = getToolByName(context, 'portal_catalog')
        except AttributeError:
            catalog = getToolByName(getSite(), 'portal_catalog')
        brains = catalog(**self.query)
        return BrainsVocabulary.fromBrains(brains, context)


@implementer(IContextSourceBinder)
class CatalogSourceBinder(object):

    def __init__(self, name, query):
        self.__name__ = name
        self.query = query

    def _getBrains(self, context):
        try:
            catalog = getToolByName(context, 'portal_catalog')
        except AttributeError:
            catalog = getToolByName(getSite(), 'portal_catalog')
        return catalog(**self.query)

    def getTerms(self, context):
        brains = self._getBrains(context)
        terms = [BrainsVocabulary.createTerm(brain, context)
                 for brain in brains]  # has to be a list will be iterated more than once
        return terms

    def __call__(self, context):
        brains = self._getBrains(context)
        return BrainsVocabulary.fromBrains(brains, context)


species_presence_datasets_vocab = CatalogVocabularyFactory(
    'species_presence_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSO'],
        'BCCSpeciesLayer': BCCVOCAB['SpeciesLayerP'],
        'job_state': 'COMPLETED'
    })

species_absence_datasets_vocab = CatalogVocabularyFactory(
    'species_absence_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSO'],
        'BCCSpeciesLayer': BCCVOCAB['SpeciesLayerX'],
        'job_state': 'COMPLETED',
    })

species_abundance_datasets_vocab = CatalogVocabularyFactory(
    'species_abundance_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSO'],
        'BCCSpeciesLayer': BCCVOCAB['SpeciesLayerA'],
        'job_state': 'COMPLETED',
    })

environmental_datasets_vocab = CatalogVocabularyFactory(
    'environmental_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreE'],
        #'job_state': 'COMPLETED',
    })

future_climate_datasets_vocab = CatalogVocabularyFactory(
    # TODO: might be useful for this vocab to support additional parameters like
    #       year, emsc, gcm, etc...
    'future_climate_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreFC'],
        #'job_state': 'COMPLETED',
    })

species_distributions_models_vocab = CatalogVocabularyFactory(
    # TODO: would this here work better with path restrictions?
    'species_distributions_models_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSDMModel'],
        'job_state': 'COMPLETED',
    })


species_projection_datasets_vocab = CatalogVocabularyFactory(
    # TODO: would this here work better with path restrictions?
    'species_projection_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreFP'],
        'job_state': 'COMPLETED',
    })

species_traits_datasets_vocab = CatalogVocabularyFactory(
    'species_traits_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreTraits'],
        'job_state': 'COMPLETED',
    })

# TODO: Need either two vocabs to separate sdm and traits scripts,
#       or a contextsourcebinder that filters the correct scrips
sdm_functions_source = CatalogSourceBinder(
    'sdm_functions_source',
    query={
        # TODO: could use a path restriction to toolkits folder
        # 'path': {
        #     'query': '/'.join([self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID])
        # },
        'object_provides': 'org.bccvl.site.content.function.IFunction',
        # FIXME: find another way to separate SDM and traits "functions"
        'id': ['ann', 'bioclim', 'brt', 'circles', 'convhull', 'cta', 'domain',
               'fda', 'gam', 'gbm', 'glm', 'maxent'],
        'sort_on': 'sortable_title',
    },
)


traits_functions_source = CatalogSourceBinder(
    'traits_functions_source',
    query={
        # TODO: could use a path restriction to toolkits folder
        # 'path': {
        #     'query': '/'.join([self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID])
        # },
        'object_provides': 'org.bccvl.site.content.function.IFunction',
        # FIXME: find another way to separate SDM and traits "functions"
        'id': ['lm'],
        'sort_on': 'sortable_title',
    },
)


@implementer(IContextSourceBinder)
class SparqlDataSetSourceBinder(object):

    def __init__(self, name, apiFunc):
        self.__name__ = name
        self.apiFunc = apiFunc

    def __call__(self, context):
        if context is None:
            # some widgets don't provide a context so let's fall back
            # to site root
            context = queryUtility(IPloneSiteRoot)
        if context is None:
            # if we have no site return empty
            return SimpleVocabulary()
        api = QueryAPI(context)
        urirefs = getattr(api, self.apiFunc)()
        if urirefs:
            query = []
            # TODO: uri could be None???
            # TODO: maybe rebuild this query to fetch all labels from rdf
            #       and fetch all uris from catalog and do a set intersection
            #       all layers could be a 2nd vocabulary?
            # FIXME: order in sparqlquery instead of sorted call afterwards
            for uri in urirefs:
                query.append('{ BIND(%(uri)s as ?uri) '
                             '%(uri)s rdfs:label ?label }' %
                             {'uri': uri.n3()})
            query = ("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> \n"
                     "SELECT ?uri ?label WHERE { Graph?g { %s } }" %
                     "UNION".join(query))
            handler = getUtility(IORDF).getHandler()
            result = handler.query(query)
            # FIXME: can I turn this into a generator?
            terms = [SimpleTerm(value=item['uri'],
                                token=str(item['uri']),
                                title=unicode(item['label']))
                     for item in result]
            # TODO: get rid of sorted ... query should do it
            terms = sorted(terms, key=lambda o: o.title)
        else:
            terms = [] # FIXME: should be a SimpleVocabulary?
        return SimpleVocabulary(terms)


envirolayer_source = SparqlDataSetSourceBinder(
    'envirolayer_source', 'getEnviroLayers')


@implementer(IContextSourceBinder)
class SparqlValuesSourceBinder(object):
    # TODO: only return values relevant to the sdm?

    def __init__(self, name, query, title_getter=None):
        self.__name__ = name
        self._query = query
        if title_getter is None:
            title_getter = lambda x: x['label']
        self._get_term_title = title_getter

    def __call__(self, context):
        if context is None:
            # some widgets don't provide a context so let's fall back
            # to site root
            context = queryUtility(IPloneSiteRoot)
        if context is None:
            # if we have no site return empty
            return SimpleVocabulary()
        handler = getUtility(IORDF).getHandler()
        result = handler.query(self._query)
        # FIXME: generator?
        terms = [
            SimpleTerm(
                value=item['uri'],
                token=str(item['uri']),
                title=unicode(self._get_term_title(item)),
            )
            for item in result
        ]
        # TODO: get rid of sorted ... query should do it
        terms = sorted(terms, key=lambda o: o.title)
        return SimpleVocabulary(terms)

emission_scenarios_source = SparqlValuesSourceBinder(
    'emission_scenarios_source',
    """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX bccprop: <http://namespaces.bccvl.org.au/prop#>
        PREFIX bccvocab: <http://namespaces.bccvl.org.au/vocab#>

        SELECT DISTINCT ?uri, ?label WHERE {
         Graph ?a {
           ?s bccprop:datagenre bccvocab:DataGenreFC .
           ?s bccprop:emissionscenario ?uri .
         } Graph ?b {
           ?uri rdfs:label ?label .
          }
        }
    """
)

global_climate_models_source = SparqlValuesSourceBinder(
    'global_climate_models_source',
    """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX bccprop: <http://namespaces.bccvl.org.au/prop#>
        PREFIX bccvocab: <http://namespaces.bccvl.org.au/vocab#>

        SELECT DISTINCT ?uri, ?label WHERE {
          Graph ?a {
            ?s bccprop:datagenre bccvocab:DataGenreFC .
            ?s bccprop:gcm ?uri .
          } Graph ?b {
            ?uri rdfs:label ?label .
          }
        }
    """
)

fc_years_source = SparqlValuesSourceBinder(
    'fc_years_source',
    """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX bccprop: <http://namespaces.bccvl.org.au/prop#>
        PREFIX bccvocab: <http://namespaces.bccvl.org.au/vocab#>
        PREFIX dcterms: <http://purl.org/dc/terms/>

        SELECT DISTINCT ?uri, ?label WHERE {
          Graph ?a {
            ?s bccprop:datagenre bccvocab:DataGenreFC .
            ?s dcterms:temporal?uri .
            BIND(?uri as ?label) .
          }
        }
    """,
    lambda x: Period(x['label']).start,
)


BioclimVocabularyFactory = SparqlInstanceVocabularyFactory(BIOCLIM['BioclimaticVariable'])
GCMVocabularyFactory = SparqlInstanceVocabularyFactory(BCCGCM['GCM'])
EMSCVocabularyFactory = SparqlInstanceVocabularyFactory(BCCEMSC['EMSC'])

SpeciesDataGenreVocabularyFactory = SparqlInstanceVocabularyFactory(BCCVOCAB['SpeciesDataGenre'])
SpeciesLayerVocabularyFactory = SparqlInstanceVocabularyFactory(BCCVOCAB['SpeciesLayer'])
EnvironmentalDataGenreVocabularyFactory = SparqlInstanceVocabularyFactory(BCCVOCAB['EnvironmentalDataGenre'])
DatasetTypeVocabularyFactory = SparqlInstanceVocabularyFactory(BCCVOCAB['DataSetType'])
ResolutionVocabularyFactory = SparqlInstanceVocabularyFactory(BCCVOCAB['Resolution'],
                                                              RDF['value'])


programming_language_vocab = SimpleVocabulary([
    SimpleTerm("R", "R", u'R'),
    SimpleTerm("Perl", "Perl", u'Perl'),
#    SimpleTerm("Python", "Python", u'Python'),
])


@provider(IVocabularyFactory)
def programming_language_vocab_factory(context):
    return programming_language_vocab
