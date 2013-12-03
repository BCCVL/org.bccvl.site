from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from org.bccvl.site.api import QueryAPI
from zope.interface import implementer


@implementer(IContextSourceBinder)
class DataSetSourceBinder(object):

    def __init__(self, name, apiFunc, tokenKey='UID'):
        self.__name__ = name
        self.apiFunc = apiFunc
        self.tokenKey = tokenKey

    def __call__(self, context):
        api = QueryAPI(context)
        brains = getattr(api, self.apiFunc)()
        terms = [SimpleTerm(value=brain['UID'],
                            token=brain[self.tokenKey],
                            title=brain['Title'])
                 for brain in brains]
        terms = sorted(terms, key=lambda o: o.title)
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

functions_source = DataSetSourceBinder(
    'functions_source', 'getFunctions', 'id'
)
