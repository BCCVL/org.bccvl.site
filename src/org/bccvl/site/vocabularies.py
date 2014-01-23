from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from org.bccvl.site.api import QueryAPI
from zope.interface import implementer
from zope.component import getUtility, queryUtility
from gu.z3cform.rdf.interfaces import IORDF
from gu.z3cform.rdf.utils import Period
from Products.CMFPlone.interfaces import IPloneSiteRoot
from Products.CMFCore.utils import getToolByName
from gu.z3cform.rdf.vocabulary import SparqlInstanceVocabularyFactory
from org.bccvl.site.namespace import BCCGCM, BCCEMSC, BIOCLIM


@implementer(IContextSourceBinder)
class DataSetSourceBinder(object):

    def __init__(self, name, apiFunc, tokenKey='UID'):
        self.__name__ = name
        self.apiFunc = apiFunc
        self.tokenKey = tokenKey

    def getTerms(self, context):
        api = QueryAPI(context)
        brains = getattr(api, self.apiFunc)()
        terms = [SimpleTerm(value=brain['UID'],
                            token=brain[self.tokenKey],
                            title=brain['Title'])
                 for brain in brains]
        return sorted(terms, key=lambda o: o.title)

    def __call__(self, context):
        if context is None:
            # some widgets don't provide a context so let's fall back
            # to site root
            context = queryUtility(IPloneSiteRoot)
        if context is not None:
            terms = self.getTerms(context)
        else:
            terms = []
        return SimpleVocabulary(terms)


class DataSetSourceBinderTitleFromParent(DataSetSourceBinder):

    def getTerms(self, context):
        api = QueryAPI(context)
        brains = getattr(api, self.apiFunc)()
        pc = getToolByName(context, 'portal_catalog')
        terms = []
        for brain in brains:
            parentpath, _ = brain.getPath().rsplit('/', 1)
            parentbrain = pc.searchResults(path={'query': parentpath,
                                                 'depth': 0})
            if parentbrain:
                title = parentbrain[0]['Title']
            else:
                title = brain['Title']
            terms.append(SimpleTerm(value=brain['UID'],
                                    token=brain[self.tokenKey],
                                    title=title))
        return sorted(terms, key=lambda o: o.title)


# species occurrence datasets
species_presence_datasets_source = DataSetSourceBinder(
    'species_presence_datasets_source', 'getSpeciesPresenceDatasets'
)

species_absence_datasets_source = DataSetSourceBinder(
    'species_absence_datasets_source', 'getSpeciesAbsenceDatasets'
)

species_abundance_datasets_source = DataSetSourceBinder(
    'species_abundance_datasets_source', 'getSpeciesAbundanceDatasets'
)

environmental_datasets_source = DataSetSourceBinder(
    'environmental_datasets_source', 'getEnvironmentalDatasets'
)

future_climate_datasets_source = DataSetSourceBinder(
    'future_climate_datasets_source', 'getFutureClimateDatasets'
)

species_distributions_models_source = DataSetSourceBinderTitleFromParent(
    'species_distributions_models_source',
    'getSpeciesDistributionModelDatasets'
)

functions_source = DataSetSourceBinder(
    'functions_source', 'getFunctions', 'id'
)


@implementer(IContextSourceBinder)
class SparqlDataSetSourceBinder(object):

    def __init__(self, name, apiFunc, tokenKey='UID'):
        self.__name__ = name
        self.apiFunc = apiFunc
        self.tokenKey = tokenKey

    def __call__(self, context):
        if context is None:
            # some widgets don't provide a context so let's fall back
            # to site root
            context = queryUtility(IPloneSiteRoot)
        if context is None:
            return SimpleVocabulary()
        api = QueryAPI(context)
        urirefs = getattr(api, self.apiFunc)()
        if urirefs:
            query = []
            # TODO: uri could be None???
            # TODO: maybe rebuild this query to fetch all labels from rdf
            #       and fetch all uris from catalog and do a set intersection
            #       all layers could be a 2nd vocabulary? (fresnel vocab?)
            for uri in urirefs:
                query.append('{ BIND(%(uri)s as ?uri) '
                             '%(uri)s rdfs:label ?label }' %
                             {'uri': uri.n3()})
            query = ("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> \n"
                     "SELECT ?uri ?label WHERE { Graph?g { %s } }" %
                     "UNION".join(query))
            handler = getUtility(IORDF).getHandler()
            result = handler.query(query)
            terms = [SimpleTerm(value=item['uri'],
                                token=str(item['uri']),
                                title=unicode(item['label']))
                     for item in result]
            terms = sorted(terms, key=lambda o: o.title)
        else:
            terms = []
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
            return SimpleVocabulary()
        handler = getUtility(IORDF).getHandler()
        result = handler.query(self._query)
        terms = [
            SimpleTerm(
                value=item['uri'],
                token=str(item['uri']),
                title=unicode(self._get_term_title(item)),
            )
            for item in result
        ]
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
