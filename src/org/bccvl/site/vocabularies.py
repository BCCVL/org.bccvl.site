from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from org.bccvl.site import defaults
from zope.interface import implementer, provider
from zope.component import getUtility, queryUtility
from gu.z3cform.rdf.interfaces import IORDF
from gu.z3cform.rdf.utils import Period
from Products.CMFCore.utils import getToolByName
from gu.z3cform.rdf.vocabulary import SparqlInstanceVocabularyFactory
from gu.z3cform.rdf.vocabulary import StaticSparqlInstanceVocabularyFactory
from org.bccvl.site.namespace import BCCGCM, BCCEMSC, BIOCLIM, BCCVOCAB, GML
from rdflib import RDF
from Products.CMFPlone.interfaces import IPloneSiteRoot
from org.bccvl.site.api import dataset


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
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreSpeciesOccurrence'],
                                job_state='COMPLETED')

    def getSpeciesDistributionModelEvaluationDatasets(self):
        return self.getDatasets(BCCDateGenre=BCCVOCAB['DataGenreSDMEval'])

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
from zope.interface import directlyProvides


class BCCVLSimpleVocabulary(SimpleVocabulary):
    """
    A SimpleVocabulary, that takes advantage of terms
    supplied as generators.
    """

    def __init__(self, terms, *interfaces):
        """Initialize the vocabulary given an iterable of terms.

        The vocabulary keeps a reference to the list of terms passed
        in; it should never be modified while the vocabulary is used.

        One or more interfaces may also be provided so that alternate
        widgets may be bound without subclassing.
        """
        self.by_value = {}
        self.by_token = {}
        self._terms = []
        for term in terms:
            if term.value in self.by_value:
                raise ValueError(
                    'term values must be unique: %s' % repr(term.value))
            if term.token in self.by_token:
                raise ValueError(
                    'term tokens must be unique: %s' % repr(term.token))
            self.by_value[term.value] = term
            self.by_token[term.token] = term
            self._terms.append(term)
        if interfaces:
            directlyProvides(self, *interfaces)

    @classmethod
    def fromItems(cls, items, *interfaces):
        """Construct a vocabulary from an iterable of (token, value) pairs.

        The order of the items is preserved as the order of the terms
        in the vocabulary.  Terms are created by calling the class
        method createTerm() with the pair (value, token).

        One or more interfaces may also be provided so that alternate
        widgets may be bound without subclassing.
        """
        terms = (cls.createTerm(value, token) for (token, value) in items)
        return cls(terms, *interfaces)

    @classmethod
    def fromValues(cls, values, *interfaces):
        """Construct a vocabulary from a simple iterable list.

        Values of the list become both the tokens and values of the
        terms in the vocabulary.  The order of the values is preserved
        as the order of the terms in the vocabulary.  Tokens are
        created by calling the class method createTerm() with the
        value as the only parameter.

        One or more interfaces may also be provided so that alternate
        widgets may be bound without subclassing.
        """
        terms = (cls.createTerm(value) for value in values)
        return cls(terms, *interfaces)


# TODO: optimize catalog vocabulary for lazy sliced access
class BrainsVocabulary(BCCVLSimpleVocabulary):
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
        terms = (cls.createTerm(brain, context) for brain in brains)
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
        brains = catalog.searchResults(**self.query)
        return BrainsVocabulary.fromBrains(brains, context)


species_presence_datasets_vocab = CatalogVocabularyFactory(
    'species_presence_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSpeciesOccurrence'],
        #'BCCSpeciesLayer': BCCVOCAB['SpeciesLayerP'],
        'job_state': 'COMPLETED'
    })

species_absence_datasets_vocab = CatalogVocabularyFactory(
    'species_absence_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSpeciesAbsence'],
        #'BCCSpeciesLayer': BCCVOCAB['SpeciesLayerX'],
        'job_state': 'COMPLETED',
    })

species_abundance_datasets_vocab = CatalogVocabularyFactory(
    'species_abundance_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreSpeciesAbundance'],
        #'BCCSpeciesLayer': BCCVOCAB['SpeciesLayerA'],
        'job_state': 'COMPLETED',
    })

environmental_datasets_vocab = CatalogVocabularyFactory(
    'environmental_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': BCCVOCAB['DataGenreE'],
        #'job_state': 'COMPLETED',
    })

