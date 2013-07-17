from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from five import grok

from org.bccvl.site import defaults
from org.bccvl.site.api import QueryAPI

# TODO: sort by title

@grok.provider(IContextSourceBinder)
def species_occurrence_datasets_source(context): 
    species_brains = QueryAPI(context).getSpeciesOccurrenceDatasets()
    species_terms = [
        SimpleTerm(value=brain['UID'], token=brain['UID'], title=brain['Title']) 
        for brain in species_brains
    ]
    return SimpleVocabulary(species_terms)

@grok.provider(IContextSourceBinder)
def environmental_datasets_source(context):
    environment_brains = QueryAPI(context).getEnvironmentalDatasets()
    environment_terms = [
        SimpleTerm(value=brain['UID'], token=brain['UID'], title=brain['Title']) 
        for brain in environment_brains
    ]
    return SimpleVocabulary(environment_terms)

@grok.provider(IContextSourceBinder)
def future_climate_datasets_source(context):
    climate_brains = QueryAPI(context).getFutureClimateDatasets()
    climate_terms = [
        SimpleTerm(value=brain['UID'], token=brain['UID'], title=brain['Title']) 
        for brain in climate_brains
    ]  
    return SimpleVocabulary(climate_terms)

@grok.provider(IContextSourceBinder)
def functions_source(context):
    function_brains = QueryAPI(context).getFunctions()
    function_terms = [
        SimpleTerm(value=brain['UID'], token=brain['UID'], title=brain['Title']) 
        for brain in function_brains
    ]
    return SimpleVocabulary(function_terms)
