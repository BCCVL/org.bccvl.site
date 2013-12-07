from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from org.bccvl.site.api import QueryAPI
from zope.interface import implementer
from zope.component import getUtility, queryUtility
from gu.z3cform.rdf.interfaces import IORDF
from Products.CMFPlone.interfaces import IPloneSiteRoot


@implementer(IContextSourceBinder)
class DataSetSourceBinder(object):

    def __init__(self, name, apiFunc, tokenKey='UID'):
        self.__name__ = name
        self.apiFunc = apiFunc
        self.tokenKey = tokenKey

    def __call__(self, context):
        if context is None:
            # some widgets don't provide a context so let's fall back to site root
            context = queryUtility(IPloneSiteRoot)
        if context is not None:
            api = QueryAPI(context)
            brains = getattr(api, self.apiFunc)()
            terms = [SimpleTerm(value=brain['UID'],
                                token=brain[self.tokenKey],
                                title=brain['Title'])
                     for brain in brains]
            terms = sorted(terms, key=lambda o: o.title)
        else:
            terms = []
        return SimpleVocabulary(terms)


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

species_distributions_models_source = DataSetSourceBinder(
    'species_distributions_models_source', 'getSpeciesDistributionModelDatasets'
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
            # some widgets don't provide a context so let's fall back to site root
            context = queryUtility(IPloneSiteRoot)
        if context is None:
            return SimpleVocabulary()
        api = QueryAPI(context)
        urirefs = getattr(api, self.apiFunc)()
        if urirefs:
            query = []
            for uri in urirefs:
                query.append('{ BIND(%(uri)s as ?uri) %(uri)s <http://www.w3.org/2000/01/rdf-schema#label> ?label }' %  {'uri': uri.n3()})
            query = "SELECT ?uri ?label WHERE { Graph?g { %s } }" % "UNION".join(query)
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

    def __init__(self, name, query):
        self.__name__ = name
        self._query = query

    def __call__(self, context):
        if context is None:
            # some widgets don't provide a context so let's fall back to site root
            context = queryUtility(IPloneSiteRoot)
        if context is None:
            return SimpleVocabulary()
        handler = getUtility(IORDF).getHandler()
        result = handler.query(self._query)
        terms = [
            SimpleTerm(
                value=item['uri'],
                token=str(item['uri']),
                title=unicode(item['label']),
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
    """
)
