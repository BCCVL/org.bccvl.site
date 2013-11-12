from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from five import grok

from org.bccvl.site import defaults
from org.bccvl.site.api import QueryAPI

# FIXME: get rid of grok :)
# TODO: sort by title

def _source_factory(name, apiFunc, token_key='UID'):
    @grok.provider(IContextSourceBinder)
    def _datasets_source(context):
        api = QueryAPI(context)
        brains = getattr(api, apiFunc)()
        terms = [
            SimpleTerm(value=brain['UID'], token=brain[token_key], title=brain['Title'])
            for brain in brains
        ]
        return SimpleVocabulary(terms)
    _datasets_source.__name__ = name # to help with debugging
    return _datasets_source

# species occurrence datasets
species_presence_datasets_source = _source_factory(
    'species_presence_datasets_source', 'getSpeciesPresenceDatasets'
)

species_absence_datasets_source = _source_factory(
    'species_absence_datasets_source', 'getSpeciesAbsenceDatasets'
)

species_abundance_datasets_source = _source_factory(
    'species_abundance_datasets_source', 'getSpeciesAbundanceDatasets'
)

environmental_datasets_source = _source_factory(
    'environmental_datasets_source', 'getEnvironmentalDatasets'
)

future_climate_datasets_source = _source_factory(
    'future_climate_datasets_source', 'getFutureClimateDatasets'
)

functions_source = _source_factory(
    'functions_source', 'getFunctions', 'id'
)