current_environmental_datasets_vocab = CatalogVocabularyFactory(
    'current_environmental_datasets_vocab',
    query={
        'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
        'BCCDataGenre': (BCCVOCAB['DataGenreCC'], BCCVOCAB['DataGenreE']),
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
sdm_functions_source = CatalogVocabularyFactory(
    'sdm_functions_source',
    query={
        # TODO: could use a path restriction to toolkits folder
        # 'path': {
        #     'query': '/'.join([self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID])
        # },
        'object_provides': 'org.bccvl.site.content.function.IFunction',
        # FIXME: find another way to separate SDM and traits "functions"
        'id': ['ann', 'bioclim', 'brt', 'circles', 'cta', 'convhull', 'domain',
               'fda', 'gam', 'gbm', 'glm', 'geoDist', 'geoIDW', 'mahal',
               'maxent', 'mars', 'rf', 'sre', 'voronoiHull'],
        'sort_on': 'sortable_title',
    },
)


traits_functions_source = CatalogVocabularyFactory(
    'traits_functions_source',
    query={
        # TODO: could use a path restriction to toolkits folder
        # 'path': {
        #     'query': '/'.join([self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID])
        # },
        'object_provides': 'org.bccvl.site.content.function.IFunction',
        # FIXME: find another way to separate SDM and traits "functions"
        'id': ['lm', 'speciestrait_glm', 'speciestrait_gam',
               'aov', 'manova'],
        'sort_on': 'sortable_title',
    },
)


@implementer(IVocabularyFactory)
class DatasetLayerVocabularyFactory(object):
    """
    Fetches layers and labels for a context.
    """

    def __init__(self, name):
        # key ... metadata field in catalog
        self.__name__ = name

    def __call__(self, context):
        if context is None:
            # we can't return anything useful if we don't have a context.
            return []
        # start with empty terms list
        terms = []
        # fetch layermetadata
        lmd = dataset.getbiolayermetadata(context)
        layers = lmd.get('layers', [])
        if len(layers) > 0:
            terms = (
                SimpleTerm(value=l['layer'],
                           token=str(l['layer']), # TODO: should probably urlencode this?
                           title=l.get('label', unicode(l['layer'])))
                for l in layers
            )
        # TODO: get rid of sorted ... query should do it
        terms = sorted(terms, key=lambda o: o.title)
        return BCCVLSimpleVocabulary(terms)


envirolayer_source = DatasetLayerVocabularyFactory(
    'envirolayer_source',
)


@implementer(IVocabularyFactory)
class SparqlValuesVocabularyFactory(object):
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
        terms = (
            SimpleTerm(
                value=item['uri'],
                token=str(item['uri']),
                title=unicode(self._get_term_title(item)),
            )
            for item in result
        )
        # TODO: get rid of sorted ... query should do it
        terms = sorted(terms, key=lambda o: o.title)
        return SimpleVocabulary(terms)

emission_scenarios_source = SparqlValuesVocabularyFactory(
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

global_climate_models_source = SparqlValuesVocabularyFactory(
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

fc_years_source = SparqlValuesVocabularyFactory(
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


BioclimVocabularyFactory = StaticSparqlInstanceVocabularyFactory(
    BIOCLIM['BioclimaticVariable'])
GCMVocabularyFactory = StaticSparqlInstanceVocabularyFactory(BCCGCM['GCM'])
EMSCVocabularyFactory = StaticSparqlInstanceVocabularyFactory(BCCEMSC['EMSC'])

SpeciesDataGenreVocabularyFactory = StaticSparqlInstanceVocabularyFactory(
    BCCVOCAB['SpeciesDataGenre'])
# TODO: SpeciesLayer will go away in favour of more fine grained genre
SpeciesLayerVocabularyFactory = SparqlInstanceVocabularyFactory(BCCVOCAB['SpeciesLayer'])
EnvironmentalDataGenreVocabularyFactory = StaticSparqlInstanceVocabularyFactory(
    BCCVOCAB['EnvironmentalDataGenre'])
DatasetTypeVocabularyFactory = StaticSparqlInstanceVocabularyFactory(
    BCCVOCAB['DataSetType'])
ResolutionVocabularyFactory = StaticSparqlInstanceVocabularyFactory(
    BCCVOCAB['Resolution'], RDF['value'])
CRSVocabularyFactory = StaticSparqlInstanceVocabularyFactory(
    GML['GeodeticCRS'])

programming_language_vocab = SimpleVocabulary([
    SimpleTerm("R", "R", u'R'),
    SimpleTerm("Perl", "Perl", u'Perl'),
#    SimpleTerm("Python", "Python", u'Python'),
])


@provider(IVocabularyFactory)
def programming_language_vocab_factory(context):
    return programming_language_vocab
